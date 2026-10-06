"""Descriptive study audit. No pooled move count is treated as sample size."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from study import trial_rows


def summarize(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["mode"], row["protocol_hash"], row["participant"],
                row["session_id"], row["condition"], row["phase"])].append(row)
    summaries = []
    for (mode, protocol, participant, session, condition, phase), group in sorted(groups.items()):
        submitted = [r for r in group if r["status"] == "submitted"]
        benchmarked = [r for r in submitted if r["benchmark_success"] is not None]
        calibrated = [r for r in benchmarked if r["final_confidence"] is not None]
        summaries.append(dict(
            mode=mode, protocol_hash=protocol, participant=participant,
            session_id=session, condition=condition, phase=phase,
            assigned=len(group), submitted=len(submitted),
            timeout=sum(r["status"] == "timeout" for r in group),
            interrupted=sum(r["status"] == "interrupted" for r in group),
            aborted=sum(r["status"] == "aborted" for r in group),
            not_started=sum(r["status"] == "not_started" for r in group),
            in_progress=sum(r["status"] == "in_progress" for r in group),
            benchmark_scored=len(benchmarked),
            benchmark_success_rate=(sum(r["benchmark_success"] for r in benchmarked)/len(benchmarked)
                                    if benchmarked else None),
            confidence_brier=(sum((r["final_confidence"]/100-int(r["benchmark_success"]))**2
                                  for r in calibrated)/len(calibrated) if calibrated else None),
            reference_agreement=sum(r["reference_agreement"] for r in submitted),
            hinted=sum(r["hint_used"] for r in group),
            reflections=sum(r["reflection_saved"] for r in group),
            focus_losses=sum(r["focus_losses"] for r in group),
            reported_repeat=sum(r["familiarity"] == "yes" for r in group),
            previously_presented=sum(r["prior_exposure"] for r in group)))
    return summaries


def collect(path: str | Path) -> list[dict]:
    path = Path(path)
    directories = [path] if (path / "manifest.json").exists() else sorted(p.parent for p in path.rglob("manifest.json"))
    return [row for directory in directories for row in trial_rows(directory)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="a session folder or collection root")
    parser.add_argument("--out", help="optional per-participant/session/phase summary CSV")
    args = parser.parse_args()
    rows = collect(args.path)
    summaries = summarize(rows)
    print(f"Sessions: {len({r['session_id'] for r in rows})}; participant codes: {len({r['participant'] for r in rows})}")
    print("Descriptive audit. Pilot and main records, protocol versions and repeated sessions remain separate.")
    print("Reference agreement is not move-quality accuracy. Missing answers and timeouts are reported separately.")
    print(json.dumps(summaries, indent=2))
    if args.out and summaries:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
            writer.writeheader(); writer.writerows(summaries)


if __name__ == "__main__":
    main()
