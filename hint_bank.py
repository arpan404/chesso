"""Prepare reproducible LLM hint requests and attach actual generated outputs.

No credentials or live model calls are needed in the participant application.
Generation outputs remain draft material until reviewed by the researcher.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path

from study import DEFAULT_PROTOCOL, digest, load_protocol, validate_protocol, write_json


def generation_requests(protocol: dict) -> dict:
    requests = []
    for item in protocol["items"]:
        if item["set"] != "training":
            continue
        prompt = (
            "Write a short chess hint for this fixed position. Give one or two sentences of tactical information, "
            "then a separate reflection question about the opponent's strongest reply. The information will be "
            "identical in two study conditions; only one condition requires answering the question. "
            "Do not reveal the exact first move or describe a tactic not supported by the supplied position. "
            "Use plain language. Return JSON with text and reflection_prompt. "
            "The reference line is a source continuation, not an independently verified best-move benchmark.\n"
            f"FEN: {item['fen']}\n"
            f"Side to move: {'white' if item['fen'].split()[1] == 'w' else 'black'}\n"
            f"Source themes: {', '.join(item.get('themes', []))}\n"
            f"Source reference line: {' '.join(item.get('reference_line', [item['reference_move']]))}"
        )
        requests.append(dict(item_id=item["id"], position_hash=digest(item["fen"]),
                             prompt=prompt, prompt_hash=digest(prompt)))
    return dict(format="chesso-hint-requests-v1", protocol_hash=digest(protocol),
                note="Training positions only. Record actual model and generation time; review outputs before collection.",
                requests=requests)


def attach_outputs(protocol: dict, response: dict) -> dict:
    issued = generation_requests(protocol)
    if response.get("format") != "chesso-hint-outputs-v1" or response.get("protocol_hash") != issued["protocol_hash"]:
        raise ValueError("Outputs must match the exact protocol used to prepare requests.")
    outputs = response.get("hints", [])
    if not isinstance(outputs, list):
        raise ValueError("Hints must be a list.")
    lookup = {h["item_id"]: h for h in outputs}
    expected = {r["item_id"]: r for r in issued["requests"]}
    if len(lookup) != len(outputs) or set(lookup) != set(expected):
        raise ValueError("Supply exactly one output for every training item, with no assessment items.")
    updated = copy.deepcopy(protocol)
    for item in updated["items"]:
        if item["set"] != "training":
            continue
        output, request = lookup[item["id"]], expected[item["id"]]
        if output.get("position_hash") != request["position_hash"]:
            raise ValueError("A generated hint refers to a different position.")
        generation = output.get("generation", {})
        if generation.get("prompt") != request["prompt"] or not generation.get("model") or not generation.get("generated_at"):
            raise ValueError("Keep the actual issued prompt, model and generation time for each output.")
        timestamp = datetime.fromisoformat(generation["generated_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Generation timestamps need a timezone.")
        for field in ("text", "reflection_prompt"):
            if not isinstance(output.get(field), str) or not 0 < len(output[field].strip()) <= 240:
                raise ValueError("Use nonempty hint and reflection text, each at most 240 characters.")
        item["hint"] = dict(text=output["text"].strip(), reflection_prompt=output["reflection_prompt"].strip(),
                            authorship="llm", review_status="draft", generation=generation,
                            request_hash=request["prompt_hash"], revision="llm-import-1")
    updated["hint_source"], updated["status"] = "llm", "pilot"
    updated["id"] = protocol["id"] + "-llm-draft"
    return validate_protocol(updated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    prepare.add_argument("--out", required=True)
    attach = commands.add_parser("attach")
    attach.add_argument("responses")
    attach.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    attach.add_argument("--out", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--protocol", required=True)
    freeze.add_argument("--out", required=True)
    args = parser.parse_args()
    protocol = load_protocol(args.protocol)
    if args.command == "prepare":
        result = generation_requests(protocol)
    elif args.command == "attach":
        result = attach_outputs(protocol, json.loads(Path(args.responses).read_text()))
    else:
        result = copy.deepcopy(protocol)
        result["status"] = "frozen"
        result = validate_protocol(result, "main")
    write_json(Path(args.out), result)
    print(f"Saved {args.out}; SHA-256 {digest(result)}")


if __name__ == "__main__":
    main()
