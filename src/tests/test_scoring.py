from __future__ import annotations

from src.scoring.confidence_score import compute_confidence
from src.scoring.setup_score import compute_setup_score


def test_confidence_is_bounded_and_outputs_direction() -> None:
    result = compute_confidence(
        structure={"bias": "buy", "strength": 1.0},
        liquidity={"direction_hint": "buy", "score": 1.0},
    )
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["direction"] == "BUY"


def test_confidence_returns_wait_on_neutral_structure() -> None:
    result = compute_confidence(
        structure={"bias": "neutral", "strength": 0.0},
        liquidity={"direction_hint": "buy", "score": 0.8},
    )
    assert result["direction"] == "WAIT"
    assert any("structure_bias=neutral" == reason for reason in result["reasons"])


def test_confidence_agreement_higher_than_conflict() -> None:
    aligned = compute_confidence(
        structure={"bias": "sell", "strength": 0.8},
        liquidity={"direction_hint": "sell", "score": 0.8},
    )
    conflict = compute_confidence(
        structure={"bias": "sell", "strength": 0.8},
        liquidity={"direction_hint": "buy", "score": 0.8},
    )
    assert aligned["confidence"] > conflict["confidence"]


def test_setup_score_is_informational_only() -> None:
    result = compute_setup_score(
        {
            "displacement": {"confidence_delta": 0.08},
            "fvg": {"confidence_delta": 0.04},
            "spread_filter": {"confidence_delta": -0.07},
        }
    )
    assert result["confidence_delta"] == 0.0
    assert result["input_count"] == 3
    assert result["score"] > 0.0
