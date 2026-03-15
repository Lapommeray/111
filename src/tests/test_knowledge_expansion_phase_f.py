from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_F_BLOCKED,
    PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW,
    PHASE_F_MANUAL_REVIEW_REQUIRED,
    run_knowledge_expansion_phase_f,
)


REQUIRED_EXECUTION_GOVERNANCE_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "governance_source_path",
    "execution_governance_timestamp",
    "governance_decision",
    "execution_decision",
    "execution_reason",
    "execution_status",
    "manual_approval_required",
    "live_activation_allowed",
    "risk_constraints",
    "governor_version",
}


def _write_promotion_governance(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_f_creates_execution_governance_directory(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_alpha.json",
        {
            "candidate_id": "cand_alpha",
            "module_name": "sandbox_cand_alpha",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved replay outcome",
        },
    )

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    output_dir = Path(result["execution_governance_dir"])
    assert output_dir.exists()
    assert output_dir.is_dir()


def test_phase_f_generates_execution_governance_artifacts_from_promotion_governance(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved",
        },
    )
    _write_promotion_governance(
        governance_dir / "cand_b.json",
        {
            "candidate_id": "cand_b",
            "module_name": "sandbox_cand_b",
            "truth_class": "failure",
            "governance_decision": "rejected",
            "governance_reason": "regressed",
        },
    )

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    assert result["execution_governance_artifact_count"] == 2

    artifacts = sorted(Path(path) for path in result["execution_governance_artifacts"])
    assert [path.name for path in artifacts] == ["cand_a.json", "cand_b.json"]
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_EXECUTION_GOVERNANCE_KEYS


def test_phase_f_outputs_deterministic_execution_decision_mapping(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_blocked.json",
        {
            "candidate_id": "cand_blocked",
            "module_name": "sandbox_cand_blocked",
            "truth_class": "failure",
            "governance_decision": "rejected",
            "governance_reason": "regressed",
        },
    )
    _write_promotion_governance(
        governance_dir / "cand_manual.json",
        {
            "candidate_id": "cand_manual",
            "module_name": "sandbox_cand_manual",
            "truth_class": "meta-intelligence",
            "governance_decision": "retained_for_further_replay",
            "governance_reason": "needs more validation",
        },
    )
    _write_promotion_governance(
        governance_dir / "cand_review.json",
        {
            "candidate_id": "cand_review",
            "module_name": "sandbox_cand_review",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved",
        },
    )

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    decisions = {}
    for path in result["execution_governance_artifacts"]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        decisions[payload["candidate_id"]] = payload["execution_decision"]

    assert decisions["cand_blocked"] == PHASE_F_BLOCKED
    assert decisions["cand_manual"] == PHASE_F_MANUAL_REVIEW_REQUIRED
    assert decisions["cand_review"] == PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW


def test_phase_f_deduplicates_duplicate_promotion_candidates(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_dup_v1.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup_v1",
            "truth_class": "timing",
            "governance_decision": "retained_for_further_replay",
            "governance_reason": "neutral",
        },
    )
    _write_promotion_governance(
        governance_dir / "cand_dup_v2.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup_v2",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved",
        },
    )

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    assert result["execution_governance_artifact_count"] == 1

    payload = json.loads((Path(result["execution_governance_dir"]) / "cand_dup.json").read_text(encoding="utf-8"))
    assert payload["module_name"] == "sandbox_cand_dup_v2"

    registry = json.loads(Path(result["controlled_execution_registry_path"]).read_text(encoding="utf-8"))
    assert len(registry["execution_records"]) == 1


def test_phase_f_defaults_to_manual_approval_required(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_manual_default.json",
        {
            "candidate_id": "cand_manual_default",
            "module_name": "sandbox_cand_manual_default",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved",
        },
    )

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    payload = json.loads(Path(result["execution_governance_artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["manual_approval_required"] is True


def test_phase_f_live_activation_is_blocked_by_default(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_live_guard.json",
        {
            "candidate_id": "cand_live_guard",
            "module_name": "sandbox_cand_live_guard",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved",
        },
    )

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    payload = json.loads(Path(result["execution_governance_artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["live_activation_allowed"] is False
    assert payload["risk_constraints"]["live_execution_blocked"] is True


def test_phase_f_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "timing",
            "governance_decision": "promotion_candidate",
            "governance_reason": "improved",
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    output_dir = Path(result["execution_governance_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents


def test_phase_f_registry_writing_is_stable(tmp_path: Path) -> None:
    governance_dir = tmp_path / "memory" / "knowledge_expansion" / "promotion_governance"
    _write_promotion_governance(
        governance_dir / "cand_beta.json",
        {
            "candidate_id": "cand_beta",
            "module_name": "sandbox_cand_beta",
            "truth_class": "timing",
            "governance_timestamp": "2026-01-01T00:00:01+00:00",
            "governance_decision": "retained_for_further_replay",
            "governance_reason": "neutral",
        },
    )
    _write_promotion_governance(
        governance_dir / "cand_alpha.json",
        {
            "candidate_id": "cand_alpha",
            "module_name": "sandbox_cand_alpha",
            "truth_class": "failure",
            "governance_timestamp": "2026-01-01T00:00:00+00:00",
            "governance_decision": "rejected",
            "governance_reason": "regressed",
        },
    )

    first_result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    first_registry = json.loads(Path(first_result["controlled_execution_registry_path"]).read_text(encoding="utf-8"))
    second_result = run_knowledge_expansion_phase_f(tmp_path, mode="replay")
    second_registry = json.loads(Path(second_result["controlled_execution_registry_path"]).read_text(encoding="utf-8"))

    assert [item["candidate_id"] for item in second_registry["execution_records"]] == ["cand_alpha", "cand_beta"]
    assert len(second_registry["execution_records"]) == 2
    assert second_registry == first_registry
