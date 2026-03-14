from __future__ import annotations

from typing import Any


def scan_tremor_state(bars: list[dict[str, Any]], lookback: int = 20) -> dict[str, Any]:
    """Scans micro-volatility tremors from observed candle ranges only."""
    if len(bars) < lookback + 1:
        return {
            "module": "quantum_tremor_scanner",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
        }

    ranges = [float(b["high"]) - float(b["low"]) for b in bars[-lookback:]]
    avg_range = sum(ranges[:-1]) / max(1, len(ranges) - 1)
    last_range = ranges[-1]
    tremor_ratio = (last_range / avg_range) if avg_range > 0 else 0.0

    if tremor_ratio > 1.8:
        state = "tremor_spike"
        vote = "wait"
        delta = -0.07
    elif tremor_ratio < 0.75:
        state = "tremor_compression"
        vote = "neutral"
        delta = -0.02
    else:
        state = "tremor_balanced"
        vote = "neutral"
        delta = 0.01

    return {
        "module": "quantum_tremor_scanner",
        "state": state,
        "direction_vote": vote,
        "confidence_delta": round(delta, 4),
        "reasons": [f"tremor_ratio={round(tremor_ratio,4)}"],
        "metrics": {"last_range": round(last_range, 4), "avg_range": round(avg_range, 4)},
    }
