from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_G_CONTROLLED_REVIEW_SIGNAL,
    PHASE_G_HOLD_NON_LIVE,
    PHASE_G_PAPER_EXECUTION_ONLY,
    run_knowledge_expansion_phase_g,
)


REQUIRED_DECISION_ARTIFACT_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "execution_source_path",
    "decision_timestamp",
    "execution_decision",
    "orchestrator_decision",
    "decision_reason",
    "decision_status",
    "market_state_snapshot",
    "market_state_memory_path",
    "manual_approval_required",
    "live_activation_allowed",
    "risk_constraints",
    "governor_version",
}


def _write_execution_governance(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_market_update(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_g_generates_controlled_decision_artifacts(tmp_path: Path) -> None:
    execution_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_governance"
    _write_execution_governance(
        execution_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "truth_class": "timing",
            "execution_decision": "eligible_for_controlled_execution_review",
        },
    )
    _write_execution_governance(
        execution_dir / "cand_b.json",
        {
            "candidate_id": "cand_b",
            "module_name": "sandbox_cand_b",
            "truth_class": "failure",
            "execution_decision": "blocked",
        },
    )
    _write_market_update(
        tmp_path / "memory" / "knowledge_expansion" / "market_data_feed" / "recent.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "EURUSD",
            "trend": "up",
            "volatility": 0.02,
            "liquidity_state": "normal",
        },
    )

    result = run_knowledge_expansion_phase_g(tmp_path, mode="replay")
    assert result["decision_artifact_count"] == 2

    artifacts = sorted(Path(path) for path in result["decision_artifacts"])
    assert [path.name for path in artifacts] == ["cand_a.json", "cand_b.json"]
    decisions = {}
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_DECISION_ARTIFACT_KEYS
        decisions[payload["candidate_id"]] = payload["orchestrator_decision"]

    assert decisions["cand_a"] == PHASE_G_CONTROLLED_REVIEW_SIGNAL
    assert decisions["cand_b"] == PHASE_G_HOLD_NON_LIVE


def test_phase_g_market_state_memory_updates_across_time(tmp_path: Path) -> None:
    execution_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_governance"
    _write_execution_governance(
        execution_dir / "cand_state.json",
        {
            "candidate_id": "cand_state",
            "module_name": "sandbox_cand_state",
            "truth_class": "timing",
            "execution_decision": "eligible_for_controlled_execution_review",
        },
    )
    market_dir = tmp_path / "memory" / "knowledge_expansion" / "market_data_feed"
    _write_market_update(
        market_dir / "update_1.json",
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "EURUSD",
            "trend": "up",
            "volatility": 0.03,
            "liquidity_state": "normal",
        },
    )
    first_result = run_knowledge_expansion_phase_g(tmp_path, mode="replay")
    first_memory = json.loads(Path(first_result["market_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(first_memory["state_history"]) == 1
    assert first_memory["latest_market_state"]["symbol"] == "EURUSD"

    _write_market_update(
        market_dir / "update_2.json",
        {
            "timestamp": "2026-01-01T00:05:00+00:00",
            "symbol": "EURUSD",
            "trend": "down",
            "volatility": 0.09,
            "liquidity_state": "thin",
        },
    )
    second_result = run_knowledge_expansion_phase_g(tmp_path, mode="replay")
    second_memory = json.loads(Path(second_result["market_state_memory_path"]).read_text(encoding="utf-8"))
    assert len(second_memory["state_history"]) == 2
    assert second_memory["latest_market_state"]["trend"] == "down"

    decision_payload = json.loads(Path(second_result["decision_artifacts"][0]).read_text(encoding="utf-8"))
    assert decision_payload["orchestrator_decision"] == PHASE_G_PAPER_EXECUTION_ONLY


def test_phase_g_live_activation_is_blocked_by_default(tmp_path: Path) -> None:
    execution_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_governance"
    _write_execution_governance(
        execution_dir / "cand_guard.json",
        {
            "candidate_id": "cand_guard",
            "module_name": "sandbox_cand_guard",
            "truth_class": "timing",
            "execution_decision": "eligible_for_controlled_execution_review",
        },
    )

    result = run_knowledge_expansion_phase_g(tmp_path, mode="replay")
    payload = json.loads(Path(result["decision_artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["live_activation_allowed"] is False
    assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_phase_g_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    execution_dir = tmp_path / "memory" / "knowledge_expansion" / "execution_governance"
    _write_execution_governance(
        execution_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "timing",
            "execution_decision": "eligible_for_controlled_execution_review",
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_g(tmp_path, mode="replay")
    output_dir = Path(result["decision_orchestrator_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
