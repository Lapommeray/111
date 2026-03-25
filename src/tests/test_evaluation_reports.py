from __future__ import annotations

import json
import pytest
from pathlib import Path

from run import RuntimeConfig, ensure_sample_data, run_replay_evaluation
from src.evaluation.blocker_effect_report import build_blocker_effect_report
from src.evaluation.decision_quality import DecisionQualityError
from src.evaluation.module_contribution_report import build_module_contribution_report
from src.evaluation.session_report import build_session_report


def _mock_record(action: str, confidence: float, blocked: bool, session: str) -> dict:
    return {
        "signal": {
            "action": action,
            "confidence": confidence,
            "blocked": blocked,
            "blocker_reasons": ["structure_liquidity_conflict"] if blocked else [],
            "advanced_modules": {
                "module_results": {
                    "sessions": {
                        "direction_vote": "neutral",
                        "confidence_delta": 0.01,
                        "payload": {"state": session},
                    },
                    "spectral_signal_fusion": {
                        "direction_vote": "buy" if action == "BUY" else "neutral",
                        "confidence_delta": 0.05 if action == "BUY" else -0.02,
                        "payload": {},
                    },
                }
            },
        }
    }


def test_module_contribution_report_shape() -> None:
    records = [
        _mock_record("BUY", 0.8, False, "london"),
        _mock_record("WAIT", 0.4, True, "off_hours"),
    ]
    report = build_module_contribution_report(records)

    assert report["module_count"] >= 1
    assert "spectral_signal_fusion" in report["modules"]
    assert report["modules"]["spectral_signal_fusion"]["samples"] == 2
    assert report["modules"]["spectral_signal_fusion"]["action_alignment"] == {
        "aligned": 1,
        "misaligned": 1,
        "wait_aligned": 0,
        "alignment_ratio": 0.5,
        "count_wait_alignment": False,
    }
    assert "regime_specific_alignment" in report["modules"]["spectral_signal_fusion"]
    assert "contradiction_reduction_proxy" in report["modules"]["spectral_signal_fusion"]
    assert "blocker_protection_strength" in report["modules"]["spectral_signal_fusion"]
    assert "confidence_calibration_shift" in report["modules"]["spectral_signal_fusion"]
    assert "drawdown_prevention_proxy" in report["modules"]["spectral_signal_fusion"]


def test_blocker_effect_report_shape() -> None:
    records = [
        _mock_record("WAIT", 0.45, True, "off_hours"),
        _mock_record("BUY", 0.82, False, "london"),
    ]
    report = build_blocker_effect_report(records)

    assert report["blocked_total"] == 1
    assert "reason_counts" in report
    assert "top_reasons" in report


def test_session_report_shape() -> None:
    records = [
        _mock_record("BUY", 0.8, False, "london"),
        _mock_record("WAIT", 0.4, True, "off_hours"),
    ]
    report = build_session_report(records)

    assert "sessions" in report
    assert report["sessions"]["london"]["buy"] == 1
    assert report["sessions"]["off_hours"]["blocked"] == 1


def test_run_replay_evaluation_writes_json_report(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    report_path = tmp_path / "memory" / "replay_eval.json"
    config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=80,
        sample_path=str(sample_path),
        memory_root=str(tmp_path / "memory"),
        mode="replay",
        replay_source="csv",
        replay_csv_path=str(sample_path),
        generated_registry_path=str(tmp_path / "memory" / "generated_code_registry.json"),
        meta_adaptive_profile_path=str(tmp_path / "memory" / "meta_adaptive_profile.json"),
        evolution_enabled=False,
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=4,
        evaluation_stride=5,
        evaluation_output_path=str(report_path),
        knowledge_expansion_enabled=True,
        knowledge_expansion_root=str(tmp_path / "memory" / "knowledge_expansion"),
        knowledge_candidate_limit=5,
    )

    # Small synthetic sample produces all-blocked records; the quality gate
    # correctly rejects this as "0 actionable records".  The evaluation report
    # and both gate artifacts must still be persisted before the error.
    with pytest.raises(DecisionQualityError, match="0 actionable"):
        run_replay_evaluation(config)

    # Main evaluation report (includes decision_completeness) was written
    # BEFORE the quality gate raised.
    assert report_path.exists()
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["steps"] == 4
    assert loaded["symbol"] == "XAUUSD"
    assert "decision_completeness" in loaded
    assert loaded["decision_completeness"]["passed"] is True

    # Quality gate artifact persisted even on failure
    quality_path = tmp_path / "memory" / "decision_quality_report.json"
    assert quality_path.exists()
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality["passed"] is False
    assert quality["actionable_count"] == 0

    # Outcome gate never ran (quality gate raised first) — no artifact.
    outcome_path = tmp_path / "memory" / "replay_outcome_report.json"
    assert not outcome_path.exists()
