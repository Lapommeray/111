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
    pain_memory = result["pain_memory_survival_layer"]
    assert Path(pain_memory["paths"]["loss_clusters"]).exists()
    assert Path(pain_memory["paths"]["pain_patterns"]).exists()
    assert Path(pain_memory["paths"]["generated_detectors"]).exists()
    assert Path(pain_memory["paths"]["registry"]).exists()
    assert result["survival_intelligence_layer"]["pain_memory_survival_layer"]["paths"]["registry"] == pain_memory["paths"]["registry"]


def test_pain_memory_survival_layer_promotes_replay_validated_detectors(tmp_path: Path) -> None:
    trade_outcomes = [
        {
            "trade_id": "l1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.4,
            "direction": "BUY",
            "setup_type": "breakout",
            "session": "london",
            "failure_cause": "execution_failure",
        },
        {
            "trade_id": "l2",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.6,
            "direction": "BUY",
            "setup_type": "breakout",
            "session": "london",
            "failure_cause": "execution_failure",
        },
        {
            "trade_id": "l3",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.2,
            "direction": "BUY",
            "setup_type": "breakout",
            "session": "london",
            "failure_cause": "execution_failure",
        },
        {
            "trade_id": "l4",
            "status": "closed",
            "result": "win",
            "pnl_points": 1.1,
            "direction": "SELL",
            "setup_type": "reversal",
            "session": "new_york",
            "failure_cause": "none",
        },
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "base_signal_confidence": 0.4, "base_risk_size": 1.0},
        replay_scope="full_replay",
    )

    pain_memory = result["pain_memory_survival_layer"]
    assert len(pain_memory["loss_cluster_contexts"]) == 1
    assert pain_memory["loss_cluster_contexts"][0]["cluster_size"] == 3
    assert pain_memory["extracted_pain_patterns"][0]["recurring_context"]["setup_type"] == "breakout"
    assert pain_memory["generated_detectors"][0]["validation"]["replay_validation_required"] is True
    assert pain_memory["generated_detectors"][0]["validation"]["replay_score"] == 1.0
    assert pain_memory["generated_detectors"][0]["decision"] in {"promote", "quarantine"}
    assert pain_memory["promotion_decisions"]["promoted"] or pain_memory["promotion_decisions"]["quarantined"]
    registry_payload = json.loads(Path(pain_memory["paths"]["registry"]).read_text(encoding="utf-8"))
    assert "promoted_survival_rules" in registry_payload
    assert "quarantined_survival_rules" in registry_payload


def test_pain_memory_survival_layer_requires_repeated_context_cluster(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "x1", "status": "closed", "result": "loss", "pnl_points": -0.8, "direction": "BUY", "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "x2", "status": "closed", "result": "loss", "pnl_points": -0.7, "direction": "SELL", "setup_type": "reversal", "session": "london", "failure_cause": "weak_setup"},
        {"trade_id": "x3", "status": "closed", "result": "win", "pnl_points": 0.9, "direction": "BUY", "setup_type": "trend_follow", "session": "new_york", "failure_cause": "none"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "base_signal_confidence": 0.4, "base_risk_size": 1.0},
        replay_scope="full_replay",
    )
    pain_memory = result["pain_memory_survival_layer"]
    assert pain_memory["loss_cluster_contexts"] == []
    assert pain_memory["extracted_pain_patterns"] == []
    assert pain_memory["generated_detectors"] == []
    assert pain_memory["promotion_decisions"]["promoted"] == []
    assert pain_memory["promotion_decisions"]["quarantined"] == []


def test_self_suggestion_governor_detects_gaps_and_creates_suggestions(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "g1", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "london", "failure_cause": "execution_failure"},
        {"trade_id": "g2", "status": "closed", "result": "loss", "pnl_points": -1.1, "setup_type": "breakout", "session": "london", "failure_cause": "execution_failure"},
        {"trade_id": "g3", "status": "closed", "result": "loss", "pnl_points": -0.9, "setup_type": "breakout", "session": "new_york", "failure_cause": "mt5_reject"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.0, "slippage_ratio": 1.9, "mt5_ready": False},
        mutation_candidates=[{"candidate_id": "n1", "mutation_score": 0.1, "replay_validation": {"passed": False}}],
        replay_scope="full_replay",
    )
    governor = result["self_suggestion_governor"]
    assert governor["detected_gaps"]
    assert governor["proposed_improvements"]
    assert governor["implemented_improvements"]
    first_suggestion = governor["proposed_improvements"][0]
    assert first_suggestion["failure_context"]["failure_cause"]
    assert first_suggestion["failure_context"]["session"]
    assert first_suggestion["session"]
    assert first_suggestion["regime"]
    assert "structure_state" in first_suggestion["macro_state"]
    assert first_suggestion["detector_or_strategy_component"]
    assert first_suggestion["missing_capability_hypothesis"]
    assert governor["safety_controls"]["direct_live_deployment_blocked"] is True
    assert Path(governor["paths"]["registry"]).exists()
    assert Path(governor["paths"]["governor"]).exists()
    assert Path(governor["paths"]["history"]).exists()


def test_self_suggestion_governor_duplicate_suppression_and_cooldown(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "d1", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "london", "failure_cause": "execution_failure"},
        {"trade_id": "d2", "status": "closed", "result": "loss", "pnl_points": -1.2, "setup_type": "breakout", "session": "london", "failure_cause": "execution_failure"},
    ]
    first = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.9, "slippage_ratio": 1.8},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.9, "slippage_ratio": 1.8},
        replay_scope="focused_replay",
    )
    assert first["self_suggestion_governor"]["proposed_improvements"]
    assert second["self_suggestion_governor"]["anti_noise_controls"]["duplicate_suppression"] >= 1
    assert second["self_suggestion_governor"]["anti_noise_controls"]["cooldown_suppressed"] >= 0


def test_self_suggestion_governor_sandbox_governance_and_no_live_rewrite(tmp_path: Path) -> None:
    execution_path = tmp_path / "memory" / "live_execution.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("LIVE = 'stable'\n", encoding="utf-8")
    before = execution_path.read_text(encoding="utf-8")
    trade_outcomes = [
        {"trade_id": "s1", "status": "closed", "result": "loss", "pnl_points": -1.3, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "s2", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "s3", "status": "closed", "result": "win", "pnl_points": 1.0, "setup_type": "reversal", "session": "london", "failure_cause": "none"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.8, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    governor = result["self_suggestion_governor"]
    assert execution_path.read_text(encoding="utf-8") == before
    for item in governor["implemented_improvements"]:
        assert item["governance"]["sandbox_only"] is True
        assert item["governance"]["live_activation_allowed"] is False
        assert item["governance"]["core_module_deletion_allowed"] is False


def test_self_suggestion_governor_pruning_and_unresolved_gap_registry(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "u1", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "london", "failure_cause": "execution_failure"},
        {"trade_id": "u2", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "london", "failure_cause": "execution_failure"},
        {"trade_id": "u3", "status": "closed", "result": "loss", "pnl_points": -0.8, "setup_type": "breakout", "session": "new_york", "failure_cause": "mt5_reject"},
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.0, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.0, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    governor = second["self_suggestion_governor"]
    assert governor["anti_noise_controls"]["max_suggestions_per_cycle"] >= 3
    registry = json.loads(Path(governor["paths"]["registry"]).read_text(encoding="utf-8"))
    assert "proposed_improvements" in registry
    assert "implemented_improvements" in registry
    assert "rejected_improvements" in registry
    assert "promoted_improvements" in registry
    assert "repeated_unresolved_gaps" in registry


def test_self_suggestion_governor_rejects_vague_suggestions(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "v1", "status": "closed", "result": "loss", "pnl_points": -0.6, "failure_cause": "unknown", "setup_type": "", "session": ""},
        {"trade_id": "v2", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "unknown", "setup_type": "", "session": ""},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={},
        replay_scope="focused_replay",
    )
    governor = result["self_suggestion_governor"]
    assert governor["anti_noise_controls"]["vague_rejected"] >= 1
    assert any(item.get("reason") == "vague_suggestion_rejected" for item in governor["rejected_improvements"])


def test_self_suggestion_governor_rejects_partially_specific_suggestions(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "pv1", "status": "closed", "result": "loss", "pnl_points": -0.6, "failure_cause": "execution_failure", "setup_type": "", "session": "london"},
        {"trade_id": "pv2", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "execution_failure", "setup_type": "", "session": "london"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.1, "slippage_ratio": 1.1},
        replay_scope="focused_replay",
    )
    governor = result["self_suggestion_governor"]
    assert governor["anti_noise_controls"]["vague_rejected"] >= 1
    assert any(item.get("reason") == "vague_suggestion_rejected" for item in governor["rejected_improvements"])


def test_self_suggestion_governor_boosts_priority_for_repeated_specific_failure_cluster(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "p1", "status": "closed", "result": "loss", "pnl_points": -1.1, "failure_cause": "execution_failure", "setup_type": "breakout", "session": "london", "direction": "BUY"},
        {"trade_id": "p2", "status": "closed", "result": "loss", "pnl_points": -1.0, "failure_cause": "execution_failure", "setup_type": "breakout", "session": "london", "direction": "BUY"},
        {"trade_id": "p3", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure", "setup_type": "breakout", "session": "london", "direction": "BUY"},
        {"trade_id": "p4", "status": "closed", "result": "win", "pnl_points": 1.0, "failure_cause": "none", "setup_type": "reversal", "session": "new_york", "direction": "SELL"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.1, "slippage_ratio": 1.0},
        replay_scope="full_replay",
    )
    specific_repeated_failure_suggestions = [
        item for item in result["self_suggestion_governor"]["proposed_improvements"] if item.get("gap_type") == "repeated_failure_pattern"
    ]
    assert specific_repeated_failure_suggestions
    assert all(item["is_repeated_specific_failure_cluster"] is True for item in specific_repeated_failure_suggestions)
    assert all(item["cluster_specificity_boost"] > 0 for item in specific_repeated_failure_suggestions)
