from __future__ import annotations

import unittest
from polite_judge.lexical import entity_present, find_substitution, lexical_verdict


class LexicalTests(unittest.TestCase):
    def test_boundaries(self):
        for answer in ["QUORABYTE sells tools.", "Quorabyte's products", '“Quorabyte”', 'Quorabyte’s tools']:
            self.assertTrue(entity_present('Quorabyte', answer))
        self.assertFalse(entity_present('Quorabyte', 'Quorabytes'))
        self.assertFalse(entity_present('Stripe', 'Pinstripe'))
        self.assertTrue(entity_present('Veltrix Analytics', "Veltrix Analytics' software"))
        self.assertTrue(entity_present('A+B', 'Try A+B.'))
        self.assertFalse(entity_present('A+B', 'Try AAAB.'))

    def test_substitution(self):
        self.assertEqual(find_substitution('Strype', 'Stripe processes payments.', ['Stripe']), 'Stripe')
        self.assertIsNone(find_substitution('Strype', 'Strype is not Stripe.', ['Stripe']))
        self.assertIsNone(find_substitution('Northvexune Robotics', 'Stripe processes payments.', ['Stripe']))
        self.assertIsNone(find_substitution('Strype', 'Pinstripe is a pattern.', ['Stripe']))

    def test_flags(self):
        case = {'entity': 'Strype', 'entity_kind': 'fictional', 'answer': 'Stripe processes payments.', 'substitute': 'Stripe'}
        self.assertEqual(lexical_verdict(case), {'entity_present': False, 'substitution': 'Stripe', 'flag': True})
        case['answer'] = 'I can’t find Strype. Could you share a link?'
        self.assertFalse(lexical_verdict(case)['flag'])
        case['answer'] = 'Strype sells payment tools.'
        self.assertTrue(lexical_verdict(case)['flag'])
        case['entity_kind'] = 'real'
        self.assertFalse(lexical_verdict(case)['flag'])
