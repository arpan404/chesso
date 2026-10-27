"""FastAPI entry point: uv run uvicorn backend.app:app --reload."""

import csv
import io
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import chess
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import ClerkVerifier
from backend.chess_service import board_data, game_board, opponent_move
from backend.database import Database, event, save_activity
from backend.learning import Learning
from backend.web_study import StudyLog, new_study, snapshot_trial, study_view, trial_for
from backend.study import legal_uci, load_protocol, position_key, rows_from_observations

ROOT = Path(__file__).resolve().parent.parent
CONSENT_VERSION = "2026-10-11-v1"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProfileInput(Input):
    nickname: str = Field(default="", max_length=40)
    experience: Literal["unspecified", "new", "casual", "club", "advanced"] = (
        "unspecified"
    )
    analytics_consent: bool = False
    research_consent: bool = False


class GameInput(Input):
    opponent: Literal["computer", "local"] = "computer"
    color: Literal["white", "black"] = "white"


class MoveInput(Input):
    move: str = Field(min_length=4, max_length=5)
    version: int = Field(ge=0)
    confidence: int | None = Field(default=None, ge=0, le=100)


class PuzzleInput(Input):
    tier: Literal["easy", "medium", "hard"] = "easy"


class VersionInput(Input):
    version: int = Field(ge=0)


class LearningInput(Input):
    size: Literal[10, 20, 30] = 20


class FeedbackInput(Input):
    satisfaction: int | None = Field(default=None, ge=1, le=5)
    helpfulness: int | None = Field(default=None, ge=1, le=5)
    skipped: bool = False


class StudyInput(VersionInput):
    action: Literal[
        "present",
        "initial",
        "candidate",
        "hint",
        "reflection",
        "submit",
        "skip",
        "reason",
        "familiarity",
        "next",
    ]
    move: str = Field(default="", max_length=5)
    confidence: int | None = Field(default=None, ge=0, le=100)
    text: str = Field(default="", max_length=1000)


class InteractionInput(Input):
    activity_id: str = Field(min_length=32, max_length=32)
    kind: Literal["focus_changed", "square_selected"]
    focused: bool | None = None
    square: str | None = Field(default=None, pattern=r"^[a-h][1-8]$")


def create_app(
    database_path: Path | None = None,
    admin_token: str | None = None,
    auth_verifier=None,
    *,
    database_url: str | None = None,
):
    database = Database(
        database_path
        or Path(os.environ.get("CHESSO_DATABASE", ROOT / "data/web/chesso.sqlite3")),
        url=(
            database_url
            if database_url is not None
            else ""
            if database_path is not None
            else os.environ.get("DATABASE_URL", "")
        ),
    )
    origins = [
        o.strip()
        for o in os.environ.get(
            "CHESSO_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if o.strip()
    ]
    verify_token = auth_verifier or ClerkVerifier(
        os.environ.get("CHESSO_CLERK_ISSUER", ""),
        origins,
        os.environ.get("CHESSO_CLERK_JWT_KEY", ""),
    )
    researcher_token = (
        admin_token
        if admin_token is not None
        else os.environ.get("CHESSO_ADMIN_TOKEN", "")
    )
    protocol = load_protocol()
    bank = json.loads((ROOT / "backend/resources/puzzles.json").read_text())
    # Discard malformed items before offering them to players.
    puzzles = []
    for puzzle in bank:
        try:
            board = chess.Board(puzzle["fen"])
            if (
                not board.is_valid()
                or board.is_game_over()
                or not puzzle.get("solution")
            ):
                continue
            for move in puzzle["solution"]:
                board.push_uci(legal_uci(board, move))
            puzzles.append(puzzle)
        except (ValueError, KeyError):
            continue

    @asynccontextmanager
    async def lifespan(app):
        database.initialize()
        try:
            yield
        finally:
            database.close()

    learning = Learning(puzzles)

    app = FastAPI(title="Chesso API", version="1.0.0", lifespan=lifespan)
    app.state.database = database
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def request_guard(request, call_next):
        if request.url.path.startswith("/api/"):
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if origin and origin not in origins:
                    return JSONResponse(
                        {"detail": "This origin cannot change Chesso records."},
                        status_code=403,
                    )
            # Strict request models also bound every accepted text field.
            if int(request.headers.get("content-length", "0")) > 32768:
                return JSONResponse(
                    {"detail": "Request is too large."}, status_code=413
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def connection():
        with database.connect() as db:
            yield db

    def current_user(request: Request, db=Depends(connection, scope="function")):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Sign in to continue.")
        clerk_id = verify_token(authorization[7:])
        database.lock_user(db, clerk_id)
        row = db.execute(
            "SELECT * FROM users WHERE clerk_id=$1", (clerk_id,)
        ).fetchone()
        if row is None:
            user = {
                "id": uuid.uuid4().hex,
                "created_at": time.time(),
                "nickname": "",
                "experience": "unspecified",
                "analytics_consent": False,
                "research_consent": False,
                "puzzle_rating": 800,
                "puzzles_attempted": 0,
                "puzzles_solved": 0,
                "points": 0,
                "calibration_complete": False,
            }
            db.execute(
                "INSERT INTO users VALUES ($1, $2, $3, $4)",
                (
                    user["id"],
                    user["created_at"],
                    json.dumps(
                        {k: v for k, v in user.items() if k not in ("id", "created_at")}
                    ),
                    clerk_id,
                ),
            )
            event(db, user["id"], None, "essential", "profile_created")
            return user
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            **json.loads(row["profile"]),
        }

    def require_researcher(request: Request):
        if not researcher_token or not secrets.compare_digest(
            request.headers.get("authorization", ""), f"Bearer {researcher_token}"
        ):
            raise HTTPException(
                403, "Researcher access requires the configured admin token."
            )

    def activity(db, user, activity_id, kind=None):
        row = db.execute(
            "SELECT * FROM activities WHERE id=$1 AND user_id=$2",
            (activity_id, user["id"]),
        ).fetchone()
        if row is None or (kind and row["kind"] != kind):
            raise HTTPException(404, "Activity not found.")
        return json.loads(row["state"])

    def add_activity(db, user, kind, state):
        activity_id = uuid.uuid4().hex
        now = time.time()
        db.execute(
            "INSERT INTO activities VALUES ($1, $2, $3, $4, $5, $6)",
            (activity_id, user["id"], kind, now, now, json.dumps(state)),
        )
        return activity_id

    def check_version(state, version):
        if state["version"] != version:
            raise HTTPException(
                409, "This activity changed. Refresh it before trying again."
            )

    def profile_stats(db, user):
        counts = dict(
            db.execute(
                "SELECT kind, COUNT(*) FROM activities WHERE user_id=$1 GROUP BY kind",
                (user["id"],),
            ).fetchall()
        )
        recent = db.execute(
            "SELECT id, kind, updated_at, state FROM activities WHERE user_id=$1 ORDER BY updated_at DESC LIMIT 12",
            (user["id"],),
        ).fetchall()
        return {
            **user,
            "activity_counts": counts,
            "recent": [
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "updated_at": r["updated_at"],
                    "completed": json.loads(r["state"]).get("completed", False),
                }
                for r in recent
            ],
            "consent_version": CONSENT_VERSION,
        }

    def update_profile(db, user):
        profile = {k: v for k, v in user.items() if k not in ("id", "created_at")}
        db.execute(
            "UPDATE users SET profile=$1 WHERE id=$2", (json.dumps(profile), user["id"])
        )

    @app.get("/api/health/live")
    def liveness():
        return {"status": "ok"}

    @app.get("/api/health")
    def health(db=Depends(connection, scope="function")):
        db.execute("SELECT 1")
        return {"status": "ok", "puzzles": len(puzzles), "study_mode": "pilot"}

    @app.post("/api/session")
    def start_session(
        user=Depends(current_user), db=Depends(connection, scope="function")
    ):
        return profile_stats(db, user)

    @app.get("/api/me")
    def me(user=Depends(current_user), db=Depends(connection, scope="function")):
        return profile_stats(db, user)

    @app.patch("/api/me")
    def edit_profile(
        body: ProfileInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        updates = body.model_dump(exclude_unset=True)
        changed = any(
            field in updates and updates[field] != user[field]
            for field in ("analytics_consent", "research_consent")
        )
        user.update(updates)
        update_profile(db, user)
        if changed:
            event(
                db,
                user["id"],
                None,
                "essential",
                "consent_updated",
                analytics_consent=user["analytics_consent"],
                research_consent=user["research_consent"],
                consent_version=CONSENT_VERSION,
            )
        if not user["analytics_consent"]:
            db.execute(
                "DELETE FROM events WHERE user_id=$1 AND category='analytics'",
                (user["id"],),
            )
        return profile_stats(db, user)

    @app.delete("/api/me", status_code=204)
    def delete_profile(
        response: Response,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        db.execute("DELETE FROM users WHERE id=$1", (user["id"],))

    @app.get("/api/activities")
    def list_activities(
        page: int = Query(1, ge=1, le=1_000_000),
        page_size: int = Query(8, ge=1, le=50),
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        total = db.execute(
            "SELECT COUNT(*) FROM activities WHERE user_id=$1", (user["id"],)
        ).fetchone()[0]
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = min(page, total_pages)
        rows = db.execute(
            "SELECT id, kind, updated_at, state FROM activities WHERE user_id=$1 ORDER BY updated_at DESC, id DESC LIMIT $2 OFFSET $3",
            (user["id"], page_size, (current_page - 1) * page_size),
        ).fetchall()
        return {
            "items": [
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "updated_at": row["updated_at"],
                    "completed": json.loads(row["state"]).get("completed", False),
                }
                for row in rows
            ],
            "page": current_page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    @app.get("/api/me/export")
    def export_profile(
        user=Depends(current_user), db=Depends(connection, scope="function")
    ):
        records = [
            {**dict(row), "payload": json.loads(row["payload"])}
            for row in db.execute(
                "SELECT id, activity_id, category, kind, recorded_at, payload FROM events WHERE user_id=$1 ORDER BY recorded_at",
                (user["id"],),
            )
        ]
        activities = [
            {**dict(row), "state": json.loads(row["state"])}
            for row in db.execute(
                "SELECT id, kind, created_at, updated_at, state FROM activities WHERE user_id=$1",
                (user["id"],),
            )
        ]
        return JSONResponse(
            {
                "schema_version": 1,
                "profile": user,
                "activities": activities,
                "events": records,
            },
            headers={"Content-Disposition": 'attachment; filename="chesso-data.json"'},
        )

    def game_view(activity_id, state):
        board = game_board(state)
        replay, history = chess.Board(), []
        for uci in state["moves"]:
            move = chess.Move.from_uci(uci)
            history.append({"uci": uci, "san": replay.san(move)})
            replay.push(move)
        return {"id": activity_id, **state, **board_data(board), "history": history}

    @app.post("/api/games", status_code=201)
    def new_game(
        body: GameInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = {
            **body.model_dump(),
            "moves": [],
            "version": 0,
            "completed": False,
            "last_move_at": time.time(),
        }
        activity_id = add_activity(db, user, "game", state)
        event(
            db,
            user["id"],
            activity_id,
            "essential",
            "game_started",
            **body.model_dump(),
        )
        if body.opponent == "computer" and body.color == "black":
            move = opponent_move(chess.Board()).uci()
            state["moves"].append(move)
            event(
                db,
                user["id"],
                activity_id,
                "essential",
                "game_move",
                move=move,
                actor="computer",
                ply=1,
            )
            save_activity(db, activity_id, state)
        return game_view(activity_id, state)

    @app.get("/api/games/{activity_id}")
    def get_game(
        activity_id: str,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        return game_view(activity_id, activity(db, user, activity_id, "game"))

    @app.post("/api/games/{activity_id}/moves")
    def game_move(
        activity_id: str,
        body: MoveInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = activity(db, user, activity_id, "game")
        check_version(state, body.version)
        board = game_board(state)
        if board.is_game_over(claim_draw=True):
            raise HTTPException(400, "This game has ended. Start a new game.")
        move = legal_uci(board, body.move)
        before = board.fen()
        board.push_uci(move)
        state["moves"].append(move)
        event(
            db,
            user["id"],
            activity_id,
            "essential",
            "game_move",
            actor="player",
            move=move,
            fen_before=before,
            fen_after=board.fen(),
            ply=len(state["moves"]),
            elapsed_ms=round((time.time() - state["last_move_at"]) * 1000),
        )
        if state["opponent"] == "computer" and not board.is_game_over(claim_draw=True):
            reply = opponent_move(board).uci()
            before = board.fen()
            board.push_uci(reply)
            state["moves"].append(reply)
            event(
                db,
                user["id"],
                activity_id,
                "essential",
                "game_move",
                actor="computer",
                move=reply,
                fen_before=before,
                fen_after=board.fen(),
                ply=len(state["moves"]),
            )
        state.update(
            version=state["version"] + 1,
            completed=board.is_game_over(claim_draw=True),
            last_move_at=time.time(),
        )
        if state["completed"]:
            event(
                db,
                user["id"],
                activity_id,
                "essential",
                "game_finished",
                result=board.result(claim_draw=True),
            )
        save_activity(db, activity_id, state)
        return game_view(activity_id, state)

    def puzzle_item(state):
        return next(p for p in puzzles if p["id"] == state["puzzle_id"])

    def puzzle_board(state):
        board = chess.Board(puzzle_item(state)["fen"])
        for move in state["moves"]:
            board.push_uci(move)
        return board

    def finish_puzzle(db, user, activity_id, state, solved, status):
        if state["completed"]:
            return
        state.update(completed=True, solved=solved, status=status)
        item = puzzle_item(state)
        expected = 1 / (1 + 10 ** ((item["rating"] - user["puzzle_rating"]) / 400))
        rated = not state.get("learning_id") or (
            learning.load(db, user, state["learning_id"])["kind"] != "calibration"
            and not state["hint_shown"]
            and status != "skipped"
        )
        delta = round(32 * (int(solved) - expected)) if rated else 0
        user["puzzle_rating"] += delta
        user["puzzles_attempted"] += 1
        user["puzzles_solved"] += int(solved)
        points = {"easy": 10, "medium": 20, "hard": 30}[state["tier"]] if solved else 0
        user["points"] += points
        state.update(rating_delta=delta, points=points)
        learning.finished(db, user, activity_id, state)
        update_profile(db, user)
        event(
            db,
            user["id"],
            activity_id,
            "essential",
            "puzzle_finished",
            puzzle_id=item["id"],
            status=status,
            solved=solved,
            hint_used=state["hint_shown"],
            rating_delta=delta,
            elapsed_ms=round((time.time() - state["started_at"]) * 1000),
            tier=state["tier"],
        )

    def tick_puzzle(db, user, activity_id, state):
        if (
            not state["completed"]
            and time.time() >= state["started_at"] + state["time_limit_seconds"]
        ):
            finish_puzzle(db, user, activity_id, state, False, "timeout")
            state["version"] += 1
            save_activity(db, activity_id, state)

    def puzzle_view(activity_id, state):
        item = puzzle_item(state)
        hint_text = (
            item.get("hint") or "Look for forcing moves: checks, captures, and threats."
        )
        # The full line ships with the puzzle so the client can check moves
        # instantly; the server still validates and records every move.
        solution_san = []
        reference = chess.Board(item["fen"])
        for move in item["solution"]:
            parsed = chess.Move.from_uci(move)
            solution_san.append(reference.san(parsed))
            reference.push(parsed)
        return {
            "id": activity_id,
            **state,
            **board_data(puzzle_board(state)),
            "rating": item["rating"],
            "themes": item.get("themes", []),
            "source_url": item.get("url", ""),
            "remaining_seconds": max(
                0, state["time_limit_seconds"] - (time.time() - state["started_at"])
            ),
            "hint": hint_text if state["hint_shown"] else None,
            # Sent upfront so the client can show a requested hint instantly;
            # the server still records when the hint was asked for.
            "hint_text": hint_text,
            "solution": item["solution"],
            "solution_san": solution_san,
        }

    @app.post("/api/puzzles", status_code=201)
    def new_puzzle(
        body: PuzzleInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        bounds = {"easy": (0, 1000), "medium": (1000, 1400), "hard": (1400, 10000)}
        low, high = bounds[body.tier]
        choices = [p for p in puzzles if low <= p["rating"] < high]
        item = secrets.choice(choices)
        state = dict(
            puzzle_id=item["id"],
            tier=body.tier,
            started_at=time.time(),
            time_limit_seconds={"easy": 60, "medium": 90, "hard": 120}[body.tier],
            moves=[],
            version=0,
            completed=False,
            solved=False,
            hint_shown=False,
            status="active",
        )
        activity_id = add_activity(db, user, "puzzle", state)
        event(
            db,
            user["id"],
            activity_id,
            "essential",
            "puzzle_started",
            puzzle_id=item["id"],
            fen=item["fen"],
            rating=item["rating"],
            tier=body.tier,
            time_limit_seconds=state["time_limit_seconds"],
        )
        return puzzle_view(activity_id, state)

    @app.get("/api/puzzles/{activity_id}")
    def get_puzzle(
        activity_id: str,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = activity(db, user, activity_id, "puzzle")
        tick_puzzle(db, user, activity_id, state)
        return puzzle_view(activity_id, state)

    @app.post("/api/puzzles/{activity_id}/moves")
    def puzzle_move(
        activity_id: str,
        body: MoveInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = activity(db, user, activity_id, "puzzle")
        check_version(state, body.version)
        tick_puzzle(db, user, activity_id, state)
        if state["completed"]:
            return puzzle_view(activity_id, state)
        board = puzzle_board(state)
        move = legal_uci(board, body.move)
        solution = puzzle_item(state)["solution"]
        correct = move == solution[len(state["moves"])]
        event(
            db,
            user["id"],
            activity_id,
            "essential",
            "puzzle_attempt",
            move=move,
            correct=correct,
            confidence=body.confidence,
            san=board.san(chess.Move.from_uci(move)),
            fen_before=board.fen(),
            elapsed_ms=round((time.time() - state["started_at"]) * 1000),
        )
        if not correct:
            finish_puzzle(db, user, activity_id, state, False, "incorrect")
        else:
            state["moves"].append(move)
            if len(state["moves"]) < len(solution):
                reply = solution[len(state["moves"])]
                board.push_uci(move)
                reply_san = board.san(chess.Move.from_uci(reply))
                reply_before = board.fen()
                board.push_uci(reply)
                state["moves"].append(reply)
                event(
                    db,
                    user["id"],
                    activity_id,
                    "essential",
                    "puzzle_reply",
                    move=reply,
                    san=reply_san,
                    fen_before=reply_before,
                    fen_after=board.fen(),
                )
            if len(state["moves"]) == len(solution):
                finish_puzzle(db, user, activity_id, state, True, "solved")
        state["version"] += 1
        save_activity(db, activity_id, state)
        return puzzle_view(activity_id, state)

    @app.post("/api/puzzles/{activity_id}/hint")
    def puzzle_hint(
        activity_id: str,
        body: VersionInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = activity(db, user, activity_id, "puzzle")
        check_version(state, body.version)
        if state.get("learning_id") and not state.get("hints_available"):
            raise HTTPException(
                403, "Hints are unavailable for this assessment or session."
            )
        tick_puzzle(db, user, activity_id, state)
        if not state["completed"] and not state["hint_shown"]:
            state["hint_shown"] = True
            state["version"] += 1
            event(
                db,
                user["id"],
                activity_id,
                "essential",
                "puzzle_hint_shown",
                hint_text=puzzle_item(state).get("hint")
                or "Look for forcing moves: checks, captures, and threats.",
                hint_source="authored" if puzzle_item(state).get("hint") else "general",
                elapsed_ms=round((time.time() - state["started_at"]) * 1000),
            )
            save_activity(db, activity_id, state)
        return puzzle_view(activity_id, state)

    def learning_view(db, user, identifier):
        state = learning.load(db, user, identifier)
        puzzle_id = state["current_puzzle"]
        puzzle = activity(db, user, puzzle_id, "puzzle")
        tick_puzzle(db, user, puzzle_id, puzzle)
        state = learning.load(db, user, identifier)
        return {
            **learning.summary(identifier, state),
            "puzzle": puzzle_view(puzzle_id, puzzle),
        }

    @app.get("/api/learning")
    def learning_home(
        user=Depends(current_user), db=Depends(connection, scope="function")
    ):
        calibration = learning.pending(db, user, "calibration")
        pending = learning.pending(db, user, "puzzle_session")
        rows = db.execute(
            "SELECT id, state FROM activities WHERE user_id=$1 AND kind='puzzle_session' ORDER BY created_at DESC LIMIT 5",
            (user["id"],),
        ).fetchall()
        return {
            "profile": profile_stats(db, user),
            "onboarding_id": calibration[0] if calibration else None,
            "active_session": learning.summary(*pending) if pending else None,
            "recent": [
                learning.summary(row["id"], json.loads(row["state"])) for row in rows
            ],
        }

    @app.post("/api/onboarding")
    def start_onboarding(
        user=Depends(current_user), db=Depends(connection, scope="function")
    ):
        identifier, _ = learning.create(db, user, calibration=True)
        return learning_view(db, user, identifier)

    @app.post("/api/learning/sessions")
    def start_learning_session(
        body: LearningInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        identifier, _ = learning.create(db, user, size=body.size)
        return learning_view(db, user, identifier)

    @app.get("/api/learning/history")
    def learning_history(
        page: int = Query(1, ge=1, le=1_000_000),
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        total = db.execute(
            "SELECT COUNT(*) FROM activities WHERE user_id=$1 AND kind='puzzle_session'",
            (user["id"],),
        ).fetchone()[0]
        pages = max(1, (total + 7) // 8)
        current = min(page, pages)
        rows = db.execute(
            "SELECT id, state FROM activities WHERE user_id=$1 AND kind='puzzle_session' ORDER BY created_at DESC, id DESC LIMIT 8 OFFSET $2",
            (user["id"], (current - 1) * 8),
        ).fetchall()
        return {
            "items": [
                learning.summary(row["id"], json.loads(row["state"])) for row in rows
            ],
            "page": current,
            "total_pages": pages,
            "total": total,
        }

    @app.get("/api/learning/{identifier}")
    def get_learning(
        identifier: str,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        return learning_view(db, user, identifier)

    @app.post("/api/learning/{identifier}/next")
    def next_learning(
        identifier: str,
        body: VersionInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = learning.load(db, user, identifier)
        check_version(state, body.version)
        puzzle = activity(db, user, state["current_puzzle"], "puzzle")
        if not puzzle["completed"]:
            raise HTTPException(409, "Finish the current puzzle first.")
        learning.next_puzzle(db, user, identifier, state)
        return learning_view(db, user, identifier)

    @app.post("/api/puzzles/{activity_id}/skip")
    def skip_puzzle(
        activity_id: str,
        body: VersionInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = activity(db, user, activity_id, "puzzle")
        check_version(state, body.version)
        tick_puzzle(db, user, activity_id, state)
        if not state["completed"]:
            finish_puzzle(db, user, activity_id, state, False, "skipped")
            state["version"] += 1
            save_activity(db, activity_id, state)
        return puzzle_view(activity_id, state)

    @app.post("/api/learning/{identifier}/feedback")
    def learning_feedback(
        identifier: str,
        body: FeedbackInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = learning.load(db, user, identifier)
        if not state["completed"] or state["kind"] != "puzzle_session":
            raise HTTPException(409, "Finish your session first.")
        if not body.skipped and body.satisfaction is None:
            raise HTTPException(422, "Choose a satisfaction rating or skip feedback.")
        if state["feedback"] is None:
            state["feedback"] = body.model_dump()
            state["version"] += 1
            save_activity(db, identifier, state)
            event(
                db,
                user["id"],
                identifier,
                "research" if user["research_consent"] else "essential",
                "session_feedback",
                **body.model_dump(),
            )
        return learning_view(db, user, identifier)

    @app.post("/api/studies", status_code=201)
    def start_study(
        user=Depends(current_user), db=Depends(connection, scope="function")
    ):
        if not user["research_consent"]:
            raise HTTPException(
                403, "Review and accept study data collection in your profile first."
            )
        state = new_study(protocol)
        state["participant_experience"] = user["experience"]
        # Exposure is flagged, as in the desktop pilot. This is not a frozen main study.
        prior = db.execute(
            "SELECT COUNT(*) FROM activities WHERE user_id=$1 AND kind='study'",
            (user["id"],),
        ).fetchone()[0]
        state["prior_sessions"] = prior
        exposed = {
            position_key(json.loads(row[0])["fen"])
            for row in db.execute(
                "SELECT payload FROM events WHERE user_id=$1 AND category='research' AND kind='position_presented'",
                (user["id"],),
            )
        }
        state["prior_exposure_item_ids"] = [
            item["id"]
            for item in protocol["items"]
            if position_key(item["fen"]) in exposed
        ]
        activity_id = add_activity(db, user, "study", state)
        StudyLog(db, user["id"], activity_id, state).append(
            "session_started",
            mode="pilot",
            condition=state["condition"],
            form_order=state["form_order"],
            prior_sessions=prior,
            prior_exposure_item_ids=state["prior_exposure_item_ids"],
            consent_version=CONSENT_VERSION,
            participant_experience=state["participant_experience"],
            protocol=protocol,
            assignments=state["assignments"],
        )
        return {
            "id": activity_id,
            **study_view(state, trial_for(db, user["id"], activity_id, state)),
        }

    def read_study(db, user, activity_id, state):
        trial = trial_for(db, user["id"], activity_id, state)
        if trial is not None:
            was_finished = trial.finished
            if user["research_consent"]:
                trial.tick()
            snapshot_trial(state, trial)
            if trial.finished != was_finished:
                state["version"] += 1
            save_activity(db, activity_id, state)
        return {"id": activity_id, **study_view(state, trial)}

    @app.get("/api/studies/{activity_id}")
    def get_study(
        activity_id: str,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        return read_study(
            db, user, activity_id, activity(db, user, activity_id, "study")
        )

    @app.post("/api/studies/{activity_id}/actions")
    def study_action(
        activity_id: str,
        body: StudyInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        if not user["research_consent"]:
            raise HTTPException(
                403,
                "Study collection is paused. Accept study consent in your profile to continue.",
            )
        state = activity(db, user, activity_id, "study")
        check_version(state, body.version)
        trial = trial_for(db, user["id"], activity_id, state)
        if trial is None:
            raise HTTPException(400, "This study has finished.")
        if trial.tick() and body.action not in ("reason", "next"):
            snapshot_trial(state, trial)
            state["version"] += 1
            save_activity(db, activity_id, state)
            return {"id": activity_id, **study_view(state, trial)}
        if body.action == "present":
            trial.present()
        elif body.action == "initial":
            trial.record_initial(body.move, body.confidence)
            state["candidate_move"] = body.move
        elif body.action == "candidate":
            trial.record_candidate(body.move)
            state["candidate_move"] = body.move
        elif body.action == "hint":
            trial.request_hint()
        elif body.action == "reflection":
            trial.record_reflection(body.text)
        elif body.action == "submit":
            trial.submit(body.move, body.confidence)
        elif body.action == "skip":
            trial.active()
            trial.finish("aborted")
        elif body.action == "reason":
            trial.reason(body.text)
        elif body.action == "familiarity":
            trial.familiarity(body.text)
        elif body.action == "next":
            if not trial.finished:
                raise ValueError("Finish the current position first.")
            state["index"] += 1
            state["trial"] = {}
            state["candidate_move"] = None
            state["completed"] = state["index"] == len(state["assignments"])
            if state["completed"]:
                StudyLog(db, user["id"], activity_id, state).append("session_completed")
        if body.action != "next":
            snapshot_trial(state, trial)
        state["version"] += 1
        save_activity(db, activity_id, state)
        return read_study(db, user, activity_id, state)

    @app.post("/api/interactions", status_code=204)
    def interaction(
        body: InteractionInput,
        user=Depends(current_user),
        db=Depends(connection, scope="function"),
    ):
        state = activity(db, user, body.activity_id)
        if body.kind == "focus_changed" and body.focused is None:
            raise HTTPException(422, "Focus events need a focused value.")
        if body.kind == "square_selected" and body.square is None:
            raise HTTPException(422, "Square events need a square.")
        if user["analytics_consent"] or user["research_consent"]:
            # Cap optional telemetry per player to bound accidental client loops.
            recent = db.execute(
                "SELECT COUNT(*) FROM events WHERE user_id=$1 AND kind IN ('focus_changed', 'square_selected') AND recorded_at>$2",
                (user["id"], time.time() - 60),
            ).fetchone()[0]
            if recent >= 120:
                raise HTTPException(
                    429, "Too many interaction events. Try again shortly."
                )
            if user["analytics_consent"]:
                event(
                    db,
                    user["id"],
                    body.activity_id,
                    "analytics",
                    body.kind,
                    focused=body.focused,
                    square=body.square,
                )
        if body.kind == "focus_changed" and user["research_consent"]:
            row = db.execute(
                "SELECT kind FROM activities WHERE id=$1", (body.activity_id,)
            ).fetchone()
            if row["kind"] == "study":
                trial = trial_for(db, user["id"], body.activity_id, state)
                if trial:
                    was_finished = trial.finished
                    trial.tick()
                    trial.focus(body.focused)
                    snapshot_trial(state, trial)
                    if trial.finished != was_finished:
                        state["version"] += 1
                    save_activity(db, body.activity_id, state)
            elif state.get("learning_id"):
                event(
                    db,
                    user["id"],
                    body.activity_id,
                    "research",
                    "focus_changed",
                    focused=body.focused,
                    elapsed_ms=round((time.time() - state["started_at"]) * 1000),
                )

    @app.get("/api/research/summary", dependencies=[Depends(require_researcher)])
    def summary(db=Depends(connection, scope="function")):
        return {
            "players": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "activities": dict(
                db.execute(
                    "SELECT kind, COUNT(*) FROM activities GROUP BY kind"
                ).fetchall()
            ),
            "events": dict(
                db.execute(
                    "SELECT category, COUNT(*) FROM events GROUP BY category"
                ).fetchall()
            ),
        }

    @app.get("/api/research/export", dependencies=[Depends(require_researcher)])
    def researcher_export(db=Depends(connection, scope="function")):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                "event_id",
                "participant",
                "activity_id",
                "category",
                "kind",
                "recorded_at",
                "payload_json",
            ]
        )
        # Only consented players enter the research export; optional profile fields are excluded.
        for row in db.execute(
            "SELECT events.* FROM events JOIN users ON events.user_id=users.id "
            f"WHERE {database.research_consent_sql} ORDER BY events.recorded_at"
        ):
            writer.writerow(
                [
                    row["id"],
                    row["user_id"],
                    row["activity_id"],
                    row["category"],
                    row["kind"],
                    datetime.fromtimestamp(
                        row["recorded_at"], timezone.utc
                    ).isoformat(),
                    row["payload"],
                ]
            )
        return Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="chesso-research.csv"'
            },
        )

    @app.get("/api/research/trials", dependencies=[Depends(require_researcher)])
    def trial_export(
        format: Literal["json", "csv"] = "json",
        db=Depends(connection, scope="function"),
    ):
        result = []
        for row in db.execute(
            "SELECT activities.* FROM activities JOIN users ON activities.user_id=users.id "
            f"WHERE activities.kind='study' AND {database.research_consent_sql} "
            "ORDER BY activities.created_at"
        ):
            state = json.loads(row["state"])
            manifest = dict(
                **state,
                participant=row["user_id"],
                session_id=row["id"],
                assignment_method="independent_random",
            )
            events = [
                {"kind": e["kind"], **json.loads(e["payload"])}
                for e in db.execute(
                    "SELECT kind, payload FROM events WHERE activity_id=$1 AND category='research' ORDER BY recorded_at",
                    (row["id"],),
                )
            ]
            for trial_row in rows_from_observations(manifest, events):
                trial_row["participant_experience"] = state.get(
                    "participant_experience", "unspecified"
                )
                result.append(trial_row)
        if format == "json":
            return result
        stream = io.StringIO()
        if result:
            writer = csv.DictWriter(stream, fieldnames=list(result[0]))
            writer.writeheader()
            writer.writerows(result)
        return Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="chesso-study-trials.csv"'
            },
        )

    # A build can be served by the API under one origin; API misses stay JSON 404s.
    build = ROOT / "frontend/dist"
    if (build / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=build / "assets"), name="assets")
    if (build / "index.html").is_file():

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "Endpoint not found.")
            return FileResponse(build / "index.html")

    return app


app = create_app()
