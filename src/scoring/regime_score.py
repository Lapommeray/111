from __future__ import annotations

from typing import Any


def compute_regime_score(structure: dict[str, Any], volatility: dict[str, Any]) -> dict[str, Any]:
    """Score regime suitability from structure trend quality and volatility state."""
    structure_strength = float(structure.get("strength", 0.0))
    volatility_state = str(volatility.get("state", "unknown"))

    volatility_bonus = {
        "balanced": 0.1,
        "compression": -0.05,
        "high_volatility": -0.1,
    }.get(volatility_state, 0.0)

    regime_score = max(0.0, min(1.0, round(structure_strength + volatility_bonus, 4)))
    confidence_delta = round((regime_score - 0.5) * 0.15, 4)

    return {
        "module": "regime_score",
        "score": regime_score,
        "confidence_delta": confidence_delta,
        "reasons": [f"structure_strength={structure_strength}", f"volatility_state={volatility_state}"],
    }
