from __future__ import annotations

from typing import Any


def classify_market_structure(bars: list[dict[str, Any]], lookback: int = 20) -> dict[str, Any]:
    """Classify market direction from recent higher-high / lower-low behavior."""
    if len(bars) < max(lookback, 5):
        return {
            "state": "range",
            "bias": "neutral",
            "strength": 0.0,
            "reasons": ["insufficient_bars"],
        }

    window = bars[-lookback:]
    highs = [b["high"] for b in window]
    lows = [b["low"] for b in window]

    rising_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i - 1])
    rising_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i - 1])
    falling_highs = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i - 1])
    falling_lows = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i - 1])

    bull_score = rising_highs + rising_lows
    bear_score = falling_highs + falling_lows
    total = max(1, (len(highs) - 1) * 2)

    if bull_score > bear_score:
        return {
            "state": "trend_up",
            "bias": "buy",
            "strength": round(bull_score / total, 4),
            "reasons": ["higher_high_sequence", "higher_low_sequence"],
        }
    if bear_score > bull_score:
        return {
            "state": "trend_down",
            "bias": "sell",
            "strength": round(bear_score / total, 4),
            "reasons": ["lower_high_sequence", "lower_low_sequence"],
        }

    return {
        "state": "range",
        "bias": "neutral",
        "strength": 0.5,
        "reasons": ["balanced_structure"],
    }
