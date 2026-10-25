"""Minimal standard-library judge adapters. No requests occur until score()."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from typing import Protocol

from .prompts import judge_prompt


class Judge(Protocol):
    name: str

    def score(self, question: str, answer: str) -> dict:
        ...


def error_result(reason):
    return {"score": None, "verdict": "error", "reason": reason}


def parse_reply(reply):
    try:
        start = reply.index("{")
        obj, _ = json.JSONDecoder().raw_decode(reply[start:])
        score = obj["score"]
        if type(score) is not int or not 1 <= score <= 5 or (not isinstance(obj["reason"], str) or not obj["reason"].strip()):
            raise ValueError("invalid score or reason")
        return {"score": score, "verdict": "pass" if score >= 4 else "fail", "reason": obj["reason"]}
    except (ValueError, TypeError, KeyError, AttributeError):
        return error_result("Invalid judge JSON response")


class MockJudge:
    name = "mock"

    def score(self, question, answer):
        words = len(answer.split())
        score = 5 if words > 35 else 4 if words > 15 else 3
        return {"score": score, "verdict": "pass" if score >= 4 else "fail",
                "reason": "Deterministic mock rating based only on answer length."}


class RESTJudge:
    provider = ""
    key_variable = ""

    def __init__(self, model):
        if not model.strip():
            raise ValueError("model must not be empty")
        self.model = model
        self.name = self.provider + ":" + model

    def score(self, question, answer):
        key = os.environ.get(self.key_variable)
        if not key:
            return error_result("Missing " + self.key_variable)
        url, headers, body = self.request_data(key, judge_prompt(question, answer))
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers=dict(headers, **{"Content-Type": "application/json"}))
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                return parse_reply(self.extract(payload))
            except urllib.error.HTTPError as exc:
                if attempt == 0 and (exc.code == 429 or 500 <= exc.code <= 599):
                    exc.close()
                    time.sleep(2)
                    continue
                code = exc.code
                exc.close()
                return error_result("HTTP {} from {}".format(code, self.provider))
            except (urllib.error.URLError, TimeoutError, OSError):
                return error_result("Transport error from " + self.provider)
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                return error_result("Invalid response envelope from " + self.provider)


class OpenAIJudge(RESTJudge):
    provider = "openai"
    key_variable = "OPENAI_API_KEY"

    def request_data(self, key, prompt):
        return ("https://api.openai.com/v1/chat/completions", {"Authorization": "Bearer " + key},
                {"model": self.model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})

    def extract(self, payload):
        return payload["choices"][0]["message"]["content"]


class AnthropicJudge(RESTJudge):
    provider = "anthropic"
    key_variable = "ANTHROPIC_API_KEY"

    def request_data(self, key, prompt):
        return ("https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"},
                {"model": self.model, "temperature": 0, "max_tokens": 512,
                 "messages": [{"role": "user", "content": prompt}]})

    def extract(self, payload):
        return "".join(block["text"] for block in payload["content"] if block.get("type") == "text")


class GeminiJudge(RESTJudge):
    provider = "gemini"
    key_variable = "GEMINI_API_KEY"

    def request_data(self, key, prompt):
        from urllib.parse import quote
        return ("https://generativelanguage.googleapis.com/v1beta/models/" + quote(self.model, safe="") + ":generateContent",
                {"x-goog-api-key": key}, {"generationConfig": {"temperature": 0},
                 "contents": [{"parts": [{"text": prompt}]}]})

    def extract(self, payload):
        return "".join(part.get("text", "") for part in payload["candidates"][0]["content"]["parts"])


class CLIJudge:
    """Scores through a locally signed-in agent CLI instead of an API key.

    These harnesses add their own system prompt and sampling settings, so results
    are labelled by CLI and are not directly comparable with the REST judges.
    """
    cli = ""
    timeout = 180

    def __init__(self, model):
        if not model.strip():
            raise ValueError("model must not be empty")
        self.model = model
        self.name = self.cli + ":" + model

    def score(self, question, answer):
        prompt = judge_prompt(question, answer)
        with tempfile.TemporaryDirectory(prefix="polite-judge-") as workdir:
            for attempt in range(2):
                try:
                    done = subprocess.run(self.argv(prompt, workdir), cwd=workdir, capture_output=True,
                                          text=True, timeout=self.timeout, stdin=subprocess.DEVNULL)
                except (OSError, subprocess.TimeoutExpired):
                    reply = None
                else:
                    reply = self.reply(done, workdir) if done.returncode == 0 else None
                if reply:
                    return parse_reply(reply)
            return error_result("No usable reply from " + self.cli)

    def reply(self, done, workdir):
        return done.stdout


class ClaudeCLIJudge(CLIJudge):
    cli = "claude-cli"

    def argv(self, prompt, workdir):
        return ["claude", "-p", prompt, "--model", self.model,
                "--system-prompt", "Follow the user's instructions exactly.", "--output-format", "text",
                "--tools", "", "--strict-mcp-config", "--no-session-persistence"]


class CodexCLIJudge(CLIJudge):
    cli = "codex-cli"

    def argv(self, prompt, workdir):
        return ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only", "-C", workdir,
                "-m", self.model, "-c", "model_reasoning_effort=low",
                "-o", os.path.join(workdir, "reply.txt"), prompt]

    def reply(self, done, workdir):
        try:
            with open(os.path.join(workdir, "reply.txt"), encoding="utf-8") as stream:
                return stream.read()
        except OSError:
            return None


class AntigravityCLIJudge(CLIJudge):
    cli = "agy-cli"

    def argv(self, prompt, workdir):
        return ["agy", "-p", prompt, "--model", self.model, "--effort", "low", "--mode", "plan",
                "--sandbox", "--disable-slash-commands"]


def make_judge(spec):
    if spec == "mock":
        return MockJudge()
    provider, separator, model = spec.partition(":")
    classes = {"openai": OpenAIJudge, "anthropic": AnthropicJudge, "gemini": GeminiJudge,
               "claude-cli": ClaudeCLIJudge, "codex-cli": CodexCLIJudge, "agy-cli": AntigravityCLIJudge}
    if not separator or provider not in classes or not model.strip():
        raise ValueError("judge must be mock, openai|anthropic|gemini:<model>, or claude-cli|codex-cli|agy-cli:<model>")
    return classes[provider](model)
