"""Apply the Trial rules to transactional, restartable web sessions."""

import random
import time
import uuid

from backend.chess_service import board_data
from backend.database import event
from backend.study import Trial, digest


class StudyLog:
    def __init__(self, db, user_id, activity_id, state):
        self.db, self.user_id, self.activity_id, self.state = (
            db,
            user_id,
            activity_id,
            state,
        )

    def append(self, kind, **fields):
        event(
            self.db,
            self.user_id,
            self.activity_id,
            "research",
            kind,
            schema_version=2,
            session_id=self.activity_id,
            participant=self.user_id,
            protocol_hash=self.state["protocol_hash"],
            **fields,
        )


def new_study(protocol):
    rng = random.SystemRandom()
    condition = rng.choice(("informational", "reflective"))
    form_order = rng.choice(("AB", "BA"))
    before, after = ("form_a", "form_b") if form_order == "AB" else ("form_b", "form_a")
    assignments = []
    for phase, group, seconds in (
        ("baseline", before, protocol["assessment_seconds"]),
        ("training", "training", protocol["training_seconds"]),
        ("transfer", after, protocol["assessment_seconds"]),
    ):
        items = [i for i in protocol["items"] if i["set"] == group]
        rng.shuffle(items)
        for item in items:
            assignments.append(
                dict(
                    trial_id=uuid.uuid4().hex,
                    order=len(assignments) + 1,
                    phase=phase,
                    item_id=item["id"],
                    time_limit_seconds=seconds,
                )
            )
    return dict(
        protocol=protocol,
        protocol_hash=digest(protocol),
        condition=condition,
        form_order=form_order,
        assignments=assignments,
        index=0,
        trial={},
        version=0,
        completed=False,
        mode="pilot",
    )


def trial_for(db, user_id, activity_id, state):
    if state["completed"]:
        return None
    assignment = state["assignments"][state["index"]]
    item = next(
        i for i in state["protocol"]["items"] if i["id"] == assignment["item_id"]
    )
    trial = Trial(
        StudyLog(db, user_id, activity_id, state),
        assignment,
        item,
        state["condition"],
        clock=time.time,
    )
    for key, value in state["trial"].items():
        setattr(trial, key, value)
    return trial


def snapshot_trial(state, trial):
    state["trial"] = {
        key: getattr(trial, key)
        for key in (
            "presented_at",
            "initial_move",
            "hint_shown",
            "reflection",
            "finished",
            "status",
        )
    }


def study_view(state, trial):
    view = {
        k: state[k]
        for k in ("condition", "form_order", "index", "version", "completed", "mode")
    }
    view.update(
        candidate_move=state.get("candidate_move"),
        total=len(state["assignments"]),
        protocol_id=state["protocol"]["id"],
        task_prompt=state["protocol"].get("task_prompt")
        or "Choose the strongest move in this position. The board stays fixed while you consider your answer.",
    )
    if trial is not None:
        view.update(board_data(trial.board))
        view.update(trial.assignment)
        view.update(state["trial"])
        view["remaining_seconds"] = max(
            0, trial.assignment["time_limit_seconds"] - (trial.elapsed_ms or 0) / 1000
        )
        view["hint"] = trial.item["hint"]["text"] if trial.hint_shown else None
        view["reflection_prompt"] = (
            trial.item["hint"]["reflection_prompt"]
            if trial.hint_shown and trial.condition == "reflective"
            else None
        )
    return view
