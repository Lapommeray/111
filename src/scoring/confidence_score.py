from __future__ import annotations

from typing import Any

# Minimum structure strength required for a directional signal.
_MIN_STRUCTURE_STRENGTH = 0.55
# Minimum liquidity score required for a directional signal.
_MIN_LIQUIDITY_SCORE = 0.45


def compute_confidence(structure: dict[str, Any], liquidity: dict[str, Any]) -> dict[str, Any]:
    """Build a transparent confidence score from directional agreement + strength."""
    structure_bias = structure.get("bias", "neutral")
    liquidity_hint = liquidity.get("direction_hint", "neutral")

    structure_strength = float(structure.get("strength", 0.0))
    liquidity_score = float(liquidity.get("score", 0.0))

    agreement = 1.0 if structure_bias in {"buy", "sell"} and structure_bias == liquidity_hint else 0.4
    confidence = (0.55 * structure_strength) + (0.35 * liquidity_score) + (0.10 * agreement)
    confidence = max(0.0, min(1.0, round(confidence, 4)))

    reasons = [
        f"structure_bias={structure_bias}",
        f"liquidity_hint={liquidity_hint}",
        f"agreement={agreement}",
    ]

    # Force WAIT when structure or liquidity is too weak to be actionable.
    direction = "WAIT"
    if structure_bias == "neutral":
        reasons.append("structure_neutral_wait")
    elif structure_strength < _MIN_STRUCTURE_STRENGTH:
        reasons.append(f"structure_strength_below_min({_MIN_STRUCTURE_STRENGTH})")
    elif liquidity_score < _MIN_LIQUIDITY_SCORE:
        reasons.append(f"liquidity_score_below_min({_MIN_LIQUIDITY_SCORE})")
    else:
        direction = structure_bias.upper()

    return {
        "confidence": confidence,
        "direction": direction,
        "reasons": reasons,
    }
