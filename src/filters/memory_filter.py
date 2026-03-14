from __future__ import annotations

from typing import Any


def apply_memory_filter(
    direction: str,
    blocked_setups: list[dict[str, Any]],
    trade_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Use stored outcomes to block repeated losing directions."""
    d = direction.upper()
    recent_outcomes = [o for o in trade_outcomes[-30:] if str(o.get("direction", "")).upper() == d]
    losses = [o for o in recent_outcomes if o.get("result") == "loss"]

    recent_blocked_same_direction = [
        b for b in blocked_setups[-20:] if str(b.get("direction", "")).upper() == d
    ]

    blocked = len(losses) >= 3
    reasons = [
        f"recent_direction_outcomes={len(recent_outcomes)}",
        f"recent_direction_losses={len(losses)}",
        f"recent_blocked_same_direction={len(recent_blocked_same_direction)}",
    ]
    if blocked:
        reasons.append("memory_loss_cluster_block")

    return {
        "module": "memory_filter",
        "blocked": blocked,
        "reasons": reasons,
        "confidence_delta": -0.08 if blocked else 0.02,
        "direction_vote": "wait" if blocked else d.lower(),
    }
