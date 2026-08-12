from __future__ import annotations

from typing import Any

# Minimum fraction by which the dominant vote side must lead the minority side.
# Splits tighter than this threshold are too contested to act on.
_MIN_VOTE_MARGIN = 0.15
# Minimum number of active (buy or sell) votes before margin filtering applies.
_MIN_ACTIVE_VOTES = 4


def apply_conflict_filter(votes: list[str], base_direction: str) -> dict[str, Any]:
    """Block when buy/sell votes are simultaneously strong and contradictory."""
    normalized = [v.lower() for v in votes]
    buy_count = sum(1 for v in normalized if v == "buy")
    sell_count = sum(1 for v in normalized if v == "sell")

    active_votes = buy_count + sell_count
    # Block when both sides are present and the winning margin is too small.
    # This covers exact ties (margin == 0) and near-ties (margin < _MIN_VOTE_MARGIN).
    blocked = (
        active_votes >= _MIN_ACTIVE_VOTES
        and buy_count > 0
        and sell_count > 0
        and abs(buy_count - sell_count) / active_votes < _MIN_VOTE_MARGIN
    )
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
