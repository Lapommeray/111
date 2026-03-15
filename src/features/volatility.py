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


def detect_compression_expansion_state(bars: list[dict[str, Any]], lookback: int = 20) -> dict[str, Any]:
    """Detect contraction phases and estimate expansion breakout probability."""
    if len(bars) < lookback + 2:
        return {
            "module": "compression_expansion",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence": 0.0,
            "confidence_level": "low",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
            "metrics": {},
        }

    ranges = [float(b["high"]) - float(b["low"]) for b in bars[-(lookback + 1) :]]
    compression_window = ranges[:-1]
    current_range = ranges[-1]
    avg_range = safe_mean(compression_window)
    min_range = min(compression_window) if compression_window else 0.0
    compression_ratio = (min_range / avg_range) if avg_range > 0 else 0.0
    expansion_ratio = (current_range / avg_range) if avg_range > 0 else 0.0
    volatility_contracted = compression_ratio < 0.7
    breakout_probability = round(
        max(0.0, min(1.0, (0.55 if volatility_contracted else 0.25) + max(0.0, expansion_ratio - 1.0) * 0.25)),
        4,
    )

    last = bars[-1]
    direction_vote = "buy" if float(last["close"]) > float(last["open"]) else "sell"
    reasons = [
        f"compression_ratio={round(compression_ratio, 4)}",
        f"expansion_ratio={round(expansion_ratio, 4)}",
    ]

    if volatility_contracted and breakout_probability >= 0.6:
        state = "compression_breakout_ready"
        confidence_delta = 0.05
    elif volatility_contracted:
        state = "compression"
        confidence_delta = 0.01
        reasons.append("weak_pattern_pruned")
    elif expansion_ratio > 1.3:
        state = "expansion_active"
        confidence_delta = 0.03
    else:
        state = "balanced"
        direction_vote = "neutral"
        confidence_delta = -0.01
        reasons.append("weak_pattern_pruned")

    confidence = round(max(0.2, breakout_probability), 4)
    return {
        "module": "compression_expansion",
        "state": state,
        "direction_vote": direction_vote,
        "confidence": confidence,
        "confidence_level": "high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
        "confidence_delta": round(confidence_delta, 4),
        "reasons": reasons,
        "metrics": {
            "avg_range": round(avg_range, 4),
            "current_range": round(current_range, 4),
            "compression_ratio": round(compression_ratio, 4),
            "expansion_ratio": round(expansion_ratio, 4),
            "breakout_probability": breakout_probability,
        },
    }
