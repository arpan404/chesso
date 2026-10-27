import { useState } from "react";
import { Eye } from "lucide-react";
import { cn } from "@/lib/utils";

// A puzzle's difficulty can be discouraging mid-solve, so it stays blurred
// until the player asks.
// The real value is not rendered until then; a same-length placeholder is.
export function HiddenScore({
  label,
  value,
  className,
}: {
  label: string;
  value: string | number;
  className?: string;
}) {
  const [shown, setShown] = useState(false);
  const text = String(value);
  return (
    <button
      type="button"
      className={cn("hidden-score", className)}
      data-shown={shown}
      aria-pressed={shown}
      onClick={() => setShown((current) => !current)}
    >
      <span className="sr-only">Show {label}</span>
      {shown ? (
        <span>{text}</span>
      ) : (
        <>
          <span className="hidden-score-mask" aria-hidden="true">
            {text.replace(/\d/g, "8")}
          </span>
          <Eye className="hidden-score-icon" aria-hidden="true" />
        </>
      )}
    </button>
  );
}
