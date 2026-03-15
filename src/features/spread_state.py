from __future__ import annotations

from typing import Any


def compute_spread_state(bars: list[dict[str, Any]], baseline_points: float = 40.0) -> dict[str, Any]:
    """Estimate a spread proxy from candle structure when no tick spread stream is available."""
    if len(bars) < 5:
        return {
            "module": "spread_state",
            "state": "insufficient_data",
            "spread_points": baseline_points,
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
        }

    recent = bars[-5:]
    avg_range = sum(float(b["high"]) - float(b["low"]) for b in recent) / 5.0
    spread_points = max(5.0, min(120.0, round(avg_range * 18.0, 2)))

    if spread_points > baseline_points * 1.4:
        state = "wide"
        delta = -0.06
        reasons = ["spread_proxy_wide"]
    elif spread_points < baseline_points * 0.8:
        state = "tight"
        delta = 0.02
        reasons = ["spread_proxy_tight"]
    else:
        state = "normal"
        delta = 0.0
        reasons = ["spread_proxy_normal"]

    return {
        "module": "spread_state",
        "state": state,
        "spread_points": spread_points,
        "direction_vote": "neutral",
        "confidence_delta": delta,
        "reasons": reasons,
    }
