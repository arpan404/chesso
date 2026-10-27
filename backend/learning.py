"""Adaptive puzzle calibration and durable, non-repeating learning sessions."""

import json
import math
import random
import time
import uuid

import chess
from fastapi import HTTPException

from backend.database import event, save_activity
from backend.study import position_key


class Learning:
    def __init__(self, puzzles):
        positions = set()
        self.bank = {}
        for item in puzzles:
            key = position_key(item["fen"])
            if key not in positions:
                self.bank[item["id"]] = item
                positions.add(key)
        self.rng = random.SystemRandom()

    def load(self, db, user, identifier):
        row = db.execute(
            "SELECT kind, state FROM activities WHERE id=$1 AND user_id=$2",
            (identifier, user["id"]),
        ).fetchone()
        if row is None or row["kind"] not in ("calibration", "puzzle_session"):
            raise HTTPException(404, "Session not found.")
        return json.loads(row["state"])

    def insert(self, db, user, kind, state):
        identifier = uuid.uuid4().hex
        now = time.time()
        db.execute(
            "INSERT INTO activities VALUES ($1, $2, $3, $4, $5, $6)",
            (identifier, user["id"], kind, now, now, json.dumps(state)),
        )
        return identifier

    def pending(self, db, user, kind):
        for row in db.execute(
            "SELECT id, state FROM activities WHERE user_id=$1 AND kind=$2 ORDER BY created_at DESC LIMIT 50",
            (user["id"], kind),
        ):
            state = json.loads(row["state"])
            if not state["completed"]:
                return row["id"], state
        return None

    def estimate(self, attempts):
        grid = list(range(300, 2401, 25))
        scores = []
        for rating in grid:
            score = -0.5 * ((rating - 1200) / 600) ** 2
            for attempt in attempts:
                if attempt["status"] == "skipped":
                    continue
                probability = 1 / (1 + 10 ** ((attempt["rating"] - rating) / 400))
                score += math.log(probability if attempt["solved"] else 1 - probability)
            scores.append(score)
        weights = [math.exp(score - max(scores)) for score in scores]
        total = sum(weights)
        mean = round(sum(r * w for r, w in zip(grid, weights)) / total / 25) * 25
        cumulative = 0
        lower, upper = grid[0], grid[-1]
        for rating, weight in zip(grid, weights):
            before = cumulative
            cumulative += weight / total
            if before < 0.1 <= cumulative:
                lower = rating
            if before < 0.9 <= cumulative:
                upper = rating
        return mean, [lower, upper]

    def create(self, db, user, calibration=False, size=20):
        kind = "calibration" if calibration else "puzzle_session"
        pending = self.pending(db, user, kind)
        if pending:
            return pending
        if calibration and user.get("calibration_complete"):
            raise HTTPException(409, "Your onboarding is already complete.")
        if not calibration and not user.get("calibration_complete"):
            raise HTTPException(409, "Complete your rating assessment first.")
        state = {
            "kind": kind,
            "total": 10 if calibration else size,
            "version": 0,
            "completed": False,
            "started_at": time.time(),
            "attempts": [],
            "seen_ids": [],
            "current_puzzle": None,
            "rating_before": user["puzzle_rating"],
            "estimated_rating": 1200 if calibration else user["puzzle_rating"],
            "rating_range": [300, 2400],
            "hints_available": False if calibration else self.rng.choice([True, False]),
            "protocol_version": "adaptive-puzzles-v1",
            "feedback": None,
        }
        if not calibration:
            recent = [
                json.loads(row["state"])["puzzle_id"]
                for row in db.execute(
                    "SELECT state FROM activities WHERE user_id=$1 AND kind='puzzle' ORDER BY created_at DESC LIMIT 40",
                    (user["id"],),
                )
            ]
            last = recent[0] if recent else None
            pool = [p for p in self.bank.values() if p["id"] not in recent]
            if len(pool) < size:
                pool = [p for p in self.bank.values() if p["id"] != last]
            if len(pool) < size:
                raise HTTPException(409, "Not enough unique puzzles for this session.")
            plan = []
            for index in range(size):
                depth = 1 + index % 4
                weights = [
                    math.exp(-abs(p["rating"] - user["puzzle_rating"]) / 450)
                    * (2 if (len(p["solution"]) + 1) // 2 == depth else 1)
                    for p in pool
                ]
                chosen = self.rng.choices(pool, weights=weights, k=1)[0]
                plan.append(chosen["id"])
                pool.remove(chosen)
            state["plan"] = plan
        identifier = self.insert(db, user, kind, state)
        event(
            db,
            user["id"],
            identifier,
            "essential",
            "learning_session_started",
            session_kind=kind,
            total=state["total"],
            hints_available=state["hints_available"],
            protocol_version=state["protocol_version"],
            rating_before=state["rating_before"],
        )
        self.next_puzzle(db, user, identifier, state)
        return identifier, state

    def next_puzzle(self, db, user, identifier, state):
        if state["completed"]:
            return
        if state["kind"] == "calibration":
            desired = 1 + len(state["attempts"]) % 4
            available = [
                p for p in self.bank.values() if p["id"] not in state["seen_ids"]
            ]
            available.sort(
                key=lambda p: (
                    abs(p["rating"] - state["estimated_rating"])
                    + (0 if (len(p["solution"]) + 1) // 2 == desired else 120)
                )
            )
            item = self.rng.choice(available[:3])
        else:
            item = self.bank[state["plan"][len(state["attempts"])]]
        depth = (len(item["solution"]) + 1) // 2
        puzzle = {
            "puzzle_id": item["id"],
            "tier": "easy"
            if item["rating"] < 1000
            else "medium"
            if item["rating"] < 1400
            else "hard",
            "started_at": time.time(),
            "time_limit_seconds": 90 + 30 * (depth - 1),
            "moves": [],
            "version": 0,
            "completed": False,
            "solved": False,
            "hint_shown": False,
            "hints_available": state["hints_available"],
            "status": "active",
            "learning_id": identifier,
            "player_moves_required": depth,
            "player_color": "white" if chess.Board(item["fen"]).turn else "black",
        }
        puzzle_id = self.insert(db, user, "puzzle", puzzle)
        state["seen_ids"].append(item["id"])
        state["current_puzzle"] = puzzle_id
        state["version"] += 1
        save_activity(db, identifier, state)
        event(
            db,
            user["id"],
            puzzle_id,
            "essential",
            "puzzle_started",
            puzzle_id=item["id"],
            fen=item["fen"],
            rating=item["rating"],
            time_limit_seconds=puzzle["time_limit_seconds"],
            learning_id=identifier,
            ordinal=len(state["attempts"]) + 1,
            player_moves_required=depth,
            hints_available=state["hints_available"],
        )

    def finished(self, db, user, puzzle_id, puzzle):
        identifier = puzzle.get("learning_id")
        if not identifier:
            return
        state = self.load(db, user, identifier)
        if any(a["id"] == puzzle_id for a in state["attempts"]):
            return
        item = self.bank[puzzle["puzzle_id"]]
        state["attempts"].append(
            {
                "id": puzzle_id,
                "puzzle_id": item["id"],
                "rating": item["rating"],
                "solved": puzzle["solved"],
                "status": puzzle["status"],
                "hint_used": puzzle["hint_shown"],
                "elapsed_ms": round((time.time() - puzzle["started_at"]) * 1000),
                "player_moves_required": puzzle["player_moves_required"],
                "moves": puzzle["moves"],
            }
        )
        state["version"] += 1
        if state["kind"] == "calibration":
            state["estimated_rating"], state["rating_range"] = self.estimate(
                state["attempts"]
            )
        if len(state["attempts"]) == state["total"]:
            state["completed"] = True
            state["finished_at"] = time.time()
            if state["kind"] == "calibration":
                user["calibration_complete"] = True
                user["puzzle_rating"] = state["estimated_rating"]
                user["rating_range"] = state["rating_range"]
                user["calibration_version"] = state["protocol_version"]
            state["rating_after"] = user["puzzle_rating"]
            event(
                db,
                user["id"],
                identifier,
                "essential",
                "learning_session_completed",
                total=state["total"],
                solved=sum(a["solved"] for a in state["attempts"]),
                rating_after=user["puzzle_rating"],
                rating_range=state["rating_range"],
            )
        save_activity(db, identifier, state)

    def summary(self, identifier, state):
        return {
            "id": identifier,
            "kind": state["kind"],
            "version": state["version"],
            "total": state["total"],
            "completed": state["completed"],
            "started_at": state["started_at"],
            "finished_at": state.get("finished_at"),
            "finished_count": len(state["attempts"]),
            "solved": sum(a["solved"] for a in state["attempts"]),
            "hints_available": state["hints_available"],
            "estimated_rating": state["estimated_rating"],
            "rating_range": state["rating_range"],
            "rating_before": state["rating_before"],
            "rating_after": state.get("rating_after"),
            "feedback": state["feedback"],
            "outcomes": [
                {
                    "solved": a["solved"],
                    "hint_used": a["hint_used"],
                    "status": a["status"],
                }
                for a in state["attempts"]
            ],
        }
