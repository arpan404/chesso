"""Profile — ratings, adaptive AI ladder, puzzle tiers, research logging.

- Game rating: starts at 400. Each rated game vs a ladder AI blends the
  result (65%) with move quality from coach grades (35%) into an Elo update.
- Puzzle rating: starts at 800 (migrated once from legacy rating.json).
- Graded puzzle and game moves are appended to data/attempts.jsonl as legacy
  gameplay observations. The independent study uses study.py instead.
"""

from __future__ import annotations

import json
import os
import time

PROFILE_FILE = "profile.json"
LEGACY_RATING_FILE = "rating.json"
DATA_DIR = "data"
ATTEMPTS_FILE = os.path.join(DATA_DIR, "attempts.jsonl")

GAME_START = 400
PUZZLE_START = 800

# Adaptive ladder: (name, rating). Engine params live in coach.AI_LADDER.
AI_LADDER = [
    {"name": "Rookie", "rating": 300},
    {"name": "Casual", "rating": 600},
    {"name": "Club", "rating": 900},
    {"name": "Strong", "rating": 1200},
]

# Puzzle tiers: band by PUZZLE rating, clock seconds, base points.
TIERS = {
    "easy": {"label": "Easy", "max": 1000, "time": 60, "base": 10},
    "medium": {"label": "Medium", "max": 1400, "time": 90, "base": 20},
    "hard": {"label": "Hard", "max": 10 ** 9, "time": 120, "base": 30},
}

# Partial credit: a wrong-but-decent first try (cp_loss <= this) earns +3
# and a second chance instead of instant failure.
VALID_LOSS_MAX = 70
VALID_POINTS = 3
BEST_BONUS_PCT = 0.10  # first-try Best: +10% on the solve points


def _default() -> dict:
    import uuid

    return {
        "subject_id": uuid.uuid4().hex[:12],  # anonymous research subject
        "game_rating": GAME_START,
        "game_games": 0,
        "puzzle_rating": PUZZLE_START,
        "puzzles_solved": 0,
        "puzzles_attempted": 0,
        "tier_solves": {"easy": 0, "medium": 0, "hard": 0},
        "tier_attempts": {"easy": 0, "medium": 0, "hard": 0},
        "points_total": 0,
        "best_streak": 0,
        "history": [],  # capped, newest last: {t, kind, ...}
    }


def load(path: str = PROFILE_FILE) -> dict:
    d: dict | None = None
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception:
        d = None
    if d is None:
        d = _default()
        # one-time migration from legacy rating.json (puzzle rating only)
        try:
            with open(LEGACY_RATING_FILE) as f:
                d["puzzle_rating"] = int(json.load(f).get("puzzle_rating", PUZZLE_START))
        except Exception:
            pass
        save(d, path)
        return d
    base = _default()
    base.update(d)
    if not base.get("subject_id"):
        import uuid

        base["subject_id"] = uuid.uuid4().hex[:12]
        save(base, path)
    return base


def save(profile: dict, path: str = PROFILE_FILE) -> None:
    try:
        profile["history"] = profile.get("history", [])[-200:]
        with open(path, "w") as f:
            json.dump(profile, f)
    except Exception:
        pass


def match_ai(game_rating: int) -> dict:
    """Ladder rung closest to the user (ties go to the weaker rung)."""
    best = AI_LADDER[0]
    for rung in AI_LADDER[1:]:
        if abs(rung["rating"] - game_rating) < abs(best["rating"] - game_rating):
            best = rung
    return best


def expected_score(user: int, opp: int) -> float:
    return 1.0 / (1.0 + 10 ** ((opp - user) / 400.0))


def quality_from_loss(avg_loss: float) -> float:
    """Map average centipawn loss (0..inf) to 0..1 move-quality score."""
    if avg_loss <= 0:
        return 1.0
    return max(0.0, 1.0 - avg_loss / 400.0)


def rate_game(profile: dict, ai_rating: int, result: float, avg_loss: float) -> dict:
    """Blend result (65%) + move quality (35%), Elo-update the game rating."""
    games = profile.get("game_games", 0)
    k = 40 if games < 20 else 32
    q = quality_from_loss(avg_loss) if avg_loss >= 0 else 0.5
    actual = 0.65 * result + 0.35 * q
    exp = expected_score(profile.get("game_rating", GAME_START), ai_rating)
    delta = int(round(k * (actual - exp)))
    profile["game_rating"] = profile.get("game_rating", GAME_START) + delta
    profile["game_games"] = games + 1
    profile.setdefault("history", []).append({
        "t": int(time.time()), "kind": "game", "ai": ai_rating,
        "result": result, "avg_loss": round(avg_loss, 1) if avg_loss >= 0 else None,
        "delta": delta, "rating": profile["game_rating"],
    })
    save(profile)
    return {"delta": delta, "rating": profile["game_rating"], "actual": actual}


def rate_puzzle(profile: dict, puzzle_rating: int, solved: bool, k: int = 32,
                tier: str | None = None) -> int:
    exp = expected_score(profile.get("puzzle_rating", PUZZLE_START), puzzle_rating)
    delta = int(round(k * ((1.0 if solved else 0.0) - exp)))
    profile["puzzle_rating"] = profile.get("puzzle_rating", PUZZLE_START) + delta
    profile["puzzles_attempted"] = profile.get("puzzles_attempted", 0) + 1
    if solved:
        profile["puzzles_solved"] = profile.get("puzzles_solved", 0) + 1
    if tier in TIERS:
        profile.setdefault("tier_attempts", {}).setdefault(tier, 0)
        profile["tier_attempts"][tier] += 1
        if solved:
            profile.setdefault("tier_solves", {}).setdefault(tier, 0)
            profile["tier_solves"][tier] += 1
    profile.setdefault("history", []).append({
        "t": int(time.time()), "kind": "puzzle", "puzzle": puzzle_rating,
        "tier": tier, "solved": solved, "delta": delta,
        "rating": profile["puzzle_rating"],
    })
    save(profile)
    return delta


def calibration_puzzle(profile: dict, n: int = 5) -> bool:
    """First n puzzles are onboarding: excluded from the main SoS test."""
    return profile.get("puzzles_attempted", 0) < n


def calibration_game(profile: dict, n: int = 5) -> bool:
    return profile.get("game_games", 0) < n


def tier_of(puzzle_rating: int) -> str:
    for name, t in TIERS.items():
        if puzzle_rating < t["max"]:
            return name
    return "hard"


def solve_points(tier: str, seconds_left: float, first_try_best: bool) -> int:
    t = TIERS[tier]
    total = t["base"] + round(t["base"] * max(0.0, seconds_left) / t["time"])
    if first_try_best:
        total = round(total * (1.0 + BEST_BONUS_PCT))
    return total


def log_attempt(row: dict, path: str = ATTEMPTS_FILE) -> None:
    """Append one research row (JSONL). Never raises."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        row = {"t": int(time.time()), **row}
        with open(path, "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
