from __future__ import annotations

from typing import Any


def apply_conflict_filter(votes: list[str], base_direction: str) -> dict[str, Any]:
    """Block when buy/sell votes are simultaneously strong and contradictory."""
    normalized = [v.lower() for v in votes]
    buy_count = sum(1 for v in normalized if v == "buy")
    sell_count = sum(1 for v in normalized if v == "sell")

    active_votes = buy_count + sell_count
    # Hard-block exact-tie deadlocks.
    exact_tie = buy_count > 0 and sell_count > 0 and buy_count == sell_count and active_votes >= 4
    # Also block when the winning side's margin is less than 15% of active votes
    # (very close split, e.g. 5 buy vs 4 sell). A 3:2 split (margin=0.2) is
    # allowed to pass through so downstream conviction guards can handle it.
    low_margin = (
        active_votes >= 4
        and buy_count > 0
        and sell_count > 0
        and abs(buy_count - sell_count) / active_votes < 0.15
    )
    blocked = exact_tie or low_margin
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
