from __future__ import annotations

import json
from pathlib import Path

from src.learning.self_evolving_indicator_layer import run_self_evolving_indicator_layer


def test_self_evolving_indicator_layer_writes_governed_artifacts(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "a1", "status": "closed", "result": "loss", "pnl_points": -1.2, "direction": "BUY", "setup_type": "breakout"},
        {"trade_id": "a2", "status": "closed", "result": "win", "pnl_points": 1.6, "direction": "SELL", "setup_type": "reversal"},
        {"trade_id": "a3", "status": "closed", "result": "flat", "pnl_points": 0.0, "direction": "BUY", "setup_type": "trend_follow"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={
            "structure_state": "range",
            "volatility_ratio": 1.45,
            "spread_ratio": 1.9,
            "slippage_ratio": 1.4,
            "stale_price_data": False,
            "mt5_ready": True,
            "base_signal_confidence": 0.55,
            "recent_setup_confidence": 0.44,
            "base_risk_size": 1.0,
        },
        feature_contributors={"market_regime": 0.2},
        mutation_candidates=[{"candidate_id": "m1", "mutation_score": 0.8, "replay_validation": {"passed": True}}],
        replay_scope="full_replay",
    )

    capability = result["capability_generator"]
    assert Path(capability["paths"]["candidates"]).exists()
    assert Path(capability["paths"]["registry"]).exists()
    assert capability["capability_candidates"][0]["governance"]["replay_validation_required"] is True
    assert capability["capability_candidates"][0]["governance"]["quarantine_supported"] is True

    assert result["self_architecture_engine"]["strongest_architecture"]["architecture"]
    detector_path = Path(result["detector_generator"]["path"])
    assert detector_path.exists()
    detector_payload = json.loads(detector_path.read_text(encoding="utf-8"))
    assert len(detector_payload["detector_candidates"]) == 5

    compression_paths = result["knowledge_compression_system"]["paths"]
    assert Path(compression_paths["compressed_patterns"]).exists()
    assert Path(compression_paths["active_patterns"]).exists()
    assert Path(compression_paths["pruned_patterns"]).exists()

    strategy = result["strategy_evolution_engine"]
    assert strategy["strongest_branch"]["branch_id"] in {"current_strategy", "mutated_strategy_a"}
    assert "expectancy" in strategy["strongest_branch"]
    assert "drawdown" in strategy["strongest_branch"]
    assert "stability" in strategy["strongest_branch"]
    assert "trade_frequency" in strategy["strongest_branch"]
    assert "regime_performance" in strategy["strongest_branch"]

    meta = result["meta_learning_loop"]
    assert meta["loop"][0] == "trade"
    assert meta["latest_cycle"]["active_strategy_branch"] in {"current_strategy", "mutated_strategy_a"}
