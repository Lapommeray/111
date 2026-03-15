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


def classify_market_regime(
    structure: dict[str, Any],
    volatility_state: dict[str, Any],
) -> dict[str, Any]:
    """Classify market regime and adapt confidence according to trend/range/volatility context."""
    structure_state = str(structure.get("state", "range"))
    structure_strength = float(structure.get("strength", 0.0))
    vol_state = str(volatility_state.get("state", "balanced"))
    vol_ratio = float(volatility_state.get("metrics", {}).get("ratio", 1.0))

    if vol_state == "high_volatility" or vol_ratio > 1.6:
        regime = "high_volatility"
        confidence_delta = -0.06
    elif structure_state.startswith("trend_") and structure_strength >= 0.55:
        regime = "trend"
        confidence_delta = 0.04
    else:
        regime = "range"
        confidence_delta = -0.01

    confidence = round(max(0.2, min(0.95, 0.4 + (structure_strength * 0.4) - (0.12 if regime == "high_volatility" else 0.0))), 4)
    reasons = [
        f"structure_state={structure_state}",
        f"volatility_state={vol_state}",
        f"volatility_ratio={round(vol_ratio, 4)}",
    ]
    if confidence < 0.45:
        reasons.append("weak_pattern_pruned")

    direction_vote = str(structure.get("bias", "neutral")).lower()
    if regime in {"range", "high_volatility"} and confidence < 0.5:
        direction_vote = "neutral"

    return {
        "module": "market_regime",
        "state": regime,
        "direction_vote": direction_vote if direction_vote in {"buy", "sell"} else "neutral",
        "confidence": confidence,
        "confidence_level": "high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
        "confidence_delta": round(confidence_delta, 4),
        "reasons": reasons,
        "metrics": {"structure_strength": round(structure_strength, 4), "volatility_ratio": round(vol_ratio, 4)},
    }
