from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import run_knowledge_expansion_phase_l


REQUIRED_DISCOVERY_KEYS = {
    "candidate_id",
    "hypothesis_class",
    "pattern_signature",
    "statistical_summary",
    "replay_validation_summary",
    "discovery_timestamp",
    "discovery_version",
    "sandbox_status",
    "live_activation_allowed",
}


def _write_validated_registry(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_phase_l_generates_advanced_discovery_artifacts(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_a",
                    "truth_class": "timing",
                    "statement": "Session compression precedes trend continuation.",
                    "evidence_history": [{"signal": "compression"}, {"signal": "breakout"}],
                    "decision": "PROMOTE_TO_EXPERIMENT",
                    "decision_reasons": ["replay_gain"],
                }
            ]
        },
    )

    result = run_knowledge_expansion_phase_l(tmp_path, mode="replay")
    assert result["advanced_discovery_count"] == 1
    payload = json.loads(Path(result["advanced_discovery_artifacts"][0]).read_text(encoding="utf-8"))
    assert set(payload.keys()) == REQUIRED_DISCOVERY_KEYS
    assert payload["replay_validation_summary"]["replay_governed"] is True
    assert payload["sandbox_status"] == "replay_only"


def test_phase_l_duplicate_candidate_handling_is_deterministic(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_dup",
                    "truth_class": "liquidity",
                    "statement": "Initial statement",
                    "evidence_history": [{"signal": "sweep"}],
                    "decision": "HOLD_FOR_MORE_DATA",
                    "decision_reasons": ["insufficient_samples"],
                },
                {
                    "candidate_id": "cand_dup",
                    "truth_class": "liquidity",
                    "statement": "Updated deterministic statement",
                    "evidence_history": [{"signal": "sweep"}, {"signal": "reclaim"}],
                    "decision": "PROMOTE_TO_EXPERIMENT",
                    "decision_reasons": ["stable_replay"],
                },
            ]
        },
    )

    result = run_knowledge_expansion_phase_l(tmp_path, mode="replay")
    registry_payload = json.loads(Path(result["advanced_discovery_registry_path"]).read_text(encoding="utf-8"))
    assert result["advanced_discovery_count"] == 1
    assert len(registry_payload["discovery_records"]) == 1
    record = registry_payload["discovery_records"][0]
    assert record["replay_validation_summary"]["decision"] == "PROMOTE_TO_EXPERIMENT"
    assert record["statistical_summary"]["evidence_points"] == 2


def test_phase_l_does_not_mutate_live_execution_path(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_safe",
                    "truth_class": "meta-intelligence",
                    "statement": "Safe replay hypothesis",
                    "evidence_history": [{"signal": "diagnostic"}],
                    "decision": "HOLD_FOR_MORE_DATA",
                    "decision_reasons": ["non_live_only"],
                }
            ]
        },
    )
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_knowledge_expansion_phase_l(tmp_path, mode="replay")
    output_dir = Path(result["advanced_discovery_dir"])

    assert list(output_dir.glob("*.py")) == []
    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
