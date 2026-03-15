from __future__ import annotations

from typing import Any


def compute_confidence(structure: dict[str, Any], liquidity: dict[str, Any]) -> dict[str, Any]:
    """Build a transparent confidence score from directional agreement + strength."""
    structure_bias = structure.get("bias", "neutral")
    liquidity_hint = liquidity.get("direction_hint", "neutral")

    structure_strength = float(structure.get("strength", 0.0))
    liquidity_score = float(liquidity.get("score", 0.0))

    agreement = 1.0 if structure_bias in {"buy", "sell"} and structure_bias == liquidity_hint else 0.4
    confidence = (0.55 * structure_strength) + (0.35 * liquidity_score) + (0.10 * agreement)
    confidence = max(0.0, min(1.0, round(confidence, 4)))

    if structure_bias == "neutral":
        direction = "WAIT"
    else:
        direction = structure_bias.upper()

    return {
        "confidence": confidence,
        "direction": direction,
        "reasons": [
            f"structure_bias={structure_bias}",
            f"liquidity_hint={liquidity_hint}",
            f"agreement={agreement}",
        ],
    }
