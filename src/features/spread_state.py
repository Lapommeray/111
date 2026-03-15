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


def track_execution_quality(bars: list[dict[str, Any]], baseline_points: float = 40.0) -> dict[str, Any]:
    """Track slippage proxy, spread conditions, and fill-timing proxy from MT5-available bar data."""
    if len(bars) < 3:
        return {
            "module": "execution_quality",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence": 0.0,
            "confidence_level": "low",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
            "metrics": {},
        }

    spread_state = compute_spread_state(bars, baseline_points=baseline_points)
    current = bars[-1]
    previous = bars[-2]
    prior = bars[-3]
    slippage_proxy = abs(float(current["open"]) - float(previous["close"]))
    prev_duration = max(1, int(previous["time"]) - int(prior["time"]))
    latest_duration = max(1, int(current["time"]) - int(previous["time"]))
    fill_timing_ratio = round(latest_duration / prev_duration, 4)
    spread_points = float(spread_state.get("spread_points", baseline_points))
    spread_condition = str(spread_state.get("state", "normal"))

    reasons = [
        f"spread_condition={spread_condition}",
        f"spread_points={round(spread_points, 2)}",
        f"slippage_proxy={round(slippage_proxy, 4)}",
        f"fill_timing_ratio={fill_timing_ratio}",
    ]

    if spread_condition == "tight" and slippage_proxy <= 0.2 and fill_timing_ratio <= 1.2:
        confidence_delta = 0.04
        state = "efficient"
        confidence = 0.78
    elif spread_condition == "wide" or slippage_proxy > 0.7 or fill_timing_ratio > 1.5:
        confidence_delta = -0.05
        state = "degraded"
        confidence = 0.35
        reasons.append("weak_pattern_pruned")
    else:
        confidence_delta = 0.0
        state = "normal"
        confidence = 0.55

    return {
        "module": "execution_quality",
        "state": state,
        "direction_vote": "neutral",
        "confidence": round(confidence, 4),
        "confidence_level": "high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
        "confidence_delta": round(confidence_delta, 4),
        "reasons": reasons,
        "metrics": {
            "spread_condition": spread_condition,
            "spread_points": round(spread_points, 2),
            "slippage_proxy": round(slippage_proxy, 4),
            "fill_timing_ratio": fill_timing_ratio,
        },
    }
