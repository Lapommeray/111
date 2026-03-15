from __future__ import annotations

from typing import Any


def detect_fvg_state(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect basic 3-candle fair value gap (FVG) from visible OHLC bars."""
    if len(bars) < 3:
        return {
            "module": "fvg",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
        }

    c1, c2, c3 = bars[-3], bars[-2], bars[-1]

    bullish_gap = float(c1["high"]) < float(c3["low"])
    bearish_gap = float(c1["low"]) > float(c3["high"])

    if bullish_gap:
        return {
            "module": "fvg",
            "state": "bullish_gap",
            "direction_vote": "buy",
            "confidence_delta": 0.04,
            "reasons": ["bullish_fvg_detected"],
            "metrics": {"gap_low": float(c1["high"]), "gap_high": float(c3["low"]), "mid_candle_close": float(c2["close"])},
        }

    if bearish_gap:
        return {
            "module": "fvg",
            "state": "bearish_gap",
            "direction_vote": "sell",
            "confidence_delta": 0.04,
            "reasons": ["bearish_fvg_detected"],
            "metrics": {"gap_low": float(c3["high"]), "gap_high": float(c1["low"]), "mid_candle_close": float(c2["close"])},
        }

    return {
        "module": "fvg",
        "state": "no_gap",
        "direction_vote": "neutral",
        "confidence_delta": -0.01,
        "reasons": ["no_fvg_signal"],
    }
