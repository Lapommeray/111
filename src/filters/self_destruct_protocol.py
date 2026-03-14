from __future__ import annotations

from typing import Any


def apply_self_destruct_protocol(
    trade_outcomes: list[dict[str, Any]],
    module_outputs: dict[str, dict[str, Any]],
    loss_threshold: int = 4,
) -> dict[str, Any]:
    """Down-ranks failing logic using explicit measurable loss conditions only."""
    recent = trade_outcomes[-20:]
    losses = [o for o in recent if o.get("result") == "loss"]

    disable_risk = len(losses) >= loss_threshold
    downrank_targets: list[str] = []
    if disable_risk:
        for name in ("fvg", "human_lag_exploit", "invisible_data_miner"):
            if name in module_outputs:
                downrank_targets.append(name)

    return {
        "module": "self_destruct_protocol",
        "state": "triggered" if disable_risk else "idle",
        "blocked": disable_risk,
        "direction_vote": "wait" if disable_risk else "neutral",
        "confidence_delta": -0.12 if disable_risk else 0.0,
        "reasons": [f"recent_losses={len(losses)}", f"loss_threshold={loss_threshold}"],
        "disabled_modules": downrank_targets,
    }
