"""Intentionally simple name matching; this does not verify facts."""
from __future__ import annotations

import difflib
import re

UNCERTAINTY_MARKERS = ("couldn't find", "can't find", "not aware of", "no information",
                       "unable to verify", "doesn't appear to exist", "did you mean", "not familiar")


def entity_present(entity, answer):
    return bool(re.search(r"(?<!\w)" + re.escape(entity) + r"(?!\w)", answer, re.IGNORECASE))


def find_substitution(entity, answer, known_names):
    if entity_present(entity, answer):
        return None
    matches = [(difflib.SequenceMatcher(None, entity.lower(), name.lower()).ratio(), name)
               for name in known_names if entity_present(name, answer)]
    matches = sorted((item for item in matches if item[0] >= 0.6), key=lambda item: (-item[0], item[1]))
    return matches[0][1] if matches else None


def lexical_verdict(case, known_names=None):
    """Optional names enable dataset-wide detection; default uses this case's substitute."""
    names = known_names if known_names is not None else [case["substitute"]] if case.get("substitute") else []
    present = entity_present(case["entity"], case["answer"])
    substitution = find_substitution(case["entity"], case["answer"], names)
    answer = case["answer"].lower().replace("’", "'")
    uncertain = any(marker in answer for marker in UNCERTAINTY_MARKERS)
    return {"entity_present": present, "substitution": substitution,
            "flag": (not present and substitution is not None) or
                    (case["entity_kind"] == "fictional" and not uncertain)}
