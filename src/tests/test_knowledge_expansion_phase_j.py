from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_J_MONITOR_CONTINUE_PAPER_ONLY,
    PHASE_J_ROLLBACK_CONTROLLED_NON_LIVE,
    PHASE_J_ROLLBACK_IMMEDIATE,
    run_knowledge_expansion_phase_j,
)


REQUIRED_INCIDENT_ARTIFACT_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "portfolio_source_path",
    "incident_timestamp",
    "portfolio_decision",
    "execution_readiness",
    "incident_id",
    "incident_severity",
    "incident_control_decision",
    "rollback_status",
    "decision_reason",
    "health_state_snapshot",
    "health_state_memory_path",
    "manual_approval_required",
    "live_activation_allowed",
    "risk_constraints",
    "governor_version",
}


def _write_portfolio(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_health(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_j_generates_monitoring_incident_artifacts(tmp_path: Path) -> None:
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "truth_class": "timing",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
        },
    )
    _write_health(
        tmp_path / "memory" / "knowledge_expansion" / "system_health_inputs" / "state.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "health_score": 0.95,
            "failed_checks": 0,
            "unsafe_condition": False,
            "rollback_requested": False,
            "incident_signals": [],
        },
    )

    result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    assert result["incident_artifact_count"] == 1
    payload = json.loads(Path(result["incident_artifacts"][0]).read_text(encoding="utf-8"))
    assert set(payload.keys()) == REQUIRED_INCIDENT_ARTIFACT_KEYS
    assert payload["incident_control_decision"] == PHASE_J_MONITOR_CONTINUE_PAPER_ONLY


def test_phase_j_deterministic_severity_and_rollback_mapping(tmp_path: Path) -> None:
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_risk.json",
        {
            "candidate_id": "cand_risk",
            "module_name": "sandbox_cand_risk",
            "truth_class": "timing",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
        },
    )

    health_dir = tmp_path / "memory" / "knowledge_expansion" / "system_health_inputs"
    _write_health(
        health_dir / "critical.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "health_score": 0.3,
            "failed_checks": 4,
            "unsafe_condition": True,
            "rollback_requested": True,
            "incident_signals": ["latency_spike", "order_rejects"],
        },
    )
    critical_result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    critical_payload = json.loads(Path(critical_result["incident_artifacts"][0]).read_text(encoding="utf-8"))
    assert critical_payload["incident_control_decision"] == PHASE_J_ROLLBACK_IMMEDIATE
    assert critical_payload["incident_severity"] == "critical"
    assert critical_payload["rollback_status"] == "rollback_required"

    _write_health(
        health_dir / "degraded.json",
        {
            "timestamp": "2026-01-01T00:05:00+00:00",
            "health_score": 0.7,
            "failed_checks": 1,
            "unsafe_condition": False,
            "rollback_requested": False,
            "incident_signals": ["spread_widening"],
        },
    )
    degraded_result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    degraded_payload = json.loads(Path(degraded_result["incident_artifacts"][0]).read_text(encoding="utf-8"))
    assert degraded_payload["incident_control_decision"] == PHASE_J_ROLLBACK_CONTROLLED_NON_LIVE
    assert degraded_payload["incident_severity"] == "warning"
    assert degraded_payload["rollback_status"] == "degraded_guarded"


def test_phase_j_health_state_memory_updates_across_time(tmp_path: Path) -> None:
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_state.json",
        {
            "candidate_id": "cand_state",
            "module_name": "sandbox_cand_state",
            "truth_class": "timing",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
        },
    )

    health_dir = tmp_path / "memory" / "knowledge_expansion" / "system_health_inputs"
    _write_health(
        health_dir / "update_1.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "health_score": 0.92,
            "failed_checks": 0,
            "unsafe_condition": False,
            "rollback_requested": False,
            "incident_signals": [],
        },
    )
    first_result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    first_memory = json.loads(Path(first_result["health_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(first_memory["state_history"]) == 1

    _write_health(
        health_dir / "update_2.json",
        {
            "timestamp": "2026-01-01T00:03:00+00:00",
            "health_score": 0.74,
            "failed_checks": 1,
            "unsafe_condition": False,
            "rollback_requested": False,
            "incident_signals": ["minor_slippage"],
        },
    )
    second_result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    second_memory = json.loads(Path(second_result["health_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(second_memory["state_history"]) == 2
    assert second_memory["latest_health_state"]["health_score"] == 0.74


def test_phase_j_live_activation_is_blocked_by_default(tmp_path: Path) -> None:
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_guard.json",
        {
            "candidate_id": "cand_guard",
            "module_name": "sandbox_cand_guard",
            "truth_class": "timing",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
        },
    )

    result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    payload = json.loads(Path(result["incident_artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["live_activation_allowed"] is False
    assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_phase_j_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "timing",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_j(tmp_path, mode="replay")
    output_dir = Path(result["incident_control_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
