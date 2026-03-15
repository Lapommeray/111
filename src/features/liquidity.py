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


def detect_liquidity_sweep_state(bars: list[dict[str, Any]], lookback: int = 30) -> dict[str, Any]:
    """Detect liquidity sweeps/stop-runs and map likely liquidity zones from recent highs/lows."""
    if len(bars) < max(lookback, 12):
        return {
            "module": "liquidity_sweep",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence": 0.0,
            "confidence_level": "low",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
            "metrics": {"liquidity_zones": []},
        }

    window = bars[-lookback:]
    current = window[-1]
    previous = window[-2]
    body = abs(float(current["close"]) - float(current["open"]))
    wick = max(
        float(current["high"]) - max(float(current["open"]), float(current["close"])),
        min(float(current["open"]), float(current["close"])) - float(current["low"]),
    )
    avg_volume = sum(float(b.get("tick_volume", 0.0)) for b in window[:-1]) / max(1, lookback - 1)
    volume_ratio = float(current.get("tick_volume", 0.0)) / avg_volume if avg_volume > 0 else 0.0
    recent_high = max(float(b["high"]) for b in window[:-1])
    recent_low = min(float(b["low"]) for b in window[:-1])

    swept_high = float(current["high"]) > recent_high and float(current["close"]) < recent_high
    swept_low = float(current["low"]) < recent_low and float(current["close"]) > recent_low
    stop_run = wick > (body * 1.25) and volume_ratio >= 1.0
    strength = min(1.0, 0.45 + (0.25 if stop_run else 0.0) + min(0.3, max(0.0, volume_ratio - 0.9) * 0.4))
    confidence = round(strength if (swept_high or swept_low) else 0.3, 4)

    liquidity_zones = [
        {"kind": "recent_high", "price": round(recent_high, 4)},
        {"kind": "recent_low", "price": round(recent_low, 4)},
    ]
    reasons = [f"volume_ratio={round(volume_ratio, 4)}"]
    if stop_run:
        reasons.append("stop_run_pattern")
    if swept_high:
        reasons.append("buy_side_liquidity_swept")
        direction_vote = "sell"
    elif swept_low:
        reasons.append("sell_side_liquidity_swept")
        direction_vote = "buy"
    else:
        reasons.append("no_sweep_detected")
        direction_vote = "neutral"

    if confidence < 0.4:
        reasons.append("weak_pattern_pruned")
        state = "pruned"
        confidence_delta = -0.01
    else:
        state = "computed"
        confidence_delta = 0.06 if direction_vote in {"buy", "sell"} else 0.0

    return {
        "module": "liquidity_sweep",
        "state": state,
        "direction_vote": direction_vote,
        "confidence": confidence,
        "confidence_level": "high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
        "confidence_delta": round(confidence_delta, 4),
        "reasons": reasons,
        "metrics": {
            "swept_high": swept_high,
            "swept_low": swept_low,
            "stop_run": stop_run,
            "volume_ratio": round(volume_ratio, 4),
            "liquidity_zones": liquidity_zones,
            "previous_close": float(previous["close"]),
        },
    }
