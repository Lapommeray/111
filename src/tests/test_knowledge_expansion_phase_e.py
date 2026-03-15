from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_E_PROMOTION_CANDIDATE,
    PHASE_E_REJECTED,
    PHASE_E_RETAINED_FOR_FURTHER_REPLAY,
    run_knowledge_expansion_phase_e,
)


REQUIRED_GOVERNANCE_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "governance_timestamp",
    "judgment_summary",
    "governance_decision",
    "governance_reason",
    "promotion_status",
    "replay_revalidation_required",
    "source_judgment_path",
    "governor_version",
}


def _write_sandbox_judgment(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_e_creates_promotion_governance_directory(tmp_path: Path) -> None:
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"
    _write_sandbox_judgment(
        judgments_dir / "cand_alpha.json",
        {
            "candidate_id": "cand_alpha",
            "module_name": "sandbox_cand_alpha",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:00+00:00",
            "comparison_summary": {"effect": "improved", "score_delta": 1.5},
            "decision": "promotion_candidate",
            "decision_reason": "positive replay delta",
        },
    )

    result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    output_dir = Path(result["promotion_governance_dir"])
    assert output_dir.exists()
    assert output_dir.is_dir()


def test_phase_e_generates_governance_artifacts_from_sandbox_judgments(tmp_path: Path) -> None:
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"
    _write_sandbox_judgment(
        judgments_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "module_name": "sandbox_cand_a",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:00+00:00",
            "comparison_summary": {"effect": "improved", "score_delta": 2.0},
            "decision": "promotion_candidate",
            "decision_reason": "improved",
        },
    )
    _write_sandbox_judgment(
        judgments_dir / "cand_b.json",
        {
            "candidate_id": "cand_b",
            "module_name": "sandbox_cand_b",
            "truth_class": "failure",
            "judgment_timestamp": "2026-01-01T00:00:01+00:00",
            "comparison_summary": {"effect": "regressed", "score_delta": -1.0},
            "decision": "reject",
            "decision_reason": "regressed",
        },
    )

    result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    assert result["governance_artifact_count"] == 2

    artifacts = sorted(Path(path) for path in result["promotion_governance_artifacts"])
    assert [path.name for path in artifacts] == ["cand_a.json", "cand_b.json"]
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_GOVERNANCE_KEYS


def test_phase_e_outputs_deterministic_decision_mapping(tmp_path: Path) -> None:
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"
    _write_sandbox_judgment(
        judgments_dir / "cand_reject.json",
        {
            "candidate_id": "cand_reject",
            "module_name": "sandbox_cand_reject",
            "truth_class": "failure",
            "judgment_timestamp": "2026-01-01T00:00:00+00:00",
            "comparison_summary": {"effect": "regressed", "score_delta": -1.2},
            "decision": "reject",
            "decision_reason": "regressed",
        },
    )
    _write_sandbox_judgment(
        judgments_dir / "cand_retain.json",
        {
            "candidate_id": "cand_retain",
            "module_name": "sandbox_cand_retain",
            "truth_class": "meta-intelligence",
            "judgment_timestamp": "2026-01-01T00:00:01+00:00",
            "comparison_summary": {"effect": "no_meaningful_effect", "score_delta": 0.0},
            "decision": "retain_for_further_replay",
            "decision_reason": "neutral",
        },
    )
    _write_sandbox_judgment(
        judgments_dir / "cand_promote.json",
        {
            "candidate_id": "cand_promote",
            "module_name": "sandbox_cand_promote",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:02+00:00",
            "comparison_summary": {"effect": "improved", "score_delta": 0.8},
            "decision": "promotion_candidate",
            "decision_reason": "improved",
        },
    )

    result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    decisions = {}
    for path in result["promotion_governance_artifacts"]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        decisions[payload["candidate_id"]] = payload["governance_decision"]

    assert decisions["cand_reject"] == PHASE_E_REJECTED
    assert decisions["cand_retain"] == PHASE_E_RETAINED_FOR_FURTHER_REPLAY
    assert decisions["cand_promote"] == PHASE_E_PROMOTION_CANDIDATE


def test_phase_e_deduplicates_duplicate_candidate_judgments(tmp_path: Path) -> None:
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"
    _write_sandbox_judgment(
        judgments_dir / "cand_dup_v1.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup_v1",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:00+00:00",
            "comparison_summary": {"effect": "no_meaningful_effect", "score_delta": 0.0},
            "decision": "retain_for_further_replay",
            "decision_reason": "neutral",
        },
    )
    _write_sandbox_judgment(
        judgments_dir / "cand_dup_v2.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup_v2",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:01+00:00",
            "comparison_summary": {"effect": "improved", "score_delta": 0.7},
            "decision": "promotion_candidate",
            "decision_reason": "improved",
        },
    )

    result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    assert result["governance_artifact_count"] == 1

    payload = json.loads((Path(result["promotion_governance_dir"]) / "cand_dup.json").read_text(encoding="utf-8"))
    assert payload["module_name"] == "sandbox_cand_dup_v2"

    registry = json.loads(Path(result["promotion_registry_path"]).read_text(encoding="utf-8"))
    assert len(registry["governance_records"]) == 1


def test_phase_e_isolation_from_live_execution(tmp_path: Path) -> None:
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"
    _write_sandbox_judgment(
        judgments_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:00+00:00",
            "comparison_summary": {"effect": "improved", "score_delta": 1.0},
            "decision": "promotion_candidate",
            "decision_reason": "improved",
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    output_dir = Path(result["promotion_governance_dir"])
    payload = json.loads((output_dir / "cand_safe.json").read_text(encoding="utf-8"))

    assert list(output_dir.glob("*.py")) == []
    assert payload["promotion_status"] == "non_live_candidate"
    assert payload["replay_revalidation_required"] is True
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents


def test_phase_e_registry_writing_is_stable(tmp_path: Path) -> None:
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"
    _write_sandbox_judgment(
        judgments_dir / "cand_beta.json",
        {
            "candidate_id": "cand_beta",
            "module_name": "sandbox_cand_beta",
            "truth_class": "timing",
            "judgment_timestamp": "2026-01-01T00:00:01+00:00",
            "comparison_summary": {"effect": "no_meaningful_effect", "score_delta": 0.0},
            "decision": "retain_for_further_replay",
            "decision_reason": "neutral",
        },
    )
    _write_sandbox_judgment(
        judgments_dir / "cand_alpha.json",
        {
            "candidate_id": "cand_alpha",
            "module_name": "sandbox_cand_alpha",
            "truth_class": "failure",
            "judgment_timestamp": "2026-01-01T00:00:00+00:00",
            "comparison_summary": {"effect": "regressed", "score_delta": -1.0},
            "decision": "reject",
            "decision_reason": "regressed",
        },
    )

    first_result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    first_registry = json.loads(Path(first_result["promotion_registry_path"]).read_text(encoding="utf-8"))
    second_result = run_knowledge_expansion_phase_e(tmp_path, mode="replay")
    second_registry = json.loads(Path(second_result["promotion_registry_path"]).read_text(encoding="utf-8"))

    assert [item["candidate_id"] for item in second_registry["governance_records"]] == ["cand_alpha", "cand_beta"]
    assert len(second_registry["governance_records"]) == 2
    assert second_registry == first_registry
