from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    PHASE_D_PROMOTION_CANDIDATE,
    PHASE_D_REJECT,
    PHASE_D_RETAIN_FOR_FURTHER_REPLAY,
    run_knowledge_expansion_phase_d,
)


REQUIRED_JUDGMENT_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "judgment_timestamp",
    "replay_scope",
    "baseline_summary",
    "module_summary",
    "comparison_summary",
    "decision",
    "decision_reason",
    "promotion_status",
}


def _write_sandbox_module(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_d_creates_sandbox_judgments_directory(tmp_path: Path) -> None:
    modules_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_modules"
    _write_sandbox_module(
        modules_dir / "cand_alpha.json",
        {
            "candidate_id": "cand_alpha",
            "module_name": "sandbox_cand_alpha",
            "truth_class": "timing",
            "evidence_summary": {"evidence_points": 4},
        },
    )

    result = run_knowledge_expansion_phase_d(tmp_path, mode="replay", baseline_summary={"score": 2})
    judgments_dir = Path(result["sandbox_judgments_dir"])
    assert judgments_dir.exists()
    assert judgments_dir.is_dir()


def test_phase_d_judging_is_replay_only(tmp_path: Path) -> None:
    modules_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_modules"
    _write_sandbox_module(
        modules_dir / "cand_live.json",
        {
            "candidate_id": "cand_live",
            "module_name": "sandbox_cand_live",
            "truth_class": "failure",
            "evidence_summary": {"evidence_points": 1},
        },
    )

    result = run_knowledge_expansion_phase_d(tmp_path, mode="live", baseline_summary={"score": 1})
    judgments_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_judgments"

    assert result["sandbox_enabled"] is False
    assert result["sandbox_judgment_count"] == 0
    assert result["sandbox_judgments"] == []
    assert not judgments_dir.exists()


def test_phase_d_creates_comparison_artifact_with_required_fields(tmp_path: Path) -> None:
    modules_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_modules"
    _write_sandbox_module(
        modules_dir / "cand_compare.json",
        {
            "candidate_id": "cand_compare",
            "module_name": "sandbox_cand_compare",
            "truth_class": "liquidity",
            "evidence_summary": {"evidence_points": 8},
        },
    )

    result = run_knowledge_expansion_phase_d(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 3},
        replay_scope="window_1_to_50",
    )
    artifact_path = Path(result["sandbox_judgments"][0])
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert set(payload.keys()) == REQUIRED_JUDGMENT_KEYS
    assert payload["candidate_id"] == "cand_compare"
    assert payload["replay_scope"] == "window_1_to_50"
    assert payload["comparison_summary"]["effect"] == "improved"


def test_phase_d_outputs_deterministic_decisions(tmp_path: Path) -> None:
    modules_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_modules"
    _write_sandbox_module(
        modules_dir / "cand_improve.json",
        {
            "candidate_id": "cand_improve",
            "module_name": "sandbox_cand_improve",
            "truth_class": "timing",
            "evidence_summary": {"evidence_points": 7},
        },
    )
    _write_sandbox_module(
        modules_dir / "cand_regress.json",
        {
            "candidate_id": "cand_regress",
            "module_name": "sandbox_cand_regress",
            "truth_class": "failure",
            "evidence_summary": {"evidence_points": 2},
        },
    )
    _write_sandbox_module(
        modules_dir / "cand_neutral.json",
        {
            "candidate_id": "cand_neutral",
            "module_name": "sandbox_cand_neutral",
            "truth_class": "meta-intelligence",
            "evidence_summary": {"evidence_points": 5.02},
        },
    )

    result = run_knowledge_expansion_phase_d(tmp_path, mode="replay", baseline_summary={"score": 5})
    artifacts = sorted(Path(path) for path in result["sandbox_judgments"])
    decisions = {}
    for path in artifacts:
        payload = json.loads(path.read_text(encoding="utf-8"))
        decisions[payload["candidate_id"]] = payload["decision"]

    assert decisions["cand_improve"] == PHASE_D_PROMOTION_CANDIDATE
    assert decisions["cand_regress"] == PHASE_D_REJECT
    assert decisions["cand_neutral"] == PHASE_D_RETAIN_FOR_FURTHER_REPLAY


def test_phase_d_deduplicates_duplicate_candidate_modules(tmp_path: Path) -> None:
    modules_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_modules"
    _write_sandbox_module(
        modules_dir / "cand_dup_v1.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup_v1",
            "truth_class": "timing",
            "evidence_summary": {"evidence_points": 2},
        },
    )
    _write_sandbox_module(
        modules_dir / "cand_dup_v2.json",
        {
            "candidate_id": "cand_dup",
            "module_name": "sandbox_cand_dup_v2",
            "truth_class": "timing",
            "evidence_summary": {"evidence_points": 9},
        },
    )

    result = run_knowledge_expansion_phase_d(tmp_path, mode="replay", baseline_summary={"score": 3})
    assert result["sandbox_module_count"] == 1
    assert result["sandbox_judgment_count"] == 1

    payload = json.loads((Path(result["sandbox_judgments_dir"]) / "cand_dup.json").read_text(encoding="utf-8"))
    assert payload["module_name"] == "sandbox_cand_dup_v2"


def test_phase_d_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    modules_dir = tmp_path / "memory" / "knowledge_expansion" / "sandbox_modules"
    _write_sandbox_module(
        modules_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "module_name": "sandbox_cand_safe",
            "truth_class": "meta-intelligence",
            "evidence_summary": {"evidence_points": 5},
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_d(tmp_path, mode="replay", baseline_summary={"score": 4})
    judgments_dir = Path(result["sandbox_judgments_dir"])

    assert list(judgments_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
