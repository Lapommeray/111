from __future__ import annotations

import json
from unittest.mock import patch
import pytest
from pathlib import Path

from run import RuntimeConfig, ensure_sample_data, run_replay_evaluation, run_evolution_kernel
from src.evaluation.blocker_effect_report import build_blocker_effect_report
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
    # detects "0 actionable records" but replay completes (strict=False)
    # so all gate artifacts are persisted for diagnostic purposes.
    result = run_replay_evaluation(config)

    # Main evaluation report includes all gate results.
    assert report_path.exists()
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["steps"] == 4
    assert loaded["symbol"] == "XAUUSD"
    assert "decision_completeness" in loaded
    assert loaded["decision_completeness"]["passed"] is True

    # Quality gate artifact persisted with honest failure diagnosis
    quality_path = tmp_path / "memory" / "decision_quality_report.json"
    assert quality_path.exists()
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality["passed"] is False
    assert quality["actionable_count"] == 0
    assert any("0 actionable" in f for f in quality["failures"])

    # Quality report in the returned result surfaces the zero-actionable state
    assert result["decision_quality"]["passed"] is False
    assert result["decision_quality"]["gate_action"] == "warn"

    # Outcome gate ran (quality gate no longer blocks) — artifact exists.
    outcome_path = tmp_path / "memory" / "replay_outcome_report.json"
    assert outcome_path.exists()

    # Threshold calibration ran — artifact exists.
    calibration_path = tmp_path / "memory" / "threshold_calibration_report.json"
    assert calibration_path.exists()


def test_run_replay_evaluation_persists_drawdown_comparison_for_quarantined_runs(tmp_path: Path) -> None:
    report_path = tmp_path / "memory" / "replay_eval.json"
    config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=80,
        sample_path=str(tmp_path / "samples" / "xauusd.csv"),
        memory_root=str(tmp_path / "memory"),
        mode="replay",
        replay_source="csv",
        replay_csv_path=str(tmp_path / "samples" / "xauusd.csv"),
        generated_registry_path=str(tmp_path / "memory" / "generated_code_registry.json"),
        meta_adaptive_profile_path=str(tmp_path / "memory" / "meta_adaptive_profile.json"),
        evolution_enabled=False,
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=2,
        evaluation_stride=1,
        evaluation_output_path=str(report_path),
        quarantined_modules=["invisible_data_miner"],
    )

    def _closed_rec(pnl_points: float, trade_id: str) -> dict:
        result = "win" if pnl_points > 0 else "loss"
        return {
            "signal": {
                "action": "BUY",
                "confidence": 0.85,
                "blocked": False,
                "blocker_reasons": [],
                "reasons": ["test reason"],
            },
            "status_panel": {
                "memory_result": {
                    "latest_trade_outcome": {
                        "trade_id": trade_id,
                        "symbol": "XAUUSD",
                        "direction": "BUY",
                        "status": "closed",
                        "result": result,
                        "pnl_points": pnl_points,
                    },
                },
            },
        }

    def _mock_evaluate_replay(*args, **kwargs) -> dict:
        quarantined = kwargs.get("quarantined_modules", [])
        records = (
            [_closed_rec(5.0, "inc_win"), _closed_rec(-1.0, "inc_loss")]
            if not quarantined
            else [_closed_rec(4.0, "quar_win"), _closed_rec(-2.0, "quar_loss")]
        )
        return {
            "symbol": "XAUUSD",
            "mode": "replay_evaluation",
            "steps": len(records),
            "records": records,
        }

    def _mock_completeness(records: list[dict], artifact_path: str) -> dict:
        payload = {"passed": True}
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _mock_quality(records: list[dict], completeness_report: dict, artifact_path: str, strict: bool) -> dict:
        payload = {"passed": True, "gate_action": "pass", "actionable_count": len(records)}
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _mock_threshold(records: list[dict], outcome_report: dict, artifact_path: str) -> dict:
        payload = {"passed": True}
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    with (
        patch("run.ensure_sample_data"),
        patch("run.evaluate_replay", side_effect=_mock_evaluate_replay),
        patch("run.run_decision_completeness_gate", side_effect=_mock_completeness),
        patch("run.run_decision_quality_gate", side_effect=_mock_quality),
        patch("run.run_threshold_calibration", side_effect=_mock_threshold),
    ):
        result = run_replay_evaluation(config)

    comparison_path = tmp_path / "memory" / "replay_drawdown_comparison_report.json"
    assert comparison_path.exists()
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["schema_version"] == "drawdown_comparison.v1"
    assert result["drawdown_comparison_path"] == str(comparison_path)
    assert result["drawdown_comparison_schema_version"] == "drawdown_comparison.v1"
    assert report_path.exists()
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["drawdown_comparison_path"] == str(comparison_path)
    assert loaded["drawdown_comparison"]["schema_version"] == "drawdown_comparison.v1"


def test_run_replay_evaluation_skips_evolution_in_replay_isolation_and_persists_report(tmp_path: Path) -> None:
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
        evolution_enabled=True,
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=3,
        evaluation_stride=5,
        evaluation_output_path=str(report_path),
    )

    with patch("run.SelfInspector.inspect", side_effect=AssertionError("inspect should be skipped")):
        result = run_replay_evaluation(config)

    assert report_path.exists()
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["steps"] == 3
    assert loaded["symbol"] == "XAUUSD"
    assert loaded["decision_completeness"]["passed"] is True
    assert loaded["threshold_calibration"] == result["threshold_calibration"]

    quality_path = tmp_path / "memory" / "decision_quality_report.json"
    outcome_path = tmp_path / "memory" / "replay_outcome_report.json"
    calibration_path = tmp_path / "memory" / "threshold_calibration_report.json"
    assert quality_path.exists()
    assert outcome_path.exists()
    assert calibration_path.exists()


def test_run_replay_evaluation_omits_large_record_blob_from_persisted_isolated_report(tmp_path: Path) -> None:
    report_path = tmp_path / "memory" / "replay_eval.json"
    config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=80,
        sample_path=str(tmp_path / "samples" / "xauusd.csv"),
        memory_root=str(tmp_path / "memory"),
        mode="replay",
        replay_source="csv",
        replay_csv_path=str(tmp_path / "samples" / "xauusd.csv"),
        generated_registry_path=str(tmp_path / "memory" / "generated_code_registry.json"),
        meta_adaptive_profile_path=str(tmp_path / "memory" / "meta_adaptive_profile.json"),
        evolution_enabled=False,
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=2,
        evaluation_stride=1,
        evaluation_output_path=str(report_path),
    )
    large_records = [_mock_record("BUY", 0.8, False, "london") for _ in range(1001)]

    def _mock_evaluate_replay(*args, **kwargs) -> dict:
        return {
            "symbol": "XAUUSD",
            "mode": "replay_evaluation",
            "steps": len(large_records),
            "records": large_records,
            "replay_isolated": True,
        }

    def _mock_completeness(records: list[dict], artifact_path: str) -> dict:
        payload = {
            "passed": True,
            "counts": {"actionable": len(records), "blocked": 0, "abstain": 0, "invalid": 0},
        }
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _mock_quality(records: list[dict], completeness_report: dict, artifact_path: str, strict: bool) -> dict:
        payload = {"passed": True, "gate_action": "pass", "actionable_count": len(records)}
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _mock_outcome(records: list[dict], quality_report: dict, artifact_path: str) -> dict:
        payload = {
            "passed": True,
            "actionable_count": len(records),
            "closed_trades": 0,
            "drawdown_attribution_path": None,
        }
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _mock_threshold(records: list[dict], outcome_report: dict, artifact_path: str) -> dict:
        payload = {"passed": True}
        Path(artifact_path).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    with (
        patch("run.ensure_sample_data"),
        patch("run.evaluate_replay", side_effect=_mock_evaluate_replay),
        patch("run.run_decision_completeness_gate", side_effect=_mock_completeness),
        patch("run.run_decision_quality_gate", side_effect=_mock_quality),
        patch("run.run_replay_outcome_gate", side_effect=_mock_outcome),
        patch("run.run_threshold_calibration", side_effect=_mock_threshold),
    ):
        result = run_replay_evaluation(config)

    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert "records" not in loaded
    assert loaded["persisted_records_omitted"] is True
    assert loaded["persisted_record_count"] == len(large_records)
    assert result["records"] == large_records


def test_run_evolution_kernel_normal_replay_outside_isolated_evaluation_is_unchanged(tmp_path: Path) -> None:
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
        meta_adaptive_profile_path=str(tmp_path / "memory" / "meta_adaptive_profile.json"),
        evolution_enabled=True,
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_max_proposals=1,
    )
    inspection = {
        "missing_tests": ["foo"],
        "missing_hooks": [],
        "missing_state_contributions": [],
        "missing_registrations": [],
        "dead_modules": [],
        "broken_arch_links": [],
    }

    with (
        patch("run.SelfInspector.inspect", return_value=inspection) as inspect_mock,
        patch("run.GapDiscovery.discover", return_value=[]),
    ):
        result = run_evolution_kernel(config)

    inspect_mock.assert_called_once()
    assert result["enabled"] is True
    assert result["inspection"] == inspection
    assert result["gaps"] == []
    assert result["lifecycle"] == []


def test_run_evolution_kernel_live_path_is_unchanged(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=120,
        sample_path=str(sample_path),
        memory_root=str(tmp_path / "memory_live"),
        mode="live",
        replay_source="csv",
        replay_csv_path=str(sample_path),
        generated_registry_path=str(tmp_path / "memory_live" / "generated_code_registry.json"),
        meta_adaptive_profile_path=str(tmp_path / "memory_live" / "meta_adaptive_profile.json"),
        evolution_enabled=True,
        evolution_registry_path=str(tmp_path / "memory_live" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory_live" / "evolution_artifacts"),
        evolution_max_proposals=1,
    )
    inspection = {
        "missing_tests": [],
        "missing_hooks": ["hook_x"],
        "missing_state_contributions": [],
        "missing_registrations": [],
        "dead_modules": [],
        "broken_arch_links": [],
    }

    with (
        patch("run.SelfInspector.inspect", return_value=inspection) as inspect_mock,
        patch("run.GapDiscovery.discover", return_value=[]),
    ):
        result = run_evolution_kernel(config)

    inspect_mock.assert_called_once()
    assert result["enabled"] is True
    assert result["inspection"] == inspection
    assert result["gaps"] == []
    assert result["lifecycle"] == []
