from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import run_knowledge_expansion_phase_k


REQUIRED_LONG_HORIZON_MEMORY_KEYS = {
    "candidate_id",
    "module_name",
    "time_horizon_window",
    "historical_market_state_summary",
    "decision_outcome_history",
    "performance_snapshot",
    "memory_timestamp",
    "memory_version",
    "phase_g_source_path",
    "phase_i_source_path",
    "manual_approval_required",
    "live_activation_allowed",
    "risk_constraints",
}


def _write_decision(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_portfolio(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_k_generates_long_horizon_memory_artifacts(tmp_path: Path) -> None:
    decision_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_decision(
        decision_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "orchestrator_decision": "controlled_review_signal",
            "execution_readiness": "ready_for_controlled_review",
            "market_state_snapshot": {"regime_state": "stable_trend", "volatility_state": "contained"},
            "decision_timestamp": "2026-01-01T00:00:00+00:00",
        },
    )
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
            "risk_state": "adaptive_balanced",
            "drawdown_state": "within_limit",
            "allocation_state": "budget_available",
            "portfolio_timestamp": "2026-01-01T00:01:00+00:00",
            "portfolio_state_snapshot": {
                "equity": 100000.0,
                "peak_equity": 101000.0,
                "open_exposure_pct": 0.2,
                "capital_allocated_pct": 0.1,
                "max_drawdown_pct": 8.0,
            },
        },
    )

    result = run_knowledge_expansion_phase_k(tmp_path, mode="replay")
    assert result["long_horizon_memory_count"] == 1
    payload = json.loads(Path(result["long_horizon_memory_artifacts"][0]).read_text(encoding="utf-8"))
    assert set(payload.keys()) == REQUIRED_LONG_HORIZON_MEMORY_KEYS
    assert payload["time_horizon_window"] == "long_horizon_90d"
    assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_phase_k_memory_persistence_and_duplicate_handling(tmp_path: Path) -> None:
    decision_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_decision(
        decision_dir / "cand_dup_a.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup",
            "orchestrator_decision": "paper_execution_only",
            "execution_readiness": "ready_for_controlled_review",
            "decision_timestamp": "2026-01-01T00:00:00+00:00",
        },
    )
    _write_decision(
        decision_dir / "cand_dup_b.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup",
            "orchestrator_decision": "controlled_review_signal",
            "execution_readiness": "ready_for_controlled_review",
            "decision_timestamp": "2026-01-01T00:00:00+00:00",
        },
    )
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_dup.json",
        {
            "candidate_id": "cand_dup",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
            "portfolio_timestamp": "2026-01-01T00:01:00+00:00",
            "portfolio_state_snapshot": {"equity": 100000.0, "peak_equity": 101000.0},
        },
    )

    first_result = run_knowledge_expansion_phase_k(tmp_path, mode="replay")
    first_state = json.loads(Path(first_result["long_horizon_memory_state_path"]).read_text(encoding="utf-8"))
    assert first_result["long_horizon_memory_count"] == 1
    assert len(first_state["state_history"]) == 1

    second_result = run_knowledge_expansion_phase_k(tmp_path, mode="replay")
    second_state = json.loads(Path(second_result["long_horizon_memory_state_path"]).read_text(encoding="utf-8"))
    registry_payload = json.loads(Path(second_result["long_horizon_memory_registry_path"]).read_text(encoding="utf-8"))
    assert second_result["long_horizon_memory_count"] == 1
    assert len(second_state["state_history"]) == 1
    assert len(registry_payload["memory_records"]) == 1


def test_phase_k_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    decision_dir = tmp_path / "memory" / "knowledge_expansion" / "decision_orchestrator"
    _write_decision(
        decision_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "orchestrator_decision": "controlled_review_signal",
            "execution_readiness": "ready_for_controlled_review",
        },
    )
    portfolio_dir = tmp_path / "memory" / "knowledge_expansion" / "adaptive_portfolio_governance"
    _write_portfolio(
        portfolio_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "portfolio_decision": "adaptive_paper_only",
            "execution_readiness": "ready_for_supervised_review",
            "portfolio_state_snapshot": {"equity": 100000.0},
        },
    )

    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_k(tmp_path, mode="replay")
    output_dir = Path(result["long_horizon_memory_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
