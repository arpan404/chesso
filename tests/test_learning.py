"""End-to-end calibration, session planning, assistance, and feedback checks."""

import json
import unittest
from pathlib import Path

from tests import test_web
from tests.test_database import TEST_URL, PostgresSchemaMixin


class LearningTests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    tearDown = test_web.WebTests.tearDown
    make_app = test_web.WebTests.make_app

    def solve(self, session):
        bank = json.loads(Path("backend/resources/puzzles.json").read_text())
        puzzle = session["puzzle"]
        item = next(p for p in bank if p["id"] == puzzle["puzzle_id"])
        for move in item["solution"][::2]:
            response = self.client.post(
                f"/api/puzzles/{puzzle['id']}/moves",
                json={"move": move, "version": puzzle["version"], "confidence": 75},
            )
            self.assertEqual(response.status_code, 200, response.text)
            puzzle = response.json()
        return self.client.get(f"/api/learning/{session['id']}").json()

    def calibrate(self):
        session = self.client.post("/api/onboarding").json()
        for index in range(10):
            session = self.solve(session)
            if index < 9:
                session = self.client.post(
                    f"/api/learning/{session['id']}/next",
                    json={"version": session["version"]},
                ).json()
        return session

    def test_adaptive_onboarding_and_resume(self):
        self.assertEqual(
            self.client.post("/api/learning/sessions", json={"size": 20}).status_code,
            409,
        )
        session = self.client.post("/api/onboarding").json()
        self.assertEqual(
            self.client.post("/api/onboarding").json()["id"], session["id"]
        )
        self.assertEqual(
            self.client.post(
                f"/api/puzzles/{session['puzzle']['id']}/hint", json={"version": 0}
            ).status_code,
            403,
        )
        identifiers, depths = set(), set()
        for index in range(10):
            self.assertNotIn(session["puzzle"]["puzzle_id"], identifiers)
            identifiers.add(session["puzzle"]["puzzle_id"])
            depths.add(session["puzzle"]["player_moves_required"])
            session = self.solve(session)
            self.assertEqual(session["finished_count"], index + 1)
            if index < 9:
                session = self.client.post(
                    f"/api/learning/{session['id']}/next",
                    json={"version": session["version"]},
                ).json()
        self.assertTrue(session["completed"])
        self.assertGreater(len(depths), 1)
        profile = self.client.get("/api/me").json()
        self.assertTrue(profile["calibration_complete"])
        self.assertEqual(profile["puzzle_rating"], session["estimated_rating"])
        self.assertEqual(profile["puzzles_attempted"], 10)
        self.assertEqual(self.client.post("/api/onboarding").status_code, 409)
        self.client.headers["Authorization"] = "Bearer bob"
        self.assertEqual(
            self.client.get(f"/api/learning/{session['id']}").status_code, 404
        )

    def test_unique_session_plan_and_saved_feedback(self):
        self.calibrate()
        session = self.client.post("/api/learning/sessions", json={"size": 10}).json()
        self.assertEqual(
            self.client.post("/api/learning/sessions", json={"size": 30}).json()["id"],
            session["id"],
        )
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (session["id"],)
                ).fetchone()[0]
            )
            self.assertEqual(len(set(state["plan"])), 10)
        self.assertEqual(
            self.client.post(
                f"/api/learning/{session['id']}/feedback", json={"satisfaction": 5}
            ).status_code,
            409,
        )
        last = None
        for index in range(10):
            last = session["puzzle"]["puzzle_id"]
            session = self.solve(session)
            if index < 9:
                session = self.client.post(
                    f"/api/learning/{session['id']}/next",
                    json={"version": session["version"]},
                ).json()
        saved = self.client.post(
            f"/api/learning/{session['id']}/feedback", json={"satisfaction": 4}
        ).json()
        self.assertEqual(saved["feedback"]["satisfaction"], 4)
        next_session = self.client.post(
            "/api/learning/sessions", json={"size": 30}
        ).json()
        self.assertNotEqual(next_session["puzzle"]["puzzle_id"], last)
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (next_session["id"],)
                ).fetchone()[0]
            )
            self.assertEqual(len(set(state["plan"])), 30)
        self.assertEqual(self.client.get("/api/learning/history").json()["total"], 2)

    def test_assisted_solves_do_not_raise_ability_rating(self):
        self.calibrate()
        session = self.client.post("/api/learning/sessions", json={"size": 20}).json()
        with self.app.state.database.connect() as db:
            state = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (session["id"],)
                ).fetchone()[0]
            )
            state["hints_available"] = True
            db.execute(
                "UPDATE activities SET state=$1 WHERE id=$2",
                (json.dumps(state), session["id"]),
            )
            puzzle = session["puzzle"]
            child = json.loads(
                db.execute(
                    "SELECT state FROM activities WHERE id=$1", (puzzle["id"],)
                ).fetchone()[0]
            )
            child["hints_available"] = True
            db.execute(
                "UPDATE activities SET state=$1 WHERE id=$2",
                (json.dumps(child), puzzle["id"]),
            )
        rating = self.client.get("/api/me").json()["puzzle_rating"]
        self.assertEqual(
            self.client.post(
                f"/api/puzzles/{puzzle['id']}/hint", json={"version": puzzle["version"]}
            ).status_code,
            200,
        )
        session = self.client.get(f"/api/learning/{session['id']}").json()
        self.solve(session)
        self.assertEqual(self.client.get("/api/me").json()["puzzle_rating"], rating)
        events = self.client.get("/api/me/export").json()["events"]
        self.assertTrue(
            any(
                e["kind"] == "puzzle_attempt" and e["payload"]["confidence"] == 75
                for e in events
            )
        )
        self.assertTrue(
            any(
                e["kind"] == "puzzle_hint_shown" and e["payload"]["hint_text"]
                for e in events
            )
        )

    def test_skips_and_stale_progress(self):
        session = self.client.post("/api/onboarding").json()
        self.assertEqual(
            self.client.post(
                f"/api/learning/{session['id']}/next",
                json={"version": session["version"]},
            ).status_code,
            409,
        )
        skipped = self.client.post(
            f"/api/puzzles/{session['puzzle']['id']}/skip",
            json={"version": session["puzzle"]["version"]},
        ).json()
        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(
            self.client.post(
                f"/api/learning/{session['id']}/next",
                json={"version": session["version"]},
            ).status_code,
            409,
        )
        resumed = self.client.get(f"/api/learning/{session['id']}").json()
        self.assertEqual(resumed["finished_count"], 1)


@unittest.skipUnless(TEST_URL, "Set CHESSO_TEST_DATABASE_URL for PostgreSQL checks")
class PostgresLearningTests(PostgresSchemaMixin, LearningTests):
    pass
