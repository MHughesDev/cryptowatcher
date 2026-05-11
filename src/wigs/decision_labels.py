"""Decision label helpers.

Canonical machine values are underscore enums. Use display helpers for UI text.
"""

from __future__ import annotations

CANONICAL_DECISIONS = ("AVOID", "WATCH", "STRONG_WATCH", "STRONG_CANDIDATE")

_DISPLAY = {
    "AVOID": "AVOID",
    "WATCH": "WATCH",
    "STRONG_WATCH": "STRONG WATCH",
    "STRONG_CANDIDATE": "STRONG CANDIDATE",
}


def to_display_label(decision: str) -> str:
    return _DISPLAY.get(decision, decision)
