from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import (
    load_sandbox_module_artifacts,
    run_knowledge_expansion_phase_c,
)


REQUIRED_MODULE_KEYS = {
    "candidate_id",
    "module_name",
    "truth_class",
    "hypothesis_statement",
    "evidence_summary",
    "source_spec_path",
    "generation_timestamp",
    "sandbox_status",
    "module_version",
}


def _write_experimental_spec(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_c_creates_sandbox_modules_directory(tmp_path: Path) -> None:
    specs_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_experimental_spec(
        specs_dir / "cand_a.json",
        {
            "candidate_id": "cand_a",
            "truth_class": "timing",
            "hypothesis_statement": "session edge",
            "evidence_summary": {"evidence_points": 1},
        },
    )

    result = run_knowledge_expansion_phase_c(tmp_path)
    output_dir = Path(result["sandbox_modules_dir"])
    assert output_dir.exists()
    assert output_dir.is_dir()


def test_phase_c_generates_module_artifacts_from_experimental_specs(tmp_path: Path) -> None:
    specs_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_experimental_spec(
        specs_dir / "cand_alpha.json",
        {
            "candidate_id": "cand_alpha",
            "truth_class": "timing",
            "hypothesis_statement": "alpha hypothesis",
            "evidence_summary": {"evidence_points": 3},
        },
    )
    _write_experimental_spec(
        specs_dir / "cand_beta.json",
        {
            "candidate_id": "cand_beta",
            "truth_class": "failure",
            "hypothesis_statement": "beta hypothesis",
            "evidence_summary": {"evidence_points": 4},
        },
    )

    result = run_knowledge_expansion_phase_c(tmp_path)
    assert result["sandbox_module_count"] == 2

    output_dir = Path(result["sandbox_modules_dir"])
    artifacts = sorted(output_dir.glob("*.json"))
    assert [path.name for path in artifacts] == ["cand_alpha.json", "cand_beta.json"]
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_MODULE_KEYS
        assert payload["sandbox_status"] == "replay_only"
        assert payload["module_version"] == "1.0"


def test_phase_c_deduplicates_by_candidate_id(tmp_path: Path) -> None:
    specs_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_experimental_spec(
        specs_dir / "cand_repeat_v1.json",
        {
            "candidate_id": "cand_repeat",
            "truth_class": "timing",
            "hypothesis_statement": "initial version",
            "evidence_summary": {"evidence_points": 1},
        },
    )
    _write_experimental_spec(
        specs_dir / "cand_repeat_v2.json",
        {
            "candidate_id": "cand_repeat",
            "truth_class": "timing",
            "hypothesis_statement": "updated version",
            "evidence_summary": {"evidence_points": 2},
        },
    )

    result = run_knowledge_expansion_phase_c(tmp_path)
    assert result["sandbox_module_count"] == 1

    payload = json.loads((Path(result["sandbox_modules_dir"]) / "cand_repeat.json").read_text(encoding="utf-8"))
    assert payload["hypothesis_statement"] == "updated version"


def test_phase_c_loader_is_replay_only(tmp_path: Path) -> None:
    specs_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_experimental_spec(
        specs_dir / "cand_loader.json",
        {
            "candidate_id": "cand_loader",
            "truth_class": "timing",
            "hypothesis_statement": "loader replay-only check",
            "evidence_summary": {"evidence_points": 1},
        },
    )
    result = run_knowledge_expansion_phase_c(tmp_path)
    modules_dir = Path(result["sandbox_modules_dir"])

    live_payload = load_sandbox_module_artifacts(modules_dir, mode="live")
    assert live_payload == {
        "sandbox_enabled": False,
        "sandbox_module_count": 0,
        "sandbox_modules": [],
    }

    replay_payload = load_sandbox_module_artifacts(modules_dir, mode="replay")
    assert replay_payload["sandbox_enabled"] is True
    assert replay_payload["sandbox_module_count"] == 1
    assert replay_payload["sandbox_modules"][0]["candidate_id"] == "cand_loader"


def test_phase_c_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    specs_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_experimental_spec(
        specs_dir / "cand_safe.json",
        {
            "candidate_id": "cand_safe",
            "truth_class": "meta-intelligence",
            "hypothesis_statement": "governance-only module artifact",
            "evidence_summary": {"evidence_points": 1},
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_c(tmp_path)
    output_dir = Path(result["sandbox_modules_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
