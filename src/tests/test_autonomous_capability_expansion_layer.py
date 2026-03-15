from __future__ import annotations

import json
from pathlib import Path

from src.evolution.experimental_module_spec_flow import run_autonomous_capability_expansion_layer


def _write_validated_registry(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_autonomous_capability_expansion_generates_sandboxed_capabilities_and_stubs(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_strong",
                    "truth_class": "timing",
                    "statement": "Session compression before continuation.",
                    "evidence_history": [{"signal": "compression"}, {"signal": "breakout"}, {"signal": "follow_through"}],
                    "required_data_sources": ["book_feed", "trade_tape"],
                    "available_data_sources": ["book_feed"],
                },
                {
                    "candidate_id": "cand_weak",
                    "truth_class": "liquidity",
                    "statement": "Liquidity sweep reverts.",
                    "evidence_history": [{"signal": "sweep"}],
                    "required_data_sources": ["liquidity_heatmap"],
                    "available_data_sources": [],
                },
            ]
        },
    )

    result = run_autonomous_capability_expansion_layer(tmp_path, mode="replay")

    assert result["autonomous_capability_expansion_enabled"] is True
    assert result["feature_module_proposal_count"] == 2
    assert result["market_structure_detector_proposal_count"] == 2
    assert result["data_source_adapter_stub_count"] == 2
    assert result["sandbox_validation_count"] == 6
    assert result["governance_record_count"] == 6
    assert result["pruned_capability_count"] == 2

    adapter_payload = json.loads(Path(result["data_source_adapter_stubs"][0]).read_text(encoding="utf-8"))
    assert adapter_payload["capability_kind"] == "data_source_adapter_stub"
    assert adapter_payload["adapter_status"] == "inactive_stub"
    assert adapter_payload["active"] is False
    assert adapter_payload["external_data_access"] is False
    assert adapter_payload["sandbox_status"] == "replay_only"
    assert adapter_payload["live_activation_allowed"] is False

    governance_payloads = [
        json.loads(Path(path).read_text(encoding="utf-8")) for path in result["governance_records"]
    ]
    weak_pruned = [
        item
        for item in governance_payloads
        if item["candidate_id"] == "cand_weak" and item["governance_decision"] == "pruned_weak_capability"
    ]
    assert len(weak_pruned) == 2


def test_autonomous_capability_expansion_is_replay_only(tmp_path: Path) -> None:
    result = run_autonomous_capability_expansion_layer(tmp_path, mode="live")

    assert result["autonomous_capability_expansion_enabled"] is False
    assert result["feature_module_proposal_count"] == 0
    assert result["market_structure_detector_proposal_count"] == 0
    assert result["data_source_adapter_stub_count"] == 0
    assert result["sandbox_validation_count"] == 0
    assert result["governance_record_count"] == 0
    assert result["pruned_capability_count"] == 0

    expansion_dir = tmp_path / "memory" / "knowledge_expansion" / "autonomous_capability_expansion"
    assert expansion_dir.exists() is False


def test_autonomous_capability_expansion_writes_registries(tmp_path: Path) -> None:
    _write_validated_registry(
        tmp_path / "memory" / "knowledge_expansion" / "validated_knowledge_registry.json",
        {
            "validated_knowledge": [
                {
                    "candidate_id": "cand_registry",
                    "truth_class": "failure",
                    "statement": "Failure cascade detector",
                    "evidence_history": [{"signal": "halt"}, {"signal": "spread_widening"}],
                    "required_data_sources": ["venue_health"],
                    "available_data_sources": [],
                }
            ]
        },
    )

    result = run_autonomous_capability_expansion_layer(tmp_path, mode="replay")

    capability_registry = json.loads(Path(result["autonomous_capability_registry_path"]).read_text(encoding="utf-8"))
    assert len(capability_registry["generated_capabilities"]) == 3

    governance_registry = json.loads(
        Path(result["autonomous_capability_governance_registry_path"]).read_text(encoding="utf-8")
    )
    assert len(governance_registry["governance_records"]) == 3
    for governance_record in governance_registry["governance_records"]:
        assert governance_record["sandbox_status"] == "replay_only"
        assert governance_record["live_activation_allowed"] is False
