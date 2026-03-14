from __future__ import annotations

from typing import Any


def assess_liquidity_state(bars: list[dict[str, Any]], lookback: int = 30) -> dict[str, Any]:
    """Detect simple liquidity sweeps around recent highs/lows and volume support."""
    if len(bars) < max(lookback, 10):
        return {
            "liquidity_state": "unknown",
            "sweep": "none",
            "direction_hint": "neutral",
            "score": 0.0,
            "reasons": ["insufficient_bars"],
        }

    window = bars[-lookback:]
    current = bars[-1]
    previous = bars[-2]

    recent_high = max(b["high"] for b in window[:-1])
    recent_low = min(b["low"] for b in window[:-1])
    avg_volume = sum(b.get("tick_volume", 0.0) for b in window[:-1]) / max(1, lookback - 1)

    swept_high = current["high"] > recent_high and current["close"] < recent_high
    swept_low = current["low"] < recent_low and current["close"] > recent_low
    volume_ok = current.get("tick_volume", 0.0) >= avg_volume

    reasons: list[str] = []
    score = 0.4 if volume_ok else 0.2

    if swept_high:
        reasons.append("buy_side_liquidity_swept")
        return {
            "liquidity_state": "sweep",
            "sweep": "high",
            "direction_hint": "sell",
            "score": min(1.0, score + 0.4),
            "reasons": reasons + (["volume_confirmed"] if volume_ok else ["low_volume"]),
        }

    if swept_low:
        reasons.append("sell_side_liquidity_swept")
        return {
            "liquidity_state": "sweep",
            "sweep": "low",
            "direction_hint": "buy",
            "score": min(1.0, score + 0.4),
            "reasons": reasons + (["volume_confirmed"] if volume_ok else ["low_volume"]),
        }

    momentum_up = current["close"] > previous["close"]
    return {
        "liquidity_state": "stable",
        "sweep": "none",
        "direction_hint": "buy" if momentum_up else "sell",
        "score": score,
        "reasons": ["no_clear_sweep", "micro_momentum_up" if momentum_up else "micro_momentum_down"],
    }
