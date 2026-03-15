from __future__ import annotations

from typing import Any


def compute_meta_conscious_routing(
    regime_score: dict[str, Any],
    liquidity: dict[str, Any],
    volatility: dict[str, Any],
) -> dict[str, Any]:
    """Routes confidence using explicit entropy/liquidity/regime assessments."""
    regime = float(regime_score.get("score", 0.5))
    liquidity_score = float(liquidity.get("score", 0.0))
    volatility_state = str(volatility.get("state", "unknown"))

    entropy_penalty = 0.08 if volatility_state == "high_volatility" else 0.0
    liquidity_bonus = 0.04 if liquidity_score >= 0.6 else -0.02
    regime_component = (regime - 0.5) * 0.12

    delta = regime_component + liquidity_bonus - entropy_penalty

    direction_vote = "neutral"
    liquidity_hint = str(liquidity.get("direction_hint", "neutral"))
    if regime >= 0.6 and liquidity_hint in {"buy", "sell"}:
        direction_vote = liquidity_hint

    return {
        "module": "meta_conscious_routing",
        "state": "computed",
        "direction_vote": direction_vote,
        "confidence_delta": round(delta, 4),
        "reasons": [
            f"regime_score={round(regime,4)}",
            f"liquidity_score={round(liquidity_score,4)}",
            f"volatility_state={volatility_state}",
            f"entropy_penalty={round(entropy_penalty,4)}",
        ],
    }
