from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_H_BLOCKED_FAIL_SAFE,
    PHASE_H_BLOCKED_VENUE_UNHEALTHY,
    PHASE_H_SUPERVISED_NON_LIVE,
    run_knowledge_expansion_phase_h,
)


REQUIRED_SUPERVISION_ARTIFACT_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "orchestrator_source_path",
    "supervision_timestamp",
    "orchestrator_decision",
    "supervision_decision",
    "supervision_reason",
    "execution_readiness",
    "venue_health",
    "fail_safe_status",
    "interface_state_snapshot",
    "interface_state_memory_path",
    "manual_approval_required",
    "live_activation_allowed",
    "risk_constraints",
    "governor_version",
}


def _write_orchestrator_decision(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_interface_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_h_generates_supervision_artifacts(tmp_path: Path) -> None:
    orchestrator_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_orchestrator_decision(
        orchestrator_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "truth_class": "timing",
            "orchestrator_decision": "controlled_review_signal",
        },
    )
    _write_orchestrator_decision(
        orchestrator_dir / "cand_b.json",
        {
            "candidate_id": "cand_b",
            "module_name": "sandbox_cand_b",
            "truth_class": "failure",
            "orchestrator_decision": "hold_non_live",
        },
    )
    _write_interface_state(
        tmp_path / "memory" / "knowledge_expansion" / "broker_exchange_interfaces" / "venue.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "broker_name": "paper_broker",
            "exchange_name": "sim_exchange",
            "broker_connected": True,
            "exchange_connected": True,
            "venue_status": "healthy",
            "latency_ms": 14.2,
            "fail_safe_triggered": False,
        },
    )

    result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    assert result["supervision_artifact_count"] == 2
    artifacts = sorted(Path(path) for path in result["supervision_artifacts"])
    assert [path.name for path in artifacts] == ["cand_a.json", "cand_b.json"]
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_SUPERVISION_ARTIFACT_KEYS
        assert payload["supervision_decision"] == PHASE_H_SUPERVISED_NON_LIVE


def test_phase_h_deterministic_fail_safe_and_venue_health_mapping(tmp_path: Path) -> None:
    orchestrator_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_orchestrator_decision(
        orchestrator_dir / "cand_fail_safe.json",
        {
            "candidate_id": "cand_fail_safe",
            "module_name": "sandbox_cand_fail_safe",
            "truth_class": "timing",
            "orchestrator_decision": "controlled_review_signal",
        },
    )
    _write_interface_state(
        tmp_path / "memory" / "knowledge_expansion" / "broker_exchange_interfaces" / "state_1.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "broker_name": "paper_broker",
            "exchange_name": "sim_exchange",
            "broker_connected": True,
            "exchange_connected": True,
            "venue_status": "healthy",
            "latency_ms": 10.0,
            "fail_safe_triggered": True,
        },
    )
    fail_safe_result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    fail_safe_payload = json.loads(Path(fail_safe_result["supervision_artifacts"][0]).read_text(encoding="utf-8"))
    assert fail_safe_payload["supervision_decision"] == PHASE_H_BLOCKED_FAIL_SAFE
    assert fail_safe_payload["fail_safe_status"] == "fail_safe_triggered"

    _write_interface_state(
        tmp_path / "memory" / "knowledge_expansion" / "broker_exchange_interfaces" / "state_2.json",
        {
            "timestamp": "2026-01-01T00:05:00+00:00",
            "broker_name": "paper_broker",
            "exchange_name": "sim_exchange",
            "broker_connected": True,
            "exchange_connected": True,
            "venue_status": "down",
            "latency_ms": 120.0,
            "fail_safe_triggered": False,
        },
    )
    venue_result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    venue_payload = json.loads(Path(venue_result["supervision_artifacts"][0]).read_text(encoding="utf-8"))
    assert venue_payload["supervision_decision"] == PHASE_H_BLOCKED_VENUE_UNHEALTHY
    assert venue_payload["venue_health"] == "down"


def test_phase_h_interface_state_memory_updates_across_time(tmp_path: Path) -> None:
    orchestrator_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_orchestrator_decision(
        orchestrator_dir / "cand_state.json",
        {
            "candidate_id": "cand_state",
            "module_name": "sandbox_cand_state",
            "truth_class": "timing",
            "orchestrator_decision": "paper_execution_only",
        },
    )
    interface_dir = tmp_path / "memory" / "knowledge_expansion" / "broker_exchange_interfaces"
    _write_interface_state(
        interface_dir / "update_1.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "broker_name": "paper_broker",
            "exchange_name": "sim_exchange",
            "broker_connected": True,
            "exchange_connected": True,
            "venue_status": "healthy",
            "latency_ms": 12.0,
            "fail_safe_triggered": False,
        },
    )
    first_result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    first_memory = json.loads(Path(first_result["interface_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(first_memory["state_history"]) == 1

    _write_interface_state(
        interface_dir / "update_2.json",
        {
            "timestamp": "2026-01-01T00:02:00+00:00",
            "broker_name": "paper_broker",
            "exchange_name": "sim_exchange",
            "broker_connected": True,
            "exchange_connected": True,
            "venue_status": "degraded",
            "latency_ms": 44.0,
            "fail_safe_triggered": False,
        },
    )
    second_result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    second_memory = json.loads(Path(second_result["interface_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(second_memory["state_history"]) == 2
    assert second_memory["latest_interface_state"]["venue_status"] == "degraded"


def test_phase_h_live_activation_is_blocked_by_default(tmp_path: Path) -> None:
    orchestrator_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_orchestrator_decision(
        orchestrator_dir / "cand_guard.json",
        {
            "candidate_id": "cand_guard",
            "module_name": "sandbox_cand_guard",
            "truth_class": "timing",
            "orchestrator_decision": "controlled_review_signal",
        },
    )

    result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    payload = json.loads(Path(result["supervision_artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["live_activation_allowed"] is False
    assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_phase_h_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    orchestrator_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_orchestrator_decision(
        orchestrator_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "timing",
            "orchestrator_decision": "controlled_review_signal",
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_h(tmp_path, mode="replay")
    output_dir = Path(result["supervision_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
