from __future__ import annotations

from typing import Any


def mine_internal_patterns(
    bars: list[dict[str, Any]],
    structure: dict[str, Any],
    liquidity: dict[str, Any],
) -> dict[str, Any]:
    """Extracts transparent pattern metrics from existing market bars only."""
    if len(bars) < 30:
        return {
            "module": "invisible_data_miner",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["insufficient_bars"],
        }

    closes = [float(b["close"]) for b in bars[-30:]]
    slope = closes[-1] - closes[0]
    up_steps = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
    down_steps = (len(closes) - 1) - up_steps

    structure_bias = str(structure.get("bias", "neutral"))
    liquidity_hint = str(liquidity.get("direction_hint", "neutral"))

    if slope > 0 and up_steps > down_steps:
        vote = "buy"
    elif slope < 0 and down_steps > up_steps:
        vote = "sell"
    else:
        vote = "neutral"

    alignment_bonus = 0.0
    if vote != "neutral" and vote == structure_bias and vote == liquidity_hint:
        alignment_bonus = 0.04
    elif vote != "neutral" and (vote == structure_bias or vote == liquidity_hint):
        alignment_bonus = 0.02

    confidence_delta = min(0.06, round(abs(slope) / 40.0, 4)) + alignment_bonus
    if vote == "neutral":
        confidence_delta = -0.01

    return {
        "module": "invisible_data_miner",
        "state": "computed",
        "direction_vote": vote,
        "confidence_delta": round(confidence_delta, 4),
        "reasons": [
            f"slope={round(slope,4)}",
            f"up_steps={up_steps}",
            f"down_steps={down_steps}",
            f"structure_bias={structure_bias}",
            f"liquidity_hint={liquidity_hint}",
        ],
    }
