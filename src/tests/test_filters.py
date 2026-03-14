from __future__ import annotations

from src.filters.loss_blocker import LossBlocker


def test_loss_blocker_blocks_low_confidence() -> None:
    blocker = LossBlocker(min_confidence=0.6, max_spread_points=60.0)
    result = blocker.evaluate(
        confidence=0.5,
        structure={"bias": "buy"},
        liquidity={"direction_hint": "buy"},
        spread_points=20.0,
    )
    assert result["blocked"] is True
    assert "confidence_below_threshold" in result["reasons"]


def test_loss_blocker_blocks_conflict_even_with_high_confidence() -> None:
    blocker = LossBlocker(min_confidence=0.6, max_spread_points=60.0)
    result = blocker.evaluate(
        confidence=0.9,
        structure={"bias": "buy"},
        liquidity={"direction_hint": "sell"},
        spread_points=20.0,
    )
    assert result["blocked"] is True
    assert "structure_liquidity_conflict" in result["reasons"]


def test_loss_blocker_passes_aligned_signal() -> None:
    blocker = LossBlocker(min_confidence=0.6, max_spread_points=60.0)
    result = blocker.evaluate(
        confidence=0.9,
        structure={"bias": "sell"},
        liquidity={"direction_hint": "sell"},
        spread_points=20.0,
    )
    assert result["blocked"] is False
    assert result["reasons"] == []
