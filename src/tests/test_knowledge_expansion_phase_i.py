from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_I_ADAPTIVE_PAPER_ONLY,
    PHASE_I_CAPITAL_PRESERVATION_MODE,
    PHASE_I_CONSTRAINED_NON_LIVE,
    run_knowledge_expansion_phase_i,
)


REQUIRED_PORTFOLIO_ARTIFACT_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "supervision_source_path",
    "portfolio_timestamp",
    "supervision_decision",
    "portfolio_decision",
    "decision_reason",
    "execution_readiness",
    "risk_state",
    "allocation_state",
    "exposure_state",
    "sizing_state",
    "drawdown_state",
    "portfolio_state_snapshot",
    "portfolio_state_memory_path",
    "manual_approval_required",
    "live_activation_allowed",
    "risk_constraints",
    "governor_version",
}


def _write_supervision(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_portfolio_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_i_generates_adaptive_portfolio_artifacts(tmp_path: Path) -> None:
    supervision_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_supervision"
    _write_supervision(
        supervision_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "truth_class": "timing",
            "supervision_decision": "supervised_non_live",
            "execution_readiness": "ready_for_supervised_review",
            "fail_safe_status": "supervised_non_live",
        },
    )
    _write_supervision(
        supervision_dir / "cand_b.json",
        {
            "candidate_id": "cand_b",
            "module_name": "sandbox_cand_b",
            "truth_class": "failure",
            "supervision_decision": "supervised_non_live",
            "execution_readiness": "ready_for_supervised_review",
            "fail_safe_status": "supervised_non_live",
        },
    )
    _write_portfolio_state(
        tmp_path / "memory" / "knowledge_expansion" / "portfolio_risk_inputs" / "state.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "account_id": "paper",
            "strategy_group": "sandbox",
            "equity": 100000.0,
            "peak_equity": 101000.0,
            "open_exposure_pct": 0.1,
            "max_exposure_pct": 0.35,
            "suggested_position_size_pct": 0.02,
            "max_position_size_pct": 0.03,
            "capital_budget_pct": 0.3,
            "capital_allocated_pct": 0.15,
            "max_drawdown_pct": 8.0,
        },
    )

    result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    assert result["portfolio_artifact_count"] == 2

    artifacts = sorted(Path(path) for path in result["portfolio_artifacts"])
    assert [path.name for path in artifacts] == ["cand_a.json", "cand_b.json"]
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_PORTFOLIO_ARTIFACT_KEYS
        assert payload["portfolio_decision"] == PHASE_I_ADAPTIVE_PAPER_ONLY


def test_phase_i_deterministic_risk_and_allocation_mapping(tmp_path: Path) -> None:
    supervision_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_supervision"
    _write_supervision(
        supervision_dir / "cand_risk.json",
        {
            "candidate_id": "cand_risk",
            "module_name": "sandbox_cand_risk",
            "truth_class": "timing",
            "supervision_decision": "supervised_non_live",
            "execution_readiness": "ready_for_supervised_review",
            "fail_safe_status": "supervised_non_live",
        },
    )

    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "portfolio_risk_inputs"
    _write_portfolio_state(
        portfolio_dir / "state_1.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "equity": 100.0,
            "peak_equity": 120.0,
            "open_exposure_pct": 0.12,
            "max_exposure_pct": 0.35,
            "suggested_position_size_pct": 0.01,
            "max_position_size_pct": 0.03,
            "capital_budget_pct": 0.3,
            "capital_allocated_pct": 0.1,
            "max_drawdown_pct": 8.0,
        },
    )
    risk_result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    risk_payload = json.loads(Path(risk_result["portfolio_artifacts"][0]).read_text(encoding="utf-8"))
    assert risk_payload["portfolio_decision"] == PHASE_I_CAPITAL_PRESERVATION_MODE
    assert risk_payload["drawdown_state"] == "drawdown_breached"

    _write_portfolio_state(
        portfolio_dir / "state_2.json",
        {
            "timestamp": "2026-01-01T00:05:00+00:00",
            "equity": 100000.0,
            "peak_equity": 101000.0,
            "open_exposure_pct": 0.45,
            "max_exposure_pct": 0.35,
            "suggested_position_size_pct": 0.04,
            "max_position_size_pct": 0.03,
            "capital_budget_pct": 0.3,
            "capital_allocated_pct": 0.1,
            "max_drawdown_pct": 8.0,
        },
    )
    constrained_result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    constrained_payload = json.loads(Path(constrained_result["portfolio_artifacts"][0]).read_text(encoding="utf-8"))
    assert constrained_payload["portfolio_decision"] == PHASE_I_CONSTRAINED_NON_LIVE
    assert constrained_payload["exposure_state"] == "over_limit"
    assert constrained_payload["sizing_state"] == "size_constrained"


def test_phase_i_portfolio_state_memory_updates_across_time(tmp_path: Path) -> None:
    supervision_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_supervision"
    _write_supervision(
        supervision_dir / "cand_state.json",
        {
            "candidate_id": "cand_state",
            "module_name": "sandbox_cand_state",
            "truth_class": "timing",
            "supervision_decision": "supervised_non_live",
            "execution_readiness": "ready_for_supervised_review",
            "fail_safe_status": "supervised_non_live",
        },
    )

    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "portfolio_risk_inputs"
    _write_portfolio_state(
        portfolio_dir / "update_1.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "equity": 100000.0,
            "peak_equity": 100000.0,
            "open_exposure_pct": 0.1,
            "max_exposure_pct": 0.35,
            "suggested_position_size_pct": 0.01,
            "max_position_size_pct": 0.03,
            "capital_budget_pct": 0.3,
            "capital_allocated_pct": 0.1,
            "max_drawdown_pct": 8.0,
        },
    )
    first_result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    first_memory = json.loads(Path(first_result["portfolio_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(first_memory["state_history"]) == 1

    _write_portfolio_state(
        portfolio_dir / "update_2.json",
        {
            "timestamp": "2026-01-01T00:02:00+00:00",
            "equity": 99500.0,
            "peak_equity": 100000.0,
            "open_exposure_pct": 0.2,
            "max_exposure_pct": 0.35,
            "suggested_position_size_pct": 0.02,
            "max_position_size_pct": 0.03,
            "capital_budget_pct": 0.3,
            "capital_allocated_pct": 0.2,
            "max_drawdown_pct": 8.0,
        },
    )
    second_result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    second_memory = json.loads(Path(second_result["portfolio_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(second_memory["state_history"]) == 2
    assert second_memory["latest_portfolio_state"]["equity"] == 99500.0


def test_phase_i_live_activation_is_blocked_by_default(tmp_path: Path) -> None:
    supervision_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_supervision"
    _write_supervision(
        supervision_dir / "cand_guard.json",
        {
            "candidate_id": "cand_guard",
            "module_name": "sandbox_cand_guard",
            "truth_class": "timing",
            "supervision_decision": "supervised_non_live",
            "execution_readiness": "ready_for_supervised_review",
            "fail_safe_status": "supervised_non_live",
        },
    )

    result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    payload = json.loads(Path(result["portfolio_artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["live_activation_allowed"] is False
    assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_phase_i_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    supervision_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_supervision"
    _write_supervision(
        supervision_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "timing",
            "supervision_decision": "supervised_non_live",
            "execution_readiness": "ready_for_supervised_review",
            "fail_safe_status": "supervised_non_live",
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_i(tmp_path, mode="replay")
    output_dir = Path(result["portfolio_governance_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
