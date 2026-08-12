from __future__ import annotations

from typing import Any

# Sessions considered high-quality for trading (highest volume, most predictable).
_ALLOWED_SESSIONS = {"london", "new_york"}


def apply_session_filter(session_state: dict[str, Any]) -> dict[str, Any]:
    """Block entries outside London and New York sessions."""
    state = str(session_state.get("state", "unknown"))
    if state not in _ALLOWED_SESSIONS:
        reason = "off_hours_block" if state == "off_hours" else f"{state}_session_block"
        return {
            "module": "session_filter",
            "blocked": True,
            "reasons": [reason],
            "confidence_delta": -0.08,
            "direction_vote": "wait",
        }

    return {
        "module": "session_filter",
        "blocked": False,
        "reasons": ["session_allowed"],
        "confidence_delta": 0.01,
        "direction_vote": "neutral",
    }
