"""Command line entry point."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

from .dataset import DEFAULT_CASES, known_names, load_cases
from .judges import make_judge
from .lexical import lexical_verdict
from .report import load_results, markdown_report
from .runner import run


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(prog="polite-judge")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="score fixed candidate answers")
    run_parser.add_argument("--judge", required=True)
    run_parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    run_parser.add_argument("--out", type=Path)
    run_parser.add_argument("--limit", type=positive_int)
    report_parser = commands.add_parser("report", help="print a markdown report")
    report_parser.add_argument("results", nargs="+")
    check_parser = commands.add_parser("check", help="validate dataset and run lexical checks")
    check_parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            cases = load_cases(args.cases, require_counts=True)
            names = known_names(cases)
            flagged = sum(lexical_verdict(case, names)["flag"] for case in cases)
            print("OK: 48 cases; 12 per condition; schema valid; lexical flagged {}/48.".format(flagged))
        elif args.command == "run":
            judge = make_judge(args.judge)
            if getattr(judge, "key_variable", None) and not os.environ.get(judge.key_variable):
                raise ValueError("Missing " + judge.key_variable)
            out = args.out or Path("results") / (re.sub(r"[^A-Za-z0-9._-]+", "_", judge.name) + ".jsonl")
            count = run(judge, args.cases, out, args.limit)
            print("Wrote {} results to {}".format(count, out))
        else:
            print(markdown_report(load_results(args.results)))
    except (OSError, ValueError) as exc:
        parser.exit(2, "error: {}\n".format(exc))
    return 0
