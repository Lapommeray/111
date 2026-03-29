from __future__ import annotations

from src.scoring.meta_conscious_routing import compute_meta_conscious_routing
from src.scoring.regime_score import compute_regime_score
from src.scoring.spectral_signal_fusion import fuse_spectral_signals


def test_spectral_signal_fusion_votes_and_delta_are_visible() -> None:
    outputs = {
        "displacement": {"direction_vote": "buy", "confidence_delta": 0.08},
        "fvg": {"direction_vote": "buy", "confidence_delta": 0.04},
        "volatility": {"direction_vote": "neutral", "confidence_delta": -0.02},
        "quantum_tremor_scanner": {"direction_vote": "neutral", "confidence_delta": 0.01},
        "invisible_data_miner": {"direction_vote": "buy", "confidence_delta": 0.03},
        "human_lag_exploit": {"direction_vote": "sell", "confidence_delta": -0.01},
    }
    result = fuse_spectral_signals(outputs)
    assert result["module"] == "spectral_signal_fusion"
    assert result["direction_vote"] == "buy"
    assert isinstance(result["confidence_delta"], float)


def test_spectral_signal_fusion_does_not_dilute_when_optional_modules_missing() -> None:
    """Missing optional modules should not be treated as zero-delta evidence."""
    outputs = {
        "displacement": {"direction_vote": "buy", "confidence_delta": 0.08},
        "fvg": {"direction_vote": "buy", "confidence_delta": 0.04},
        "volatility": {"direction_vote": "neutral", "confidence_delta": -0.02},
    }
    result = fuse_spectral_signals(outputs)
    # Expected avg over present modules only: (0.08 + 0.04 - 0.02) / 3 = 0.0333
    assert result["confidence_delta"] == 0.0333
    assert result["direction_vote"] == "buy"


def test_spectral_signal_fusion_ignores_quarantined_missing_vote_slots() -> None:
    """When only one directional signal is available, missing slots must not force neutrality."""
    outputs = {
        "displacement": {"direction_vote": "buy", "confidence_delta": 0.08},
    }
    result = fuse_spectral_signals(outputs)
    assert result["direction_vote"] == "buy"
    assert result["confidence_delta"] == 0.08


def test_meta_conscious_routing_uses_regime_liquidity_volatility() -> None:
    regime = {"score": 0.75}
    liquidity = {"score": 0.7, "direction_hint": "buy"}
    volatility = {"state": "balanced"}

    result = compute_meta_conscious_routing(regime, liquidity, volatility)
    assert result["module"] == "meta_conscious_routing"
    assert result["direction_vote"] == "buy"
    assert "regime_score=0.75" in result["reasons"]


def test_regime_score_changes_with_volatility_state() -> None:
    base_structure = {"strength": 0.7}
    balanced = compute_regime_score(base_structure, {"state": "balanced"})
    high_vol = compute_regime_score(base_structure, {"state": "high_volatility"})

    assert balanced["module"] == "regime_score"
    assert balanced["score"] > high_vol["score"]
