from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from polite_judge.cli import main
from polite_judge.dataset import DEFAULT_CASES
from polite_judge.judges import MockJudge, OpenAIJudge, AnthropicJudge, GeminiJudge, make_judge, parse_reply
from polite_judge.prompts import judge_prompt
from polite_judge.report import load_results
from polite_judge.runner import run


class RunnerTests(unittest.TestCase):
    def test_mock_cli_end_to_end(self):
        with tempfile.TemporaryDirectory(dir='.') as directory:
            path = Path(directory) / 'mock.jsonl'
            with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['run', '--judge', 'mock', '--out', str(path), '--limit', '8']), 0)
                rows = load_results([path])
            self.assertEqual(len(rows), 8)
            self.assertEqual(len({r['id'] for r in rows}), 8)
            self.assertTrue(all(r['judge_result']['verdict'] == 'pass' for r in rows))
            self.assertEqual(sum(r['lexical']['flag'] for r in rows), 4)

    def test_mock_deterministic(self):
        judge = MockJudge()
        self.assertEqual(judge.score('q', 'short')['score'], 3)
        self.assertEqual(judge.score('q', 'word ' * 16)['verdict'], 'pass')
        self.assertEqual(judge.score('q', 'word ' * 40), judge.score('q', 'word ' * 40))

    def test_parsing_and_prompt(self):
        self.assertEqual(parse_reply('```json\n{"score":4,"reason":"Useful"}\n```')['verdict'], 'pass')
        for text in ['none', '{"score":true,"reason":"x"}', '{"score":6,"reason":"x"}',
                     '{"score":4.0,"reason":"x"}', '{"score":4}', '{"score":4,"reason":""}']:
            self.assertEqual(parse_reply(text)['verdict'], 'error')
        self.assertIn('{"score": n, "reason": "..."}', judge_prompt('question', 'answer'))
        with self.assertRaises(ValueError):
            make_judge('invalid:model')

    def test_provider_envelopes_and_no_secret_in_error(self):
        for cls, key, payload in [
            (OpenAIJudge, 'OPENAI_API_KEY', {'choices': [{'message': {'content': '{"score":5,"reason":"ok"}'}}]}),
            (AnthropicJudge, 'ANTHROPIC_API_KEY', {'content': [{'type': 'text', 'text': '{"score":5,"reason":"ok"}'}]}),
            (GeminiJudge, 'GEMINI_API_KEY', {'candidates': [{'content': {'parts': [{'text': '{"score":5,"reason":"ok"}'}]}}]})]:
            judge = cls('test-model')
            self.assertEqual(parse_reply(judge.extract(payload))['score'], 5)
            with patch.dict('os.environ', {key: 'secret-key'}):
                response = io.StringIO(__import__('json').dumps(payload))
                with patch('urllib.request.urlopen', return_value=response):
                    self.assertEqual(judge.score('q', 'a')['score'], 5)
                with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('secret-key')):
                    self.assertNotIn('secret-key', str(judge.score('q', 'a')))

    def test_malformed_envelope(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'secret'}):
            with patch('urllib.request.urlopen', return_value=io.StringIO('{"content":[null]}')):
                self.assertEqual(AnthropicJudge('model').score('q', 'a')['verdict'], 'error')

    def test_retry_once(self):
        error = urllib.error.HTTPError('url', 429, 'rate limited', {}, io.BytesIO(b''))
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'secret'}):
            with patch('urllib.request.urlopen', side_effect=[error, io.StringIO('{"choices":[{"message":{"content":"{\\"score\\":4,\\"reason\\":\\"ok\\"}"}}]}')]) as request:
                with patch('time.sleep') as sleep:
                    self.assertEqual(OpenAIJudge('model').score('q', 'a')['verdict'], 'pass')
                self.assertEqual(request.call_count, 2)
                sleep.assert_called_once_with(2)

    def test_atomic_failure(self):
        with tempfile.TemporaryDirectory(dir='.') as directory:
            path = Path(directory) / 'saved.jsonl'
            path.write_text('original')
            with patch.object(MockJudge, 'score', side_effect=RuntimeError('failed')):
                with self.assertRaises(RuntimeError):
                    run(MockJudge(), DEFAULT_CASES, path, 8)
            self.assertEqual(path.read_text(), 'original')
            self.assertEqual(list(Path(directory).iterdir()), [path])
