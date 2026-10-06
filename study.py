"""Frozen-position study tasks, durable observations and offline exports.

Participant interaction lives in study_ui.py. This module never starts a coach,
updates a rating, or advances a participant's position.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import random
import re
import time
import uuid
import weakref
from datetime import datetime, timezone
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parent
DEFAULT_PROTOCOL = ROOT / "study_protocol.json"
SCHEMA = 2
CONDITIONS = ("informational", "reflective")
REASONS = ("ready", "no_other_idea", "time", "guess", "prefer_not_to_say")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def position_key(fen: str) -> str:
    # Move counters do not turn the same board into a fresh assessment item.
    return " ".join(chess.Board(fen).fen().split()[:4])


def legal_uci(board: chess.Board, text: str) -> str:
    try:
        move = chess.Move.from_uci(text.strip().lower())
    except ValueError as exc:
        raise ValueError("Choose a legal move on this position.") from exc
    if move not in board.legal_moves:
        raise ValueError("Choose a legal move on this position.")
    return move.uci()


def validate_protocol(protocol: dict, mode: str = "pilot") -> dict:
    protocol = copy.deepcopy(protocol)
    if mode not in ("pilot", "main"):
        raise ValueError("Mode must be pilot or main.")
    if not isinstance(protocol.get("id"), str) or not protocol["id"]:
        raise ValueError("The protocol needs a versioned id.")
    for field in ("assessment_seconds", "training_seconds"):
        value = protocol.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{field} must be a positive, finite number.")
    items = protocol.get("items", [])
    if not items:
        raise ValueError("The protocol has no positions.")
    ids, positions = set(), set()
    for item in items:
        if not isinstance(item.get("id"), str) or not item["id"] or item["id"] in ids:
            raise ValueError("Every item needs a unique id.")
        ids.add(item["id"])
        board = chess.Board(item["fen"])
        if not board.is_valid() or board.is_game_over():
            raise ValueError(f"Invalid or finished position: {item['id']}")
        key = position_key(item["fen"])
        if key in positions:
            raise ValueError("Assessment and training positions must not repeat.")
        positions.add(key)
        if item.get("set") not in ("form_a", "form_b", "training"):
            raise ValueError("Items need form_a, form_b or training membership.")
        if not item.get("reference_move"):
            raise ValueError("Keep a source reference move, separate from benchmark quality.")
        legal_uci(board, item["reference_move"])
        if item["set"] == "training":
            hint = item.get("hint", {})
            for field in ("text", "reflection_prompt"):
                if not isinstance(hint.get(field), str) or not 0 < len(hint[field].strip()) <= 240:
                    raise ValueError("Training hint and question text must each be 1 to 240 characters.")
            if mode == "main" and (hint.get("review_status") != "approved" or not hint.get("reviewer")):
                raise ValueError("Main collection needs explicitly reviewed hints.")
            if mode == "main" and protocol.get("hint_source") == "llm":
                metadata = hint.get("generation", {})
                if hint.get("authorship") != "llm" or not all(metadata.get(k) for k in ("model", "prompt", "generated_at")):
                    raise ValueError("LLM hints need their model, actual prompt and generation time.")
        if mode == "main":
            benchmark = item.get("benchmark", {})
            accepted = benchmark.get("accepted_moves", [])
            if not accepted or not all(legal_uci(board, move) for move in accepted):
                raise ValueError("Main collection needs reviewed benchmark acceptance sets.")
            if not all(benchmark.get(k) for k in ("objective", "method", "reviewer", "settings")):
                raise ValueError("Document the benchmark objective, method, settings and review.")
    counts = {group: sum(i["set"] == group for i in items)
              for group in ("form_a", "form_b", "training")}
    if not all(counts.values()) or counts["form_a"] != counts["form_b"]:
        raise ValueError("Use two equally sized assessment forms and a separate training set.")
    if mode == "main" and protocol.get("status") != "frozen":
        raise ValueError("Main collection requires a frozen protocol. Use pilot for the sample bank.")
    if mode == "main" and not str(protocol.get("task_prompt", "")).strip():
        raise ValueError("Main collection needs instructions matching the benchmark objective.")
    return protocol


def load_protocol(path: str | Path = DEFAULT_PROTOCOL, mode: str = "pilot") -> dict:
    return validate_protocol(json.loads(Path(path).read_text()), mode)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


class EventLog:
    """One flushed append per observation. A write failure must be visible."""

    def __init__(self, path: Path, session_id: str, subject: str, protocol_hash: str):
        self.path, self.session_id = path, session_id
        self.subject, self.protocol_hash = subject, protocol_hash

    def append(self, kind: str, **fields) -> dict:
        row = dict(schema_version=SCHEMA, event_id=uuid.uuid4().hex,
                   session_id=self.session_id, participant=self.subject,
                   protocol_hash=self.protocol_hash, recorded_at=utc_now(),
                   kind=kind, **fields)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return row


def read_events(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupt event log at line {number}; preserve it before recovery.") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Invalid event at line {number}.")
        rows.append(row)
    return rows


def session_events(directory: Path, manifest: dict) -> list[dict]:
    rows = read_events(directory / "events.jsonl")
    event_ids = set()
    trial_ids = {a["trial_id"] for a in manifest["assignments"]}
    for row in rows:
        if (row.get("session_id") != manifest["session_id"]
                or row.get("participant") != manifest["participant"]
                or row.get("protocol_hash") != manifest["protocol_hash"]):
            raise ValueError("An event belongs to a different session or protocol.")
        if not row.get("event_id") or row["event_id"] in event_ids:
            raise ValueError("Duplicate or missing event id.")
        event_ids.add(row["event_id"])
        if row.get("trial_id") is not None and row["trial_id"] not in trial_ids:
            raise ValueError("An event refers to an unassigned trial.")
    return rows


class StudySession:
    def __init__(self, directory: Path, manifest: dict):
        # Advisory session ownership on macOS/Linux. Windows uses the stdlib
        # byte-range lock. An OS lock releases automatically after a crash.
        self._lock_stream = (directory / ".session.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self._lock_stream.seek(0)
                if not self._lock_stream.read(1):
                    self._lock_stream.write(b"0"); self._lock_stream.flush()
                self._lock_stream.seek(0)
                msvcrt.locking(self._lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_stream.close()
            raise ValueError("This session is already open in another study window.") from exc
        self._release = weakref.finalize(self, self._lock_stream.close)
        self.directory, self.manifest = directory, manifest
        self.log = EventLog(directory / "events.jsonl", manifest["session_id"],
                            manifest["participant"], manifest["protocol_hash"])
        self.index = 0
        self.trial: Trial | None = None

    def close(self) -> None:
        self._release()

    @classmethod
    def create(cls, protocol: dict, participant: str | None = None,
               condition: str | None = None, mode: str = "pilot",
               directory: Path | None = None, seed: int | None = None) -> StudySession:
        protocol = validate_protocol(protocol, mode)
        participant = participant or "P-" + uuid.uuid4().hex[:8]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", participant):
            raise ValueError("Use a study code with letters, numbers, underscores or hyphens.")
        if condition is not None and condition not in CONDITIONS:
            raise ValueError("Unknown hint condition.")
        seed = seed if seed is not None else random.SystemRandom().getrandbits(64)
        rng = random.Random(seed)
        assigned = condition or rng.choice(CONDITIONS)
        form_order = rng.choice(("AB", "BA"))
        before, after = (("form_a", "form_b") if form_order == "AB" else ("form_b", "form_a"))
        session_id = uuid.uuid4().hex
        assignments = []
        for phase, group, limit in (("baseline", before, protocol["assessment_seconds"]),
                                    ("training", "training", protocol["training_seconds"]),
                                    ("transfer", after, protocol["assessment_seconds"])):
            chosen = [i for i in protocol["items"] if i["set"] == group]
            rng.shuffle(chosen)
            for item in chosen:
                assignments.append(dict(trial_id=f"{session_id}-{len(assignments)+1:03}",
                                        order=len(assignments)+1, phase=phase, item_id=item["id"],
                                        time_limit_seconds=limit))
        directory = Path(directory or ROOT / "data" / f"study-{mode}" / session_id)
        # Pilot reruns are allowed but carry previous-exposure flags. Main
        # collection cannot quietly reuse a previously presented position.
        previous_positions = set()
        search_root = ROOT / "data" if directory.is_relative_to(ROOT / "data") else directory.parent
        for existing_path in search_root.rglob("manifest.json"):
            existing = json.loads(existing_path.read_text())
            if existing.get("participant") != participant:
                continue
            old_items = {i["id"]: i for i in existing["protocol"]["items"]}
            presented_ids = {e["item_id"] for e in session_events(existing_path.parent, existing)
                             if e["kind"] == "position_presented"}
            previous_positions.update(position_key(old_items[i]["fen"]) for i in presented_ids)
        exposed_ids = [i["id"] for i in protocol["items"] if position_key(i["fen"]) in previous_positions]
        if mode == "main" and exposed_ids:
            raise ValueError("This participant has seen positions in this bank. Resume the saved session or use fresh positions.")
        directory.mkdir(parents=True, exist_ok=False)
        manifest = dict(schema_version=SCHEMA, instrument_version="chesso-study-0.1",
                        session_id=session_id, participant=participant, mode=mode,
                        created_at=utc_now(), condition=assigned,
                        assignment_method="operator" if condition else "independent_random",
                        seed=seed, form_order=form_order, protocol_hash=digest(protocol),
                        protocol=protocol, assignments=assignments,
                        prior_exposure_item_ids=exposed_ids)
        write_json(directory / "manifest.json", manifest)
        session = cls(directory, manifest)
        session.log.append("session_started", condition=assigned, mode=mode,
                           form_order=form_order)
        return session

    @classmethod
    def resume(cls, directory: str | Path) -> StudySession:
        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        if digest(manifest["protocol"]) != manifest["protocol_hash"]:
            raise ValueError("The stored protocol snapshot was changed.")
        validate_protocol(manifest["protocol"], manifest["mode"])
        rows = session_events(directory, manifest)
        session = cls(directory, manifest)
        finished = {r["trial_id"] for r in rows if r["kind"] == "trial_finished"}
        presented = {r["trial_id"] for r in rows if r["kind"] == "position_presented"}
        # An old monotonic clock cannot tell us how much time was spent during
        # a crash. Preserve observations and explicitly interrupt that trial.
        for assignment in manifest["assignments"]:
            trial_id = assignment["trial_id"]
            if trial_id in presented and trial_id not in finished:
                session.log.append("trial_finished", trial_id=trial_id,
                                   status="interrupted", final_move=None,
                                   final_confidence=None, elapsed_ms=None,
                                   timing_complete=False)
                finished.add(trial_id)
        session.index = next((i for i, a in enumerate(manifest["assignments"])
                              if a["trial_id"] not in finished), len(manifest["assignments"]))
        session.log.append("session_resumed", next_order=session.index + 1)
        return session

    @property
    def complete(self) -> bool:
        return self.index >= len(self.manifest["assignments"])

    def prepare(self, clock=time.monotonic) -> Trial | None:
        if self.complete:
            return None
        if self.trial is not None:
            return self.trial
        assignment = self.manifest["assignments"][self.index]
        item = next(i for i in self.manifest["protocol"]["items"] if i["id"] == assignment["item_id"])
        self.trial = Trial(self.log, assignment, item, self.manifest["condition"], clock)
        return self.trial

    def advance(self) -> None:
        if self.trial is None or not self.trial.finished:
            raise ValueError("Finish the current position first.")
        self.index += 1
        self.trial = None
        if self.complete:
            self.log.append("session_completed")


class Trial:
    def __init__(self, log: EventLog, assignment: dict, item: dict,
                 condition: str, clock=time.monotonic):
        self.log, self.assignment, self.item = log, assignment, item
        self.condition, self.clock = condition, clock
        self.board = chess.Board(item["fen"])
        self.presented_at: float | None = None
        self.initial_move: str | None = None
        self.hint_shown = False
        self.reflection: str | None = None
        self.finished = False
        self.status: str | None = None

    def event(self, kind: str, **fields) -> None:
        self.log.append(kind, trial_id=self.assignment["trial_id"], **fields)

    @property
    def elapsed_ms(self) -> int | None:
        if self.presented_at is None:
            return None
        return max(0, round((self.clock() - self.presented_at) * 1000))

    def present(self) -> None:
        if self.presented_at is not None or self.finished:
            return
        now = self.clock()
        self.event("position_presented", elapsed_ms=0, fen=self.board.fen(),
                   **{k: self.assignment[k] for k in ("item_id", "phase", "order", "time_limit_seconds")})
        self.presented_at = now

    def tick(self) -> bool:
        if (not self.finished and self.presented_at is not None
                and self.clock() - self.presented_at >= self.assignment["time_limit_seconds"]):
            self.finish("timeout")
        return self.finished

    def active(self) -> None:
        self.tick()
        if self.finished:
            raise ValueError("This position has ended.")
        if self.presented_at is None:
            raise ValueError("Start the position first.")

    @staticmethod
    def confidence(value: int | float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("Select confidence between 0 and 100.")

    def record_initial(self, move: str, confidence: int | float) -> None:
        self.active()
        if self.initial_move is not None:
            raise ValueError("Your first reported choice is already saved.")
        move = legal_uci(self.board, move)
        self.confidence(confidence)
        self.event("initial_reported", move=move, confidence=confidence, elapsed_ms=self.elapsed_ms)
        self.initial_move = move

    def record_candidate(self, move: str) -> None:
        self.active()
        move = legal_uci(self.board, move)
        self.event("candidate_reported", move=move, elapsed_ms=self.elapsed_ms)

    def request_hint(self) -> str:
        self.active()
        if self.assignment["phase"] != "training":
            raise ValueError("Hints are unavailable during assessment.")
        if self.initial_move is None:
            raise ValueError("Save your own choice before requesting a hint.")
        if not self.hint_shown:
            self.event("hint_shown", elapsed_ms=self.elapsed_ms, condition=self.condition,
                       hint_hash=digest(self.item["hint"]), hint_text=self.item["hint"]["text"])
            self.hint_shown = True
        return self.item["hint"]["text"]

    def record_reflection(self, text: str) -> None:
        self.active()
        if not self.hint_shown or self.condition != "reflective":
            raise ValueError("No reflection step is active.")
        text = text.strip()
        if not text or len(text) > 1000:
            raise ValueError("Write a short response before submitting it.")
        self.event("reflection_reported", text=text, elapsed_ms=self.elapsed_ms)
        self.reflection = text

    def submit(self, move: str, confidence: int | float) -> None:
        self.active()
        if self.initial_move is None:
            raise ValueError("Save your initial choice first.")
        move = legal_uci(self.board, move)
        self.confidence(confidence)
        if self.hint_shown and self.condition == "reflective" and self.reflection is None:
            raise ValueError("Save your response to the hint question first.")
        self.finish("submitted", move, confidence)

    def finish(self, status: str, move: str | None = None, confidence=None) -> None:
        if self.finished:
            return
        if status not in ("submitted", "timeout", "aborted", "interrupted"):
            raise ValueError("Invalid completion status.")
        observed_ms = self.elapsed_ms
        deadline_ms = round(self.assignment["time_limit_seconds"] * 1000)
        if status == "aborted" and observed_ms is not None and observed_ms >= deadline_ms:
            status = "timeout"
        self.event("trial_finished", status=status, final_move=move,
                   final_confidence=confidence,
                   elapsed_ms=deadline_ms if status == "timeout" else observed_ms,
                   observed_end_ms=observed_ms, assigned_deadline_ms=deadline_ms,
                   timing_complete=True)
        self.finished, self.status = True, status

    def reason(self, reason: str) -> None:
        if not self.finished or reason not in REASONS:
            raise ValueError("Select a reason after the position ends.")
        self.event("stop_reason_reported", reason=reason)

    def familiarity(self, value: str) -> None:
        self.active()
        if value not in ("yes", "no", "unsure"):
            raise ValueError("Invalid familiarity response.")
        self.event("familiarity_reported", value=value, elapsed_ms=self.elapsed_ms)

    def focus(self, focused: bool) -> None:
        if self.presented_at is not None and not self.finished:
            self.event("focus_changed", focused=focused, elapsed_ms=self.elapsed_ms)


def trial_rows(directory: str | Path) -> list[dict]:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if digest(manifest["protocol"]) != manifest["protocol_hash"]:
        raise ValueError("Protocol snapshot does not match its hash.")
    events = session_events(directory, manifest)
    items = {i["id"]: i for i in manifest["protocol"]["items"]}
    result = []
    for assignment in manifest["assignments"]:
        item = items[assignment["item_id"]]
        rows = [e for e in events if e.get("trial_id") == assignment["trial_id"]]
        initial = next((e for e in rows if e["kind"] == "initial_reported"), {})
        final = next((e for e in rows if e["kind"] == "trial_finished"), {})
        hint = next((e for e in rows if e["kind"] == "hint_shown"), {})
        reason = next((e for e in reversed(rows) if e["kind"] == "stop_reason_reported"), {})
        familiar = next((e for e in reversed(rows) if e["kind"] == "familiarity_reported"), {})
        move = final.get("final_move")
        benchmark = item.get("benchmark", {})
        accepted = benchmark.get("accepted_moves")
        result.append(dict(
            participant=manifest["participant"], session_id=manifest["session_id"],
            protocol_id=manifest["protocol"]["id"], protocol_hash=manifest["protocol_hash"],
            mode=manifest["mode"], condition=manifest["condition"],
            assignment_method=manifest["assignment_method"], form_order=manifest["form_order"],
            **assignment, fen=item["fen"], source=item.get("source"),
            source_url=item.get("source_url"), source_rating=item.get("rating"),
            status=final.get("status", "in_progress" if rows else "not_started"),
            initial_move=initial.get("move"), initial_confidence=initial.get("confidence"),
            initial_ms=initial.get("elapsed_ms"), final_move=move,
            final_confidence=final.get("final_confidence"), final_ms=final.get("elapsed_ms"),
            post_initial_ms=(final["elapsed_ms"] - initial["elapsed_ms"]
                             if final.get("elapsed_ms") is not None and initial else None),
            revised=(move != initial["move"] if move and initial else None),
            hint_used=bool(hint), hint_ms=hint.get("elapsed_ms"),
            reflection_saved=any(e["kind"] == "reflection_reported" for e in rows),
            reported_candidates=sum(e["kind"] == "candidate_reported" for e in rows),
            focus_losses=sum(e["kind"] == "focus_changed" and not e["focused"] for e in rows),
            familiarity=familiar.get("value", "unknown"), stop_reason=reason.get("reason"),
            prior_exposure=item["id"] in manifest.get("prior_exposure_item_ids", []),
            timing_complete=final.get("timing_complete"),
            reference_move=item["reference_move"],
            reference_agreement=(move == item["reference_move"] if move else None),
            benchmark_objective=benchmark.get("objective"),
            benchmark_success=(move in accepted if move and accepted else None)))
    return result


def export_session(directory: str | Path, output: str | Path) -> Path:
    rows = trial_rows(directory)
    path = Path(output)
    if path.resolve() in {Path(directory).resolve() / "events.jsonl", Path(directory).resolve() / "manifest.json"}:
        raise ValueError("Export to a new CSV file, not a source record.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def score_session(directory: str | Path, engine_path: str, nodes: int = 100000) -> Path:
    """Analyze the same FEN with root-move restrictions, preserving mate scores."""
    import chess.engine

    if nodes < 1:
        raise ValueError("Nodes must be positive.")
    directory = Path(directory)
    rows = trial_rows(directory)
    output = directory / f"engine-analysis-{uuid.uuid4().hex[:8]}.json"
    settings = dict(nodes=nodes, threads=1, hash_mb=64, perspective="side_to_move",
                    method="same_position_root_move", clear_hash_before_each_search=True)
    results = []
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        engine.configure({"Threads": 1, "Hash": 64})
        engine_id = dict(engine.id)

        def analyze(board, move=None):
            engine.configure({"Clear Hash": None})
            info = engine.analyse(board, chess.engine.Limit(nodes=nodes),
                                  root_moves=[chess.Move.from_uci(move)] if move else None)
            score = info["score"].pov(board.turn)
            return dict(cp=score.score(), mate=score.mate(), depth=info.get("depth"),
                        nodes=info.get("nodes"), pv=[m.uci() for m in info.get("pv", [])])

        for row in rows:
            if row["initial_move"] is None and row["final_move"] is None:
                continue
            board = chess.Board(row["fen"])
            best = analyze(board)
            initial = analyze(board, row["initial_move"]) if row["initial_move"] else None
            final = analyze(board, row["final_move"]) if row["final_move"] else None
            regret = lambda score: (best["cp"] - score["cp"]
                                    if score and best["cp"] is not None and score["cp"] is not None else None)
            results.append(dict(trial_id=row["trial_id"], fen=row["fen"], best=best,
                                initial=initial, final=final, initial_regret_cp=regret(initial),
                                final_regret_cp=regret(final)))
    write_json(output, dict(created_at=utc_now(), engine=engine_id,
                            engine_binary_sha256=hashlib.sha256(Path(engine_path).read_bytes()).hexdigest(),
                            protocol_hash=rows[0]["protocol_hash"], settings=settings,
                            note="Engine estimates, not ground truth. Mate scores stay separate; negative regret is retained for audit.",
                            trials=results))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    validate.add_argument("--mode", choices=("pilot", "main"), default="pilot")
    export = commands.add_parser("export")
    export.add_argument("session")
    export.add_argument("--out", required=True)
    score = commands.add_parser("score")
    score.add_argument("session")
    score.add_argument("--engine", required=True)
    score.add_argument("--nodes", type=int, default=100000)
    args = parser.parse_args()
    if args.command == "validate":
        protocol = load_protocol(args.protocol, args.mode)
        print(f"{protocol['id']}: {len(protocol['items'])} unique legal positions; {args.mode}; hash {digest(protocol)}")
    elif args.command == "export":
        print(export_session(args.session, args.out))
    else:
        print(score_session(args.session, args.engine, args.nodes))


if __name__ == "__main__":
    main()
