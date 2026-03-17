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
        "deception_inference_state",
        "structural_memory_state",
        "latent_transition_hazard_state",
        "transfer_robustness_state",
        "causal_intervention_robustness_state",
        "temporal_execution_state",
        "decision_policy_state",
        "capital_allocation_state",
        "self_expansion_quality_state",
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
        "self_expansion_quality_evaluation",
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
        "deception_inference_state",
        "structural_memory_state",
        "latent_transition_hazard_state",
        "transfer_robustness_state",
        "causal_intervention_robustness_state",
        "temporal_execution_state",
        "decision_policy_state",
        "capital_allocation_state",
        "self_expansion_quality_state",
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


def test_dynamic_market_maker_deception_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dm1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "dm2", "status": "closed", "result": "win", "pnl_points": 0.6, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 2.2, "slippage_ratio": 2.0},
        replay_scope="focused_replay",
    )
    deception = result["dynamic_market_maker_deception_inference_layer"]
    assert Path(deception["paths"]["latest"]).exists()
    assert Path(deception["paths"]["history"]).exists()
    assert Path(deception["paths"]["deception_event_registry"]).exists()
    assert Path(deception["paths"]["deception_context_registry"]).exists()
    assert Path(deception["paths"]["deception_reliability_registry"]).exists()
    assert Path(deception["paths"]["deception_governance_state"]).exists()


def test_dynamic_market_maker_deception_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmn1", "status": "closed", "result": "loss", "pnl_points": -0.5},
            {"trade_id": "dmn2", "status": "closed", "result": "win", "pnl_points": 0.4},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    deception_state = result["dynamic_market_maker_deception_inference_layer"]["deception_state"]
    assert deception_state["deception_state"] in {"normal", "elevated", "hostile", "insufficient_data"}
    assert 0.0 <= deception_state["deception_score"] <= 1.0
    assert 0.0 <= deception_state["deception_reliability"] <= 1.0
    governance = result["dynamic_market_maker_deception_inference_layer"]["governance"]
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False


def test_dynamic_market_maker_deception_layer_detects_engineered_move_under_sweep_quotefade_partialfill_stress(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "dms1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.2,
                "failure_cause": "execution_failure",
                "intended_entry_price": 2010.0,
                "average_fill_price": 2017.5,
                "signal_time": 10,
                "first_fill_time": 90,
                "requested_size": 1.0,
                "filled_size": 0.3,
                "mae_after_fill": 4.2,
                "mfe_after_fill": 0.1,
            },
            {
                "trade_id": "dms2",
                "status": "closed",
                "result": "loss",
                "pnl_points": -0.2,
                "failure_cause": "partial_fill",
                "intended_entry_price": 2012.0,
                "average_fill_price": 2018.2,
                "signal_time": 20,
                "first_fill_time": 100,
                "requested_size": 1.0,
                "filled_size": 0.35,
                "mae_after_fill": 4.8,
                "mfe_after_fill": 0.2,
            },
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 3.1, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    state = result["dynamic_market_maker_deception_inference_layer"]["deception_state"]
    assert state["deception_score"] >= 0.55
    assert state["engineered_move_probability"] >= 0.5
    assert state["liquidity_bait_risk"] >= 0.5
    assert state["inventory_defense_proxy"] >= 0.45


def test_dynamic_market_maker_deception_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmu1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "dmu2", "status": "closed", "result": "win", "pnl_points": 0.7, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 2.1, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "deception_inference_state" in unified["components"]


def test_dynamic_market_maker_deception_layer_additively_updates_unified_confidence_and_risk_sizing(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmc1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "dmc2", "status": "closed", "result": "loss", "pnl_points": -0.4, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.9, "slippage_ratio": 2.8},
        replay_scope="focused_replay",
    )
    confidence = result["unified_market_intelligence_field"]["confidence_structure"]
    risk_sizing = result["unified_market_intelligence_field"]["decision_refinements"]["risk_sizing"]
    assert "deception_adjusted_confidence" in confidence
    assert confidence["deception_adjusted_confidence"] <= confidence["composite_confidence"]
    assert "deception_multiplier" in risk_sizing
    assert 0.25 <= float(risk_sizing["deception_multiplier"]) <= 1.0


def test_dynamic_market_maker_deception_layer_additively_updates_refusal_pause_behavior(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmr1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "dmr2", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 3.2, "slippage_ratio": 3.1},
        replay_scope="full_replay",
    )
    behavior = result["unified_market_intelligence_field"]["decision_refinements"]["refusal_pause_behavior"]
    all_reasons = set(behavior["pause_reasons"]) | set(behavior["refusal_reasons"])
    assert any(reason.startswith("deception_") for reason in all_reasons)


def test_dynamic_market_maker_deception_layer_feeds_contradiction_arbitration_with_deception_belief(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmd1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "dmd2", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.8, "slippage_ratio": 2.6},
        replay_scope="full_replay",
    )
    contradiction = result["contradiction_arbitration_and_belief_resolution_layer"]
    assert any(item.get("source_layer") == "dynamic_market_maker_deception_inference_layer" for item in contradiction["beliefs"])
    contradiction_types = {item.get("contradiction_type") for item in contradiction["contradictions"]}
    assert "continuation_vs_engineered_move" in contradiction_types or contradiction["arbitration"]["conflict_state"] in {"active", "clear"}


def test_dynamic_market_maker_deception_layer_feeds_calibration_uncertainty_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmcal1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "dmcal2", "status": "closed", "result": "loss", "pnl_points": -0.4, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.7, "slippage_ratio": 2.6},
        replay_scope="focused_replay",
    )
    calibration_state = result["calibration_and_uncertainty_governance_layer"]["calibration_state"]
    assert "deception_context" in calibration_state
    assert 0.0 <= calibration_state["deception_context"]["deception_score"] <= 1.0
    assert 0.0 <= calibration_state["execution_adjusted_uncertainty"] <= 1.0


def test_dynamic_market_maker_deception_layer_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {
            "trade_id": "dmg1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.3,
            "failure_cause": "execution_failure",
            "intended_entry_price": 2010.0,
            "average_fill_price": 2016.5,
            "signal_time": 10,
            "first_fill_time": 80,
            "requested_size": 1.0,
            "filled_size": 0.35,
            "mae_after_fill": 4.0,
            "mfe_after_fill": 0.2,
        },
        {
            "trade_id": "dmg2",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.3,
            "failure_cause": "partial_fill",
            "intended_entry_price": 2011.0,
            "average_fill_price": 2017.0,
            "signal_time": 20,
            "first_fill_time": 85,
            "requested_size": 1.0,
            "filled_size": 0.3,
            "mae_after_fill": 4.3,
            "mfe_after_fill": 0.1,
        },
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 3.2, "slippage_ratio": 3.1},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 3.2, "slippage_ratio": 3.1},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "persistent_engineered_move_deception_cluster",
        "liquidity_bait_recurrence_gap",
        "sweep_trap_deception_under_modeled",
        "deception_reliability_decay",
    }
    assert gap_types.intersection(expected)


def test_capability_evolution_ladder_reads_prior_deception_context_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "dml1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "dml2", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 2.6, "slippage_ratio": 2.5},
        replay_scope="full_replay",
    )
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "dml3", "status": "closed", "result": "loss", "pnl_points": -0.7, "failure_cause": "execution_failure"},
            {"trade_id": "dml4", "status": "closed", "result": "win", "pnl_points": 0.5, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.4, "slippage_ratio": 2.3},
        replay_scope="focused_replay",
    )
    candidates_path = memory_root / "capability_evolution" / "capability_candidates.json"
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        context = candidates[0].get("deception_inference_context", {})
        assert "prior_cycle_deception_score" in context
        assert "prior_cycle_deception_reliability" in context
        assert 0.0 <= float(context["prior_cycle_deception_score"]) <= 1.0
        assert 0.0 <= float(context["prior_cycle_deception_reliability"]) <= 1.0


def test_dynamic_market_maker_deception_layer_governance_is_sandbox_and_replay_only(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "dmgov1", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "execution_failure"},
            {"trade_id": "dmgov2", "status": "closed", "result": "win", "pnl_points": 0.7, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.8, "slippage_ratio": 1.6},
        replay_scope="focused_replay",
    )
    governance = result["dynamic_market_maker_deception_inference_layer"]["governance"]
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False
    assert governance["no_blind_live_self_rewrites"] is True


def test_dynamic_market_maker_deception_layer_history_rolls_and_is_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"dmh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.8},
                {"trade_id": f"dmh{index}b", "status": "closed", "result": "win", "pnl_points": 0.6},
            ],
            market_state={"structure_state": "range"},
            replay_scope="focused_replay",
        )
    history_path = memory_root / "deception_inference" / "deception_inference_history.json"
    assert history_path.exists()
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert payload["snapshots"]
    assert len(payload["snapshots"]) <= 200


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


def test_self_expansion_quality_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "seq1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "seq2", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.3, "spread_ratio": 1.6, "slippage_ratio": 1.4},
        replay_scope="focused_replay",
    )
    quality = result["self_expansion_quality_layer"]
    assert Path(quality["paths"]["latest"]).exists()
    assert Path(quality["paths"]["history"]).exists()
    assert Path(quality["paths"]["capability_quality_registry"]).exists()
    assert Path(quality["paths"]["capability_overlap_registry"]).exists()
    assert Path(quality["paths"]["promotion_maturity_registry"]).exists()
    assert Path(quality["paths"]["expansion_regression_watchlist"]).exists()
    assert Path(quality["paths"]["governance_state"]).exists()


def test_self_expansion_quality_layer_returns_expected_quality_schema(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "seqs1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "seqs2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "slippage_spike"},
            {"trade_id": "seqs3", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.0, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    quality = result["self_expansion_quality_layer"]
    expected_keys = {
        "self_expansion_quality_state",
        "capability_novelty_score",
        "redundancy_risk",
        "durability_score",
        "transferability_score",
        "regression_risk",
        "capability_overlap_map",
        "expansion_quality_score",
        "promotion_maturity",
        "governance_flags",
        "quality_components",
        "paths",
    }
    assert expected_keys.issubset(set(quality))
    for score_key in (
        "capability_novelty_score",
        "redundancy_risk",
        "durability_score",
        "transferability_score",
        "regression_risk",
        "expansion_quality_score",
    ):
        assert 0.0 <= float(quality[score_key]) <= 1.0
    assert quality["self_expansion_quality_state"] in {"healthy", "watch", "degraded", "critical"}
    assert quality["promotion_maturity"] in {
        "seeded",
        "sandbox_validated",
        "cross_context_validated",
        "promotion_ready",
        "promotion_hardened",
    }


def test_self_expansion_quality_layer_is_sandbox_and_replay_governed(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "seqg1", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "seqg2", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.4, "slippage_ratio": 1.3},
        replay_scope="focused_replay",
    )
    flags = result["self_expansion_quality_layer"]["governance_flags"]
    assert flags["sandbox_only"] is True
    assert flags["replay_validation_required"] is True
    assert flags["live_deployment_allowed"] is False
    assert flags["no_blind_live_self_rewrites"] is True


def test_self_expansion_quality_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "seqm1", "status": "closed", "result": "loss", "pnl_points": -0.4},
            {"trade_id": "seqm2", "status": "closed", "result": "win", "pnl_points": 0.3},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    quality = result["self_expansion_quality_layer"]
    assert quality["paths"]["latest"]
    assert isinstance(quality["capability_overlap_map"], dict)
    assert isinstance(quality["quality_components"], dict)


def test_self_expansion_quality_feeds_self_suggestion_governor_discipline_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    quality_dir = memory_root / "self_expansion_quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    (quality_dir / "self_expansion_quality_latest.json").write_text(
        json.dumps(
            {
                "self_expansion_quality_state": "critical",
                "integration_enabled": True,
                "expansion_quality_score": 0.2,
                "redundancy_risk": 0.9,
                "regression_risk": 0.85,
                "durability_score": 0.25,
                "transferability_score": 0.3,
                "quality_components": {"promotion_confidence_multiplier": 0.8, "quarantine_pressure_delta": 0.15},
            }
        ),
        encoding="utf-8",
    )
    result = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "seqd1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "seqd2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "slippage_spike"},
            {"trade_id": "seqd3", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.0, "slippage_ratio": 1.8},
        replay_scope="full_replay",
    )
    discipline = result["self_suggestion_governor"]["anti_noise_controls"]["self_expansion_quality_discipline"]
    assert discipline["quality_threshold_delta"] > 0.0
    assert discipline["expansion_rate_limit"] == 1
    assert 0.0 <= discipline["expansion_quality_score"] <= 1.0


def test_self_expansion_quality_feeds_capability_evolution_ladder_confidence_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    quality_dir = memory_root / "self_expansion_quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    (quality_dir / "self_expansion_quality_latest.json").write_text(
        json.dumps(
            {
                "self_expansion_quality_state": "degraded",
                "integration_enabled": True,
                "expansion_quality_score": 0.35,
                "redundancy_risk": 0.7,
                "regression_risk": 0.65,
                "quality_components": {"promotion_confidence_multiplier": 0.78, "quarantine_pressure_delta": 0.12},
                "promotion_maturity": "sandbox_validated",
            }
        ),
        encoding="utf-8",
    )
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "seql1", "status": "closed", "result": "loss", "pnl_points": -1.1, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "seql2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "spread_spike"},
            {"trade_id": "seql3", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.9, "spread_ratio": 2.1, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    payload = json.loads((memory_root / "capability_evolution" / "capability_candidates.json").read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        candidate = candidates[0]
        assert "self_expansion_quality_context" in candidate
        replay = candidate["replay_validation"]
        assert replay["score"] <= replay["raw_score"]
        assert candidate["promotion_maturity"] in {
            "seeded",
            "sandbox_validated",
            "cross_context_validated",
            "promotion_ready",
            "promotion_hardened",
        }


def test_self_expansion_quality_history_rolls_bounded(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"seqh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "execution_failure"},
                {"trade_id": f"seqh{index}b", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london", "failure_cause": "none"},
            ],
            market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.8, "slippage_ratio": 1.6},
            replay_scope="focused_replay",
        )
    history_payload = json.loads((memory_root / "self_expansion_quality" / "self_expansion_quality_history.json").read_text(encoding="utf-8"))
    assert history_payload["snapshots"]
    assert len(history_payload["snapshots"]) <= 200


def test_cross_regime_transfer_robustness_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "trp1", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "trp2", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.9, "slippage_ratio": 1.7},
        replay_scope="focused_replay",
    )
    transfer = result["cross_regime_transfer_robustness_layer"]
    assert Path(transfer["paths"]["latest"]).exists()
    assert Path(transfer["paths"]["history"]).exists()
    assert Path(transfer["paths"]["context_transfer_registry"]).exists()
    assert Path(transfer["paths"]["context_failure_clusters"]).exists()
    assert Path(transfer["paths"]["transfer_penalty_registry"]).exists()
    assert Path(transfer["paths"]["overfit_watchlist"]).exists()
    assert Path(transfer["paths"]["transfer_robustness_governance_state"]).exists()


def test_cross_regime_transfer_robustness_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "trn1", "status": "closed", "result": "loss", "pnl_points": -0.3},
            {"trade_id": "trn2", "status": "closed", "result": "flat", "pnl_points": 0.0},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    transfer = result["cross_regime_transfer_robustness_layer"]
    assert 0.0 <= transfer["cross_regime_transfer_score"] <= 1.0
    assert 0.0 <= transfer["overfit_risk"] <= 1.0
    assert transfer["governance_flags"]["sandbox_only"] is True
    assert transfer["governance_flags"]["replay_validation_required"] is True
    assert transfer["governance_flags"]["live_deployment_allowed"] is False


def test_cross_regime_transfer_robustness_layer_returns_expected_schema(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "trs1", "status": "closed", "result": "loss", "pnl_points": -0.4, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "trs2", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "new_york", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.2, "spread_ratio": 1.6, "slippage_ratio": 1.5},
        replay_scope="full_replay",
    )
    transfer = result["cross_regime_transfer_robustness_layer"]
    expected_keys = {
        "transfer_robustness_state",
        "cross_regime_transfer_score",
        "session_transfer_score",
        "volatility_transfer_score",
        "liquidity_transfer_score",
        "overfit_risk",
        "robustness_reliability",
        "context_failure_clusters",
        "promotion_transfer_penalty",
        "governance_flags",
        "paths",
    }
    assert expected_keys.issubset(set(transfer))


def test_cross_regime_transfer_robustness_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tru1", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "tru2", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.0, "slippage_ratio": 1.8},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "transfer_robustness_state" in unified["components"]
    assert "cross_regime_transfer_score" in unified["confidence_structure"]


def test_cross_regime_transfer_robustness_layer_additively_influences_risk_sizing_and_refusal_pause_behavior(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "trr1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "trr2", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "trr3", "status": "closed", "result": "loss", "pnl_points": -0.6, "session": "asia", "failure_cause": "execution_failure"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.9, "spread_ratio": 3.0, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    refinements = result["unified_market_intelligence_field"]["decision_refinements"]
    assert "transfer_robustness_multiplier" in refinements["risk_sizing"]
    assert 0.25 <= float(refinements["risk_sizing"]["transfer_robustness_multiplier"]) <= 1.0
    behavior = refinements["refusal_pause_behavior"]
    all_reasons = set(behavior.get("refusal_reasons", [])) | set(behavior.get("pause_reasons", []))
    assert any(reason.startswith("transfer_") for reason in all_reasons)


def test_cross_regime_transfer_robustness_layer_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "trg1", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "trg2", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia", "failure_cause": "execution_failure"},
        {"trade_id": "trg3", "status": "closed", "result": "loss", "pnl_points": -0.6, "session": "asia", "failure_cause": "execution_failure"},
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.8, "slippage_ratio": 2.7},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.8, "slippage_ratio": 2.7},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "cross_regime_transfer_breakdown",
        "session_transfer_instability",
        "volatility_transfer_failure",
        "liquidity_transfer_failure",
        "overfit_narrow_regime_dependency",
    }
    assert gap_types.intersection(expected)


def test_cross_regime_transfer_robustness_layer_feeds_self_expansion_quality_transferability_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tre1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "tre2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "slippage_spike"},
            {"trade_id": "tre3", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.4, "slippage_ratio": 2.2},
        replay_scope="full_replay",
    )
    quality = result["self_expansion_quality_layer"]
    assert 0.0 <= quality["transferability_score"] <= 1.0
    components = quality["quality_components"]
    assert "cross_regime_transfer_score_context" in components
    assert "transfer_overfit_risk_context" in components


def test_capability_evolution_ladder_reads_prior_transfer_robustness_context_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "trl1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "trl2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "execution_failure"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.3, "slippage_ratio": 2.1},
        replay_scope="full_replay",
    )
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "trl3", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "trl4", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "london", "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.9, "slippage_ratio": 1.7},
        replay_scope="focused_replay",
    )
    payload = json.loads((memory_root / "capability_evolution" / "capability_candidates.json").read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        context = candidates[0].get("transfer_robustness_context", {})
        assert "prior_cycle_transfer_score" in context
        assert "prior_cycle_promotion_transfer_penalty" in context
        assert "prior_cycle_overfit_risk" in context


def test_cross_regime_transfer_robustness_history_rolls_and_governance_is_sandbox_replay_only(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        result = run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"trh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.6, "session": "asia", "failure_cause": "execution_failure"},
                {"trade_id": f"trh{index}b", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "london", "failure_cause": "none"},
            ],
            market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 2.0, "slippage_ratio": 1.8},
            replay_scope="focused_replay",
        )
    transfer = result["cross_regime_transfer_robustness_layer"]
    flags = transfer["governance_flags"]
    assert flags["sandbox_only"] is True
    assert flags["replay_validation_required"] is True
    assert flags["live_deployment_allowed"] is False
    history_payload = json.loads((memory_root / "transfer_robustness" / "transfer_robustness_history.json").read_text(encoding="utf-8"))
    assert history_payload["snapshots"]
    assert len(history_payload["snapshots"]) <= 200


def test_cross_regime_transfer_robustness_penalizes_narrow_regime_overfit(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tro1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "tro2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "tro3", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "tro4", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia", "failure_cause": "execution_failure"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.2, "slippage_ratio": 3.1},
        replay_scope="full_replay",
    )
    transfer = result["cross_regime_transfer_robustness_layer"]
    assert transfer["overfit_risk"] >= 0.6
    assert transfer["promotion_transfer_penalty"] > 0.0
    watchlist = json.loads(Path(transfer["paths"]["overfit_watchlist"]).read_text(encoding="utf-8"))
    assert watchlist["watchlist"]


def test_causal_intervention_counterfactual_robustness_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cip1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
            {"trade_id": "cip2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.8, "slippage_ratio": 1.6},
        replay_scope="focused_replay",
    )
    causal = result["causal_intervention_counterfactual_robustness_layer"]
    assert Path(causal["paths"]["latest"]).exists()
    assert Path(causal["paths"]["history"]).exists()
    assert Path(causal["paths"]["intervention_context_registry"]).exists()
    assert Path(causal["paths"]["intervention_axis_reliability_registry"]).exists()
    assert Path(causal["paths"]["false_improvement_watchlist"]).exists()
    assert Path(causal["paths"]["intervention_priority_trace"]).exists()
    assert Path(causal["paths"]["causal_intervention_governance_state"]).exists()


def test_causal_intervention_counterfactual_robustness_layer_returns_expected_schema(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cis1", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "cis2", "status": "closed", "result": "loss", "pnl_points": -0.6, "session": "asia"},
            {"trade_id": "cis3", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "new_york"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.2, "slippage_ratio": 2.1},
        replay_scope="full_replay",
    )
    causal = result["causal_intervention_counterfactual_robustness_layer"]
    expected_keys = {
        "intervention_quality_state",
        "intervention_priority_score",
        "counterfactual_robustness_score",
        "primary_intervention_axis",
        "intervention_consistency",
        "intervention_reliability",
        "context_sensitive_intervention_map",
        "false_improvement_risk",
        "causal_confidence_proxy",
        "governance_flags",
        "paths",
    }
    assert expected_keys.issubset(set(causal))


def test_causal_intervention_counterfactual_robustness_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cin1", "status": "closed", "result": "loss", "pnl_points": -0.2},
            {"trade_id": "cin2", "status": "closed", "result": "flat", "pnl_points": 0.0},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    causal = result["causal_intervention_counterfactual_robustness_layer"]
    assert 0.0 <= causal["intervention_priority_score"] <= 1.0
    assert 0.0 <= causal["counterfactual_robustness_score"] <= 1.0
    assert 0.0 <= causal["false_improvement_risk"] <= 1.0
    assert causal["governance_flags"]["sandbox_only"] is True
    assert causal["governance_flags"]["replay_validation_required"] is True
    assert causal["governance_flags"]["live_deployment_allowed"] is False


def test_causal_intervention_counterfactual_robustness_layer_derives_primary_intervention_axis_from_counterfactuals(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cia1", "status": "closed", "result": "loss", "pnl_points": -1.1, "session": "asia"},
            {"trade_id": "cia2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "cia3", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.0, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    causal = result["causal_intervention_counterfactual_robustness_layer"]
    assert causal["primary_intervention_axis"] == "opposite_trade"


def test_causal_intervention_counterfactual_robustness_layer_computes_false_improvement_risk_under_narrow_context_concentration(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cir1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia"},
            {"trade_id": "cir2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
            {"trade_id": "cir3", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "cir4", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 2.9},
        replay_scope="full_replay",
    )
    causal = result["causal_intervention_counterfactual_robustness_layer"]
    assert causal["false_improvement_risk"] >= 0.6


def test_causal_intervention_counterfactual_robustness_layer_history_rolls_and_governance_is_sandbox_replay_only(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        result = run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"cih{index}a", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia"},
                {"trade_id": f"cih{index}b", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "london"},
            ],
            market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.1, "slippage_ratio": 2.0},
            replay_scope="focused_replay",
        )
    causal = result["causal_intervention_counterfactual_robustness_layer"]
    flags = causal["governance_flags"]
    assert flags["sandbox_only"] is True
    assert flags["replay_validation_required"] is True
    assert flags["live_deployment_allowed"] is False
    history_payload = json.loads(
        (memory_root / "causal_intervention_robustness" / "causal_intervention_robustness_history.json").read_text(encoding="utf-8")
    )
    assert history_payload["snapshots"]
    assert len(history_payload["snapshots"]) <= 200


def test_causal_intervention_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "ciu1", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "ciu2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.1, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "causal_intervention_robustness_state" in unified["components"]
    assert "counterfactual_robustness_score" in unified["confidence_structure"]
    assert "causal_confidence_proxy" in unified["confidence_structure"]


def test_causal_intervention_layer_additively_influences_risk_sizing_and_refusal_pause_behavior(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cib1", "status": "closed", "result": "loss", "pnl_points": -1.1, "session": "asia"},
            {"trade_id": "cib2", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia"},
            {"trade_id": "cib3", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
            {"trade_id": "cib4", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.1, "spread_ratio": 3.4, "slippage_ratio": 3.2},
        replay_scope="full_replay",
    )
    refinements = result["unified_market_intelligence_field"]["decision_refinements"]
    assert "causal_intervention_multiplier" in refinements["risk_sizing"]
    assert 0.25 <= float(refinements["risk_sizing"]["causal_intervention_multiplier"]) <= 1.0
    behavior = refinements["refusal_pause_behavior"]
    all_reasons = set(behavior.get("refusal_reasons", [])) | set(behavior.get("pause_reasons", []))
    assert any(reason.startswith("causal_") for reason in all_reasons)


def test_causal_intervention_layer_feeds_self_suggestion_governor_gap_detection(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    trade_outcomes = [
        {"trade_id": "cig1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia"},
        {"trade_id": "cig2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
        {"trade_id": "cig3", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
        {"trade_id": "cig4", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia"},
    ]
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 2.9},
        replay_scope="full_replay",
    )
    second = run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 2.9},
        replay_scope="focused_replay",
    )
    gap_types = {item.get("gap_type") for item in second["self_suggestion_governor"]["detected_gaps"]}
    expected = {
        "causal_intervention_robustness_breakdown",
        "false_improvement_risk_elevated",
        "intervention_axis_instability",
        "low_intervention_reliability",
    }
    assert gap_types.intersection(expected)


def test_causal_intervention_layer_feeds_self_expansion_quality_components_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cie1", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
            {"trade_id": "cie2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "cie3", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.3, "slippage_ratio": 2.1},
        replay_scope="full_replay",
    )
    quality = result["self_expansion_quality_layer"]
    components = quality["quality_components"]
    assert "causal_counterfactual_robustness_context" in components
    assert "causal_false_improvement_pressure" in components
    assert "causal_intervention_reliability_context" in components


def test_capability_evolution_ladder_reads_prior_causal_intervention_context_nonbreaking(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "cil1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia"},
            {"trade_id": "cil2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.9, "spread_ratio": 2.7, "slippage_ratio": 2.5},
        replay_scope="full_replay",
    )
    run_self_evolving_indicator_layer(
        memory_root=memory_root,
        trade_outcomes=[
            {"trade_id": "cil3", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "cil4", "status": "closed", "result": "win", "pnl_points": 0.5, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.0, "slippage_ratio": 1.8},
        replay_scope="focused_replay",
    )
    payload = json.loads((memory_root / "capability_evolution" / "capability_candidates.json").read_text(encoding="utf-8"))
    candidates = payload.get("capability_candidates", [])
    if candidates:
        context = candidates[0].get("intervention_robustness_context", {})
        assert "prior_cycle_counterfactual_robustness_score" in context
        assert "prior_cycle_intervention_reliability" in context
        assert "prior_cycle_false_improvement_risk" in context


def test_hierarchical_decision_policy_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdp1", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "hdp2", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 1.9, "slippage_ratio": 1.8},
        replay_scope="full_replay",
    )
    policy = result["hierarchical_decision_policy_layer"]
    assert Path(policy["paths"]["latest"]).exists()
    assert Path(policy["paths"]["history"]).exists()
    assert Path(policy["paths"]["policy_reason_registry"]).exists()
    assert Path(policy["paths"]["policy_conflict_registry"]).exists()
    assert Path(policy["paths"]["policy_transition_trace"]).exists()
    assert Path(policy["paths"]["decision_policy_governance_state"]).exists()


def test_hierarchical_decision_policy_layer_returns_expected_schema(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hds1", "status": "closed", "result": "loss", "pnl_points": -0.9},
            {"trade_id": "hds2", "status": "closed", "result": "loss", "pnl_points": -0.7},
            {"trade_id": "hds3", "status": "closed", "result": "win", "pnl_points": 0.5},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.3, "slippage_ratio": 2.1},
        replay_scope="full_replay",
    )
    policy = result["hierarchical_decision_policy_layer"]
    expected_keys = {
        "decision_policy_state",
        "dominant_policy_mode",
        "recommended_policy_posture",
        "survival_priority_score",
        "opportunity_priority_score",
        "refusal_priority_score",
        "deferral_priority_score",
        "dominant_reason_cluster",
        "policy_conflict_score",
        "policy_reliability",
        "policy_risk_multiplier",
        "policy_confidence_adjustment",
        "governance_flags",
        "paths",
    }
    assert expected_keys.issubset(set(policy))


def test_hierarchical_decision_policy_layer_adds_unified_field_components_without_overwriting_existing_fields(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdu1", "status": "closed", "result": "loss", "pnl_points": -0.7},
            {"trade_id": "hdu2", "status": "closed", "result": "win", "pnl_points": 0.5},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.8, "slippage_ratio": 1.7},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "decision_policy_state" in unified["components"]
    assert "decision_policy" in unified["decision_refinements"]
    assert "policy_reliability" in unified["confidence_structure"]


def test_hierarchical_decision_policy_layer_additively_influences_risk_sizing_and_refusal_pause_behavior(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdb1", "status": "closed", "result": "loss", "pnl_points": -1.1, "session": "asia"},
            {"trade_id": "hdb2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
            {"trade_id": "hdb3", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.1, "spread_ratio": 3.3, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    refinements = result["unified_market_intelligence_field"]["decision_refinements"]
    assert "decision_policy_multiplier" in refinements["risk_sizing"]
    assert 0.25 <= float(refinements["risk_sizing"]["decision_policy_multiplier"]) <= 1.0
    behavior = refinements["refusal_pause_behavior"]
    all_reasons = set(behavior.get("refusal_reasons", [])) | set(behavior.get("pause_reasons", []))
    assert any(reason.startswith("decision_policy_") for reason in all_reasons)


def test_hierarchical_decision_policy_layer_dominates_survival_when_contradiction_and_calibration_fragility_are_high(
    tmp_path: Path,
) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdc1", "status": "closed", "result": "loss", "pnl_points": -1.2, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "hdc2", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "hdc3", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia", "failure_cause": "execution_failure"},
            {"trade_id": "hdc4", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia", "failure_cause": "execution_failure"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.2, "spread_ratio": 3.4, "slippage_ratio": 3.3},
        replay_scope="full_replay",
    )
    policy = result["hierarchical_decision_policy_layer"]
    assert policy["survival_priority_score"] >= policy["opportunity_priority_score"]
    assert policy["dominant_policy_mode"] in {"survival_first", "refusal_first", "deferral_first"}


def test_hierarchical_decision_policy_layer_allows_opportunity_bias_only_when_policy_reliability_is_high(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdo1", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london"},
            {"trade_id": "hdo2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "new_york"},
            {"trade_id": "hdo3", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "asia"},
        ],
        market_state={"structure_state": "trend", "volatility_ratio": 1.0, "spread_ratio": 1.0, "slippage_ratio": 1.0},
        replay_scope="focused_replay",
    )
    policy = result["hierarchical_decision_policy_layer"]
    if policy["dominant_policy_mode"] == "opportunity_first":
        assert policy["policy_reliability"] >= 0.6
    else:
        assert policy["opportunity_priority_score"] <= max(
            policy["survival_priority_score"],
            policy["refusal_priority_score"],
            policy["deferral_priority_score"],
        )


def test_hierarchical_decision_policy_layer_feeds_self_suggestion_governor_discipline_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdg1", "status": "closed", "result": "loss", "pnl_points": -1.0, "session": "asia"},
            {"trade_id": "hdg2", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "hdg3", "status": "closed", "result": "loss", "pnl_points": -0.7, "session": "asia"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 2.8},
        replay_scope="full_replay",
    )
    governor = result["self_suggestion_governor"]
    assert "hierarchical_decision_policy_layer" in governor
    assert "anti_noise_controls" in governor
    assert "priority_threshold" in governor["anti_noise_controls"]


def test_hierarchical_decision_policy_layer_feeds_self_expansion_quality_components_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hde1", "status": "closed", "result": "loss", "pnl_points": -0.9},
            {"trade_id": "hde2", "status": "closed", "result": "win", "pnl_points": 0.6},
            {"trade_id": "hde3", "status": "closed", "result": "loss", "pnl_points": -0.4},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.2, "slippage_ratio": 2.0},
        replay_scope="full_replay",
    )
    quality = result["self_expansion_quality_layer"]
    components = quality["quality_components"]
    assert "decision_policy_state_context" in components
    assert "decision_policy_mode_context" in components
    assert "decision_policy_conflict_pressure" in components
    assert "decision_policy_refusal_deferral_pressure" in components


def test_hierarchical_decision_policy_layer_history_rolls_and_governance_is_sandbox_replay_only(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        result = run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"hdh{index}a", "status": "closed", "result": "loss", "pnl_points": -0.8},
                {"trade_id": f"hdh{index}b", "status": "closed", "result": "win", "pnl_points": 0.5},
            ],
            market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.1, "slippage_ratio": 2.0},
            replay_scope="focused_replay",
        )
    policy = result["hierarchical_decision_policy_layer"]
    flags = policy["governance_flags"]
    assert flags["sandbox_only"] is True
    assert flags["replay_validation_required"] is True
    assert flags["live_deployment_allowed"] is False
    history_payload = json.loads((memory_root / "decision_policy" / "decision_policy_history.json").read_text(encoding="utf-8"))
    assert history_payload["snapshots"]
    assert len(history_payload["snapshots"]) <= 200


def test_hierarchical_decision_policy_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "hdn1", "status": "closed", "result": "loss", "pnl_points": -0.2},
            {"trade_id": "hdn2", "status": "closed", "result": "flat", "pnl_points": 0.0},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    policy = result["hierarchical_decision_policy_layer"]
    assert 0.0 <= policy["survival_priority_score"] <= 1.0
    assert 0.0 <= policy["opportunity_priority_score"] <= 1.0
    assert 0.0 <= policy["policy_conflict_score"] <= 1.0
    assert 0.0 <= policy["policy_reliability"] <= 1.0
    assert policy["governance_flags"]["sandbox_only"] is True
    assert policy["governance_flags"]["replay_validation_required"] is True
    assert policy["governance_flags"]["live_deployment_allowed"] is False


def test_portfolio_multi_context_capital_allocation_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cap1", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
            {"trade_id": "cap2", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "london"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.6, "spread_ratio": 2.0, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    assert Path(allocation["paths"]["latest"]).exists()
    assert Path(allocation["paths"]["history"]).exists()
    assert Path(allocation["paths"]["allocation_reason_registry"]).exists()
    assert Path(allocation["paths"]["context_competition_registry"]).exists()
    assert Path(allocation["paths"]["exposure_compression_trace"]).exists()
    assert Path(allocation["paths"]["capital_allocation_governance_state"]).exists()


def test_portfolio_multi_context_capital_allocation_layer_returns_expected_schema(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cas1", "status": "closed", "result": "loss", "pnl_points": -1.0},
            {"trade_id": "cas2", "status": "closed", "result": "win", "pnl_points": 0.5},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.1, "slippage_ratio": 1.9},
        replay_scope="full_replay",
    )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    expected_keys = {
        "capital_allocation_state",
        "allocation_priority_score",
        "survival_exposure_bias",
        "opportunity_allocation_bias",
        "exposure_compression_score",
        "context_competition_score",
        "allocation_reliability",
        "recommended_capital_fraction",
        "allocation_reason_cluster",
        "governance_flags",
        "paths",
    }
    assert expected_keys.issubset(set(allocation))


def test_portfolio_multi_context_capital_allocation_layer_adds_unified_field_components_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cau1", "status": "closed", "result": "loss", "pnl_points": -0.7},
            {"trade_id": "cau2", "status": "closed", "result": "win", "pnl_points": 0.4},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.4, "spread_ratio": 1.8, "slippage_ratio": 1.6},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "capital_allocation_state" in unified["components"]
    assert "allocation_reliability" in unified["confidence_structure"]
    assert "context_competition_score" in unified["confidence_structure"]
    assert "capital_allocation" in unified["decision_refinements"]
    assert "refined" in unified["decision_refinements"]["risk_sizing"]


def test_portfolio_multi_context_capital_allocation_layer_additively_influences_risk_sizing_and_refusal_pause_behavior(
    tmp_path: Path,
) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "car1", "status": "closed", "result": "loss", "pnl_points": -1.2, "failure_cause": "execution_failure"},
            {"trade_id": "car2", "status": "closed", "result": "loss", "pnl_points": -1.0, "failure_cause": "execution_failure"},
            {"trade_id": "car3", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.2, "spread_ratio": 3.2, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    refinements = result["unified_market_intelligence_field"]["decision_refinements"]
    assert "capital_allocation_multiplier" in refinements["risk_sizing"]
    assert 0.25 <= float(refinements["risk_sizing"]["capital_allocation_multiplier"]) <= 1.0
    behavior = refinements["refusal_pause_behavior"]
    all_reasons = set(behavior.get("refusal_reasons", [])) | set(behavior.get("pause_reasons", []))
    assert any(reason.startswith("capital_allocation_") for reason in all_reasons)


def test_portfolio_multi_context_capital_allocation_layer_prioritizes_survival_under_fragility(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "caf1", "status": "closed", "result": "loss", "pnl_points": -1.1, "session": "asia"},
            {"trade_id": "caf2", "status": "closed", "result": "loss", "pnl_points": -0.9, "session": "asia"},
            {"trade_id": "caf3", "status": "closed", "result": "loss", "pnl_points": -0.8, "session": "asia"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.3, "spread_ratio": 3.5, "slippage_ratio": 3.4},
        replay_scope="full_replay",
    )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    assert allocation["survival_exposure_bias"] >= allocation["opportunity_allocation_bias"]
    assert allocation["capital_allocation_state"] in {"capital_preservation", "context_competitive", "balanced_guarded"}


def test_portfolio_multi_context_capital_allocation_layer_allows_opportunity_bias_only_when_reliability_high(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cao1", "status": "closed", "result": "win", "pnl_points": 0.8, "session": "london"},
            {"trade_id": "cao2", "status": "closed", "result": "win", "pnl_points": 0.7, "session": "new_york"},
            {"trade_id": "cao3", "status": "closed", "result": "win", "pnl_points": 0.6, "session": "asia"},
        ],
        market_state={"structure_state": "trend", "volatility_ratio": 1.0, "spread_ratio": 1.0, "slippage_ratio": 1.0},
        replay_scope="focused_replay",
    )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    if allocation["opportunity_allocation_bias"] > allocation["survival_exposure_bias"]:
        assert allocation["allocation_reliability"] >= 0.55
    else:
        assert allocation["opportunity_allocation_bias"] <= allocation["survival_exposure_bias"]


def test_portfolio_multi_context_capital_allocation_layer_feeds_self_suggestion_governor_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cag1", "status": "closed", "result": "loss", "pnl_points": -1.0},
            {"trade_id": "cag2", "status": "closed", "result": "loss", "pnl_points": -0.8},
            {"trade_id": "cag3", "status": "closed", "result": "loss", "pnl_points": -0.7},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.1, "slippage_ratio": 2.9},
        replay_scope="full_replay",
    )
    governor = result["self_suggestion_governor"]
    assert "portfolio_multi_context_capital_allocation_layer" in governor
    assert "anti_noise_controls" in governor
    assert "priority_threshold" in governor["anti_noise_controls"]


def test_portfolio_multi_context_capital_allocation_layer_feeds_self_expansion_quality_components_nonbreaking(
    tmp_path: Path,
) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "cae1", "status": "closed", "result": "loss", "pnl_points": -0.9},
            {"trade_id": "cae2", "status": "closed", "result": "win", "pnl_points": 0.5},
            {"trade_id": "cae3", "status": "closed", "result": "loss", "pnl_points": -0.3},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.2, "slippage_ratio": 2.0},
        replay_scope="full_replay",
    )
    quality = result["self_expansion_quality_layer"]
    components = quality["quality_components"]
    assert "capital_allocation_state_context" in components
    assert "capital_allocation_reliability_context" in components
    assert "capital_allocation_exposure_compression_pressure" in components
    assert "capital_allocation_context_competition_pressure" in components


def test_portfolio_multi_context_capital_allocation_layer_history_rolls_and_governance_is_sandbox_replay_only(
    tmp_path: Path,
) -> None:
    memory_root = tmp_path / "memory"
    for index in range(3):
        result = run_self_evolving_indicator_layer(
            memory_root=memory_root,
            trade_outcomes=[
                {"trade_id": f"cah{index}a", "status": "closed", "result": "loss", "pnl_points": -0.8},
                {"trade_id": f"cah{index}b", "status": "closed", "result": "win", "pnl_points": 0.5},
            ],
            market_state={"structure_state": "range", "volatility_ratio": 1.5, "spread_ratio": 2.0, "slippage_ratio": 1.9},
            replay_scope="focused_replay",
        )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    flags = allocation["governance_flags"]
    assert flags["sandbox_only"] is True
    assert flags["replay_validation_required"] is True
    assert flags["live_deployment_allowed"] is False
    history_payload = json.loads((memory_root / "capital_allocation" / "capital_allocation_history.json").read_text(encoding="utf-8"))
    assert history_payload["snapshots"]
    assert len(history_payload["snapshots"]) <= 200
    governance = json.loads(
        (memory_root / "capital_allocation" / "capital_allocation_governance_state.json").read_text(encoding="utf-8")
    )
    assert governance["sandbox_only"] is True
    assert governance["replay_validation_required"] is True
    assert governance["live_deployment_allowed"] is False
    assert governance["replay_scope"] == "focused_replay"


def test_portfolio_multi_context_capital_allocation_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "can1", "status": "closed", "result": "loss", "pnl_points": -0.2},
            {"trade_id": "can2", "status": "closed", "result": "flat", "pnl_points": 0.0},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    assert 0.0 <= allocation["allocation_priority_score"] <= 1.0
    assert 0.0 <= allocation["survival_exposure_bias"] <= 1.0
    assert 0.0 <= allocation["opportunity_allocation_bias"] <= 1.0
    assert 0.0 <= allocation["exposure_compression_score"] <= 1.0
    assert 0.0 <= allocation["context_competition_score"] <= 1.0
    assert 0.0 <= allocation["allocation_reliability"] <= 1.0
    assert 0.05 <= allocation["recommended_capital_fraction"] <= 0.95
    assert allocation["governance_flags"]["sandbox_only"] is True
    assert allocation["governance_flags"]["replay_validation_required"] is True
    assert allocation["governance_flags"]["live_deployment_allowed"] is False


def test_temporal_execution_sequencing_layer_persists_required_artifacts(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "tesp1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -1.1,
                "failure_cause": "execution_failure",
                "signal_time": 10,
                "first_fill_time": 95,
                "intended_entry_price": 2010.0,
                "average_fill_price": 2018.0,
                "mae_after_fill": 4.2,
                "mfe_after_fill": 0.2,
            },
            {"trade_id": "tesp2", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.0, "slippage_ratio": 2.8},
        replay_scope="full_replay",
    )
    temporal = result["temporal_execution_sequencing_layer"]
    assert Path(temporal["paths"]["latest"]).exists()
    assert Path(temporal["paths"]["history"]).exists()
    assert Path(temporal["paths"]["sequencing_reason_registry"]).exists()
    assert Path(temporal["paths"]["execution_window_quality_registry"]).exists()
    assert Path(temporal["paths"]["temporal_sequence_transition_trace"]).exists()
    assert Path(temporal["paths"]["temporal_execution_governance_state"]).exists()


def test_temporal_execution_sequencing_layer_returns_expected_schema(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tess1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "tess2", "status": "closed", "result": "win", "pnl_points": 0.5, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.7, "spread_ratio": 2.2, "slippage_ratio": 2.0},
        replay_scope="focused_replay",
    )
    temporal = result["temporal_execution_sequencing_layer"]
    expected_keys = {
        "temporal_execution_state",
        "timing_priority_score",
        "sequencing_reliability",
        "entry_now_bias",
        "delay_bias",
        "stagger_bias",
        "abandon_bias",
        "phase_maturity_score",
        "execution_window_quality",
        "sequencing_reason_cluster",
        "recommended_sequence_mode",
        "sequence_actions",
        "timing_controls",
        "governance_flags",
        "paths",
    }
    assert expected_keys.issubset(set(temporal))
    for key in (
        "timing_priority_score",
        "sequencing_reliability",
        "entry_now_bias",
        "delay_bias",
        "stagger_bias",
        "abandon_bias",
        "phase_maturity_score",
        "execution_window_quality",
    ):
        assert 0.0 <= float(temporal[key]) <= 1.0


def test_temporal_execution_sequencing_layer_adds_unified_field_components_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tesu1", "status": "closed", "result": "loss", "pnl_points": -1.0, "failure_cause": "execution_failure"},
            {"trade_id": "tesu2", "status": "closed", "result": "win", "pnl_points": 0.6, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.8, "spread_ratio": 2.4, "slippage_ratio": 2.1},
        replay_scope="full_replay",
    )
    unified = result["unified_market_intelligence_field"]
    assert "unified_field_score" in unified
    assert "composite_confidence" in unified["confidence_structure"]
    assert "temporal_execution_state" in unified["components"]
    assert "timing_priority_score" in unified["confidence_structure"]
    assert "sequencing_reliability" in unified["confidence_structure"]
    assert "execution_window_quality" in unified["confidence_structure"]
    assert "temporal_execution" in unified["decision_refinements"]
    assert "strategy_selection" in unified["decision_refinements"]
    assert "risk_sizing" in unified["decision_refinements"]


def test_temporal_execution_sequencing_layer_additively_influences_hierarchical_decision_policy_nonbreaking(
    tmp_path: Path,
) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tesh1", "status": "closed", "result": "loss", "pnl_points": -1.2, "failure_cause": "execution_failure"},
            {"trade_id": "tesh2", "status": "closed", "result": "loss", "pnl_points": -1.0, "failure_cause": "execution_failure"},
            {"trade_id": "tesh3", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.1, "spread_ratio": 3.2, "slippage_ratio": 3.0},
        replay_scope="full_replay",
    )
    policy = result["hierarchical_decision_policy_layer"]
    assert "temporal_sequencing_pressure" in policy
    assert 0.0 <= float(policy["temporal_sequencing_pressure"]) <= 1.0
    assert "decision_policy_state" in policy
    assert "dominant_policy_mode" in policy


def test_temporal_execution_sequencing_layer_additively_influences_capital_allocation_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tesc1", "status": "closed", "result": "loss", "pnl_points": -1.1, "failure_cause": "execution_failure"},
            {"trade_id": "tesc2", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "tesc3", "status": "closed", "result": "win", "pnl_points": 0.3, "failure_cause": "none"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.0, "spread_ratio": 3.1, "slippage_ratio": 2.9},
        replay_scope="full_replay",
    )
    allocation = result["portfolio_multi_context_capital_allocation_layer"]
    assert "temporal_pacing_pressure" in allocation
    assert "staged_deployment_bias" in allocation
    assert 0.0 <= float(allocation["temporal_pacing_pressure"]) <= 1.0
    assert 0.0 <= float(allocation["staged_deployment_bias"]) <= 1.0
    assert 0.05 <= float(allocation["recommended_capital_fraction"]) <= 0.95


def test_temporal_execution_sequencing_layer_feeds_refusal_pause_behavior_with_timing_reasons(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {
                "trade_id": "tesr1",
                "status": "closed",
                "result": "loss",
                "pnl_points": -1.3,
                "failure_cause": "execution_failure",
                "signal_time": 10,
                "first_fill_time": 110,
                "intended_entry_price": 2010.0,
                "average_fill_price": 2020.0,
                "mae_after_fill": 5.0,
                "mfe_after_fill": 0.2,
            },
            {"trade_id": "tesr2", "status": "closed", "result": "loss", "pnl_points": -1.0, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.3, "spread_ratio": 3.4, "slippage_ratio": 3.3},
        replay_scope="full_replay",
    )
    behavior = result["unified_market_intelligence_field"]["decision_refinements"]["refusal_pause_behavior"]
    reasons = set(behavior.get("pause_reasons", [])) | set(behavior.get("refusal_reasons", []))
    assert any(reason.startswith("temporal_execution_") for reason in reasons)


def test_temporal_execution_sequencing_layer_feeds_self_suggestion_governor_gap_detection_nonbreaking(
    tmp_path: Path,
) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tesg1", "status": "closed", "result": "loss", "pnl_points": -1.2, "failure_cause": "execution_failure"},
            {"trade_id": "tesg2", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "tesg3", "status": "closed", "result": "loss", "pnl_points": -0.8, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 2.2, "spread_ratio": 3.3, "slippage_ratio": 3.2},
        replay_scope="full_replay",
    )
    governor = result["self_suggestion_governor"]
    gap_types = {str(item.get("gap_type", "")) for item in governor.get("detected_gaps", []) if isinstance(item, dict)}
    assert (
        "temporal_sequencing_instability" in gap_types
        or "execution_window_quality_degradation" in gap_types
        or "temporal_abandonment_pressure" in gap_types
    )
    assert "anti_noise_controls" in governor


def test_temporal_execution_sequencing_layer_feeds_self_expansion_quality_components_nonbreaking(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tese1", "status": "closed", "result": "loss", "pnl_points": -0.9, "failure_cause": "execution_failure"},
            {"trade_id": "tese2", "status": "closed", "result": "win", "pnl_points": 0.6, "failure_cause": "none"},
            {"trade_id": "tese3", "status": "closed", "result": "loss", "pnl_points": -0.4, "failure_cause": "partial_fill"},
        ],
        market_state={"structure_state": "range", "volatility_ratio": 1.9, "spread_ratio": 2.5, "slippage_ratio": 2.2},
        replay_scope="full_replay",
    )
    components = result["self_expansion_quality_layer"]["quality_components"]
    assert "temporal_execution_state_context" in components
    assert "temporal_sequencing_reliability_context" in components
    assert "temporal_delay_abandon_pressure" in components
    assert "temporal_execution_window_quality_context" in components
    assert "temporal_timing_priority_context" in components
    assert "temporal_sequencing_pressure_context" in components


def test_temporal_execution_sequencing_layer_nonbreaking_with_missing_inputs(tmp_path: Path) -> None:
    result = run_self_evolving_indicator_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=[
            {"trade_id": "tesn1", "status": "closed", "result": "loss", "pnl_points": -0.2},
            {"trade_id": "tesn2", "status": "closed", "result": "flat", "pnl_points": 0.0},
        ],
        market_state={"structure_state": "range"},
        replay_scope="focused_replay",
    )
    temporal = result["temporal_execution_sequencing_layer"]
    assert temporal["temporal_execution_state"] in {"ready", "deferential", "unstable"}
    assert temporal["recommended_sequence_mode"] in {"enter_now", "delay", "stagger", "hold", "abandon"}
    assert isinstance(temporal["sequence_actions"], list)
    assert temporal["governance_flags"]["sandbox_only"] is True
    assert temporal["governance_flags"]["replay_validation_required"] is True
    assert temporal["governance_flags"]["live_deployment_allowed"] is False
