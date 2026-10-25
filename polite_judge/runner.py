"""Run a judge over fixed answers and save JSONL atomically."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .dataset import known_names, load_cases
from .lexical import lexical_verdict


def run(judge, cases_path, out_path, limit=None, workers=1):
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
            with ThreadPoolExecutor(max_workers=workers) as pool:
                scores = pool.map(lambda case: judge.score(case["question"], case["answer"]), selected)
                for case, result in zip(selected, scores):
                    row = {"id": case["id"], "condition": case["condition"],
                           "entity_kind": case["entity_kind"], "judge": judge.name,
                           "judge_result": result, "lexical": lexical_verdict(case, names)}
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return len(selected)
