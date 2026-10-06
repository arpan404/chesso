import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

import chess

from import_puzzletrack import import_protocol
from study import (StudySession, digest, export_session, load_protocol, read_events,
                   trial_rows, validate_protocol)
from study_analysis import summarize


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.protocol = load_protocol()
        self.clock = Clock()
        self.session = StudySession.create(self.protocol, "SYNTHETIC", "reflective",
                                           directory=self.root / "session", seed=12)

    def trial(self, phase="baseline"):
        self.session.index = next(i for i, a in enumerate(self.session.manifest["assignments"])
                                  if a["phase"] == phase)
        trial = self.session.prepare(self.clock)
        trial.present()
        return trial

    def test_board_stays_frozen_through_hint_and_submission(self):
        trial = self.trial("training")
        fen = trial.board.fen()
        moves = [m.uci() for m in trial.board.legal_moves]
        trial.record_initial(moves[0], 25)
        trial.record_candidate(moves[1])
        trial.request_hint()
        trial.record_reflection("The opponent may capture my piece.")
        self.clock.now += 2
        trial.submit(moves[1], 50)
        self.assertEqual(fen, trial.board.fen())
        self.assertEqual([], trial.board.move_stack)
        row = next(r for r in trial_rows(self.session.directory) if r["phase"] == "training" and r["status"] == "submitted")
        self.assertTrue(row["revised"])
        self.assertTrue(row["reflection_saved"])
        self.assertEqual(row["initial_confidence"], 25)
        self.assertEqual(row["post_initial_ms"], 2000)

    def test_assessment_cannot_show_hints(self):
        trial = self.trial()
        trial.record_initial(next(iter(trial.board.legal_moves)).uci(), 50)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            trial.request_hint()

    def test_reflection_is_required_only_after_reflective_hint(self):
        trial = self.trial("training")
        move = next(iter(trial.board.legal_moves)).uci()
        with self.assertRaisesRegex(ValueError, "own choice"):
            trial.request_hint()
        trial.record_initial(move, 25)
        trial.request_hint()
        with self.assertRaisesRegex(ValueError, "response"):
            trial.submit(move, 50)
        with self.assertRaises(ValueError):
            trial.record_reflection("   ")
        self.assertFalse(trial.finished)
        trial.record_reflection("I need to check the king's reply.")
        trial.submit(move, 75)
        self.assertTrue(trial.finished)

    def test_informational_and_reflective_receive_identical_hint_content(self):
        trial = self.trial("training")
        move = next(iter(trial.board.legal_moves)).uci()
        trial.record_initial(move, 50)
        reflective = trial.request_hint()
        other = StudySession.create(self.protocol, "OTHER", "informational",
                                    directory=self.root / "other", seed=12)
        other.index = self.session.index
        info = other.prepare(self.clock); info.present()
        info.record_initial(move, 50)
        self.assertEqual(reflective, info.request_hint())
        info.submit(move, 50)

    def test_timeout_preserves_initial_and_rejects_late_submission(self):
        trial = self.trial()
        move = next(iter(trial.board.legal_moves)).uci()
        trial.record_initial(move, 50)
        self.clock.now += trial.assignment["time_limit_seconds"] + 8
        with self.assertRaisesRegex(ValueError, "ended"):
            trial.submit(move, 100)
        row = trial_rows(self.session.directory)[self.session.index]
        self.assertEqual(row["status"], "timeout")
        self.assertEqual(row["initial_move"], move)
        self.assertIsNone(row["final_move"])
        self.assertIsNone(row["final_confidence"])
        self.assertEqual(row["final_ms"], 90000)
        self.assertEqual(row["post_initial_ms"], 90000)
        self.assertEqual(read_events(self.session.log.path)[-1]["observed_end_ms"], 98000)

    def test_abort_after_deadline_is_timeout(self):
        trial = self.trial()
        self.clock.now += trial.assignment["time_limit_seconds"]
        trial.finish("aborted")
        self.assertEqual(trial.status, "timeout")

    def test_deadline_does_not_start_until_position_is_presented(self):
        trial = self.session.prepare(self.clock)
        self.clock.now += 1000
        self.assertFalse(trial.tick())
        self.assertIsNone(trial.elapsed_ms)
        trial.present()
        self.assertEqual(trial.elapsed_ms, 0)

    def test_invalid_inputs_and_duplicate_final_do_not_create_extra_records(self):
        trial = self.trial()
        with self.assertRaises(ValueError):
            trial.record_initial("a1a8", 50)
        move = next(iter(trial.board.legal_moves)).uci()
        for value in (None, -1, 101, float("nan"), True):
            with self.assertRaises(ValueError):
                trial.record_initial(move, value)
        trial.record_initial(move, 50)
        trial.submit(move, 50)
        with self.assertRaises(ValueError):
            trial.submit(move, 50)
        self.assertEqual(sum(e["kind"] == "trial_finished" for e in read_events(self.session.log.path)), 1)

    def test_resume_marks_unfinished_trial_interrupted_without_inventing_time(self):
        trial = self.trial()
        move = next(iter(trial.board.legal_moves)).uci()
        trial.record_initial(move, 25)
        self.session.close()
        resumed = StudySession.resume(self.session.directory)
        row = trial_rows(resumed.directory)[0]
        self.assertEqual(row["status"], "interrupted")
        self.assertEqual(row["initial_move"], move)
        self.assertIsNone(row["final_ms"])
        self.assertFalse(row["timing_complete"])
        self.assertEqual(resumed.index, 1)

    def test_resume_completed_trial_does_not_repeat_it(self):
        trial = self.trial()
        move = next(iter(trial.board.legal_moves)).uci()
        trial.record_initial(move, 25); trial.submit(move, 50)
        self.session.close()
        resumed = StudySession.resume(self.session.directory)
        self.assertEqual(resumed.index, 1)

    def test_changed_snapshot_and_corrupt_events_fail_loudly(self):
        manifest_path = self.session.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["protocol"]["assessment_seconds"] = 30
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "changed"):
            StudySession.resume(self.session.directory)
        with self.session.log.path.open("a") as f:
            f.write('{"partial":\n')
        with self.assertRaisesRegex(ValueError, "Corrupt"):
            read_events(self.session.log.path)

    def test_forms_switch_without_repeating_positions(self):
        orders = set()
        for seed in range(12):
            session = StudySession.create(self.protocol, f"TEST_{seed}",
                                          directory=self.root / f"form_{seed}", seed=seed)
            orders.add(session.manifest["form_order"])
            assigned = session.manifest["assignments"]
            self.assertEqual(len({a["item_id"] for a in assigned}), 16)
            self.assertEqual([a["phase"] for a in assigned], ["baseline"]*4+["training"]*8+["transfer"]*4)
        self.assertEqual(orders, {"AB", "BA"})

    def test_main_collection_rejects_draft_hints_and_missing_benchmarks(self):
        with self.assertRaises(ValueError):
            validate_protocol(self.protocol, "main")
        protocol = copy.deepcopy(self.protocol)
        protocol["status"] = "frozen"
        for item in protocol["items"]:
            item["benchmark"] = dict(accepted_moves=[item["reference_move"]], objective="test fixture only",
                                      method="synthetic", reviewer="TEST", settings="TEST")
            if item["set"] == "training":
                item["hint"].update(review_status="approved", reviewer="TEST")
        protocol["task_prompt"] = "Test fixture only."
        validate_protocol(protocol, "main")
        protocol["hint_source"] = "llm"
        with self.assertRaisesRegex(ValueError, "model"):
            validate_protocol(protocol, "main")

    def test_same_position_with_different_counters_is_rejected(self):
        protocol = copy.deepcopy(self.protocol)
        fen = protocol["items"][0]["fen"].split()
        fen[-1] = "999"
        protocol["items"][1]["fen"] = " ".join(fen)
        with self.assertRaisesRegex(ValueError, "repeat"):
            validate_protocol(protocol)

    def test_export_keeps_missing_assignments_and_self_reports(self):
        trial = self.trial()
        move = next(iter(trial.board.legal_moves)).uci()
        trial.familiarity("yes"); trial.focus(False)
        trial.record_initial(move, 75); trial.submit(move, 100); trial.reason("guess")
        output = export_session(self.session.directory, self.root / "export.csv")
        with output.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0]["stop_reason"], "guess")
        self.assertEqual(rows[0]["familiarity"], "yes")
        self.assertEqual(rows[0]["focus_losses"], "1")
        self.assertEqual(rows[1]["status"], "not_started")
        self.assertEqual(rows[1]["final_move"], "")
        with self.assertRaises(ValueError):
            export_session(self.session.directory, self.session.log.path)

    def test_pilot_reference_agreement_is_not_benchmark_accuracy(self):
        trial = self.trial()
        move = trial.item["reference_move"]
        trial.record_initial(move, 100); trial.submit(move, 100)
        summary = next(r for r in summarize(trial_rows(self.session.directory)) if r["phase"] == "baseline")
        self.assertEqual(summary["reference_agreement"], 1)
        self.assertEqual(summary["benchmark_scored"], 0)
        self.assertIsNone(summary["benchmark_success_rate"])
        self.assertIsNone(summary["confidence_brier"])

    def test_benchmark_calibration_uses_reviewed_outcome_not_reference(self):
        item_id = self.session.manifest["assignments"][0]["item_id"]
        item = next(i for i in self.protocol["items"] if i["id"] == item_id)
        moves = [m.uci() for m in chess.Board(item["fen"]).legal_moves]
        alternative = next(m for m in moves if m != item["reference_move"])
        item["benchmark"] = dict(accepted_moves=[alternative], objective="synthetic test")
        self.session = StudySession.create(self.protocol, "SCORING_TEST", "reflective",
                                           directory=self.root / "scoring", seed=12)
        trial = self.trial()
        trial.record_initial(alternative, 50); trial.submit(alternative, 75)
        summary = next(r for r in summarize(trial_rows(self.session.directory)) if r["phase"] == "baseline")
        self.assertEqual(summary["reference_agreement"], 0)
        self.assertEqual(summary["benchmark_success_rate"], 1)
        self.assertAlmostEqual(summary["confidence_brier"], .0625)

    def test_foreign_events_are_not_silently_combined(self):
        event = read_events(self.session.log.path)[0]
        event["participant"] = "SOMEONE_ELSE"
        self.session.log.path.write_text(json.dumps(event)+"\n")
        with self.assertRaisesRegex(ValueError, "different session"):
            trial_rows(self.session.directory)

    def test_session_cannot_be_collected_in_two_windows(self):
        with self.assertRaisesRegex(ValueError, "already open"):
            StudySession.resume(self.session.directory)
        self.session.close()
        resumed = StudySession.resume(self.session.directory)
        resumed.close()

    def test_pilot_rerun_records_actual_prior_exposure(self):
        trial = self.trial()
        trial.finish("aborted")
        second = StudySession.create(self.protocol, "SYNTHETIC", "reflective",
                                      directory=self.root / "rerun", seed=12)
        rows = trial_rows(second.directory)
        self.assertTrue(rows[0]["prior_exposure"])
        self.assertEqual(sum(r["prior_exposure"] for r in rows), 1)

    def test_importer_applies_setup_and_preserves_source_fields(self):
        rows = [i["source_row"] for i in self.protocol["items"]]
        source = dict(format="puzzletrack-local-pool", version=1,
                      source=self.protocol["source_bank"]["provenance"], puzzles=rows)
        path = self.root / "pool.json"; path.write_text(json.dumps(source))
        imported = import_protocol(path)
        original = {i["id"]: i for i in self.protocol["items"]}
        for item in imported["items"]:
            self.assertEqual(item["fen"], original[item["id"]]["fen"])
            self.assertEqual(item["reference_move"], item["source_row"]["Moves"].split()[1])
            self.assertEqual(item["source_license"], "CC0-1.0")
        source["puzzles"][0]["Moves"] += " a1a1"
        path.write_text(json.dumps(source))
        with self.assertRaises(ValueError):
            import_protocol(path)

    def test_writing_failure_does_not_claim_the_choice_was_saved(self):
        from unittest.mock import patch
        trial = self.trial()
        move = next(iter(trial.board.legal_moves)).uci()
        with patch.object(trial.log, "append", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                trial.record_initial(move, 50)
        self.assertIsNone(trial.initial_move)


if __name__ == "__main__":
    unittest.main()
