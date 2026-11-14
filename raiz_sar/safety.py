"""Checks applied to model-authored text before it reaches the UI, AR scene or report."""

from __future__ import annotations

import re

# Claims the product must never make without a validated model and evidence.
BANNED_PATTERNS = [
    (re.compile(r"\bguarantee[sd]?\b", re.I), "guarantee claims"),
    (re.compile(r"\b(will|shall)\s+(fully\s+)?prevent\b", re.I), "certain prevention claims"),
    (re.compile(r"\bprevents?\s+(all|every|any)\b", re.I), "universal prevention claims"),
    (re.compile(r"\bsurvival\s+(probability|rate)\s+(of|is|=)\s*\d", re.I), "numeric survival claims"),
    (re.compile(r"\b\d{1,3}\s?%\s+survival\b", re.I), "numeric survival claims"),
    (re.compile(r"\bprotected\s+homes?\b", re.I), "protected-homes counts"),
    (re.compile(r"\b(officially\s+)?(approved|certified|endorsed)\s+by\b", re.I), "approval or endorsement claims"),
    (re.compile(r"\broots?\s+(are\s+)?(confirmed|proven)\b", re.I), "confirmed root claims"),
    (re.compile(r"\bx-?ray\b", re.I), "literal subsurface imaging metaphors"),
    (re.compile(r"\bunderground\s+(reservoir|water\s+pocket)s?\b", re.I), "underground water claims"),
]
_MARKUP = re.compile(r"[<>]|javascript:|data:text/html", re.I)


def text_problems(text: str) -> list[str]:
    problems = []
    if not isinstance(text, str):
        return ["not text"]
    if any((not ch.isprintable()) and ch not in "\n" for ch in text):
        problems.append("control characters")
    if _MARKUP.search(text):
        problems.append("markup or script content")
    for pat, label in BANNED_PATTERNS:
        if pat.search(text):
            problems.append(f"unsupported claim ({label})")
    return problems
