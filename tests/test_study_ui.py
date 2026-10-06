import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess
import pygame

import main
from study import StudySession, Trial, load_protocol, trial_rows
from study_ui import StudyScreen


class StudyUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.object(main.profile_mod, "load", return_value=main.profile_mod._default()):
            self.host = main.ChessGame()
        self.addCleanup(pygame.quit)
        self.ui = StudyScreen(self.host, {"participant": "SYNTHETIC_UI"})
        self.ui.session = StudySession.create(load_protocol(), "SYNTHETIC_UI", "reflective",
                                               directory=Path(self.temp.name) / "session", seed=12)
        self.ui.begin_position()
        self.ui.draw()

    def test_mouse_selection_does_not_play_move_and_confidence_resets(self):
        trial = self.ui.trial
        fen = trial.board.fen()
        move = next(iter(trial.board.legal_moves))
        self.ui.choose_square(move.from_square)
        self.ui.choose_square(move.to_square)
        self.assertEqual(self.ui.candidate, move.uci())
        self.assertEqual(trial.board.fen(), fen)
        self.ui.confidence = 50
        self.ui.act("initial")
        self.assertIsNone(self.ui.confidence)
        self.ui.draw()
        final = next(c for c in self.ui.controls if c[1] == "final")
        self.assertFalse(final[3])

    def test_promotion_requires_explicit_piece_choice(self):
        item = dict(id="SYNTHETIC_PROMOTION", fen="7k/P7/8/8/8/8/8/7K w - - 0 1")
        self.ui.session.trial = Trial(self.ui.session.log, self.ui.trial.assignment, item, "reflective")
        self.ui.trial.present()
        self.ui.orientation_white = True
        self.ui.choose_square(chess.A7); self.ui.choose_square(chess.A8)
        self.assertEqual(len(self.ui.promotions), 4)
        self.assertIsNone(self.ui.candidate)
        rook = next(m for m in self.ui.promotions if m.promotion == chess.ROOK)
        self.ui.act("promotion", rook)
        self.assertEqual(self.ui.candidate, "a7a8r")
        self.assertIsNotNone(self.ui.trial.board.piece_at(chess.A7))

    def test_main_loop_never_runs_gameplay_coach_or_opponent_in_study(self):
        self.host.study_screen = self.ui
        self.host.screen_state = "study"
        original = self.host.board.fen()
        with patch.object(pygame.event, "get", side_effect=[[], [pygame.event.Event(pygame.QUIT)]]), \
             patch.object(self.host, "maybe_start_ai", side_effect=AssertionError("AI during study")), \
             patch.object(self.host, "fire_pending_reply", side_effect=AssertionError("Opponent during study")), \
             patch.object(self.host, "_maybe_rate_game", side_effect=AssertionError("Rating during study")):
            self.host.run()
        self.assertEqual(self.host.board.fen(), original)
        self.assertEqual(trial_rows(self.ui.session.directory)[0]["status"], "aborted")
