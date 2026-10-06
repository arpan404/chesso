"""Participant interface for Chesso's frozen-position hint study."""

from __future__ import annotations

import uuid
import math

import chess
import pygame

from study import DEFAULT_PROTOCOL, StudySession, export_session, load_protocol

BG = (21, 22, 33)
PANEL = (32, 33, 50)
TEXT = (236, 236, 245)
MUTED = (155, 157, 180)
ACCENT = (129, 182, 255)
GREEN = (110, 200, 130)
RED = (235, 110, 110)
LIGHT = (237, 214, 179)
DARK = (175, 130, 95)
PHASES = {"baseline": "Your own choices", "training": "Practice with hints",
          "transfer": "New positions without hints"}


class StudyScreen:
    def __init__(self, host, options: dict | None = None):
        self.host, self.screen = host, host.screen
        self.options = options or {}
        self.font, self.bold, self.small = host.font_ui, host.font_ui_b, host.font_small
        self.title = host.font_title
        self.board_rect = pygame.Rect(32, 72, 640, 640)
        self.renderer = type(host.renderer)(80)
        self.panel_rect = pygame.Rect(696, 40, 432, 688)
        self.controls: list[tuple[pygame.Rect, str, object, bool]] = []
        self.selected = None
        self.candidate: str | None = None
        self.promotions: list[chess.Move] = []
        self.confidence: int | None = None
        self.response = ""
        self.editing = "participant"
        self.participant = self.options.get("participant") or "P-" + uuid.uuid4().hex[:8]
        self.state = "setup"
        self.error = ""
        self.fatal = False
        self.session: StudySession | None = None
        self.seen = None
        self.orientation_white = True
        pygame.key.start_text_input()
        if self.options.get("resume"):
            self.session = StudySession.resume(self.options["resume"])
            self.participant = self.session.manifest["participant"]
            self.state = "complete" if self.session.complete else "intro"
            self.editing = None

    @property
    def trial(self):
        return self.session.trial if self.session else None

    def wrap(self, text, x, y, width=380, color=TEXT, font=None, gap=5):
        font = font or self.font
        words, line = text.split(), ""
        for word in words:
            candidate = (line + " " + word).strip()
            if line and font.size(candidate)[0] > width:
                self.screen.blit(font.render(line, True, color), (x, y))
                y += font.get_linesize() + gap
                line = word
            else:
                line = candidate
        if line:
            self.screen.blit(font.render(line, True, color), (x, y))
            y += font.get_linesize() + gap
        return y

    def button(self, label, action, x, y, w=380, h=38, value=None, enabled=True, selected=False):
        rect = pygame.Rect(x, y, w, h)
        hover = rect.collidepoint(pygame.mouse.get_pos()) and enabled
        color = (52, 78, 116) if selected else (56, 61, 86) if hover else (43, 46, 68)
        pygame.draw.rect(self.screen, color, rect, border_radius=7)
        pygame.draw.rect(self.screen, ACCENT if selected else (75, 80, 107), rect, 1, border_radius=7)
        image = self.small.render(label, True, TEXT if enabled else (104, 108, 132))
        self.screen.blit(image, (rect.centerx-image.get_width()/2, rect.centery-image.get_height()/2))
        self.controls.append((rect, action, value, enabled))

    def start(self):
        protocol = load_protocol(self.options.get("protocol", DEFAULT_PROTOCOL),
                                 self.options.get("collection", "pilot"))
        self.session = StudySession.create(protocol, self.participant,
                                           self.options.get("condition"),
                                           self.options.get("collection", "pilot"))
        self.state, self.editing = "intro", None

    def begin_position(self):
        trial = self.session.prepare()
        self.selected, self.candidate, self.confidence = None, None, None
        self.promotions, self.response, self.seen = [], "", None
        self.orientation_white = trial.board.turn
        self.state = "position"

    def next_position(self):
        self.session.advance()
        self.state = "complete" if self.session.complete else "intro"
        self.error = ""

    def leave(self):
        if self.session:
            try:
                if not self.fatal:
                    if self.trial and not self.trial.finished and self.trial.presented_at is not None:
                        self.trial.finish("aborted")
                    self.session.log.append("session_left", next_order=self.session.index + 1)
            finally:
                self.session.close()
        return True

    def act(self, action, value=None):
        self.error = ""
        if action == "leave":
            return self.leave()
        if self.fatal:
            return False
        if action == "start":
            self.start()
        elif action == "begin":
            self.begin_position()
        elif action == "next":
            self.next_position()
        elif action == "confidence":
            self.confidence = value
        elif action == "initial":
            self.trial.record_initial(self.candidate, self.confidence)
            self.confidence = None
        elif action == "candidate":
            self.trial.record_candidate(self.candidate)
            self.error = "Candidate saved."
        elif action == "hint":
            self.trial.request_hint()
            if self.trial.condition == "reflective" and self.trial.reflection is None:
                self.state, self.editing = "reflection", "response"
        elif action == "reflect":
            self.trial.record_reflection(self.response)
            self.state, self.editing = "position", None
        elif action == "final":
            self.trial.submit(self.candidate, self.confidence)
            self.state = "finished"
        elif action == "reason":
            self.trial.reason(value)
            self.error = "Response saved."
        elif action == "seen":
            self.trial.familiarity(value)
            self.seen = value
        elif action == "promotion":
            self.candidate = value.uci()
            self.confidence = None
            self.promotions = []
        elif action == "export":
            target = self.session.directory / "trials.csv"
            export_session(self.session.directory, target)
            self.error = "Saved trials.csv in this session's folder."
        elif action == "edit_participant":
            self.editing = "participant"
        return False

    def pixel_square(self, pos):
        if not self.board_rect.collidepoint(pos):
            return None
        file = (pos[0] - self.board_rect.x) // 80
        rank = 7 - (pos[1] - self.board_rect.y) // 80
        if not self.orientation_white:
            file, rank = 7-file, 7-rank
        return chess.square(file, rank)

    def choose_square(self, square):
        self.trial.active()
        if self.promotions:
            return
        board = self.trial.board
        piece = board.piece_at(square)
        if piece and piece.color == board.turn:
            self.selected = None if self.selected == square else square
            return
        if self.selected is not None:
            moves = [m for m in board.legal_moves if m.from_square == self.selected and m.to_square == square]
            if len(moves) > 1:
                self.promotions = moves
            elif moves:
                self.candidate = moves[0].uci()
                self.confidence = None
                self.selected = None

    def handle_event(self, event):
        try:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return self.leave()
                if event.key == pygame.K_BACKSPACE and self.editing:
                    field = "participant" if self.editing == "participant" else "response"
                    setattr(self, field, getattr(self, field)[:-1])
                elif event.key == pygame.K_RETURN and self.state == "setup":
                    self.act("start")
            elif event.type == pygame.TEXTINPUT and self.editing:
                if self.editing == "participant":
                    allowed = "".join(c for c in event.text if c.isascii() and (c.isalnum() or c in "_-"))
                    self.participant = (self.participant + allowed)[:48]
                else:
                    self.response = (self.response + event.text)[:1000]
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, action, value, enabled in self.controls:
                    if enabled and rect.collidepoint(event.pos):
                        return self.act(action, value)
                if self.state in ("position", "reflection") and not self.fatal:
                    square = self.pixel_square(event.pos)
                    if square is not None:
                        self.choose_square(square)
            elif event.type == pygame.WINDOWFOCUSLOST and self.trial:
                self.trial.focus(False)
            elif event.type == pygame.WINDOWFOCUSGAINED and self.trial:
                self.trial.focus(True)
        except (ValueError, TypeError) as exc:
            self.error = str(exc)
        except OSError:
            self.fatal = True
            self.error = "Saving failed. Stop this session and check the local data folder."
        return False

    def update(self):
        if self.trial and not self.fatal:
            try:
                if self.trial.tick() and self.state in ("position", "reflection"):
                    self.state, self.editing = "finished", None
            except OSError:
                self.fatal = True
                self.error = "Saving failed. Stop this session and check the local data folder."

    def draw_board(self):
        board = self.trial.board
        side = "White" if board.turn else "Black"
        self.screen.blit(self.bold.render(side + " to move", True, TEXT), (32, 40))
        candidate = chess.Move.from_uci(self.candidate) if self.candidate else None
        for square in chess.SQUARES:
            file, rank = chess.square_file(square), chess.square_rank(square)
            col, row = (file, 7-rank) if self.orientation_white else (7-file, rank)
            rect = pygame.Rect(self.board_rect.x+80*col, self.board_rect.y+80*row, 80, 80)
            color = LIGHT if (file+rank) % 2 else DARK
            pygame.draw.rect(self.screen, color, rect)
            if square == self.selected or candidate and square in (candidate.from_square, candidate.to_square):
                pygame.draw.rect(self.screen, (65, 132, 170), rect.inflate(-6, -6), 3, border_radius=4)
            piece = board.piece_at(square)
            if piece:
                image = self.renderer.get(piece.piece_type, piece.color)
                self.screen.blit(image, image.get_rect(center=rect.center))
            if col == 0:
                self.screen.blit(self.small.render(str(rank+1), True, (65, 58, 54)), (rect.x+5, rect.y+3))
            if row == 7:
                self.screen.blit(self.small.render(chess.FILE_NAMES[file], True, (65, 58, 54)), (rect.right-14, rect.bottom-21))

    def draw_setup(self):
        x, y = 250, 180
        self.screen.blit(self.title.render("Chess decision study", True, TEXT), (x, y))
        mode = self.options.get("collection", "pilot")
        y = self.wrap("Pilot session" if mode == "pilot" else "Study session", x, y+50, 660, ACCENT)
        y = self.wrap("Choose moves on fixed positions. Start with your own choices, practice with hints, then try new positions without help.", x, y+12, 650)
        y = self.wrap("There are no points, ratings or answer feedback. Your choices, confidence and responses are saved on this computer. Use a participant code, not your name.", x, y+10, 650, MUTED)
        self.screen.blit(self.small.render("Participant code", True, MUTED), (x, y+12))
        self.button(self.participant + (" |" if self.editing else ""), "edit_participant", x, y+38, 650, 42)
        if mode == "pilot":
            y = self.wrap("The sample bank uses hand-written draft hints. It is for testing the study software.", x, y+96, 650, MUTED, self.small)
        else:
            y += 96
        self.button("Start session", "start", x, y+24, 315)
        self.button("Back to Chesso", "leave", x+335, y+24, 315)
        if self.error:
            self.wrap(self.error, x, y+82, 650, RED, self.small)

    def draw_intro(self):
        assignment = self.session.manifest["assignments"][self.session.index]
        phase = assignment["phase"]
        self.screen.blit(self.title.render(PHASES[phase], True, TEXT), (260, 225))
        text = ("Hints are available after you save your first choice. You can keep or change that choice before submitting."
                if phase == "training" else "Work on your own. Hints and answer feedback are unavailable in this part.")
        y = self.wrap(text, 260, 285, 640)
        y = self.wrap(f"You have {assignment['time_limit_seconds']:g} seconds for this position. The timer starts when the board appears.", 260, y+18, 640, MUTED)
        self.button("Show position", "begin", 260, y+40, 310)
        self.button("Leave session", "leave", 590, y+40, 310)

    def draw_confidence(self, y):
        x = self.panel_rect.x+24
        self.wrap("How confident are you that this move meets the task?", x, y, 382, MUTED, self.small)
        for i, confidence in enumerate((0, 25, 50, 75, 100)):
            self.button(str(confidence)+"%", "confidence", x+i*77, y+42, 69, 34,
                        confidence, selected=self.confidence == confidence)

    def draw_position(self):
        x = self.panel_rect.x+24
        trial = self.trial
        self.screen.blit(self.bold.render(PHASES[trial.assignment["phase"]], True, ACCENT), (x, 65))
        remaining = max(0, trial.assignment["time_limit_seconds"] - (trial.elapsed_ms or 0)/1000)
        self.screen.blit(self.title.render(f"{math.ceil(remaining)}s", True, TEXT), (x, 103))
        pygame.draw.rect(self.screen, (48, 51, 70), (x, 146, 382, 5), border_radius=2)
        pygame.draw.rect(self.screen, ACCENT, (x, 146, int(382*remaining/trial.assignment["time_limit_seconds"]), 5), border_radius=2)
        if self.promotions:
            self.wrap("Choose the promotion piece.", x, 190)
            for i, move in enumerate(self.promotions):
                self.button(chess.piece_name(move.promotion).title(), "promotion", x, 245+i*48, value=move)
            return
        if self.state == "reflection":
            y = self.wrap(trial.item["hint"]["text"], x, 178)
            y = self.wrap(trial.item["hint"]["reflection_prompt"], x, y+22, color=ACCENT)
            rect = pygame.Rect(x, y+12, 382, min(170, 570-y))
            pygame.draw.rect(self.screen, (23, 25, 39), rect, border_radius=7)
            pygame.draw.rect(self.screen, ACCENT, rect, 1, border_radius=7)
            previous_clip = self.screen.get_clip()
            self.screen.set_clip(rect.inflate(-16, -12))
            lines, line = [], ""
            for word in (self.response + " |").split():
                candidate = (line + " " + word).strip()
                if line and self.font.size(candidate)[0] > 360:
                    lines.append(line); line = word
                else:
                    line = candidate
            lines.append(line)
            line_height = self.font.get_linesize()+5
            visible = max(1, (rect.h-18)//line_height)
            for i, line in enumerate(lines[-visible:]):
                self.screen.blit(self.font.render(line, True, TEXT), (rect.x+9, rect.y+9+i*line_height))
            self.screen.set_clip(previous_clip)
            self.button("Save response", "reflect", x, 595, enabled=bool(self.response.strip()))
            self.wrap("The timer continues while you write.", x, 644, color=MUTED, font=self.small)
            return
        if trial.initial_move is None:
            self.wrap("Select a piece and destination. The board stays in place.", x, 174, color=MUTED)
            selected = trial.board.san(chess.Move.from_uci(self.candidate)) if self.candidate else "None selected"
            self.screen.blit(self.bold.render("First choice: " + selected, True, TEXT), (x, 252))
            self.draw_confidence(300)
            self.button("Save first choice", "initial", x, 402,
                        enabled=bool(self.candidate) and self.confidence is not None)
            self.wrap("Have you seen this exact position before?", x, 472, color=MUTED, font=self.small)
            for i, (label, value) in enumerate((("No", "no"), ("Yes", "yes"), ("Not sure", "unsure"))):
                self.button(label, "seen", x+i*130, 508, 122, value=value, selected=self.seen == value)
        else:
            if trial.hint_shown:
                self.wrap(trial.item["hint"]["text"], x, 174)
            else:
                self.wrap("You can keep your first choice or select a different move.", x, 174, color=MUTED)
            move = trial.board.san(chess.Move.from_uci(self.candidate)) if self.candidate else "None"
            first = trial.board.san(chess.Move.from_uci(trial.initial_move))
            self.screen.blit(self.small.render("Saved first choice: " + first, True, MUTED), (x, 268))
            self.screen.blit(self.bold.render("Final choice: " + move, True, TEXT), (x, 291))
            self.draw_confidence(332)
            self.button("Submit final choice", "final", x, 430,
                        enabled=bool(self.candidate) and self.confidence is not None)
            self.button("Save another candidate", "candidate", x, 483, enabled=bool(self.candidate))
            if trial.assignment["phase"] == "training" and not trial.hint_shown:
                self.button("See hint", "hint", x, 536)
            elif trial.reflection:
                self.wrap("Your response to the hint is saved.", x, 544, color=MUTED, font=self.small)
        prompt = self.session.manifest["protocol"].get("task_prompt", "Find the strongest move.")
        self.wrap(prompt + " The board stays in place.", x, 605, color=MUTED, font=self.small)

    def draw_finished(self):
        x = self.panel_rect.x+24
        self.screen.blit(self.title.render("Choice saved" if self.trial.status == "submitted" else "Position ended", True, TEXT), (x, 84))
        self.wrap("Optional: what led you to finish?", x, 152, color=MUTED)
        for i, (label, value) in enumerate((("I was ready to choose", "ready"), ("I had no other idea", "no_other_idea"),
                                          ("The time available", "time"), ("I was guessing", "guess"),
                                          ("Prefer not to answer", "prefer_not_to_say"))):
            self.button(label, "reason", x, 212+i*48, value=value)
        self.button("Continue", "next", x, 505)
        self.wrap("Your response is saved without showing an answer.", x, 567, color=MUTED, font=self.small)

    def draw_complete(self):
        self.screen.blit(self.title.render("Session complete", True, TEXT), (240, 215))
        y = self.wrap("Your responses have been saved. Thank you.", 240, 280, 680)
        y = self.wrap("Participant code: " + self.participant, 240, y+20, 680, MUTED)
        y = self.wrap("Session folder: " + str(self.session.directory), 240, y+15, 680, MUTED, self.small)
        self.button("Export this session as CSV", "export", 240, y+40, 330)
        self.button("Back to Chesso", "leave", 590, y+40, 330)
        if self.error:
            self.wrap(self.error, 240, y+105, 680, GREEN, self.small)

    def draw(self):
        self.controls = []
        self.screen.fill(BG)
        if self.state == "setup":
            self.draw_setup()
        elif self.state == "intro":
            self.draw_intro()
        elif self.state == "complete":
            self.draw_complete()
        else:
            self.draw_board()
            pygame.draw.rect(self.screen, PANEL, self.panel_rect, border_radius=12)
            if self.state == "finished":
                self.draw_finished()
            else:
                self.draw_position()
            if self.error:
                self.wrap(self.error, 720, 660, 382, RED, self.small)
        pygame.display.flip()
        if self.state == "position" and self.trial.presented_at is None and not self.fatal:
            try:
                self.trial.present()
            except OSError:
                self.fatal = True
                self.error = "Saving failed. Stop this session and check the local data folder."
