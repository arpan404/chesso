import { Chess } from "chess.js";
import type { Activity, Position } from "./types";

function position(game: Chess): Position {
  const pieces: Record<string, string> = {};
  for (const row of game.board())
    for (const cell of row)
      if (cell)
        pieces[cell.square] =
          cell.color === "w" ? cell.type.toUpperCase() : cell.type;
  return {
    fen: game.fen(),
    pieces,
    legal_moves: game
      .moves({ verbose: true })
      .map((move) => move.from + move.to + (move.promotion || "")),
    turn: game.turn() === "w" ? "white" : "black",
    check: game.inCheck(),
    result: null,
  };
}

/**
 * Plays a move against the solution that ships with the puzzle, mirroring
 * the server's rules so feedback is instant. Returns the position after the
 * player's move and, when the line continues, after the scripted reply.
 * Returns null when the move cannot be checked locally; the server decides.
 */
export function playLocally(
  puzzle: Activity,
  move: string,
): { played: Activity; replied?: Activity } | null {
  const solution = puzzle.solution;
  const moves = puzzle.moves || [];
  const expected = solution?.[moves.length];
  if (!solution || !expected || puzzle.completed) return null;
  const game = new Chess(puzzle.fen);
  const next = { ...puzzle, version: puzzle.version + 1 };
  if (move !== expected)
    // The server ends the puzzle without playing a wrong move.
    return {
      played: { ...next, completed: true, solved: false, status: "incorrect" },
    };
  try {
    game.move({ from: move.slice(0, 2), to: move.slice(2, 4), promotion: move[4] });
  } catch {
    return null;
  }
  const finished = moves.length + 1 === solution.length;
  const played: Activity = {
    ...next,
    ...position(game),
    moves: [...moves, move],
    ...(finished ? { completed: true, solved: true, status: "solved" } : {}),
  };
  if (finished) return { played };
  const reply = solution[moves.length + 1];
  try {
    game.move({
      from: reply.slice(0, 2),
      to: reply.slice(2, 4),
      promotion: reply[4],
    });
  } catch {
    return { played };
  }
  const done = moves.length + 2 === solution.length;
  return {
    played: { ...played, legal_moves: [] },
    replied: {
      ...played,
      ...position(game),
      moves: [...moves, move, reply],
      ...(done ? { completed: true, solved: true, status: "solved" } : {}),
    },
  };
}
