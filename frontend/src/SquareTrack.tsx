import { cn } from "@/lib/utils";
import type { LearningSummary } from "./types";

export type SquareState = "solved" | "missed" | "current" | "upcoming";

// A rank of board squares, one per puzzle. Upcoming squares keep the
// maple/walnut alternation of the board; played squares take their result.
export function SquareTrack({
  states,
  className,
}: {
  states: SquareState[];
  className?: string;
}) {
  return (
    <span className={cn("square-track", className)} aria-hidden="true">
      {states.map((state, index) => (
        <span
          key={index}
          className="track-square"
          data-state={state}
          data-shade={index % 2 ? "dark" : "light"}
        />
      ))}
    </span>
  );
}

export function sessionStates(
  session: Pick<LearningSummary, "total" | "outcomes" | "completed">,
  current?: number,
): SquareState[] {
  return Array.from({ length: session.total }, (_, index) => {
    const outcome = session.outcomes[index];
    if (outcome) return outcome.solved ? "solved" : "missed";
    return index === current && !session.completed ? "current" : "upcoming";
  });
}
