from __future__ import annotations

from collections import Counter
import copy
import tempfile
from pathlib import Path
import unittest

from polite_judge.dataset import load_cases, validate_cases


class DatasetTests(unittest.TestCase):
    def test_dataset(self):
        cases = load_cases(require_counts=True)
        self.assertEqual(len(cases), 48)
        self.assertEqual(Counter(c['condition'] for c in cases),
                         dict.fromkeys(('honest', 'fabricated', 'substituted', 'correct'), 12))
        self.assertEqual(len({c['id'] for c in cases}), 48)

    def test_invalid_schema(self):
        for key, value in [('entity', ''), ('condition', 'unknown'), ('entity_kind', 'unknown')]:
            cases = copy.deepcopy(load_cases())
            cases[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_cases(cases)
        cases = load_cases()
        with self.assertRaises(ValueError):
            validate_cases(cases + [cases[0]])
        with self.assertRaises(ValueError):
            validate_cases(cases[:8], require_counts=True)

    def test_collision_and_missing_substitute(self):
        cases = load_cases()
        cases[0]['entity'] = 'Stripe'
        with self.assertRaises(ValueError):
            validate_cases(cases)
        cases = load_cases()
        del cases[24]['substitute']
        with self.assertRaises(ValueError):
            validate_cases(cases)

    def test_bad_json_diagnostic(self):
        with tempfile.TemporaryDirectory(dir='.') as directory:
            path = Path(directory) / 'bad.jsonl'
            path.write_text('{}\nnot json\n')
            with self.assertRaisesRegex(ValueError, ':2: invalid JSON'):
                load_cases(path)
