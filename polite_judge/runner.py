"""Run a judge over fixed answers and save JSONL atomically."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .dataset import known_names, load_cases
from .lexical import lexical_verdict


def run(judge, cases_path, out_path, limit=None):
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    cases = load_cases(cases_path)
    names = known_names(cases)
    selected = cases if limit is None else cases[:limit]
    destination = Path(out_path)
    if Path(cases_path).resolve() == destination.resolve():
        raise ValueError("output must differ from input cases")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=destination.name + ".tmp.", delete=False) as stream:
            temporary = stream.name
            for case in selected:
                row = {"id": case["id"], "condition": case["condition"],
                       "entity_kind": case["entity_kind"], "judge": judge.name,
                       "judge_result": judge.score(case["question"], case["answer"]),
                       "lexical": lexical_verdict(case, names)}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return len(selected)
