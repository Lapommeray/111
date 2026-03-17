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


def test_advanced_discovery_layers_generate_signals_and_persist_artifacts(tmp_path: Path) -> None:
    trade_outcomes = [
        {
            "trade_id": "ad1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.2,
            "entry_price": 2010.0,
            "direction": "BUY",
            "setup_type": "breakout",
            "session": "asia",
            "failure_cause": "execution_failure",
            "trade_tags": {"session": "asia", "spread_ratio": 1.8, "volatility_ratio": 1.5, "macro_state": "risk_off"},
        },
        {
            "trade_id": "ad2",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.8,
            "entry_price": 2010.0,
            "direction": "BUY",
            "setup_type": "breakout",
            "session": "asia",
            "failure_cause": "execution_failure",
            "trade_tags": {"session": "asia", "spread_ratio": 1.7, "volatility_ratio": 1.4, "macro_state": "risk_off"},
        },
        {
            "trade_id": "ad3",
            "status": "closed",
            "result": "win",
            "pnl_points": 1.1,
            "entry_price": 2015.0,
            "direction": "SELL",
            "setup_type": "reversal",
            "session": "london",
            "failure_cause": "none",
            "trade_tags": {"session": "london", "spread_ratio": 1.2, "volatility_ratio": 1.1, "macro_state": "balanced"},
        },
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={
            "structure_state": "range",
            "session_state": "asia",
            "volatility_ratio": 1.45,
            "spread_ratio": 1.85,
            "slippage_ratio": 1.7,
            "dxy_state": "strong_usd",
            "yield_state": "bearish_gold",
            "xau_dxy_corr": 0.25,
            "xau_real_yield_corr": 0.2,
            "volatility_response_corr": -0.2,
        },
        replay_scope="full_replay",
    )

    synthetic = result["synthetic_feature_invention_engine"]
    assert synthetic["feature_candidates"]
    assert synthetic["feature_performance"]
    assert Path(synthetic["paths"]["synthetic_features"]).exists()
    assert Path(synthetic["paths"]["feature_candidates"]).exists()
    assert Path(synthetic["paths"]["feature_performance"]).exists()

    negative_space = result["negative_space_pattern_recognition"]["signal"]
    assert "negative_space_signal" in negative_space
    assert negative_space["validation"]["sandbox_only"] is True
    assert Path(result["negative_space_pattern_recognition"]["paths"]["latest"]).exists()

    invariant = result["temporal_invariance_break_detection"]
    assert invariant["invariant_break_events"]
    assert any(item["trigger_deeper_analysis"] for item in invariant["invariant_break_events"])
    assert Path(invariant["paths"]["events"]).exists()
    assert Path(invariant["paths"]["models"]).exists()

    pain_geometry = result["pain_geometry_fields"]
    assert pain_geometry["pain_risk_surface"]["current_state_risk"] >= 0.0
    assert Path(pain_geometry["paths"]["coordinates"]).exists()
    assert Path(pain_geometry["paths"]["surface"]).exists()

    counterfactual = result["counterfactual_trade_engine"]["counterfactual_evaluations"]
    assert counterfactual
    assert "opposite_trade" in counterfactual[0]["counterfactual_scenarios"]
    assert Path(result["counterfactual_trade_engine"]["paths"]["latest"]).exists()

    liquidity_decay = result["fractal_liquidity_decay_functions"]
    assert liquidity_decay["liquidity_decay_models"]
    assert Path(liquidity_decay["path"]).exists()

    self_modeling = result["recursive_self_modeling"]
    assert self_modeling["selected_configuration"]["config_id"]
    assert self_modeling["governance"]["direct_live_self_rewrite_allowed"] is False
    assert Path(self_modeling["path"]).exists()

    unified = result["unified_market_intelligence_field"]
    assert set(unified["components"]) == {
        "macro_state",
        "regime_state",
        "detector_reliability",
        "synthetic_feature_state",
        "negative_space_state",
        "invariant_break_state",
        "pain_geometry_risk",
        "counterfactual_evaluation",
        "liquidity_decay_state",
        "execution_microstructure_state",
        "adversarial_execution_state",
        "structural_memory_state",
        "latent_transition_hazard_state",
    }
    assert 0.0 <= unified["unified_field_score"] <= 1.0
    assert 0.0 <= unified["confidence_structure"]["composite_confidence"] <= 1.0
    assert unified["decision_refinements"]["signal_confidence"]["refined"] <= 1.0
    assert unified["decision_refinements"]["risk_sizing"]["refined"] >= 0.05
    assert Path(unified["paths"]["latest"]).exists()
    assert Path(unified["paths"]["history"]).exists()
    governor_unified = result["self_suggestion_governor"]["unified_market_intelligence_field"]
    assert "unified_field_score" in governor_unified
    assert "composite_confidence" in governor_unified
    assert "refusal_pause_behavior" in governor_unified

    tags = result["discovery_state_tags"]
    assert set(tags) == {
        "synthetic_feature_state",
        "negative_space_state",
        "invariant_break_state",
        "pain_geometry_risk",
        "counterfactual_evaluation",
        "liquidity_decay_state",
    }
    assert result["self_suggestion_governor"]["discovery_state_tags"] == tags


def test_synthetic_feature_engine_prunes_low_value_features(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "sp1", "status": "closed", "result": "win", "pnl_points": 0.9, "session": "london", "failure_cause": "none"},
        {"trade_id": "sp2", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "new_york", "failure_cause": "none"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={
            "structure_state": "range",
            "session_state": "london",
            "volatility_ratio": 1.0,
            "spread_ratio": 1.0,
            "slippage_ratio": 1.0,
            "dxy_state": "neutral",
            "yield_state": "neutral",
        },
        replay_scope="focused_replay",
    )
    synthetic = result["synthetic_feature_invention_engine"]
    assert synthetic["pruned_feature_count"] >= 1


def test_unified_market_intelligence_field_refines_pause_and_strategy_selection(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "u-mi-1", "status": "closed", "result": "loss", "pnl_points": -1.2, "entry_price": 2010.0, "direction": "BUY", "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "u-mi-2", "status": "closed", "result": "loss", "pnl_points": -1.1, "entry_price": 2012.0, "direction": "BUY", "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "u-mi-3", "status": "closed", "result": "loss", "pnl_points": -0.9, "entry_price": 2014.0, "direction": "BUY", "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "u-mi-4", "status": "closed", "result": "win", "pnl_points": 0.6, "entry_price": 2013.0, "direction": "SELL", "setup_type": "reversal", "session": "london", "failure_cause": "none"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={
            "structure_state": "range",
            "session_state": "asia",
            "volatility_ratio": 1.9,
            "spread_ratio": 2.2,
            "slippage_ratio": 1.8,
            "base_signal_confidence": 0.55,
            "base_risk_size": 1.0,
            "stale_price_data": True,
            "mt5_ready": False,
        },
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    refinements = unified["decision_refinements"]
    assert refinements["signal_confidence"]["refined"] <= refinements["signal_confidence"]["base"]
    assert refinements["risk_sizing"]["refined"] <= refinements["risk_sizing"]["base"]
    assert refinements["strategy_selection"]["mode"] in {"defensive", "adaptive", "offensive"}
    assert refinements["strategy_selection"]["selected_branch_id"]
    assert refinements["refusal_pause_behavior"]["should_pause"] in {True, False}
    assert refinements["refusal_pause_behavior"]["should_refuse"] in {True, False}


def test_execution_microstructure_layer_persists_required_artifacts(tmp_path: Path) -> None:
    trade_outcomes = [
        {
            "trade_id": "em1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.0,
            "failure_cause": "execution_failure",
            "intended_entry_price": 2010.0,
            "average_fill_price": 2011.2,
            "signal_time": 10,
            "first_fill_time": 14,
            "requested_size": 1.0,
            "filled_size": 0.7,
        },
        {
            "trade_id": "em2",
            "status": "closed",
            "result": "win",
            "pnl_points": 0.8,
            "failure_cause": "none",
            "intended_entry_price": 2012.0,
            "average_fill_price": 2012.4,
            "signal_time": 20,
            "first_fill_time": 21,
            "requested_size": 1.0,
            "filled_size": 1.0,
        },
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "spread_ratio": 1.3, "slippage_ratio": 1.2},
        replay_scope="full_replay",
    )
    execution_layer = result["execution_microstructure_intelligence_layer"]
    assert Path(execution_layer["paths"]["latest"]).exists()
    assert Path(execution_layer["paths"]["history"]).exists()
    assert Path(execution_layer["paths"]["failure_clusters"]).exists()
    assert Path(execution_layer["paths"]["quality_baselines"]).exists()
    assert Path(execution_layer["paths"]["entry_timing_degradation"]).exists()


def test_execution_microstructure_layer_is_wired_between_liquidity_and_recursive_outputs(tmp_path: Path) -> None:
    trade_outcomes = [
        {
            "trade_id": "emw1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.2,
            "failure_cause": "execution_failure",
            "intended_entry_price": 2005.0,
            "average_fill_price": 2007.0,
            "requested_size": 1.0,
            "filled_size": 0.6,
            "signal_time": 10,
            "first_fill_time": 17,
        },
        {"trade_id": "emw2", "status": "closed", "result": "win", "pnl_points": 0.7, "failure_cause": "none"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "spread_ratio": 1.6, "slippage_ratio": 1.5},
        replay_scope="full_replay",
    )
    assert "execution_microstructure_intelligence_layer" in result
    assert "execution_microstructure_intelligence_layer" in result["survival_intelligence_layer"]
    assert "execution_microstructure_assessment" in result["recursive_self_modeling"]
    assert "execution_microstructure_state" in result["unified_market_intelligence_field"]["components"]
    assert "execution_microstructure_intelligence_layer" in result["self_suggestion_governor"]


def test_execution_microstructure_missing_fields_stays_sandbox_and_nonbreaking(tmp_path: Path) -> None:
    trade_outcomes = [
        {"trade_id": "emn1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
        {"trade_id": "emn2", "status": "closed", "result": "win", "pnl_points": 0.9, "failure_cause": "none"},
    ]
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    execution_layer = result["execution_microstructure_intelligence_layer"]
    assert 0.0 <= execution_layer["execution_quality_score"] <= 1.0
    assert 0.25 <= execution_layer["execution_confidence"] <= 1.0
    assert 0.0 <= execution_layer["execution_penalty"] <= 1.0
    assert 0.0 <= execution_layer["failure_cluster_risk"] <= 1.0
    assert execution_layer["governance"]["sandbox_only"] is True
    assert execution_layer["governance"]["no_blind_live_self_rewrites"] is True
    assert execution_layer["governance"]["replay_validation_required"] is True


def test_intelligence_gap_discovery_persists_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "ig1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -1.2,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
            {
                "trade_id": "ig2",
                "status": "closed",
                "result": "loss",
                "pnl_points": -1.1,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
            {
                "trade_id": "ig3",
                "status": "closed",
                "result": "win",
                "pnl_points": 0.6,
                "session": "london",
                "failure_cause": "none",
            },
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 1.9, "slippage_ratio": 1.6},
        replay_scope="full_replay",
    )
    assert result["self_suggestion_governor"]["safety_controls"]["sandbox_only"] is True
    latest_path = tmp_path / "memory" / "intelligence_gaps" / "intelligence_gap_latest.json"
    history_path = tmp_path / "memory" / "intelligence_gaps" / "intelligence_gap_history.json"
    assert latest_path.exists()
    assert history_path.exists()
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert payload["intelligence_gaps"]
    first_gap = payload["intelligence_gaps"][0]
    assert first_gap["sandbox_only"] is True
    assert first_gap["replay_validation_required"] is True


def test_synthetic_data_plane_expansion_generates_safe_candidates(tmp_path: Path) -> None:
    run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "spx1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "spx2", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london", "failure_cause": "none"},
            {"trade_id": "spx3", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "new_york", "failure_cause": "slippage_spike"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.8, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    latest_path = tmp_path / "memory" / "synthetic_data_planes" / "synthetic_data_planes_latest.json"
    history_path = tmp_path / "memory" / "synthetic_data_planes" / "synthetic_data_planes_history.json"
    assert latest_path.exists()
    assert history_path.exists()
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert payload["synthetic_data_planes"]
    first_plane = payload["synthetic_data_planes"][0]
    assert first_plane["synthetic_plane_name"]
    assert first_plane["governance"]["sandbox_only"] is True
    assert first_plane["governance"]["replay_validation_required"] is True


def test_capability_evolution_ladder_enforces_sandbox_replay_promotion_flow(tmp_path: Path) -> None:
    run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ce1", "status": "closed", "result": "loss", "pnl_points": -1.3, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "ce2", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "spread_spike"},
            {"trade_id": "ce3", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.0, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    candidates_path = tmp_path / "memory" / "capability_evolution" / "capability_candidates.json"
    validation_path = tmp_path / "memory" / "capability_evolution" / "capability_validation_history.json"
    promotion_path = tmp_path / "memory" / "capability_evolution" / "capability_promotion_registry.json"
    assert candidates_path.exists()
    assert validation_path.exists()
    assert promotion_path.exists()
    candidates_payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    assert candidates_payload["capability_candidates"]
    candidate = candidates_payload["capability_candidates"][0]
    assert candidate["lifecycle_stages"] == [
        "gap_detection",
        "capability_hypothesis_generation",
        "synthetic_prototype_construction",
        "replay_validation",
        "comparative_advantage_test",
        "conflict_check_unified_field",
        "governor_promotion_decision",
    ]
    assert candidate["governance"]["sandbox_only"] is True
    assert candidate["governance"]["live_deployment_allowed"] is False
    assert candidate["governance_decision"] in {"rejected", "quarantined", "sandbox_only_retained", "promoted"}
    registry_payload = json.loads(promotion_path.read_text(encoding="utf-8"))
    assert set(registry_payload) == {"rejected", "quarantined", "sandbox_only_retained", "promoted"}


def test_unified_market_intelligence_field_non_regression_with_meta_capability_layers(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ur1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "ur2", "status": "closed", "result": "win", "pnl_points": 0.9, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.4, "slippage_ratio": 1.2},
        replay_scope="focused_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert set(unified["components"]) == {
        "macro_state",
        "regime_state",
        "detector_reliability",
        "synthetic_feature_state",
        "negative_space_state",
        "invariant_break_state",
        "pain_geometry_risk",
        "counterfactual_evaluation",
        "liquidity_decay_state",
        "execution_microstructure_state",
        "adversarial_execution_state",
        "structural_memory_state",
        "latent_transition_hazard_state",
    }


def test_contradiction_arbitration_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ca1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "ca2", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.4, "slippage_ratio": 1.2},
        replay_scope="focused_replay",
    )
    contradiction_layer = result["contradiction_arbitration_and_belief_resolution_layer"]
    assert Path(contradiction_layer["paths"]["latest"]).exists()
    assert Path(contradiction_layer["paths"]["history"]).exists()
    assert Path(contradiction_layer["paths"]["belief_state_registry"]).exists()
    assert Path(contradiction_layer["paths"]["contradiction_events"]).exists()
    assert Path(contradiction_layer["paths"]["resolution_outcome_registry"]).exists()
    assert Path(contradiction_layer["paths"]["contextual_contradiction_clusters"]).exists()
    assert Path(contradiction_layer["paths"]["governance_state"]).exists()


def test_contradiction_arbitration_detects_directional_opposition_between_sources(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cd1", "status": "closed", "result": "loss", "pnl_points": -1.2, "entry_price": 2010.0, "average_fill_price": 2012.5, "signal_time": 10, "first_fill_time": 19, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cd2", "status": "closed", "result": "win", "pnl_points": 1.1, "entry_price": 2012.0, "average_fill_price": 2012.2, "signal_time": 20, "first_fill_time": 21, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.9, "slippage_ratio": 1.8},
        replay_scope="full_replay",
    )
    contradictions = result["contradiction_arbitration_and_belief_resolution_layer"]["contradictions"]
    assert any(item["contradiction_type"] == "directional_opposition" for item in contradictions)


def test_contradiction_arbitration_flags_high_confidence_vs_execution_hostility_conflict(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "ceh1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.2,
                "entry_price": 2010.0,
                "intended_entry_price": 2010.0,
                "average_fill_price": 2014.0,
                "signal_time": 10,
                "first_fill_time": 60,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
            {
                "trade_id": "ceh2",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.1,
                "entry_price": 2012.0,
                "intended_entry_price": 2012.0,
                "average_fill_price": 2015.0,
                "signal_time": 20,
                "first_fill_time": 75,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    contradictions = result["contradiction_arbitration_and_belief_resolution_layer"]["contradictions"]
    assert any(item["contradiction_type"] == "confidence_execution_conflict" for item in contradictions)


def test_contradiction_arbitration_updates_unified_field_additively_without_overwriting_base_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cu1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cu2", "status": "closed", "result": "win", "pnl_points": 0.9, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.7, "slippage_ratio": 1.5},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "contradiction_arbitration" in unified
    assert "contradiction_adjusted_confidence" in unified["confidence_structure"]
    assert "contradiction_multiplier" in unified["decision_refinements"]["risk_sizing"]


def test_contradiction_arbitration_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {
            "trade_id": "cg1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.2,
            "entry_price": 2010.0,
            "intended_entry_price": 2010.0,
            "average_fill_price": 2014.5,
            "signal_time": 10,
            "first_fill_time": 65,
            "session": "asia",
            "failure_cause": "execution_failure",
        },
        {
            "trade_id": "cg2",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.2,
            "entry_price": 2012.0,
            "intended_entry_price": 2012.0,
            "average_fill_price": 2016.0,
            "signal_time": 20,
            "first_fill_time": 80,
            "session": "asia",
            "failure_cause": "execution_failure",
        },
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    contradiction_gap_types = {
        "high_confidence_vs_execution_hostility_conflict",
        "chronic_risk_enable_vs_risk_disable_conflict",
        "persistent_continuation_vs_trap_conflict",
    }
    assert gap_types.intersection(contradiction_gap_types)


def test_contradiction_arbitration_governance_is_sandbox_and_replay_only(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cgov1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cgov2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.3, "slippage_ratio": 1.1},
        replay_scope="focused_replay",
    )
    governance = result["contradiction_arbitration_and_belief_resolution_layer"]["governance"]
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False
    assert governance["no_blind_live_rewrites"] is True


def test_contradiction_arbitration_history_rolls_and_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"ch{index}a", "status": "closed", "result": "loss", "pnl_points": -0.8},
                {"trade_id": f"ch{index}b", "status": "closed", "result": "win", "pnl_points": 0.6},
            ],
            market_state={"structure_state": "range"},
            replay_scope="focused_replay",
        )
    history_path = memory_root / "contradiction_arbitration" / "contradiction_arbitration_history.json"
    assert history_path.exists()
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(payload["snapshots"]) <= 200
    assert payload["snapshots"]


def test_calibration_uncertainty_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cuap1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cuap2", "status": "closed", "result": "win", "pnl_points": 0.9, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.4, "slippage_ratio": 1.2},
        replay_scope="focused_replay",
    )
    calibration = result["calibration_and_uncertainty_governance_layer"]
    assert Path(calibration["paths"]["latest"]).exists()
    assert Path(calibration["paths"]["history"]).exists()
    assert Path(calibration["paths"]["confidence_error_registry"]).exists()
    assert Path(calibration["paths"]["regime_reliability_registry"]).exists()
    assert Path(calibration["paths"]["governance_state"]).exists()


def test_calibration_uncertainty_adds_calibrated_confidence_without_overwriting_composite_confidence(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cuac1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cuac2", "status": "closed", "result": "win", "pnl_points": 1.1, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.6, "slippage_ratio": 1.3},
        replay_scope="full_replay",
    )
    confidence = result["unified_market_intelligence_field"]["confidence_structure"]
    assert "composite_confidence" in confidence
    assert "calibrated_confidence" in confidence
    assert "calibration_drift" in confidence
    assert "confidence_reliability_band" in confidence
    assert 0.0 <= confidence["composite_confidence"] <= 1.0
    assert 0.0 <= confidence["calibrated_confidence"] <= 1.0


def test_calibration_uncertainty_increases_pause_or_refusal_when_drift_and_execution_hostility_are_high(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "cuph1", "status": "closed", "result": "win", "pnl_points": 1.2, "session": "asia", "failure_cause": "none"},
            {"trade_id": "cuph2", "status": "closed", "result": "win", "pnl_points": 1.0, "session": "asia", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 1.0, "slippage_ratio": 1.0},
        replay_scope="focused_replay",
    )
    result = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {
                "trade_id": "cuph3",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.1,
                "intended_entry_price": 2010.0,
                "average_fill_price": 2015.0,
                "signal_time": 10,
                "first_fill_time": 70,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
            {
                "trade_id": "cuph4",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.1,
                "intended_entry_price": 2011.0,
                "average_fill_price": 2016.0,
                "signal_time": 20,
                "first_fill_time": 90,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="focused_replay",
    )
    behavior = result["unified_market_intelligence_field"]["decision_refinements"]["refusal_pause_behavior"]
    reasons = set(behavior["pause_reasons"] + behavior["refusal_reasons"])
    assert behavior["should_pause"] or behavior["should_refuse"]
    assert (
        "calibration_drift_elevated" in reasons
        or "calibration_uncertainty_refuse_guard" in reasons
        or "execution_adjusted_uncertainty_elevated" in reasons
    )


def test_calibration_uncertainty_updates_unified_risk_sizing_with_governed_multiplier(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cur1", "status": "closed", "result": "loss", "pnl_points": -1.1, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cur2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.8, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    risk = result["unified_market_intelligence_field"]["decision_refinements"]["risk_sizing"]
    assert "calibration_multiplier" in risk
    assert "calibration_adjusted_refined" in risk
    assert 0.25 <= risk["calibration_multiplier"] <= 1.0
    assert risk["calibration_adjusted_refined"] <= risk["refined"]


def test_calibration_uncertainty_feeds_contradiction_layer_input_confidence_path_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cuc1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cuc2", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.4, "slippage_ratio": 1.3},
        replay_scope="focused_replay",
    )
    confidence = result["unified_market_intelligence_field"]["confidence_structure"]
    calibrated = confidence["calibrated_confidence"]
    composite = confidence["composite_confidence"]
    contradiction = result["contradiction_arbitration_and_belief_resolution_layer"]
    assert contradiction["beliefs"]
    assert contradiction["beliefs"][0]["source_layer"] == "unified_market_intelligence_field"
    assert contradiction["beliefs"][0]["belief_confidence"] >= composite
    assert contradiction["beliefs"][0]["belief_confidence"] >= calibrated


def test_calibration_uncertainty_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "cug_base1", "status": "closed", "result": "win", "pnl_points": 1.1, "session": "asia", "failure_cause": "none"},
            {"trade_id": "cug_base2", "status": "closed", "result": "win", "pnl_points": 1.0, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 1.0, "slippage_ratio": 1.0},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {
                "trade_id": "cug1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.2,
                "intended_entry_price": 2010.0,
                "average_fill_price": 2015.0,
                "signal_time": 10,
                "first_fill_time": 70,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
            {
                "trade_id": "cug2",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.1,
                "intended_entry_price": 2012.0,
                "average_fill_price": 2017.0,
                "signal_time": 20,
                "first_fill_time": 85,
                "session": "asia",
                "failure_cause": "execution_failure",
            },
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "confidence_miscalibration_drift",
        "regime_reliability_decay",
        "chronic_overconfidence_under_execution_hostility",
    }
    assert gap_types.intersection(expected)


def test_capability_evolution_ladder_reads_prior_calibration_reliability_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "cul1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cul2", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.4, "slippage_ratio": 1.2},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "cul3", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cul4", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.5, "slippage_ratio": 1.3},
        replay_scope="focused_replay",
    )
    candidates_path = memory_root / "capability_evolution" / "capability_candidates.json"
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        assert "calibration_reliability_context" in candidates[0]
        assert 0.0 <= candidates[0]["calibration_reliability_context"]["prior_cycle_reliability"] <= 1.0


def test_calibration_uncertainty_history_rolls_and_missing_inputs_are_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"cuh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.8},
                {"trade_id": f"cuh{index}b", "status": "closed", "result": "win", "pnl_points": 0.6},
            ],
            market_state={"structure_state": "range"},
            replay_scope="focused_replay",
        )
    history_path = memory_root / "calibration_uncertainty" / "calibration_uncertainty_history.json"
    assert history_path.exists()
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(payload["snapshots"]) <= 200
    assert payload["snapshots"]
    assert "calibration_state" in payload["snapshots"][-1]


def test_calibration_uncertainty_governance_is_sandbox_and_replay_only(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cugov1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "cugov2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.1, "spread_ratio": 1.3, "slippage_ratio": 1.2},
        replay_scope="focused_replay",
    )
    governance = result["calibration_and_uncertainty_governance_layer"]["governance"]
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False
    assert governance["no_blind_live_self_rewrites"] is True


def test_adversarial_execution_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "ae1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -1.1,
                "failure_cause": "execution_failure",
                "intended_entry_price": 2010.0,
                "average_fill_price": 2015.0,
                "signal_time": 10,
                "first_fill_time": 70,
                "requested_size": 1.0,
                "filled_size": 0.5,
            },
            {"trade_id": "ae2", "status": "closed", "result": "win", "pnl_points": 0.5, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 2.5, "slippage_ratio": 2.2},
        replay_scope="focused_replay",
    )
    adversarial = result["adversarial_execution_intelligence_layer"]
    assert Path(adversarial["paths"]["latest"]).exists()
    assert Path(adversarial["paths"]["history"]).exists()
    assert Path(adversarial["paths"]["hostility_event_registry"]).exists()
    assert Path(adversarial["paths"]["contextual_hostility_clusters"]).exists()
    assert Path(adversarial["paths"]["hostility_governance_state"]).exists()
    assert Path(adversarial["paths"]["detector_reliability_registry"]).exists()


def test_adversarial_execution_layer_nonbreaking_with_missing_microstructure_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "aen1", "status": "closed", "result": "loss", "pnl_points": -0.6},
            {"trade_id": "aen2", "status": "closed", "result": "win", "pnl_points": 0.4},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    adversarial = result["adversarial_execution_intelligence_layer"]
    state = adversarial["adversarial_execution_state"]
    assert 0.0 <= state["hostile_execution_score"] <= 1.0
    assert 0.0 <= state["toxicity_proxy"] <= 1.0
    assert 0.0 <= state["historical_execution_hostility"] <= 1.0
    assert adversarial["governance"]["sandbox_only"] is True
    assert adversarial["governance"]["replay_validation_required"] is True
    assert adversarial["governance"]["live_deployment_allowed"] is False


def test_adversarial_execution_layer_detects_hostile_execution_state_under_spread_slippage_delay_partial_stress(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "aes1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.2,
                "failure_cause": "execution_failure",
                "intended_entry_price": 2010.0,
                "average_fill_price": 2017.0,
                "signal_time": 10,
                "first_fill_time": 90,
                "requested_size": 1.0,
                "filled_size": 0.35,
                "mae_after_fill": 4.5,
                "mfe_after_fill": 0.1,
            },
            {
                "trade_id": "aes2",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.2,
                "failure_cause": "partial_fill",
                "intended_entry_price": 2012.0,
                "average_fill_price": 2018.0,
                "signal_time": 20,
                "first_fill_time": 100,
                "requested_size": 1.0,
                "filled_size": 0.4,
                "mae_after_fill": 5.0,
                "mfe_after_fill": 0.2,
            },
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    state = result["adversarial_execution_intelligence_layer"]["adversarial_execution_state"]
    assert state["hostile_execution_score"] >= 0.55
    assert state["predatory_liquidity_state"] in {"elevated", "hostile"}
    assert state["quote_fade_proxy"] >= 0.45
    assert state["fill_collapse_risk"] >= 0.45


def test_adversarial_execution_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "aeu1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "aeu2", "status": "closed", "result": "win", "pnl_points": 0.7, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 2.1, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "adversarial_execution_state" in unified["components"]
    assert "hostility_adjusted_confidence" in unified["confidence_structure"]
    assert "adversarial_execution_multiplier" in unified["decision_refinements"]["risk_sizing"]


def test_adversarial_execution_layer_additively_influences_calibration_uncertainty_path(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "aec1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "aec2", "status": "closed", "result": "loss", "pnl_points": -0.4, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.8, "slippage_ratio": 2.7},
        replay_scope="focused_replay",
    )
    confidence = result["unified_market_intelligence_field"]["confidence_structure"]
    calibration_state = result["calibration_and_uncertainty_governance_layer"]["calibration_state"]
    assert "hostility_adjusted_confidence" in confidence
    assert confidence["hostility_adjusted_confidence"] <= confidence["composite_confidence"]
    assert "execution_adjusted_uncertainty" in calibration_state
    assert 0.0 <= calibration_state["execution_adjusted_uncertainty"] <= 1.0


def test_adversarial_execution_layer_additively_feeds_contradiction_confidence_execution_path(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "aed1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "aed2", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 2.7, "slippage_ratio": 2.6},
        replay_scope="full_replay",
    )
    contradiction = result["contradiction_arbitration_and_belief_resolution_layer"]
    assert any(item.get("source_layer") == "adversarial_execution_intelligence_layer" for item in contradiction["beliefs"])
    assert contradiction["arbitration"]["conflict_state"] in {"active", "clear"}


def test_adversarial_execution_layer_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {
            "trade_id": "aeg1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.3,
            "failure_cause": "execution_failure",
            "intended_entry_price": 2010.0,
            "average_fill_price": 2016.0,
            "signal_time": 10,
            "first_fill_time": 80,
            "requested_size": 1.0,
            "filled_size": 0.4,
            "mae_after_fill": 4.0,
            "mfe_after_fill": 0.2,
        },
        {
            "trade_id": "aeg2",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.3,
            "failure_cause": "partial_fill",
            "intended_entry_price": 2011.0,
            "average_fill_price": 2017.0,
            "signal_time": 20,
            "first_fill_time": 85,
            "requested_size": 1.0,
            "filled_size": 0.35,
            "mae_after_fill": 4.2,
            "mfe_after_fill": 0.1,
        },
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "persistent_hostile_execution_cluster",
        "chronic_adverse_selection_risk",
        "quote_fade_execution_fragility",
        "sweep_aftermath_fill_collapse_pattern",
    }
    assert gap_types.intersection(expected)


def test_capability_evolution_ladder_reads_prior_adversarial_hostility_context_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "ael1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "ael2", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 2.5, "slippage_ratio": 2.4},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "ael3", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "execution_failure"},
            {"trade_id": "ael4", "status": "closed", "result": "win", "pnl_points": 0.5, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 2.0, "slippage_ratio": 2.1},
        replay_scope="focused_replay",
    )
    assert second["adversarial_execution_intelligence_layer"]["adversarial_execution_state"]
    candidates_path = memory_root / "capability_evolution" / "capability_candidates.json"
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        context = candidates[0].get("adversarial_execution_context", {})
        assert "prior_cycle_hostility" in context
        assert 0.0 <= float(context["prior_cycle_hostility"]) <= 1.0


def test_structural_memory_graph_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "sm1", "status": "closed", "result": "loss", "pnl_points": -1.0, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "sm2", "status": "closed", "result": "win", "pnl_points": 0.8, "entry_price": 2011.0, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.3, "slippage_ratio": 1.2},
        replay_scope="focused_replay",
    )
    structural = result["structural_memory_graph_layer"]
    assert Path(structural["paths"]["latest"]).exists()
    assert Path(structural["paths"]["history"]).exists()
    assert Path(structural["paths"]["structural_context_registry"]).exists()
    assert Path(structural["paths"]["zone_magnet_registry"]).exists()
    assert Path(structural["paths"]["episodic_pattern_links"]).exists()
    assert Path(structural["paths"]["regime_memory_alignment_registry"]).exists()
    assert Path(structural["paths"]["structural_memory_governance_state"]).exists()


def test_structural_memory_graph_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "smn1", "status": "closed", "result": "loss", "pnl_points": -0.5},
            {"trade_id": "smn2", "status": "closed", "result": "win", "pnl_points": 0.4},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    structural_state = result["structural_memory_graph_layer"]["structural_memory_state"]
    assert structural_state["structural_memory_state"] in {"insufficient_data", "weak", "moderate", "strong"}
    assert 0.0 <= structural_state["historical_recurrence_score"] <= 1.0
    assert 0.0 <= structural_state["memory_reliability"] <= 1.0
    assert result["structural_memory_graph_layer"]["governance"]["sandbox_only"] is True


def test_structural_memory_graph_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "smu1", "status": "closed", "result": "loss", "pnl_points": -0.9, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "smu2", "status": "closed", "result": "win", "pnl_points": 0.7, "entry_price": 2012.0, "setup_type": "reversal", "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.5, "slippage_ratio": 1.3},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "structural_memory_state" in unified["components"]
    assert "historical_recurrence_score" in unified["confidence_structure"]
    assert "memory_reliability" in unified["confidence_structure"]


def test_structural_memory_graph_layer_additively_influences_confidence_and_risk_sizing(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "smc1", "status": "closed", "result": "loss", "pnl_points": -0.8, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "smc2", "status": "closed", "result": "loss", "pnl_points": -0.7, "entry_price": 2010.5, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "smc3", "status": "closed", "result": "win", "pnl_points": 0.6, "entry_price": 2011.0, "setup_type": "reversal", "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 1.9, "slippage_ratio": 1.8},
        replay_scope="full_replay",
    )
    confidence = result["unified_market_intelligence_field"]["confidence_structure"]
    risk = result["unified_market_intelligence_field"]["decision_refinements"]["risk_sizing"]
    assert "long_horizon_context_match" in confidence
    assert "memory_reliability" in confidence
    assert "memory_adjusted_confidence" in confidence
    assert "structural_memory_multiplier" in risk
    assert 0.25 <= risk["structural_memory_multiplier"] <= 1.0


def test_structural_memory_graph_layer_adds_pause_refusal_reasons_under_recurrent_structural_hostility(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "smh1", "status": "closed", "result": "loss", "pnl_points": -1.2, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "smh2", "status": "closed", "result": "win", "pnl_points": 0.2, "entry_price": 2010.1, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        {"trade_id": "smh3", "status": "closed", "result": "loss", "pnl_points": -1.0, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "smh4", "status": "closed", "result": "win", "pnl_points": 0.1, "entry_price": 2010.2, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        {"trade_id": "smh5", "status": "closed", "result": "loss", "pnl_points": -1.1, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "smh6", "status": "closed", "result": "win", "pnl_points": 0.15, "entry_price": 2010.2, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.1, "slippage_ratio": 2.0},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.1, "slippage_ratio": 2.0},
        replay_scope="full_replay",
    )
    behavior = second["unified_market_intelligence_field"]["decision_refinements"]["refusal_pause_behavior"]
    reasons = set(behavior["pause_reasons"] + behavior["refusal_reasons"])
    assert (
        "structural_memory_recurrence_hostility" in reasons
        or "structural_memory_reversal_refuse_guard" in reasons
        or "structural_memory_regime_misalignment" in reasons
    )


def test_structural_memory_graph_layer_feeds_contradiction_arbitration_belief_set_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "smb1", "status": "closed", "result": "loss", "pnl_points": -0.9, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "smb2", "status": "closed", "result": "win", "pnl_points": 0.6, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.8, "slippage_ratio": 1.6},
        replay_scope="full_replay",
    )
    contradiction = result["contradiction_arbitration_and_belief_resolution_layer"]
    assert any(item.get("source_layer") == "structural_memory_graph_layer" for item in contradiction["beliefs"])
    assert contradiction["arbitration"]["conflict_state"] in {"active", "clear"}


def test_structural_memory_graph_layer_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "smg1", "status": "closed", "result": "loss", "pnl_points": -1.0, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "smg2", "status": "closed", "result": "win", "pnl_points": 0.2, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        {"trade_id": "smg3", "status": "closed", "result": "loss", "pnl_points": -1.1, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "smg4", "status": "closed", "result": "win", "pnl_points": 0.15, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.9, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.9, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "low_structural_memory_reliability",
        "recurrent_structural_reversal_not_captured",
        "regime_memory_misalignment",
        "persistent_structural_magnet_behavior_unmodeled",
    }
    assert gap_types.intersection(expected)


def test_capability_evolution_ladder_reads_prior_structural_memory_context_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "sml1", "status": "closed", "result": "loss", "pnl_points": -0.9, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "sml2", "status": "closed", "result": "win", "pnl_points": 0.6, "entry_price": 2010.0, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.5, "slippage_ratio": 1.3},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "sml3", "status": "closed", "result": "loss", "pnl_points": -0.8, "entry_price": 2011.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "sml4", "status": "closed", "result": "win", "pnl_points": 0.5, "entry_price": 2011.0, "setup_type": "breakout", "session": "asia", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.6, "slippage_ratio": 1.4},
        replay_scope="focused_replay",
    )
    assert second["structural_memory_graph_layer"]["structural_memory_state"]
    candidates_path = memory_root / "capability_evolution" / "capability_candidates.json"
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        context = candidates[0].get("structural_memory_context", {})
        assert "prior_alignment_score" in context
        assert "context_coverage" in context
        assert 0.0 <= float(context["prior_alignment_score"]) <= 1.0


def test_structural_memory_graph_history_rolls_and_governance_is_sandbox_replay_only(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"smh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.6, "entry_price": 2010.0},
                {"trade_id": f"smh{index}b", "status": "closed", "result": "win", "pnl_points": 0.5, "entry_price": 2011.0},
            ],
            market_state={"structure_state": "range"},
            replay_scope="focused_replay",
        )
    history_path = memory_root / "structural_memory_graph" / "structural_memory_graph_history.json"
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(payload["snapshots"]) <= 200
    latest = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "smhl1", "status": "closed", "result": "loss", "pnl_points": -0.7, "entry_price": 2010.0},
            {"trade_id": "smhl2", "status": "closed", "result": "win", "pnl_points": 0.6, "entry_price": 2011.0},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    governance = latest["structural_memory_graph_layer"]["governance"]
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False
    assert governance["no_blind_live_self_rewrites"] is True


def test_latent_transition_hazard_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "lth1", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "lth2", "status": "closed", "result": "win", "pnl_points": 0.5, "setup_type": "reversal", "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.3, "slippage_ratio": 2.1},
        replay_scope="focused_replay",
    )
    latent = result["latent_transition_hazard_layer"]
    assert Path(latent["paths"]["latest"]).exists()
    assert Path(latent["paths"]["history"]).exists()
    assert Path(latent["paths"]["transition_hazard_registry"]).exists()
    assert Path(latent["paths"]["precursor_instability_events"]).exists()
    assert Path(latent["paths"]["historical_transition_match_registry"]).exists()
    assert Path(latent["paths"]["latent_transition_governance_state"]).exists()


def test_latent_transition_hazard_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ltn1", "status": "closed", "result": "loss", "pnl_points": -0.5},
            {"trade_id": "ltn2", "status": "closed", "result": "win", "pnl_points": 0.4},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    state = result["latent_transition_hazard_layer"]["latent_transition_hazard_state"]
    assert state["transition_hazard_state"] in {"stable", "watch", "elevated", "critical"}
    assert 0.0 <= state["transition_hazard_score"] <= 1.0
    assert 0.0 <= state["hazard_reliability"] <= 1.0
    assert result["latent_transition_hazard_layer"]["governance"]["sandbox_only"] is True


def test_latent_transition_hazard_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ltu1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "ltu2", "status": "closed", "result": "win", "pnl_points": 0.6, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.0, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "latent_transition_hazard_state" in unified["components"]
    assert "transition_hazard_score" in unified["confidence_structure"]
    assert "hazard_adjusted_confidence" in unified["confidence_structure"]


def test_latent_transition_hazard_layer_additively_influences_confidence_and_risk_sizing(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ltc1", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "ltc2", "status": "closed", "result": "loss", "pnl_points": -0.9, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "ltc3", "status": "closed", "result": "win", "pnl_points": 0.3, "setup_type": "reversal", "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.5, "slippage_ratio": 2.3},
        replay_scope="full_replay",
    )
    confidence = result["unified_market_intelligence_field"]["confidence_structure"]
    risk = result["unified_market_intelligence_field"]["decision_refinements"]["risk_sizing"]
    assert "transition_confidence_suppression" in confidence
    assert "hazard_adjusted_confidence" in confidence
    assert "transition_hazard_multiplier" in risk
    assert 0.25 <= risk["transition_hazard_multiplier"] <= 1.0


def test_latent_transition_hazard_layer_adds_pause_refusal_reasons_under_precursor_instability(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ltp1", "status": "closed", "result": "loss", "pnl_points": -1.2, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure", "intended_entry_price": 2010.0, "average_fill_price": 2017.0, "signal_time": 10, "first_fill_time": 95, "requested_size": 1.0, "filled_size": 0.35},
            {"trade_id": "ltp2", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "asia", "failure_cause": "partial_fill", "intended_entry_price": 2011.0, "average_fill_price": 2018.0, "signal_time": 15, "first_fill_time": 100, "requested_size": 1.0, "filled_size": 0.3},
            {"trade_id": "ltp3", "status": "closed", "result": "loss", "pnl_points": -0.9, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure", "intended_entry_price": 2012.0, "average_fill_price": 2019.0, "signal_time": 20, "first_fill_time": 105, "requested_size": 1.0, "filled_size": 0.25},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    behavior = result["unified_market_intelligence_field"]["decision_refinements"]["refusal_pause_behavior"]
    reasons = set(behavior["pause_reasons"] + behavior["refusal_reasons"])
    assert "latent_precursor_instability_pause" in reasons or "latent_transition_hazard_refuse_guard" in reasons


def test_latent_transition_hazard_layer_feeds_contradiction_arbitration_belief_set_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ltb1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "ltb2", "status": "closed", "result": "win", "pnl_points": 0.4, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.4, "slippage_ratio": 2.2},
        replay_scope="full_replay",
    )
    contradiction = result["contradiction_arbitration_and_belief_resolution_layer"]
    assert any(item.get("source_layer") == "latent_transition_hazard_layer" for item in contradiction["beliefs"])
    assert contradiction["arbitration"]["conflict_state"] in {"active", "clear"}


def test_latent_transition_hazard_layer_feeds_calibration_uncertainty_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ltk1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "ltk2", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.3, "slippage_ratio": 2.2},
        replay_scope="focused_replay",
    )
    calibration = result["calibration_and_uncertainty_governance_layer"]["calibration_state"]
    assert "latent_transition_context" in calibration
    assert 0.0 <= calibration["latent_transition_context"]["transition_hazard_score"] <= 1.0


def test_latent_transition_hazard_layer_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "ltg1", "status": "closed", "result": "loss", "pnl_points": -1.0, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "ltg2", "status": "closed", "result": "loss", "pnl_points": -0.9, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "ltg3", "status": "closed", "result": "loss", "pnl_points": -0.8, "setup_type": "breakout", "session": "asia", "failure_cause": "execution_failure"},
    ]
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "latent_transition_hazard_under_modeled",
        "hazard_directional_bias_mismatch",
        "hazard_reliability_decay",
        "precursor_instability_not_captured",
    }
    assert gap_types.intersection(expected)


def test_capability_evolution_ladder_reads_prior_latent_transition_context_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "ltl1", "status": "closed", "result": "loss", "pnl_points": -1.0, "failure_cause": "execution_failure"},
            {"trade_id": "ltl2", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.4, "slippage_ratio": 2.2},
        replay_scope="full_replay",
    )
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "ltl3", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "execution_failure"},
            {"trade_id": "ltl4", "status": "closed", "result": "win", "pnl_points": 0.4, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.0, "slippage_ratio": 1.9},
        replay_scope="focused_replay",
    )
    payload = json.loads((memory_root / "capability_evolution" / "capability_candidates.json").read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        context = candidates[0].get("latent_transition_context", {})
        assert "prior_cycle_transition_hazard_score" in context
        assert "context_coverage" in context
        assert 0.0 <= float(context["prior_cycle_transition_hazard_score"]) <= 1.0


def test_latent_transition_hazard_history_rolls_and_governance_is_sandbox_replay_only(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"lthh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.9},
                {"trade_id": f"lthh{index}b", "status": "closed", "result": "win", "pnl_points": 0.4},
            ],
            market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.0, "slippage_ratio": 1.9},
            replay_scope="focused_replay",
        )
    history_payload = json.loads((memory_root / "latent_transition_hazard" / "latent_transition_hazard_history.json").read_text(encoding="utf-8"))
    assert len(history_payload["snapshots"]) <= 200
    latest = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "lthhl1", "status": "closed", "result": "loss", "pnl_points": -0.8},
            {"trade_id": "lthhl2", "status": "closed", "result": "win", "pnl_points": 0.5},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.2, "slippage_ratio": 2.0},
        replay_scope="focused_replay",
    )
    governance = latest["latent_transition_hazard_layer"]["governance"]
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False
    assert governance["no_blind_live_self_rewrites"] is True
