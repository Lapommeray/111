"""Tests for Phase 1 governed quarantine threading.

All fields marked NEW below are Phase 1 governance additions, not pre-existing:
- quarantined_modules (config + report)
- data_sufficiency_tier (report)
- calibration_status (report)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from run import RuntimeConfig, load_runtime_config, validate_runtime_config
from src.pipeline import OversoulDirector, run_advanced_modules


# ---------------------------------------------------------------------------
# Section A: quarantine config threading
# ---------------------------------------------------------------------------


def test_runtime_config_quarantined_modules_defaults_to_empty_list() -> None:
    """quarantined_modules must default to [] so current behavior is preserved."""
    config = RuntimeConfig()
    assert config.quarantined_modules == []


def test_runtime_config_quarantined_modules_accepts_valid_modules() -> None:
    config = RuntimeConfig(quarantined_modules=["invisible_data_miner", "human_lag_exploit"])
    validate_runtime_config(config)
    assert config.quarantined_modules == ["invisible_data_miner", "human_lag_exploit"]


def test_runtime_config_quarantined_modules_rejects_unknown_module() -> None:
    config = RuntimeConfig(quarantined_modules=["nonexistent_module"])
    with pytest.raises(ValueError, match="quarantined_modules contains unknown module"):
        validate_runtime_config(config)


def test_settings_json_has_quarantined_modules_default_empty() -> None:
    settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.json"
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "quarantined_modules" in payload
    assert payload["quarantined_modules"] == []


def test_load_runtime_config_parses_quarantined_modules(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "bars": 220,
                "sample_path": "data/samples/xauusd.csv",
                "memory_root": "memory",
                "mode": "live",
                "quarantined_modules": ["quantum_tremor_scanner"],
            }
        ),
        encoding="utf-8",
    )
    config = load_runtime_config(config_path)
    assert config.quarantined_modules == ["quantum_tremor_scanner"]


def test_load_runtime_config_rejects_non_list_quarantined_modules(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "bars": 220,
                "sample_path": "data/samples/xauusd.csv",
                "memory_root": "memory",
                "mode": "live",
                "quarantined_modules": "invisible_data_miner",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected list of strings"):
        load_runtime_config(config_path)


def test_load_runtime_config_rejects_list_with_non_string(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "bars": 220,
                "sample_path": "data/samples/xauusd.csv",
                "memory_root": "memory",
                "mode": "live",
                "quarantined_modules": [123],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected list of strings"):
        load_runtime_config(config_path)


# ---------------------------------------------------------------------------
# Section B: pipeline quarantine gating
# ---------------------------------------------------------------------------


def _make_bars(count: int = 40, base: float = 2030.0) -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    for i in range(count):
        close = base + i * 0.1
        bars.append(
            {
                "time": 1700000000 + i * 60,
                "open": round(close - 0.2, 2),
                "high": round(close + 0.4, 2),
                "low": round(close - 0.4, 2),
                "close": round(close, 2),
                "tick_volume": 100 + i,
            }
        )
    return bars


def test_pipeline_quarantine_empty_preserves_all_modules() -> None:
    """When quarantined_modules=[], all modules must be present."""
    director = OversoulDirector()
    bars = _make_bars(40)
    state = run_advanced_modules(
        director=director,
        bars=bars,
        base_direction="BUY",
        structure={"state": "trend_up", "bias": "buy", "strength": 0.7},
        liquidity={"score": 0.5, "direction_hint": "neutral"},
        base_confidence=0.6,
        blocked_setups=[],
        trade_outcomes=[],
        quarantined_modules=[],
    )
    assert "invisible_data_miner" in state.module_results
    assert "human_lag_exploit" in state.module_results
    assert "quantum_tremor_scanner" in state.module_results
    assert "spectral_signal_fusion" in state.module_results
    assert "meta_conscious_routing" in state.module_results


def test_pipeline_quarantine_removes_suspect_modules_from_results() -> None:
    """Quarantined modules must not appear in pipeline results."""
    director = OversoulDirector()
    bars = _make_bars(40)
    quarantined = [
        "invisible_data_miner",
        "human_lag_exploit",
        "quantum_tremor_scanner",
        "spectral_signal_fusion",
        "meta_conscious_routing",
    ]
    state = run_advanced_modules(
        director=director,
        bars=bars,
        base_direction="BUY",
        structure={"state": "trend_up", "bias": "buy", "strength": 0.7},
        liquidity={"score": 0.5, "direction_hint": "neutral"},
        base_confidence=0.6,
        blocked_setups=[],
        trade_outcomes=[],
        quarantined_modules=quarantined,
    )
    for module_name in quarantined:
        assert module_name not in state.module_results, f"{module_name} should be quarantined"
    # Core modules must still be present
    assert "displacement" in state.module_results
    assert "fvg" in state.module_results
    assert "volatility" in state.module_results
    assert "setup_score" in state.module_results
    assert "regime_score" in state.module_results


def test_pipeline_quarantine_partial_only_removes_specified() -> None:
    """Only the specified modules should be quarantined."""
    director = OversoulDirector()
    bars = _make_bars(40)
    state = run_advanced_modules(
        director=director,
        bars=bars,
        base_direction="BUY",
        structure={"state": "trend_up", "bias": "buy", "strength": 0.7},
        liquidity={"score": 0.5, "direction_hint": "neutral"},
        base_confidence=0.6,
        blocked_setups=[],
        trade_outcomes=[],
        quarantined_modules=["invisible_data_miner", "quantum_tremor_scanner"],
    )
    assert "invisible_data_miner" not in state.module_results
    assert "quantum_tremor_scanner" not in state.module_results
    # These should still be present
    assert "human_lag_exploit" in state.module_results
    assert "spectral_signal_fusion" in state.module_results
    assert "meta_conscious_routing" in state.module_results


def test_pipeline_quarantine_none_preserves_all_modules() -> None:
    """When quarantined_modules=None (default), all modules must be present."""
    director = OversoulDirector()
    bars = _make_bars(40)
    state = run_advanced_modules(
        director=director,
        bars=bars,
        base_direction="BUY",
        structure={"state": "trend_up", "bias": "buy", "strength": 0.7},
        liquidity={"score": 0.5, "direction_hint": "neutral"},
        base_confidence=0.6,
        blocked_setups=[],
        trade_outcomes=[],
        quarantined_modules=None,
    )
    assert "invisible_data_miner" in state.module_results
    assert "human_lag_exploit" in state.module_results
    assert "quantum_tremor_scanner" in state.module_results
    assert "spectral_signal_fusion" in state.module_results
    assert "meta_conscious_routing" in state.module_results


# ---------------------------------------------------------------------------
# Section C: new report fields (Phase 1 governance additions)
# ---------------------------------------------------------------------------


def test_evaluate_replay_includes_new_phase1_fields() -> None:
    """evaluate_replay must include quarantined_modules, data_sufficiency_tier,
    and calibration_status — all NEW Phase 1 governance fields."""
    from src.evaluation.replay_evaluator import evaluate_replay

    call_count = {"n": 0}

    def mock_runner(_cfg: Any) -> dict[str, Any]:
        call_count["n"] += 1
        return {
            "signal": {
                "action": "WAIT",
                "confidence": 0.5,
                "blocked": False,
                "advanced_modules": {"module_results": {}},
            }
        }

    report = evaluate_replay(
        pipeline_runner=mock_runner,
        config_factory=RuntimeConfig,
        symbol="XAUUSD",
        timeframe="M5",
        bars=5,
        replay_csv_path=_write_tiny_csv(Path("/tmp/test_phase1_fields")),
        sample_path="/tmp/test_phase1_fields/xauusd.csv",
        memory_root="/tmp/test_phase1_fields/memory",
        generated_registry_path="/tmp/test_phase1_fields/memory/generated_code_registry.json",
        meta_adaptive_profile_path="/tmp/test_phase1_fields/memory/meta_adaptive_profile.json",
        evolution_enabled=False,
        evolution_registry_path="/tmp/test_phase1_fields/memory/evolution_registry.json",
        evolution_artifact_root="/tmp/test_phase1_fields/memory/evolution_artifacts",
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=2,
        evaluation_stride=1,
        quarantined_modules=["invisible_data_miner"],
    )
    # NEW fields
    assert report["quarantined_modules"] == ["invisible_data_miner"]
    assert report["data_sufficiency_tier"] == "insufficient"
    assert report["calibration_status"] == "temporary_defaults_pending_broker_measurement"


def test_data_sufficiency_tier_plumbing_validation() -> None:
    """5000+ rows → plumbing_validation tier."""
    from src.evaluation.replay_evaluator import evaluate_replay

    csv_path = _write_csv_with_n_rows(Path("/tmp/test_plumbing_tier"), 5001)

    report = evaluate_replay(
        pipeline_runner=lambda _: {
            "signal": {"action": "WAIT", "confidence": 0.5, "blocked": False, "advanced_modules": {"module_results": {}}},
        },
        config_factory=RuntimeConfig,
        symbol="XAUUSD",
        timeframe="M5",
        bars=5,
        replay_csv_path=csv_path,
        sample_path=csv_path,
        memory_root="/tmp/test_plumbing_tier/memory",
        generated_registry_path="/tmp/test_plumbing_tier/memory/gcr.json",
        meta_adaptive_profile_path="/tmp/test_plumbing_tier/memory/map.json",
        evolution_enabled=False,
        evolution_registry_path="/tmp/test_plumbing_tier/memory/er.json",
        evolution_artifact_root="/tmp/test_plumbing_tier/memory/ea",
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=1,
        evaluation_stride=1,
    )
    assert report["data_sufficiency_tier"] == "plumbing_validation"


def test_evaluate_replay_persists_deterministic_decision_trace() -> None:
    """Replay evaluation writes deterministic per-record decision trace artifact."""
    from src.evaluation.replay_evaluator import evaluate_replay

    root = Path("/tmp/test_decision_trace")
    csv_path = _write_tiny_csv(root)

    def runner(_cfg: Any) -> dict[str, Any]:
        return {
            "signal": {
                "action": "WAIT",
                "confidence": 0.58,
                "blocked": True,
                "reasons": [
                    "structure_liquidity_conflict",
                    "confidence_below_threshold",
                ],
                "signal_lifecycle": {"source_bar_time": 1700000300},
                    "advanced_modules": {
                        "final_direction": "BUY",
                        "module_results": {
                            "market_structure": {"direction_vote": "buy"},
                            "liquidity_sweep": {"direction_vote": "sell"},
                        },
                    },
                },
            "status_panel": {
                "structure_state": "trend_up",
                "liquidity_state": "sweep",
                "blocker_result": {
                    "blocked": True,
                    "blocker_reasons": [
                        "structure_liquidity_conflict",
                        "confidence_below_threshold",
                    ],
                },
            },
        }

    report = evaluate_replay(
        pipeline_runner=runner,
        config_factory=RuntimeConfig,
        symbol="XAUUSD",
        timeframe="M5",
        bars=5,
        replay_csv_path=csv_path,
        sample_path=csv_path,
        memory_root=str(root / "memory"),
        generated_registry_path=str(root / "memory" / "gcr.json"),
        meta_adaptive_profile_path=str(root / "memory" / "map.json"),
        evolution_enabled=False,
        evolution_registry_path=str(root / "memory" / "er.json"),
        evolution_artifact_root=str(root / "memory" / "ea"),
        evolution_max_proposals=1,
        compact_output=True,
        evaluation_steps=2,
        evaluation_stride=1,
    )

    trace_path = Path(report["decision_trace_path"])
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["schema_version"] == "replay.decision_trace.v1"
    assert trace["record_count"] == len(trace["records"]) == 2
    assert report["decision_trace_record_count"] == 2
    assert report["decision_trace_schema_version"] == "replay.decision_trace.v1"
    assert report["decision_trace_blocker_first_counts"]["structure_liquidity_conflict"] == 2
    assert report["decision_diagnosis_schema_version"] == "replay.decision_diagnosis.v1"
    diagnosis_path = Path(report["decision_diagnosis_path"])
    assert diagnosis_path.exists()
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    assert diagnosis["counts"]["by_first_blocker"]["structure_liquidity_conflict"] == 2
    assert diagnosis["counts"]["structure_liquidity_conflict"] == 2
    assert diagnosis["counts"]["by_pre_gate_direction"]["BUY"] == 2

    first = trace["records"][0]
    assert first["record_index"] == 1
    assert first["timestamp"] == 1700000300
    assert first["pre_gate_direction"] == "BUY"
    assert first["final_action"] == "WAIT"
    assert first["structure_bias"] == "BUY"
    assert first["liquidity_hint"] == "SELL"
    assert first["first_blocker"] == "structure_liquidity_conflict"
    assert first["full_blocker_sequence"] == [
        "structure_liquidity_conflict",
        "confidence_below_threshold",
    ]
    assert first["raw_layer_votes"] == {
        "liquidity_sweep": "SELL",
        "market_structure": "BUY",
    }

# ---------------------------------------------------------------------------
# Section D: all five quarantinable modules are documented
# ---------------------------------------------------------------------------


def test_quarantinable_modules_are_exactly_five() -> None:
    """Validate the governance allows exactly the five suspect modules."""
    config_all = RuntimeConfig(
        quarantined_modules=[
            "invisible_data_miner",
            "human_lag_exploit",
            "quantum_tremor_scanner",
            "spectral_signal_fusion",
            "meta_conscious_routing",
        ]
    )
    validate_runtime_config(config_all)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

import csv


def _write_tiny_csv(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "xauusd.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["time", "open", "high", "low", "close", "tick_volume"])
        writer.writeheader()
        for i in range(20):
            close = 2030.0 + i * 0.1
            writer.writerow(
                {
                    "time": 1700000000 + i * 60,
                    "open": round(close - 0.2, 2),
                    "high": round(close + 0.4, 2),
                    "low": round(close - 0.4, 2),
                    "close": round(close, 2),
                    "tick_volume": 100 + i,
                }
            )
    return str(path)


def _write_csv_with_n_rows(root: Path, n: int) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "xauusd.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["time", "open", "high", "low", "close", "tick_volume"])
        writer.writeheader()
        for i in range(n):
            close = 2030.0 + (i % 100) * 0.1
            writer.writerow(
                {
                    "time": 1700000000 + i * 60,
                    "open": round(close - 0.2, 2),
                    "high": round(close + 0.4, 2),
                    "low": round(close - 0.4, 2),
                    "close": round(close, 2),
                    "tick_volume": 100 + (i % 40),
                }
            )
    return str(path)
