from __future__ import annotations

from src.filters.conflict_filter import apply_conflict_filter


def test_conflict_filter_does_not_block_clear_majority_split() -> None:
    """A 2:1 directional split should not be treated as a hard contradiction."""
    result = apply_conflict_filter(votes=["buy", "buy", "sell"], base_direction="BUY")
    assert result["blocked"] is False
    assert "direction_conflict" not in result["reasons"]


def test_conflict_filter_blocks_when_both_sides_strong_and_close() -> None:
    """Near-even strong conflict should still be blocked."""
    result = apply_conflict_filter(votes=["buy", "buy", "sell", "sell"], base_direction="BUY")
    assert result["blocked"] is True
    assert "direction_conflict" in result["reasons"]


def test_conflict_filter_does_not_hard_block_three_vs_two_split() -> None:
    """3:2 split should degrade conviction downstream, not hard-block here."""
    result = apply_conflict_filter(
        votes=["buy", "buy", "buy", "sell", "sell"],
        base_direction="BUY",
    )
    assert result["blocked"] is False
    assert "direction_conflict" not in result["reasons"]

