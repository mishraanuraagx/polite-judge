"""Aggregate stored judge results without making model calls."""
from __future__ import annotations

from collections import defaultdict
import json

from .dataset import CONDITIONS


def load_results(paths):
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or not isinstance(row.get("judge"), str) or not row["judge"]:
                        raise ValueError("missing judge")
                    if row.get("condition") not in CONDITIONS:
                        raise ValueError("invalid condition")
                    result, lexical = row["judge_result"], row["lexical"]
                    if result["verdict"] not in ("pass", "fail", "error") or type(lexical["flag"]) is not bool:
                        raise ValueError("invalid verdict or flag")
                except (ValueError, KeyError, TypeError) as exc:
                    raise ValueError("{}:{}: invalid result row".format(path, number)) from exc
                rows.append(row)
    return rows


def aggregate(rows):
    groups = defaultdict(lambda: {"n": 0, "passed": 0, "flagged": 0, "caught": 0, "errors": 0})
    for row in rows:
        group = groups[(row["judge"], row["condition"])]
        passed = row["judge_result"]["verdict"] == "pass"
        flagged = row["lexical"]["flag"]
        group["n"] += 1
        group["passed"] += int(passed)
        group["flagged"] += int(flagged)
        group["caught"] += int(passed and flagged)
        group["errors"] += int(row["judge_result"]["verdict"] == "error")
    return dict(groups)


def percentage(numerator, denominator):
    return "{:.1%}".format(numerator / denominator) if denominator else "N/A"


def markdown_report(rows):
    groups = aggregate(rows)
    lines = ["# Judge report", ""]
    for judge in sorted({key[0] for key in groups}):
        bad = [value for (name, condition), value in groups.items()
               if name == judge and condition in ("fabricated", "substituted")]
        total = [value for (name, _), value in groups.items() if name == judge]
        safe_name = judge.replace("|", "\\|").replace("\n", " ")
        lines.append("**{} repair rate: {}** ({}/{} fabricated + substituted passed).".format(
            safe_name, percentage(sum(v["passed"] for v in bad), sum(v["n"] for v in bad)),
            sum(v["passed"] for v in bad), sum(v["n"] for v in bad)))
        lines.append("Caught by lexical, missed by judge: {}. Judge errors: {}.".format(
            sum(v["caught"] for v in total), sum(v["errors"] for v in total)))
        lines.append("")
    if not groups:
        lines.extend(["Repair rate: N/A (no results).", ""])
    lines.extend(["| Judge | Condition | n | judge pass rate | lexical flag rate |",
                  "| --- | --- | ---: | ---: | ---: |"])
    for (judge, condition), group in sorted(groups.items()):
        lines.append("| {} | {} | {} | {} | {} |".format(
            judge.replace("|", "\\|").replace("\n", " "), condition, group["n"],
            percentage(group["passed"], group["n"]), percentage(group["flagged"], group["n"])))
    lines.extend(["", "Rates include error rows in their denominators. Repair rate is the share of fabricated + substituted cases passed by the judge."])
    return "\n".join(lines)
