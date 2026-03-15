from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import run_continuous_governed_improvement_cycle


def _write_validated_registry(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_validated_knowledge(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_alpha",
                    "truth_class": "timing",
                    "statement": "Session compression precedes continuation.",
                    "evidence_history": [{"signal": "compression"}, {"signal": "breakout"}],
                    "decision": "PROMOTE_TO_EXPERIMENT",
                    "decision_reasons": ["replay_gain"],
                }
            ]
        },
    )


def test_continuous_cycle_executes_governed_phases(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    result = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="cycle-001",
    )

    assert result["continuous_governed_improvement_enabled"] is True
    phase_results = result["phase_results"]
    assert phase_results["discovery"]["advanced_discovery_count"] == 1
    assert phase_results["sandbox_generation"]["sandbox_module_count"] == 1
    assert phase_results["replay_judgment"]["sandbox_judgment_count"] == 1
    assert phase_results["promotion_governance"]["governance_artifact_count"] == 1
    assert phase_results["execution_governance"]["execution_governance_artifact_count"] == 1
    assert Path(result["cycle_artifact_path"]).exists()


def test_continuous_cycle_is_duplicate_safe_per_iteration(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    run_continuous_governed_improvement_cycle(tmp_path, mode="replay", baseline_summary={"score": 0.0}, iteration_id="dup")
    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="dup",
    )
    registry_payload = json.loads(Path(second["cycle_registry_path"]).read_text(encoding="utf-8"))

    assert len(registry_payload["cycles"]) == 1
    assert registry_payload["cycles"][0]["iteration_id"] == "dup"


def test_continuous_cycle_artifact_updates_are_deterministic(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)

    first = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="deterministic",
    )
    first_cycle_payload = json.loads(Path(first["cycle_artifact_path"]).read_text(encoding="utf-8"))
    first_sandbox = Path(first["phase_results"]["sandbox_generation"]["sandbox_module_artifacts"][0]).read_text(
        encoding="utf-8"
    )
    first_judgment = Path(first["phase_results"]["replay_judgment"]["sandbox_judgments"][0]).read_text(
        encoding="utf-8"
    )

    second = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="deterministic",
    )
    second_cycle_payload = json.loads(Path(second["cycle_artifact_path"]).read_text(encoding="utf-8"))
    second_sandbox = Path(second["phase_results"]["sandbox_generation"]["sandbox_module_artifacts"][0]).read_text(
        encoding="utf-8"
    )
    second_judgment = Path(second["phase_results"]["replay_judgment"]["sandbox_judgments"][0]).read_text(
        encoding="utf-8"
    )

    assert second["cycle_signature"] == first["cycle_signature"]
    assert second_cycle_payload == first_cycle_payload
    assert second_sandbox == first_sandbox
    assert second_judgment == first_judgment


def test_continuous_cycle_does_not_mutate_live_execution_paths(tmp_path: Path) -> None:
    _seed_validated_knowledge(tmp_path)
    execution_path = tmp_path / "src" / "execution_pipeline.py"
    execution_path.parent.mkdir(parents=True, exist_ok=True)
    execution_path.write_text("EXECUTION_PATH = 'stable'\n", encoding="utf-8")
    before_execution_contents = execution_path.read_text(encoding="utf-8")

    result = run_continuous_governed_improvement_cycle(
        tmp_path,
        mode="replay",
        baseline_summary={"score": 0.0},
        iteration_id="live-guard",
    )

    assert execution_path.read_text(encoding="utf-8") == before_execution_contents
    execution_phase = result["phase_results"]["execution_governance"]
    for artifact_path in execution_phase["execution_governance_artifacts"]:
        payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        assert payload["live_activation_allowed"] is False
        assert payload["risk_constraints"]["live_execution_blocked"] is True
