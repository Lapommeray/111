from __future__ import annotations

from typing import Any


def apply_spread_filter(spread_state: dict[str, Any], max_spread_points: float = 60.0) -> dict[str, Any]:
    """Block trading when spread proxy exceeds configured threshold."""
    spread_points = float(spread_state.get("spread_points", max_spread_points))
    blocked = spread_points > max_spread_points

    return {
        "module": "spread_filter",
        "blocked": blocked,
        "reasons": ["spread_too_wide" if blocked else "spread_ok"],
        "confidence_delta": -0.07 if blocked else 0.0,
        "direction_vote": "wait" if blocked else "neutral",
        "metrics": {"spread_points": spread_points, "max_spread_points": max_spread_points},
    }
