from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import run_continuous_governed_improvement_cycle


def _write_validated_registry(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_validated_knowledge(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_alpha",
                    "truth_class": "timing",
                    "statement": "Session compression precedes continuation.",
                    "evidence_history": [{"signal": "compression"}, {"signal": "breakout"}],
                    "decision": "PROMOTE_TO_EXPERIMENT",
                    "decision_reasons": ["replay_gain"],
                }
            ]
        },
    )


def _seed_multi_validated_knowledge(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_alpha",
                    "truth_class": "timing",
                    "statement": "Session compression precedes continuation.",
                    "evidence_history": [{"signal": "compression"}, {"signal": "breakout"}],
                    "decision": "PROMOTE_TO_EXPERIMENT",
                    "decision_reasons": ["replay_gain"],
                },
                {
                    "candidate_id": "cand_beta",
                    "truth_class": "risk",
                    "statement": "Volatility burst often invalidates weak continuation setups.",
                    "evidence_history": [{"signal": "volatility_spike"}, {"signal": "failed_breakout"}],
                    "decision": "PROMOTE_TO_EXPERIMENT",
                    "decision_reasons": ["replay_guardrail"],
                },
            ]
        },
    )


def _write_in_progress_cycle_state(tmp_path: Path, iteration_id: str, phase_results: dict) -> Path:
    cycle_dir = tmp_path / "memory" / "knowledge_expansion" / "continuous_governed_improvement"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    cycle_state_path = cycle_dir / f"cycle_state_{iteration_id}.json"
    cycle_state_path.write_text(
        json.dumps(
            {
                "iteration_id": iteration_id,
                "status": "in_progress",
                "phase_results": phase_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return cycle_state_path


def _neutralize_cycle_artifact_stale_detection(cycle_artifact_path: str) -> None:
    Path(cycle_artifact_path).write_text(json.dumps({"stale_detection": "disabled_for_resume_test"}, indent=2), encoding="utf-8")


def test_continuous_cycle_executes_governed_phases(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    result = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="cycle-001",
    )

    assert result["continuous_governed_improvement_enabled"] is True
    phase_results = result["phase_results"]
    assert phase_results["discovery"]["advanced_discovery_count"] == 1
    assert phase_results["sandbox_generation"]["sandbox_module_count"] == 1
    assert phase_results["replay_judgment"]["sandbox_judgment_count"] == 1
    assert phase_results["promotion_governance"]["governance_artifact_count"] == 1
    assert phase_results["execution_governance"]["execution_governance_artifact_count"] == 1
    assert phase_results["decision_orchestration"]["decision_artifact_count"] == 1
    assert phase_results["execution_supervision"]["supervision_artifact_count"] == 1
    assert phase_results["adaptive_portfolio"]["portfolio_artifact_count"] == 1
    assert phase_results["incident_control"]["incident_artifact_count"] == 1
    assert phase_results["long_horizon_memory"]["long_horizon_memory_count"] == 1
    assert "live_learning_feedback" in result
    assert "autonomous_behavior_layer" in result
    assert "self_evolving_indicator_layer" in result
    assert Path(result["live_learning_feedback"]["paths"]["mutation_candidates"]).exists()
    assert Path(result["autonomous_behavior_layer"]["trade_review_engine"]["path"]).exists()
    capability_paths = result["self_evolving_indicator_layer"]["capability_generator"]["paths"]
    assert Path(capability_paths["candidates"]).exists()
    assert Path(capability_paths["registry"]).exists()
    parameter_control = result["evolution_parameter_control"]
    assert Path(parameter_control["parameter_state_path"]).exists()
    assert Path(parameter_control["parameter_changes_path"]).exists()
    assert Path(parameter_control["adaptation_reasons_path"]).exists()
    assert Path(parameter_control["parameter_performance_by_regime_path"]).exists()
    parameter_state_payload = json.loads(Path(parameter_control["parameter_state_path"]).read_text(encoding="utf-8"))
    assert parameter_state_payload["regime_context"]["volatility_regime"] in {
        "low_volatility",
        "medium_volatility",
        "high_volatility",
    }
    assert parameter_state_payload["replay_evaluated"] is True
    assert parameter_state_payload["governed"] is True
    assert Path(result["cycle_artifact_path"]).exists()


def test_continuous_cycle_is_duplicate_safe_per_iteration(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    run_continuous_governed_improvement_cycle(tmp_path, mode="replay", baseline_summary={"score": 0.0}, iteration_id="dup")
    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="dup",
    )
    registry_payload = json.loads(Path(second["cycle_registry_path"]).read_text(encoding="utf-8"))

    assert len(registry_payload["cycles"]) == 1
    assert registry_payload["cycles"][0]["iteration_id"] == "dup"


def test_continuous_cycle_artifact_updates_are_deterministic(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="deterministic",
    )
    first_cycle_payload = json.loads(Path(first["cycle_artifact_path"]).read_text(encoding="utf-8"))
    first_sandbox = Path(first["phase_results"]["sandbox_generation"]["sandbox_module_artifacts"][0]).read_text(
        encoding="utf-8"
    )
    first_judgment = Path(first["phase_results"]["replay_judgment"]["sandbox_judgments"][0]).read_text(
        encoding="utf-8"
    )

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="deterministic",
    )
    second_cycle_payload = json.loads(Path(second["cycle_artifact_path"]).read_text(encoding="utf-8"))
    second_sandbox = Path(second["phase_results"]["sandbox_generation"]["sandbox_module_artifacts"][0]).read_text(
        encoding="utf-8"
    )
    second_judgment = Path(second["phase_results"]["replay_judgment"]["sandbox_judgments"][0]).read_text(
        encoding="utf-8"
    )

    assert second["cycle_signature"] == first["cycle_signature"]
    assert second_cycle_payload == first_cycle_payload
    assert second_sandbox == first_sandbox
    assert second_judgment == first_judgment


def test_continuous_cycle_does_not_mutate_live_execution_paths(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="live-guard",
    )

    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
    execution_phase = result["phase_results"]["execution_governance"]
    for artifact_path in execution_phase["execution_governance_artifacts"]:
        payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        assert payload["live_activation_allowed"] is False
        assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_continuous_cycle_reports_artifact_integrity_and_registry_consistency(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    result = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="integrity",
    )

    integrity = result["artifact_integrity"]
    assert integrity["all_checks_passed"] is True
    assert integrity["execution_governance"]["all_present"] is True
    first_exec_artifact = integrity["execution_governance"]["artifacts"][0]
    assert first_exec_artifact["canonical_digest"]
    assert first_exec_artifact["raw_digest"]

    consistency = result["phase_registry_consistency"]
    assert consistency["all_checks_passed"] is True
    assert consistency["candidate_counts"]["replay_judgment"] == 1
    assert consistency["candidate_counts"]["promotion_governance"] == 1
    assert consistency["candidate_counts"]["execution_governance"] == 1


def test_continuous_cycle_recovers_from_interrupted_state(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    cycle_dir = tmp_path / "memory" / "knowledge_expansion" / "continuous_governed_improvement"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    cycle_state_path = cycle_dir / "cycle_state_recover.json"
    cycle_state_path.write_text(
        json.dumps(
            {
                "iteration_id": "recover",
                "status": "in_progress",
                "recovery": {"interrupted_cycle_recovered": False},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="recover",
    )
    final_state = json.loads(Path(result["cycle_state_path"]).read_text(encoding="utf-8"))

    assert result["cycle_recovery"]["interrupted_cycle_recovered"] is True
    assert final_state["status"] == "completed"
    assert final_state["recovery"]["interrupted_cycle_recovered"] is True


def test_continuous_cycle_detects_stale_artifacts_and_applies_safe_refresh(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="stale",
    )
    first_cycle_payload = json.loads(Path(first["cycle_artifact_path"]).read_text(encoding="utf-8"))
    sandbox_digest_map = first_cycle_payload["phase_artifact_digests"]["sandbox_generation"]
    stale_path = Path(next(iter(sandbox_digest_map)))
    stale_path.write_text(json.dumps({"candidate_id": "cand_alpha", "tampered": True}, indent=2), encoding="utf-8")

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="stale",
    )

    assert second["cycle_recovery"]["stale_artifacts_detected"] is True
    assert second["cycle_recovery"]["safe_refresh_applied"] is True
    second_cycle_payload = json.loads(Path(second["cycle_artifact_path"]).read_text(encoding="utf-8"))
    assert any("digest_mismatch" in reason for reason in second_cycle_payload["stale_artifact_reasons"])


def test_continuous_cycle_detects_decision_chain_anomaly_and_triggers_rollback(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="anomaly",
    )
    _write_in_progress_cycle_state(tmp_path, "anomaly", first["phase_results"])
    _neutralize_cycle_artifact_stale_detection(first["cycle_artifact_path"])

    execution_artifact_path = Path(first["phase_results"]["execution_governance"]["execution_governance_artifacts"][0])
    execution_payload = json.loads(execution_artifact_path.read_text(encoding="utf-8"))
    execution_payload["execution_decision"] = "blocked"
    execution_artifact_path.write_text(json.dumps(execution_payload, indent=2), encoding="utf-8")

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="anomaly",
    )
    rolled_back_execution = json.loads(execution_artifact_path.read_text(encoding="utf-8"))

    assert second["cross_phase_anomaly_detection"]["has_anomalies"] is True
    assert second["governed_rollback"]["triggered"] is True
    assert rolled_back_execution["execution_decision"] == "blocked"
    assert rolled_back_execution["live_activation_allowed"] is False
    assert rolled_back_execution["governed_rollback"]["triggered"] is True


def test_continuous_cycle_detects_traceability_issues_and_triggers_rollback(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="trace",
    )
    _write_in_progress_cycle_state(tmp_path, "trace", first["phase_results"])
    _neutralize_cycle_artifact_stale_detection(first["cycle_artifact_path"])

    promotion_artifact_path = Path(first["phase_results"]["promotion_governance"]["promotion_governance_artifacts"][0])
    promotion_payload = json.loads(promotion_artifact_path.read_text(encoding="utf-8"))
    promotion_payload["source_judgment_path"] = str(tmp_path / "missing_judgment.json")
    promotion_artifact_path.write_text(json.dumps(promotion_payload, indent=2), encoding="utf-8")

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="trace",
    )

    assert second["replay_governance_traceability"]["has_issues"] is True
    assert second["governed_rollback"]["triggered"] is True
    assert "replay_to_governance_traceability_failed" in second["governed_rollback"]["trigger_reasons"]


def test_continuous_cycle_partial_resume_reruns_from_first_unsafe_phase(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="resume-safe",
    )
    _write_in_progress_cycle_state(tmp_path, "resume-safe", first["phase_results"])
    _neutralize_cycle_artifact_stale_detection(first["cycle_artifact_path"])

    sandbox_artifact_path = Path(first["phase_results"]["sandbox_generation"]["sandbox_module_artifacts"][0])
    sandbox_artifact_path.write_text("{not-json", encoding="utf-8")

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="resume-safe",
    )

    assert second["cycle_recovery"]["interrupted_cycle_recovered"] is True
    assert second["cycle_recovery"]["partial_resume_applied"] is True
    assert second["cycle_recovery"]["resumed_phases"] == ["discovery", "experimental_specs"]
    assert second["cycle_recovery"]["rerun_from_phase"] == "sandbox_generation"


def test_continuous_cycle_generates_end_to_end_chain_verification_and_self_audit(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="pack3-audit",
    )
    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="pack3-audit",
    )

    chain_report = first["end_to_end_governance_chain"]
    assert chain_report["all_checks_passed"] is True
    assert chain_report["phase_candidate_counts"]["phase_a"] == 1
    assert chain_report["phase_candidate_counts"]["phase_l"] == 1
    assert chain_report["traceability_checks"]["phase_k_phase_i_source_paths_valid"] is True

    self_audit_path = Path(first["self_audit_artifact"]["self_audit_path"])
    self_audit_payload = json.loads(self_audit_path.read_text(encoding="utf-8"))
    assert self_audit_payload["self_audit_signature"] == first["self_audit_artifact"]["self_audit_signature"]
    assert second["self_audit_artifact"]["self_audit_signature"] == first["self_audit_artifact"]["self_audit_signature"]


def test_continuous_cycle_quarantines_invalid_artifacts_and_refuses_unsafe_continuation(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="pack3-quarantine",
    )
    _write_in_progress_cycle_state(tmp_path, "pack3-quarantine", first["phase_results"])
    _neutralize_cycle_artifact_stale_detection(first["cycle_artifact_path"])

    phase_k_artifact_path = Path(first["phase_results"]["long_horizon_memory"]["long_horizon_memory_artifacts"][0])
    phase_k_payload = json.loads(phase_k_artifact_path.read_text(encoding="utf-8"))
    phase_k_payload["phase_i_source_path"] = str(tmp_path / "missing_phase_i_artifact.json")
    phase_k_artifact_path.write_text(json.dumps(phase_k_payload, indent=2), encoding="utf-8")

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="pack3-quarantine",
    )
    cycle_state_payload = json.loads(Path(second["cycle_state_path"]).read_text(encoding="utf-8"))

    assert second["end_to_end_governance_chain"]["all_checks_passed"] is False
    assert second["invalid_artifact_quarantine"]["quarantine_required"] is True
    assert second["invalid_artifact_quarantine"]["quarantined_record_count"] >= 1
    assert second["governed_refusal"]["refused"] is True
    assert second["governed_refusal"]["safe_to_continue"] is False
    assert cycle_state_payload["status"] == "refused_unsafe_continuation"


def test_continuous_cycle_adapts_parameters_by_regime_and_weak_module_clusters(tmp_path: Path) -> None:
    _seed_multi_validated_knowledge(tmp_path)

    low_volatility = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 10.0, "volatility_ratio": 0.85},
        iteration_id="params-low",
    )
    high_volatility = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 10.0, "volatility_ratio": 1.35},
        iteration_id="params-high",
    )

    low_control = low_volatility["evolution_parameter_control"]
    high_control = high_volatility["evolution_parameter_control"]
    low_state = json.loads(Path(low_control["parameter_state_path"]).read_text(encoding="utf-8"))
    high_state = json.loads(Path(high_control["parameter_state_path"]).read_text(encoding="utf-8"))
    low_reasons = json.loads(Path(low_control["adaptation_reasons_path"]).read_text(encoding="utf-8"))
    high_reasons = json.loads(Path(high_control["adaptation_reasons_path"]).read_text(encoding="utf-8"))
    performance_by_regime = json.loads(Path(high_control["parameter_performance_by_regime_path"]).read_text(encoding="utf-8"))

    assert low_state["regime_context"]["volatility_regime"] == "low_volatility"
    assert high_state["regime_context"]["volatility_regime"] == "high_volatility"
    assert low_state["regime_context"]["weak_module_cluster_detected"] is True
    assert high_state["parameter_state"]["quarantine_strictness"] >= low_state["parameter_state"]["quarantine_strictness"]
    assert high_state["parameter_state"]["mutation_rate"] > low_state["parameter_state"]["mutation_rate"]
    assert "strict promotion works better in low volatility" in low_reasons["adaptation_reasons"]
    assert "faster mutation works better in high volatility" in high_reasons["adaptation_reasons"]
    assert "quarantine should tighten after weak-module clusters" in high_reasons["adaptation_reasons"]
    assert "low_volatility" in performance_by_regime["by_regime"]
    assert "high_volatility" in performance_by_regime["by_regime"]
