import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { Position } from "./types";
import { pieceImage } from "./piece-images";
import { play } from "./sound";

const names: Record<string, string> = {
  k: "king",
  q: "queen",
  r: "rook",
  b: "bishop",
  n: "knight",
  p: "pawn",
};

export function Board({
  position,
  disabled,
  orientation = "white",
  candidate,
  lastMove,
  resetKey,
  onMove,
  onSelect,
}: {
  position: Position;
  disabled: boolean;
  orientation?: "white" | "black";
  candidate?: string;
  lastMove?: string;
  resetKey?: string;
  onMove: (move: string) => void;
  onSelect?: (square: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [promotions, setPromotions] = useState<string[]>([]);
  const [focused, setFocused] = useState(
    () => position.legal_moves[0]?.slice(0, 2) || "a8",
  );
  const [message, setMessage] = useState("");
  const squares = useRef(new Map<string, HTMLButtonElement>());
  const promotionFocus = useRef<HTMLButtonElement | null>(null);
  const helpId = useId();
  useEffect(() => {
    setSelected(null);
    setPromotions([]);
    setMessage("");
  }, [position.fen, resetKey, disabled]);
  const reverse = (orientation === "black") !== flipped;
  const files = reverse ? "hgfedcba" : "abcdefgh";
  const ranks = reverse ? "12345678" : "87654321";
  const destinations = [
    ...new Set(
      position.legal_moves
        .filter((move) => move.startsWith(selected || "!"))
        .map((move) => move.slice(2, 4)),
    ),
  ];

  function choose(square: string) {
    if (disabled) return;
    onSelect?.(square);
    if (selected) {
      const matches = position.legal_moves.filter((move) =>
        move.startsWith(selected + square),
      );
      if (matches.length > 1) {
        promotionFocus.current = squares.current.get(square) || null;
        setPromotions(matches);
        return;
      }
      if (matches.length === 1) {
        onMove(matches[0]);
        setSelected(null);
        setMessage(`Move ${selected} to ${square} selected.`);
        return;
      }
    }
    const piece = position.pieces[square];
    const color = piece && (piece === piece.toUpperCase() ? "white" : "black");
    if (selected === square) {
      setSelected(null);
      setMessage("Selection cleared.");
    } else if (color === position.turn) {
      setSelected(square);
      play("select");
      const legal = [
        ...new Set(
          position.legal_moves
            .filter((move) => move.startsWith(square))
            .map((move) => move.slice(2, 4)),
        ),
      ];
      setMessage(
        `${names[piece.toLowerCase()]} on ${square} selected. ${legal.length ? `Legal destinations: ${legal.join(", ")}.` : "No legal destinations."}`,
      );
    } else {
      setMessage(
        selected
          ? `${square} is not a legal destination. Choose another square or press Escape to clear.`
          : `Choose a ${position.turn} piece.`,
      );
    }
  }

  function navigate(
    event: KeyboardEvent<HTMLButtonElement>,
    row: number,
    col: number,
  ) {
    let nextRow = row,
      nextCol = col;
    switch (event.key) {
      case "ArrowUp":
        nextRow = Math.max(0, row - 1);
        break;
      case "ArrowDown":
        nextRow = Math.min(7, row + 1);
        break;
      case "ArrowLeft":
        nextCol = Math.max(0, col - 1);
        break;
      case "ArrowRight":
        nextCol = Math.min(7, col + 1);
        break;
      case "Home":
        nextCol = 0;
        if (event.ctrlKey) nextRow = 0;
        break;
      case "End":
        nextCol = 7;
        if (event.ctrlKey) nextRow = 7;
        break;
      case "Escape":
        setSelected(null);
        setMessage("Selection cleared.");
        event.preventDefault();
        return;
      default:
        return;
    }
    event.preventDefault();
    const next = files[nextCol] + ranks[nextRow];
    setFocused(next);
    squares.current.get(next)?.focus();
  }

  const turn = `${position.turn === "white" ? "White" : "Black"} to move${position.check ? ", check" : ""}`;
  const choice = candidate
    ? `Your choice: ${candidate.slice(0, 2)} to ${candidate.slice(2, 4)}${candidate[4] ? `, promote to ${names[candidate[4]]}` : ""}.`
    : "";
  return (
    <div className="board-wrap">
      <div className="board-frame">
        <div className="board-ranks" aria-hidden="true">
          {[...ranks].map((rank) => (
            <span key={rank}>{rank}</span>
          ))}
        </div>
        <div
          className="chessboard"
          role="grid"
          aria-label="Chessboard"
          aria-describedby={helpId}
          aria-readonly={disabled}
        >
          {[...ranks].map((rank, row) => (
            <div className="board-row" role="row" key={rank}>
              {[...files].map((file, col) => {
                const square = file + rank;
                const piece = position.pieces[square];
                const highlighted =
                  candidate?.slice(0, 2) === square ||
                  candidate?.slice(2, 4) === square;
                const previous =
                  lastMove?.slice(0, 2) === square ||
                  lastMove?.slice(2, 4) === square;
                return (
                  <div
                    role="gridcell"
                    aria-selected={selected === square}
                    key={square}
                  >
                    <button
                      type="button"
                      aria-disabled={disabled}
                      tabIndex={focused === square ? 0 : -1}
                      ref={(element) => {
                        if (element) squares.current.set(square, element);
                        else squares.current.delete(square);
                      }}
                      onFocus={() => setFocused(square)}
                      onKeyDown={(event) => navigate(event, row, col)}
                      onClick={() => choose(square)}
                      aria-label={`${square}${piece ? ` ${piece === piece.toUpperCase() ? "white" : "black"} ${names[piece.toLowerCase()]}` : " empty"}${destinations.includes(square) ? ", legal destination" : ""}${previous ? ", last move" : ""}${highlighted ? ", chosen move" : ""}`}
                      aria-pressed={selected === square}
                      className={cn(
                        "square",
                        (row + col) % 2 ? "dark-square" : "light-square",
                        selected === square && "selected",
                        highlighted && "candidate-square",
                        previous && "previous-square",
                      )}
                    >
                      {piece ? (
                        <img
                          className="piece"
                          src={pieceImage(piece)}
                          alt=""
                          aria-hidden="true"
                          draggable={false}
                        />
                      ) : null}
                      {destinations.includes(square) ? (
                        <span
                          aria-hidden="true"
                          className={cn(
                            "destination",
                            piece && "capture-destination",
                          )}
                        />
                      ) : null}
                    </button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="board-files" aria-hidden="true">
          {[...files].map((file) => (
            <span key={file}>{file}</span>
          ))}
        </div>
      </div>
      <div className="board-topline board-toolbar">
        <span>{position.result || (disabled ? "" : turn)}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setFlipped((f) => !f)}
          aria-label="Flip board"
        >
          <RotateCw className="size-3.5" aria-hidden="true" />
          Flip
        </Button>
      </div>
      <p id={helpId} className="board-keyboard-help">
        Arrow keys move · Enter selects · Esc clears
      </p>
      <p
        className="board-caption"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {message ||
          choice ||
          (lastMove
            ? `Last move: ${lastMove.slice(0, 2)} to ${lastMove.slice(2, 4)}. ${turn}.`
            : "")}
      </p>
      <Dialog
        open={promotions.length > 0}
        onOpenChange={(open) => {
          if (!open) setPromotions([]);
        }}
      >
        <DialogContent finalFocus={() => promotionFocus.current}>
          <DialogHeader>
            <DialogTitle>Promote your pawn</DialogTitle>
            <DialogDescription>
              Choose the piece your pawn becomes.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap gap-2">
            {promotions.map((move) => (
              <Button
                key={move}
                onClick={() => {
                  onMove(move);
                  setPromotions([]);
                  setSelected(null);
                }}
              >
                {names[move[4]]}
              </Button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
