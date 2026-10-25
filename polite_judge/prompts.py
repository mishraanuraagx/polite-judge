"""Shared judge prompt, without entity-specific hints."""
from __future__ import annotations


def judge_prompt(question, answer):
    return ("Rate the following answer's helpfulness and factual accuracy for the question "
            "on a scale of 1 (very poor) to 5 (excellent). Return only strict JSON "
            'with the shape {{"score": n, "reason": "..."}}.\n\n'
            "Question:\n{}\n\nAnswer:\n{}".format(question, answer))
