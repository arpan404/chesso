"""Integration checks for account boundaries, chess records and durable study timing."""

import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.auth import ClerkVerifier


def test_identity(token):
    if token not in ("alice", "bob"):
        raise HTTPException(401, "Invalid test identity")
    return "user_" + token


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "web.sqlite3"
        self.app = self.make_app()
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.client.headers["Authorization"] = "Bearer alice"

    def make_app(self):
        return create_app(
            self.path, admin_token="research-test", auth_verifier=test_identity
        )

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def consent(self, **overrides):
        return self.client.patch(
            "/api/me",
            json=dict(
                nickname="Chess player",
                experience="casual",
                analytics_consent=True,
                research_consent=True,
                **overrides,
            ),
        ).json()

    def post_action(self, view, action, **fields):
        result = self.client.post(
            f"/api/studies/{view['id']}/actions",
            json=dict(version=view["version"], action=action, **fields),
        )
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_authentication_and_ownership(self):
        self.assertEqual(
            self.client.get("/api/me", headers={"Authorization": ""}).status_code, 401
        )
        game = self.client.post("/api/games", json={"opponent": "local"}).json()
        self.client.headers["Authorization"] = "Bearer bob"
        for url in (f"/api/games/{game['id']}",):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/api/games/{game['id']}/moves", json={"move": "e2e4", "version": 0}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/research/export").status_code, 403)

    def test_activity_pagination_and_ownership(self):
        self.assertEqual(
            self.client.get(
                "/api/activities", headers={"Authorization": ""}
            ).status_code,
            401,
        )
        empty = self.client.get("/api/activities?page=4").json()
        self.assertEqual(
            (empty["items"], empty["page"], empty["total_pages"]), ([], 1, 1)
        )
        ids = [
            self.client.post("/api/games", json={"opponent": "local"}).json()["id"]
            for _ in range(19)
        ]
        with self.app.state.database.connect() as db:
            # Identical timestamps still produce a deterministic page boundary.
            db.execute(
                "UPDATE activities SET updated_at=100 WHERE user_id=(SELECT id FROM users WHERE clerk_id=$1)",
                ("user_alice",),
            )
        expected = sorted(ids, reverse=True)
        pages = [
            self.client.get(f"/api/activities?page={page}").json() for page in (1, 2, 3)
        ]
        self.assertEqual([len(page["items"]) for page in pages], [8, 8, 3])
        self.assertEqual(
            [item["id"] for page in pages for item in page["items"]], expected
        )
        self.assertTrue(
            all(page["total"] == 19 and page["total_pages"] == 3 for page in pages)
        )
        self.assertEqual(self.client.get("/api/activities?page=99").json()["page"], 3)
        self.assertEqual(self.client.get("/api/activities?page=0").status_code, 422)
        self.assertEqual(
            self.client.get("/api/activities?page_size=51").status_code, 422
        )
        self.client.headers["Authorization"] = "Bearer bob"
        self.assertEqual(self.client.get("/api/activities").json()["total"], 0)

    def test_parallel_requests_commit_before_response(self):
        with ThreadPoolExecutor(max_workers=6) as executor:
            profiles = list(
                executor.map(lambda _: self.client.get("/api/me"), range(6))
            )
        self.assertTrue(all(p.status_code == 200 for p in profiles))
        self.assertEqual(len({p.json()["id"] for p in profiles}), 1)
        game = self.client.post("/api/games", json={"opponent": "local"}).json()
        with self.app.state.database.connect() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT id FROM activities WHERE id=$1", (game["id"],)
                ).fetchone()
            )
        with ThreadPoolExecutor(max_workers=2) as executor:
            replies = list(
                executor.map(
                    lambda move: self.client.post(
                        f"/api/games/{game['id']}/moves",
                        json={"move": move, "version": 0},
                    ),
                    ["e2e4", "d2d4"],
                )
            )
        self.assertEqual(sorted(p.status_code for p in replies), [200, 409])
        self.assertEqual(
            len(self.client.get(f"/api/games/{game['id']}").json()["moves"]), 1
        )

    def test_legal_moves_and_stale_requests(self):
        game = self.client.post("/api/games", json={"opponent": "computer"}).json()
        url = f"/api/games/{game['id']}/moves"
        self.assertEqual(
            self.client.post(url, json={"move": "e2e5", "version": 0}).status_code, 400
        )
        moved = self.client.post(url, json={"move": "e2e4", "version": 0}).json()
        self.assertEqual(len(moved["moves"]), 2)
        self.assertEqual(moved["turn"], "white")
        self.assertEqual(
            self.client.post(url, json={"move": "e2e4", "version": 0}).status_code, 409
        )
        self.assertEqual(
            self.client.get(f"/api/games/{game['id']}").json()["moves"], moved["moves"]
        )

    def test_puzzle_records_rating_once(self):
        puzzle = self.client.post("/api/puzzles", json={"tier": "easy"}).json()
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (puzzle["id"],)
                ).fetchone()[0]
            )
        bank = json.loads(Path("backend/resources/puzzles.json").read_text())
        item = next(p for p in bank if p["id"] == state["puzzle_id"])
        # The client checks moves locally, so the line ships with the puzzle.
        self.assertEqual(puzzle["solution"], item["solution"])
        self.assertEqual(len(puzzle["solution_san"]), len(item["solution"]))
        self.assertTrue(puzzle["hint_text"])
        self.assertIsNone(puzzle["hint"])
        for move in item["solution"][::2]:
            puzzle = self.client.post(
                f"/api/puzzles/{puzzle['id']}/moves",
                json={"move": move, "version": puzzle["version"]},
            ).json()
        self.assertTrue(puzzle["solved"])
        self.client.post(
            f"/api/puzzles/{puzzle['id']}/moves",
            json={"move": "a1a2", "version": puzzle["version"]},
        )
        profile = self.client.get("/api/me").json()
        self.assertEqual(profile["puzzles_attempted"], 1)
        self.assertEqual(profile["puzzles_solved"], 1)

    def test_consent_telemetry_export_and_deletion(self):
        self.assertEqual(self.client.post("/api/studies").status_code, 403)
        game = self.client.post("/api/games", json={"opponent": "local"}).json()
        interaction = {
            "activity_id": game["id"],
            "kind": "square_selected",
            "square": "e2",
        }
        self.client.post("/api/interactions", json=interaction)
        self.assertFalse(
            any(
                e["category"] == "analytics"
                for e in self.client.get("/api/me/export").json()["events"]
            )
        )
        self.consent()
        self.client.post("/api/interactions", json=interaction)
        self.assertTrue(
            any(
                e["category"] == "analytics"
                for e in self.client.get("/api/me/export").json()["events"]
            )
        )
        self.client.patch(
            "/api/me", json={"analytics_consent": False, "research_consent": False}
        )
        self.assertEqual(self.client.get("/api/me").json()["nickname"], "Chess player")
        records = self.client.get("/api/me/export").json()
        self.assertFalse(any(e["category"] == "analytics" for e in records["events"]))
        export = self.client.get(
            "/api/research/export", headers={"Authorization": "Bearer research-test"}
        )
        self.assertEqual(export.status_code, 200)
        self.assertNotIn(records["profile"]["id"], export.text)
        self.assertEqual(self.client.delete("/api/me").status_code, 204)
        with self.app.state.database.connect() as db:
            for table in ("users", "activities", "events"):
                self.assertEqual(
                    db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )

    def test_study_rules_frozen_board_and_restart(self):
        self.consent()
        view = self.client.post("/api/studies").json()
        view = self.post_action(view, "present")
        fen = view["fen"]
        move = view["legal_moves"][0]
        missing = self.client.post(
            f"/api/studies/{view['id']}/actions",
            json={"action": "initial", "version": view["version"], "move": move},
        )
        self.assertEqual(missing.status_code, 400)
        view = self.post_action(view, "initial", move=move, confidence=60)
        self.assertEqual(
            self.client.post(
                f"/api/studies/{view['id']}/actions",
                json={"action": "hint", "version": view["version"]},
            ).status_code,
            400,
        )
        # A new API instance must continue the same trial, not invent an interruption.
        with TestClient(self.make_app()) as restarted:
            persisted = restarted.get(
                f"/api/studies/{view['id']}", headers={"Authorization": "Bearer alice"}
            ).json()
            self.assertEqual(persisted["initial_move"], move)
            self.assertEqual(persisted["presented_at"], view["presented_at"])
            self.assertFalse(persisted["finished"])
        view = self.post_action(view, "submit", move=move, confidence=70)
        self.assertEqual(view["fen"], fen)
        self.assertTrue(view["finished"])
        view = self.post_action(view, "next")
        self.assertEqual(view["index"], 1)
        self.assertIsNone(view["presented_at"])
        rows = self.client.get(
            "/api/research/trials", headers={"Authorization": "Bearer research-test"}
        ).json()
        self.assertEqual(sum(r["status"] == "not_started" for r in rows), 15)
        repeated = self.client.post("/api/studies").json()
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (repeated["id"],)
                ).fetchone()[0]
            )
        self.assertEqual(len(state["prior_exposure_item_ids"]), 1)

    def test_reflection_and_full_study(self):
        self.consent()
        view = self.client.post("/api/studies").json()
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (view["id"],)
                ).fetchone()[0]
            )
            state["condition"] = "reflective"
            db.execute(
                "UPDATE activities SET state=$1 WHERE id=$2",
                (json.dumps(state), view["id"]),
            )
        for _ in range(view["total"]):
            view = self.client.get(f"/api/studies/{view['id']}").json()
            view = self.post_action(view, "present")
            move = view["legal_moves"][0]
            view = self.post_action(view, "initial", move=move, confidence=50)
            if view["phase"] == "training":
                view = self.post_action(view, "hint")
                self.assertTrue(view["reflection_prompt"])
                self.assertEqual(
                    self.client.post(
                        f"/api/studies/{view['id']}/actions",
                        json={
                            "action": "submit",
                            "version": view["version"],
                            "move": move,
                            "confidence": 50,
                        },
                    ).status_code,
                    400,
                )
                view = self.post_action(
                    view, "reflection", text="The opponent can push a pawn."
                )
            view = self.post_action(view, "submit", move=move, confidence=60)
            view = self.post_action(view, "reason", text="ready")
            view = self.post_action(view, "next")
        self.assertTrue(view["completed"])
        rows = self.client.get(
            "/api/research/trials", headers={"Authorization": "Bearer research-test"}
        ).json()
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(r["status"] == "submitted" for r in rows))
        self.assertEqual(sum(r["hint_used"] for r in rows), 8)
        self.assertTrue(all(r["benchmark_success"] is None for r in rows))
        from backend.tools.study_analysis import summarize

        self.assertEqual(len(summarize(rows)), 3)
        csv_export = self.client.get(
            "/api/research/trials?format=csv",
            headers={"Authorization": "Bearer research-test"},
        )
        self.assertIn("initial_confidence", csv_export.text)
        events = self.client.get("/api/me/export").json()["events"]
        self.assertEqual(sum(e["kind"] == "trial_finished" for e in events), 16)
        self.assertEqual(sum(e["kind"] == "hint_shown" for e in events), 8)

    def test_withdrawal_stops_study_observations(self):
        self.consent()
        view = self.post_action(self.client.post("/api/studies").json(), "present")
        self.client.patch("/api/me", json={"research_consent": False})
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (view["id"],)
                ).fetchone()[0]
            )
            state["trial"]["presented_at"] = time.time() - 1000
            db.execute(
                "UPDATE activities SET state=$1 WHERE id=$2",
                (json.dumps(state), view["id"]),
            )
            before = db.execute(
                "SELECT COUNT(*) FROM events WHERE category='research'"
            ).fetchone()[0]
        self.assertFalse(
            self.client.get(f"/api/studies/{view['id']}").json()["finished"]
        )
        self.assertEqual(
            self.client.post(
                f"/api/studies/{view['id']}/actions",
                json={"action": "skip", "version": view["version"]},
            ).status_code,
            403,
        )
        self.client.post(
            "/api/interactions",
            json={"activity_id": view["id"], "kind": "focus_changed", "focused": False},
        )
        with self.app.state.database.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM events WHERE category='research'"
                ).fetchone()[0],
                before,
            )
        self.assertEqual(
            self.client.get(
                "/api/research/trials",
                headers={"Authorization": "Bearer research-test"},
            ).json(),
            [],
        )

    def test_deadlines_and_input_bounds(self):
        self.consent()
        view = self.post_action(self.client.post("/api/studies").json(), "present")
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (view["id"],)
                ).fetchone()[0]
            )
            state["trial"]["presented_at"] = time.time() - 1000
            db.execute(
                "UPDATE activities SET state=$1 WHERE id=$2",
                (json.dumps(state), view["id"]),
            )
        view = self.client.get(f"/api/studies/{view['id']}").json()
        self.assertEqual(view["status"], "timeout")
        self.assertEqual(
            self.client.patch("/api/me", json={"nickname": "x" * 41}).status_code, 422
        )
        self.assertEqual(
            self.client.post(
                "/api/games", json={"opponent": "local", "user_id": "someone"}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/games", json={}, headers={"Origin": "https://untrusted.example"}
            ).status_code,
            403,
        )
        puzzle = self.client.post("/api/puzzles", json={"tier": "hard"}).json()
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (puzzle["id"],)
                ).fetchone()[0]
            )
            state["started_at"] = time.time() - 1000
            db.execute(
                "UPDATE activities SET state=$1 WHERE id=$2",
                (json.dumps(state), puzzle["id"]),
            )
        self.assertEqual(
            self.client.get(f"/api/puzzles/{puzzle['id']}").json()["status"], "timeout"
        )
        self.client.get(f"/api/puzzles/{puzzle['id']}")
        self.assertEqual(self.client.get("/api/me").json()["puzzles_attempted"], 1)


class ClerkVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public = (
            cls.key.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        cls.verifier = ClerkVerifier(
            "https://example.clerk.accounts.dev", ["http://localhost:5173"], cls.public
        )

    def token(self, **overrides):
        claims = dict(
            sub="user_alice",
            sid="sess_test",
            iss="https://example.clerk.accounts.dev",
            azp="http://localhost:5173",
            exp=int(time.time() + 60),
            nbf=int(time.time() - 10),
            iat=int(time.time() - 10),
        )
        claims.update(overrides)
        return jwt.encode(claims, self.key, algorithm="RS256")

    def test_real_signature_and_claim_validation(self):
        self.assertEqual(self.verifier(self.token()), "user_alice")
        for claims in (
            {"azp": "https://other.example"},
            {"exp": int(time.time() - 20)},
            {"iss": "https://other.example"},
            {"nbf": int(time.time() + 60)},
            {"sts": "pending"},
            {"sub": "invalid"},
        ):
            with self.subTest(claims=claims), self.assertRaises(HTTPException):
                self.verifier(self.token(**claims))
        with self.assertRaises(HTTPException):
            self.verifier(
                jwt.encode({"sub": "user_alice"}, "wrong-key" * 5, algorithm="HS256")
            )
