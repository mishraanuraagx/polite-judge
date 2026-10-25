from __future__ import annotations

import unittest
from polite_judge.report import aggregate, markdown_report


def row(condition, verdict, flag, judge='mock'):
    return {'judge': judge, 'condition': condition, 'judge_result': {'verdict': verdict}, 'lexical': {'flag': flag}}


class ReportTests(unittest.TestCase):
    def test_math(self):
        rows = [row('fabricated', 'pass', True), row('fabricated', 'fail', True),
                row('substituted', 'pass', True), row('substituted', 'error', False),
                row('correct', 'pass', False), row('honest', 'pass', False),
                row('fabricated', 'fail', False, 'other')]
        groups = aggregate(rows)
        self.assertEqual(groups[('mock', 'fabricated')],
                         {'n': 2, 'passed': 1, 'flagged': 2, 'caught': 1, 'errors': 0})
        report = markdown_report(rows)
        self.assertIn('mock repair rate: 50.0%', report)
        self.assertIn('other repair rate: 0.0%', report)
        self.assertIn('Caught by lexical, missed by judge: 2. Judge errors: 1.', report)
        self.assertIn('| mock | fabricated | 2 | 50.0% | 100.0% |', report)

    def test_empty_and_no_bad_cases(self):
        self.assertIn('N/A', markdown_report([]))
        self.assertIn('repair rate: N/A', markdown_report([row('correct', 'pass', False)]))
