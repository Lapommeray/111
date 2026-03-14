from __future__ import annotations

from typing import Any

from src.utils import safe_mean


def compute_volatility_state(bars: list[dict[str, Any]], lookback: int = 20) -> dict[str, Any]:
    """Classify recent range volatility to guide confidence and risk gating."""
    if len(bars) < lookback + 1:
        return {
            "module": "volatility",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
        }

    ranges = [float(b["high"]) - float(b["low"]) for b in bars[-lookback:]]
    avg_range = safe_mean(ranges)
    last_range = ranges[-1]
    ratio = last_range / avg_range if avg_range > 0 else 0.0

    if ratio > 1.6:
        return {
            "module": "volatility",
            "state": "high_volatility",
            "direction_vote": "neutral",
            "confidence_delta": -0.05,
            "reasons": ["volatility_spike"],
            "metrics": {"last_range": round(last_range, 4), "avg_range": round(avg_range, 4), "ratio": round(ratio, 4)},
        }

    if ratio < 0.7:
        return {
            "module": "volatility",
            "state": "compression",
            "direction_vote": "neutral",
            "confidence_delta": -0.02,
            "reasons": ["low_momentum_environment"],
            "metrics": {"last_range": round(last_range, 4), "avg_range": round(avg_range, 4), "ratio": round(ratio, 4)},
        }

    return {
        "module": "volatility",
        "state": "balanced",
        "direction_vote": "neutral",
        "confidence_delta": 0.01,
        "reasons": ["volatility_supportive"],
        "metrics": {"last_range": round(last_range, 4), "avg_range": round(avg_range, 4), "ratio": round(ratio, 4)},
    }
