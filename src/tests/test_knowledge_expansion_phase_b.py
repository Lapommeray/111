from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import generate_experimental_module_specs


REQUIRED_SPEC_KEYS = {
    "candidate_id",
    "truth_class",
    "truth_class_rationale",
    "usefulness_scope",
    "hypothesis_statement",
    "evidence_summary",
    "promotion_status",
    "spec_version",
    "generated_at",
}


def _write_validated_registry(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"validated_knowledge": entries}, indent=2), encoding="utf-8")


def test_phase_b_creates_experimental_spec_directory(tmp_path: Path) -> None:
    registry_path = tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json"
    output_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_validated_registry(
        registry_path,
        entries=[{"candidate_id": "cand_001", "truth_class": "timing", "statement": "test", "decision": "KEEP"}],
    )

    generate_experimental_module_specs(registry_path, output_dir)
    assert output_dir.exists()
    assert output_dir.is_dir()


def test_phase_b_generates_specs_from_validated_knowledge(tmp_path: Path) -> None:
    registry_path = tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json"
    output_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_validated_registry(
        registry_path,
        entries=[
            {
                "candidate_id": "cand_alpha",
                "truth_class": "timing",
                "truth_class_rationale": "Session-sensitive signal quality.",
                "usefulness_scope": "conditional",
                "statement": "Only useful during london session.",
                "evidence_history": [{"session": "london", "alignment_ratio": 0.72}],
                "decision_reasons": ["consistent_alignment"],
                "decision": "KEEP",
            },
            {
                "candidate_id": "cand_beta",
                "truth_class": "failure",
                "statement": "Reject setup when spread is too wide.",
                "evidence_history": [{"reason": "spread_too_wide", "count": 10}],
                "decision": "MERGE",
            },
        ],
    )

    result = generate_experimental_module_specs(registry_path, output_dir)
    assert result["experimental_spec_count"] == 2

    artifacts = sorted(output_dir.glob("*.json"))
    assert len(artifacts) == 2
    assert [path.name for path in artifacts] == ["cand_alpha.json", "cand_beta.json"]
    for artifact_path in artifacts:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert set(payload.keys()) == REQUIRED_SPEC_KEYS


def test_phase_b_deduplicates_by_candidate_id(tmp_path: Path) -> None:
    registry_path = tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json"
    output_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_validated_registry(
        registry_path,
        entries=[
            {
                "candidate_id": "cand_repeat",
                "truth_class": "timing",
                "statement": "initial",
                "decision": "HOLD_FOR_MORE_DATA",
            },
            {
                "candidate_id": "cand_repeat",
                "truth_class": "timing",
                "statement": "updated",
                "decision": "KEEP",
            },
        ],
    )

    result = generate_experimental_module_specs(registry_path, output_dir)
    assert result["experimental_spec_count"] == 1

    spec_path = output_dir / "cand_repeat.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    assert payload["hypothesis_statement"] == "updated"
    assert payload["promotion_status"] == "KEEP"


def test_phase_b_artifacts_are_governance_json_only(tmp_path: Path) -> None:
    registry_path = tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json"
    output_dir = tmp_path / "memory" / "knowledge_expansion" / "experimental_module_specs"
    _write_validated_registry(
        registry_path,
        entries=[
            {
                "candidate_id": "cand_safe",
                "truth_class": "meta-intelligence",
                "statement": "governance-only artifact",
                "decision": "KEEP",
            }
        ],
    )

    generate_experimental_module_specs(registry_path, output_dir)

    assert list(output_dir.glob("*.py")) == []
    payload = json.loads((output_dir / "cand_safe.json").read_text(encoding="utf-8"))
    assert set(payload.keys()) == REQUIRED_SPEC_KEYS
