from __future__ import annotations

from typing import Any

from src.utils import safe_mean


def compute_displacement(bars: list[dict[str, Any]], lookback: int = 20) -> dict[str, Any]:
    """Measure recent candle-body displacement vs historical average body size."""
    if len(bars) < lookback + 2:
        return {
            "module": "displacement",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
        }

    window = bars[-(lookback + 1) :]
    last = window[-1]
    previous = window[:-1]

    body = abs(float(last["close"]) - float(last["open"]))
    avg_body = safe_mean([abs(float(b["close"]) - float(b["open"])) for b in previous])
    ratio = body / avg_body if avg_body > 0 else 0.0

    direction_vote = "buy" if float(last["close"]) > float(last["open"]) else "sell"
    confidence_delta = 0.0
    reasons = [f"displacement_ratio={round(ratio, 4)}"]

    if ratio >= 1.8:
        confidence_delta = 0.08
        reasons.append("strong_displacement")
    elif ratio >= 1.2:
        confidence_delta = 0.03
        reasons.append("moderate_displacement")
    else:
        direction_vote = "neutral"
        reasons.append("weak_displacement")

    return {
        "module": "displacement",
        "state": "computed",
        "direction_vote": direction_vote,
        "confidence_delta": round(confidence_delta, 4),
        "reasons": reasons,
        "metrics": {"body": round(body, 4), "avg_body": round(avg_body, 4), "ratio": round(ratio, 4)},
    }
