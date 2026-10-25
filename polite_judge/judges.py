"""Minimal standard-library judge adapters. No requests occur until score()."""
from __future__ import annotations

import json
import os
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


def make_judge(spec):
    if spec == "mock":
        return MockJudge()
    provider, separator, model = spec.partition(":")
    classes = {"openai": OpenAIJudge, "anthropic": AnthropicJudge, "gemini": GeminiJudge}
    if not separator or provider not in classes or not model.strip():
        raise ValueError("judge must be mock, openai:<model>, anthropic:<model>, or gemini:<model>")
    return classes[provider](model)
