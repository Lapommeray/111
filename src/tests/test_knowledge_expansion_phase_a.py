from __future__ import annotations

from pathlib import Path

from src.evolution.knowledge_expansion_orchestrator import run_knowledge_expansion_phase_a


def test_phase_a_orchestrator_writes_governance_artifacts(tmp_path: Path) -> None:
    replay_report = {
        "module_contribution_report": {
            "modules": {
                "sessions": {
                    "samples": 3,
                    "avg_confidence_delta": -0.01,
                    "action_alignment": {"aligned": 0, "misaligned": 3, "wait_aligned": 3, "alignment_ratio": 0.0, "count_wait_alignment": False},
                    "buy_votes": 0,
                    "sell_votes": 0,
                    "wait_votes": 3,
                },
                "spectral_signal_fusion": {
                    "samples": 3,
                    "avg_confidence_delta": 0.08,
                    "action_alignment": {"aligned": 2, "misaligned": 1, "wait_aligned": 0, "alignment_ratio": 0.666667, "count_wait_alignment": False},
                    "buy_votes": 2,
                    "sell_votes": 1,
                    "wait_votes": 0,
                },
            }
        },
        "blocker_effect_report": {
            "blocked_total": 3,
            "protective_proxy_hits": 3,
            "top_reasons": [
                {"reason": "spread_too_wide", "count": 2},
                {"reason": "low_confidence", "count": 1},
            ],
        },
        "session_report": {
            "sessions": {
                "london": {"blocked": 1, "samples": 3},
                "off_hours": {"blocked": 2, "samples": 2},
            }
        },
    }

    result = run_knowledge_expansion_phase_a(
        replay_report=replay_report,
        root=tmp_path / "knowledge_expansion",
        candidate_limit=6,
    )

    assert result["enabled"] is True
    assert result["candidate_count"] == 6
    assert "decision_summary" in result
    assert result["decision_summary"]["total_candidates"] == 6

    decisions = result["decisions"]
    assert any(item["decision"] == "HOLD_FOR_MORE_DATA" for item in decisions)
    assert any(item["decision"] == "REJECT" for item in decisions)
    assert all(item.get("decision_reasons") for item in decisions)

    ledger = Path(result["artifact_paths"]["governance_ledger"]).read_text(encoding="utf-8")
    assert "truth_class_rationale" in ledger
    assert "usefulness_scope" in ledger
    assert "context" in ledger
    assert "regime_specific_alignment" in ledger
    assert "blocker_protection_strength" in ledger
    assert "confidence_calibration_shift" in ledger

    for _, path in result["artifact_paths"].items():
        assert Path(path).exists()


def test_phase_a_overlap_includes_structural_components(tmp_path: Path) -> None:
    replay_report = {
        "module_contribution_report": {
            "modules": {
                "fvg": {
                    "samples": 12,
                    "avg_confidence_delta": 0.06,
                    "action_alignment": {"aligned": 9, "misaligned": 3, "wait_aligned": 0, "alignment_ratio": 0.75, "count_wait_alignment": False},
                    "buy_votes": 9,
                    "sell_votes": 1,
                    "wait_votes": 2,
                }
            }
        },
        "blocker_effect_report": {"blocked_total": 12, "protective_proxy_hits": 10, "top_reasons": []},
        "session_report": {"sessions": {}},
    }

    result = run_knowledge_expansion_phase_a(
        replay_report=replay_report,
        root=tmp_path / "knowledge_expansion2",
        candidate_limit=1,
    )

    overlap = result["decisions"][0]["overlap"]
    assert "overlap_components" in overlap
    assert set(overlap["overlap_components"].keys()) == {"truth_class", "purpose", "inputs", "outputs", "constraints"}


def test_existing_signatures_use_richer_replay_metadata(tmp_path: Path) -> None:
    replay_report = {
        "module_contribution_report": {
            "modules": {
                "sessions": {
                    "samples": 8,
                    "avg_confidence_delta": 0.02,
                    "action_alignment": {
                        "aligned": 4,
                        "misaligned": 4,
                        "wait_aligned": 2,
                        "alignment_ratio": 0.5,
                        "count_wait_alignment": False,
                    },
                    "buy_votes": 2,
                    "sell_votes": 1,
                    "wait_votes": 5,
                }
            }
        },
        "blocker_effect_report": {"blocked_total": 8, "protective_proxy_hits": 4, "top_reasons": []},
        "session_report": {"sessions": {"london": {"blocked": 3, "samples": 8}}},
        "records": [
            {
                "signal": {
                    "advanced_modules": {
                        "module_results": {
                            "sessions": {
                                "direction_vote": "wait",
                                "confidence_delta": 0.02,
                                "reasons": ["session_bias"],
                                "payload": {"state": "london", "window": "open"},
                            }
                        }
                    }
                }
            }
        ],
    }

    result = run_knowledge_expansion_phase_a(
        replay_report=replay_report,
        root=tmp_path / "knowledge_expansion3",
        candidate_limit=1,
    )

    overlap_path = Path(result["artifact_paths"]["overlap_report"])
    overlap_text = overlap_path.read_text(encoding="utf-8")
    assert "payload_keys=state,window" in overlap_text
    assert "session=london" in overlap_text
    assert "replay_only_governance_comparison" in overlap_text
