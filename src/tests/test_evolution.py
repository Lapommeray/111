from __future__ import annotations

from pathlib import Path

from run import RuntimeConfig, ensure_sample_data, run_evolution_kernel
from src.evolution.evolution_registry import EvolutionRegistry
from src.evolution.promoter import Promoter
from src.evolution.self_inspector import SelfInspector
from src.evolution.verifier import Verifier
from src.utils import write_json_atomic


def test_evolution_registry_lifecycle(tmp_path: Path) -> None:
    registry = EvolutionRegistry(tmp_path / "evolution_registry.json")
    entry = registry.append_entry(
        gap={"gap_id": "missing_tests_1", "reason": "missing_tests", "target": "foo", "priority": "high"},
        artifact_path="memory/evolution_artifacts/proposal_1.json",
        artifact_type="code_proposal",
        status="proposed",
        validation={"passed": True},
        duplicate_check={"is_duplicate": False, "content_hash": "abc"},
    )
    updated = registry.update_status(entry["entry_id"], "verified")
    assert updated["status"] == "verified"
    assert len(updated.get("status_history", [])) >= 2


def test_promoter_supports_promoted_and_archived_states(tmp_path: Path) -> None:
    registry = EvolutionRegistry(tmp_path / "evolution_registry.json")
    entry = registry.append_entry(
        gap={"gap_id": "gap_1", "reason": "missing_tests", "target": "foo", "priority": "high"},
        artifact_path="memory/evolution_artifacts/proposal_1.json",
        artifact_type="code_proposal",
        status="proposed",
        validation={"passed": True},
        duplicate_check={"is_duplicate": False, "content_hash": "abc"},
    )

    promoter = Promoter(registry)
    promoter.decide_status(
        entry_id=entry["entry_id"],
        verification={"passed": True},
        duplicate_check={"is_duplicate": False},
        architecture_check={"passed": True},
    )
    promoted = promoter.promote(entry["entry_id"])
    assert promoted["status"] == "promoted"

    archived = promoter.archive(entry["entry_id"], reason="retired")
    assert archived["status"] == "archived"
    assert archived["archive_reason"] == "retired"


def test_verifier_validates_proposal_schema(tmp_path: Path) -> None:
    artifact = tmp_path / "proposal.json"
    bad_payload = {"kind": "code_proposal"}
    write_json_atomic(artifact, bad_payload)

    result = Verifier().verify(artifact, bad_payload)
    assert result["passed"] is False
    assert any("invalid_or_missing_artifact_id" in err for err in result["errors"])


def test_self_inspector_missing_hooks_only_for_expected_sources() -> None:
    inspector = SelfInspector(
        project_root=Path.cwd(),
        generated_registry_path=Path("memory/generated_code_registry.json"),
        evolution_registry_path=Path("memory/evolution_registry.json"),
    )
    report = inspector.inspect()

    # `sessions` is mapped in OversoulDirector but not configured as a connector hook source,
    # so it must not be reported as a missing hook expectation.
    assert "sessions" not in report["missing_hooks"]


def test_run_evolution_kernel_visible_outputs(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=120,
        sample_path=str(sample_path),
        memory_root=str(tmp_path / "memory"),
        mode="replay",
        replay_source="csv",
        replay_csv_path=str(sample_path),
        generated_registry_path=str(tmp_path / "memory" / "generated_code_registry.json"),
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_enabled=True,
        evolution_max_proposals=2,
    )

    result = run_evolution_kernel(config)
    assert result["enabled"] is True
    assert "inspection" in result
    assert "gaps" in result
    assert "lifecycle" in result
