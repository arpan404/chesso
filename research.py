"""Exploratory summary of legacy gameplay observations.

For the frozen-position hint experiment use study.py and study_analysis.py.
Adjacent move quality in different positions does not identify satisfaction of
search. Tier filtering and exclusions do not establish causal confound control.

Reads data/attempts.jsonl (schema v1, see DATASET.md) and prints:

1. Corpus overview (subjects, attempts, solves by tier).
2. Descriptive comparison of recorded follow-up quality after different grades.
3. Time pressure: solve rate by clock-remaining quartile.
4. Calibration check: are first-5 (onboarding) attempts different?

Exclusions remove flagged calibration, repeats and hints from both members of
already formed adjacent pairs. They do not remove all confounds or make the
pooled summary a within-participant causal estimate.

Usage:
    uv run python research.py [--file data/attempts.jsonl] [--export-csv out.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict

BAD = 130  # cp_loss above this = "worse" follow-up (Mistake/Blunder)


def load_rows(path: str) -> list[dict]:
    rows = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
    except FileNotFoundError:
        pass
    return rows


def attempts(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("kind") in ("attempt", "game_move") and r.get("cp_loss") is not None]


def clean_for_sos(rows: list[dict]) -> list[dict]:
    """Main-test sample: no calibration, no repeats, no hints, graded moves."""
    return [r for r in attempts(rows)
            if not r.get("calibration") and not r.get("seen_before")
            and not r.get("hint_used") and r.get("grade")]


def sequences(rows: list[dict]) -> list[tuple[dict, dict]]:
    """Adjacent recorded moves, checking known line order and repeat resets."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r.get("subject"), r.get("session"),
                r.get("trial_id") or r.get("attempt_id")
                or r.get("puzzle_id") or r.get("game_id"))].append(r)
    pairs = []
    for g in groups.values():
        g.sort(key=lambda r: (r.get("t", 0), r.get("move_no_in_line", 0)))
        for a, b in zip(g, g[1:]):
            if "move_no_in_line" in a and "move_no_in_line" in b:
                if b["move_no_in_line"] != a["move_no_in_line"] + 1:
                    continue
            if a.get("ms_total") is not None and b.get("ms_total") is not None:
                if b["ms_total"] < a["ms_total"]:
                    continue
            pairs.append((a, b))
    return pairs


def rate(pairs: list[tuple[dict, dict]], prev_label: str) -> tuple[float, int]:
    sel = [b for a, b in pairs if a.get("grade") == prev_label]
    if not sel:
        return 0.0, 0
    return sum(1 for b in sel if (b.get("cp_loss") or 0) > BAD) / len(sel), len(sel)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/attempts.jsonl")
    ap.add_argument("--export-csv", default=None)
    args = ap.parse_args()

    rows = load_rows(args.file)
    atts = attempts(rows)
    print(f"rows: {len(rows)}  graded attempts: {len(atts)}  "
          f"subjects: {len({r.get('subject') for r in atts})}")
    if not atts:
        print("no data yet — play rated games / puzzles to log attempts.")
        return

    # 1. overview by tier
    by_tier: dict[str, list[dict]] = defaultdict(list)
    for r in atts:
        by_tier[r.get("tier") or "game"].append(r)
    terms_by_tier: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("terminal"):
            terms_by_tier[r.get("tier") or "game"].append(r)
    print("\n-- attempts by tier --")
    for tier in sorted(set(by_tier) | set(terms_by_tier)):
        rs = by_tier.get(tier, [])
        terms = terms_by_tier.get(tier, [])
        solved = sum(1 for r in terms if r.get("solved"))
        rate_s = (solved / len(terms) * 100) if terms else 0.0
        times = [r["ms_delib"] for r in rs if r.get("ms_delib") is not None]
        avg_t = (sum(times) / len(times) / 1000) if times else 0.0
        print(f"  {tier:8s} moves={len(rs):5d} terminal={len(terms):4d} "
              f"solve%={rate_s:5.1f} avg_think={avg_t:4.1f}s")

    # 2. main SoS test (clean sample only)
    clean = clean_for_sos(atts)
    eligible = {id(r) for r in clean}
    pairs = [(a, b) for a, b in sequences(atts) if id(a) in eligible and id(b) in eligible]
    print(f"\n-- EXPLORATORY FOLLOW-UP (n={len(pairs)} adjacent recorded pairs) --")
    print("P(follow-up is Mistake/Blunder | previous move was …)")
    for label in ("Best", "Excellent", "Good", "Inaccuracy"):
        p, n = rate(pairs, label)
        print(f"  after {label:10s}: {p * 100:5.1f}%  (n={n})")
    base = [b for a, b in pairs if a.get("grade") not in ("Best",)]
    pb = (sum(1 for b in base if (b.get("cp_loss") or 0) > BAD) / len(base)) if base else 0
    print(f"  after non-Best : {pb * 100:5.1f}%  (n={len(base)})")
    # stratified: within each tier
    print("  stratified within-tier (after Best vs after non-Best):")
    for tier in sorted({b.get("tier") or "game" for _, b in pairs}):
        sub = [(a, b) for a, b in pairs if (b.get("tier") or "game") == tier]
        p1, n1 = rate(sub, "Best")
        rest = [b for a, b in sub if a.get("grade") != "Best"]
        p0 = (sum(1 for b in rest if (b.get("cp_loss") or 0) > BAD) / len(rest)) if rest else 0
        print(f"    {tier:8s} Best→bad {p1 * 100:5.1f}% (n={n1:3d})  "
              f"nonBest→bad {p0 * 100:5.1f}% (n={len(rest):3d})")

    # 3. time pressure
    timed = [r for r in clean if r.get("clock_left_ms") is not None
             and r.get("clock_total_ms")]
    if timed:
        frac = sorted(r["clock_left_ms"] / max(1, r["clock_total_ms"]) for r in timed)
        qs = [frac[len(frac) // 4], frac[len(frac) // 2], frac[3 * len(frac) // 4]]
        print("\n-- clock remaining vs follow-up quality --")
        bands = [("≤25%", lambda f: f <= qs[0]), ("25–50%", lambda f: qs[0] < f <= qs[1]),
                 ("50–75%", lambda f: qs[1] < f <= qs[2]), (">75%", lambda f: f > qs[2])]
        for name, pred in bands:
            sel = [r for r in timed
                   if pred(r["clock_left_ms"] / max(1, r["clock_total_ms"]))]
            if sel:
                bad = sum(1 for r in sel if (r.get("cp_loss") or 0) > BAD) / len(sel)
                print(f"  clock {name:7s}: bad {bad * 100:5.1f}% (n={len(sel)})")

    # 4. calibration / exclusions audit
    cal = [r for r in atts if r.get("calibration")]
    rep = [r for r in atts if r.get("seen_before")]
    hin = [r for r in atts if r.get("hint_used")]
    print(f"\n-- excluded from main test: calibration={len(cal)} "
          f"repeats={len(rep)} hinted={len(hin)} --")
    if cal:
        bad = sum(1 for r in cal if (r.get("cp_loss") or 0) > BAD) / len(cal)
        print(f"   calibration bad-rate: {bad * 100:.1f}% "
              f"(onboarding noise, kept out of the test)")

    print("\nLimits: pooled observational gameplay, no random assignment; changes "
          "in position and missing records remain. This is not evidence of search stopping. "
          "Use study_analysis.py for the new instrument. See DATASET.md.")

    if args.export_csv:
        with open(args.export_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
            w.writeheader()
            w.writerows(rows)
        print(f"exported {len(rows)} rows → {args.export_csv}")


if __name__ == "__main__":
    main()
