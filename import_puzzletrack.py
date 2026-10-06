"""Import public CC0 PuzzleTrack source pools into a Chesso pilot protocol.

Accepts the standalone bank or frozen local pool. No browser extension or
participant observations are read. Original PuzzleTrack code is not bundled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import chess

from study import position_key, validate_protocol, write_json


def shared_hint(themes: list[str]) -> str:
    if any(t.lower().startswith("mate") for t in themes):
        return "Compare forcing checks. For each one, check the king's escape squares and possible defenses."
    if "fork" in themes:
        return "Look for a move that creates two threats. Check which threat the opponent can defend."
    if "pawnEndgame" in themes:
        return "Compare the pawn races and the kings' routes. Check how a pawn move changes the position."
    if "rookEndgame" in themes:
        return "Compare rook activity and pawn safety. Check forcing moves before committing."
    if "hangingPiece" in themes:
        return "Check which pieces are undefended and whether a capture allows a stronger reply."
    return "Compare checks, captures and promotion threats. For each candidate, check the opponent's strongest reply."


def import_protocol(path: str | Path, seed: int = 20261006,
                    assessment_per_band: int = 2, training_per_band: int = 4) -> dict:
    raw = Path(path).read_bytes()
    source = json.loads(raw)
    if source.get("format") not in ("puzzletrack-endgame-bank", "puzzletrack-local-pool") or source.get("version") != 1:
        raise ValueError("Use the public standalone bank or a frozen local pool, version 1.")
    if source.get("source", {}).get("license") != "CC0-1.0":
        raise ValueError("This importer accepts CC0 source puzzle data only.")
    if assessment_per_band < 1 or training_per_band < 1:
        raise ValueError("Choose positive assessment and training counts.")
    candidates, positions, ids = [], set(), set()
    for row in source["puzzles"]:
        board = chess.Board(row["FEN"])
        if not board.is_valid():
            raise ValueError(f"Invalid source position: {row['PuzzleId']}")
        moves = row["Moves"].split()
        if len(moves) < 2:
            raise ValueError("A source row needs the setup move and a solution.")
        for number, uci in enumerate(moves):
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError(f"Illegal source continuation: {row['PuzzleId']} {uci}")
            board.push(move)
            if number == 0:
                fen = board.fen()
                if board.is_game_over():
                    raise ValueError("The setup move leaves no decision to make.")
        key = position_key(fen)
        if key in positions or row["PuzzleId"] in ids:
            continue
        positions.add(key); ids.add(row["PuzzleId"])
        rating = int(row["Rating"])
        band = "easy" if 400 <= rating <= 1399 else "hard" if 1800 <= rating <= 2600 else None
        if band:
            candidates.append(dict(id=row["PuzzleId"], fen=fen, reference_move=moves[1],
                                   reference_line=moves[1:], rating=rating,
                                   rating_deviation=int(row["RatingDeviation"]),
                                   source="lichess-puzzles", source_license="CC0-1.0",
                                   source_url="https://lichess.org/training/" + row["PuzzleId"],
                                   source_row=row, themes=row["Themes"].split(), band=band))
    rng = random.Random(seed)
    items = []
    for band in ("easy", "hard"):
        available = [i for i in candidates if i["band"] == band]
        rng.shuffle(available)
        required = 2 * assessment_per_band + training_per_band
        if len(available) < required:
            raise ValueError(f"Need {required} distinct {band} positions, found {len(available)}.")
        sizes = (("form_a", assessment_per_band), ("form_b", assessment_per_band),
                 ("training", training_per_band))
        cursor = 0
        for group, count in sizes:
            for item in available[cursor:cursor+count]:
                item["set"] = group
                if group == "training":
                    item["hint"] = dict(text=shared_hint(item["themes"]),
                                        reflection_prompt="If you play your candidate, what is the opponent's strongest reply? Does it change your choice?",
                                        authorship="human_template", review_status="draft",
                                        revision="pilot-template-1")
                items.append(item)
            cursor += count
    protocol = dict(id="chesso-puzzletrack-hints-pilot-v1", status="pilot",
                    hint_source="human_template", task="one_move_frozen_position",
                    assessment_seconds=90, training_seconds=120,
                    source_bank=dict(file_sha256=hashlib.sha256(raw).hexdigest(),
                                     format=source["format"], version=source["version"],
                                     provenance=source["source"], selection_seed=seed,
                                     importer="chesso-import-puzzletrack-1"),
                    notes="Software pilot. Source ratings are not calibrated participant difficulty. Templates need review; they are not LLM outputs. Forms are quota-balanced, not psychometrically matched.",
                    items=items)
    return validate_protocol(protocol)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank")
    parser.add_argument("--out", default="study_protocol.json")
    parser.add_argument("--seed", type=int, default=20261006)
    parser.add_argument("--assessment-per-band", type=int, default=2)
    parser.add_argument("--training-per-band", type=int, default=4)
    args = parser.parse_args()
    protocol = import_protocol(args.bank, args.seed, args.assessment_per_band, args.training_per_band)
    write_json(Path(args.out), protocol)
    print(f"Imported {len(protocol['items'])} positions into {args.out}; full reference lines validated.")


if __name__ == "__main__":
    main()
