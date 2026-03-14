from __future__ import annotations

from typing import Any


def apply_session_filter(session_state: dict[str, Any]) -> dict[str, Any]:
    """Block entries during explicitly weak session windows."""
    state = str(session_state.get("state", "unknown"))
    if state == "off_hours":
        return {
            "module": "session_filter",
            "blocked": True,
            "reasons": ["off_hours_block"],
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
