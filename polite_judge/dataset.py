"""Load and validate the experiment's JSONL cases."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

CONDITIONS = ("honest", "fabricated", "substituted", "correct")
DEFAULT_CASES = Path(__file__).resolve().parent.parent / "data" / "cases.jsonl"


def known_names(cases):
    return sorted({c["entity"] for c in cases if c["entity_kind"] == "real"} |
                  {c["substitute"] for c in cases if c.get("substitute")})


def validate_cases(cases, require_counts=False):
    seen = set()
    for index, case in enumerate(cases, 1):
        prefix = "case {}".format(index)
        if not isinstance(case, dict):
            raise ValueError(prefix + " must be an object")
        for key in ("id", "entity", "entity_kind", "question", "condition", "answer"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError(prefix + ": missing or invalid " + key)
        if case["id"] in seen:
            raise ValueError(prefix + ": duplicate id " + case["id"])
        seen.add(case["id"])
        if case["entity_kind"] not in ("real", "fictional"):
            raise ValueError(prefix + ": invalid entity_kind")
        condition = case["condition"]
        if condition not in CONDITIONS:
            raise ValueError(prefix + ": invalid condition")
        if condition == "correct" and case["entity_kind"] != "real":
            raise ValueError(prefix + ": correct requires real entity")
        if condition in ("honest", "fabricated") and case["entity_kind"] != "fictional":
            raise ValueError(prefix + ": honest/fabricated requires fictional entity")
        if "substitute" in case and (not isinstance(case["substitute"], str) or not case["substitute"].strip()):
            raise ValueError(prefix + ": invalid substitute")
        if condition == "substituted" and not case.get("substitute"):
            raise ValueError(prefix + ": substituted requires substitute")
    real = {name.casefold() for name in known_names(cases)}
    for case in cases:
        if case["entity_kind"] == "fictional" and case["entity"].casefold() in real:
            raise ValueError("fictional entity appears in known real names: " + case["entity"])
    if require_counts and Counter(c["condition"] for c in cases) != Counter({c: 12 for c in CONDITIONS}):
        raise ValueError("dataset must contain 48 cases, 12 per condition")
    return cases


def load_cases(path=DEFAULT_CASES, require_counts=False):
    cases = []
    with open(path, encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError("{}:{}: invalid JSON: {}".format(path, number, exc.msg)) from exc
    return validate_cases(cases, require_counts=require_counts)
