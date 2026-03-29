from __future__ import annotations

from typing import Any


def apply_conflict_filter(votes: list[str], base_direction: str) -> dict[str, Any]:
    """Block when buy/sell votes are simultaneously strong and contradictory."""
    normalized = [v.lower() for v in votes]
    buy_count = sum(1 for v in normalized if v == "buy")
    sell_count = sum(1 for v in normalized if v == "sell")

    active_votes = buy_count + sell_count
    # Only hard-block true deadlock contradictions; close but non-tie splits
    # are handled by downstream directional-margin conviction guards.
    blocked = buy_count > 0 and sell_count > 0 and buy_count == sell_count and active_votes >= 4
    reasons = [f"buy_votes={buy_count}", f"sell_votes={sell_count}"]

    if blocked:
        reasons.append("direction_conflict")

    return {
        "module": "conflict_filter",
        "blocked": blocked,
        "reasons": reasons,
        "confidence_delta": -0.05 if blocked else 0.01,
        "direction_vote": "wait" if blocked else base_direction.lower(),
    }
