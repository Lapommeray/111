from __future__ import annotations

import json
from pathlib import Path

import pytest

from run import RuntimeConfig, load_runtime_config, validate_runtime_config


def test_runtime_config_valid_settings_json_parses_and_validates() -> None:
    settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.json"
    config = load_runtime_config(settings_path)
    validate_runtime_config(config)
    assert isinstance(config, RuntimeConfig)


def test_runtime_config_missing_required_key_fails_clearly(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "timeframe": "M5",
                "bars": 220,
                "sample_path": "data/samples/xauusd.csv",
                "memory_root": "memory",
                "mode": "live",
                "evaluation_output_path": "memory/replay_evaluation_report.json",
                "knowledge_candidate_limit": 6,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing required config key\\(s\\).*symbol"):
        load_runtime_config(config_path)


def test_runtime_config_wrong_type_fails_clearly(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "bars": "220",
                "sample_path": "data/samples/xauusd.csv",
                "memory_root": "memory",
                "mode": "live",
                "evaluation_output_path": "memory/replay_evaluation_report.json",
                "knowledge_candidate_limit": 6,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid type for config key 'bars': expected int, got str"):
        load_runtime_config(config_path)


def test_runtime_config_malformed_json_fails_clearly(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text('{"symbol": "XAUUSD"', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON in runtime config"):
        load_runtime_config(config_path)


def test_runtime_config_invalid_range_fails_clearly() -> None:
    with pytest.raises(ValueError, match="bars must be > 20"):
        validate_runtime_config(RuntimeConfig(bars=20))

    validate_runtime_config(RuntimeConfig(bars=21))


def test_runtime_config_negative_execution_cost_fails_clearly() -> None:
    with pytest.raises(ValueError, match="execution_spread_cost_points must be >= 0"):
        validate_runtime_config(RuntimeConfig(execution_spread_cost_points=-0.01))

    with pytest.raises(ValueError, match="execution_commission_cost_points must be >= 0"):
        validate_runtime_config(RuntimeConfig(execution_commission_cost_points=-0.01))

    with pytest.raises(ValueError, match="execution_slippage_cost_points must be >= 0"):
        validate_runtime_config(RuntimeConfig(execution_slippage_cost_points=-0.01))


def test_runtime_config_invalid_walk_forward_fields_fail_clearly() -> None:
    with pytest.raises(ValueError, match="walk_forward_context_bars must be > 0"):
        validate_runtime_config(RuntimeConfig(walk_forward_context_bars=0))

    with pytest.raises(ValueError, match="walk_forward_test_bars must be > 0"):
        validate_runtime_config(RuntimeConfig(walk_forward_test_bars=0))

    with pytest.raises(ValueError, match="walk_forward_step_bars must be > 0"):
        validate_runtime_config(RuntimeConfig(walk_forward_step_bars=0))

    with pytest.raises(ValueError, match="walk_forward_context_bars must be >= bars"):
        validate_runtime_config(
            RuntimeConfig(
                bars=221,
                walk_forward_enabled=True,
                walk_forward_context_bars=220,
            )
        )

    with pytest.raises(ValueError, match="walk_forward_test_bars must be >= evaluation_stride"):
        validate_runtime_config(
            RuntimeConfig(
                walk_forward_enabled=True,
                walk_forward_test_bars=4,
                evaluation_stride=5,
            )
        )


def test_runtime_config_invalid_mode_and_replay_source_fail_clearly() -> None:
    with pytest.raises(ValueError, match="Unsupported mode: paper\\. Supported modes: live, replay"):
        validate_runtime_config(RuntimeConfig(mode="paper"))

    with pytest.raises(
        ValueError,
        match="Unsupported replay_source: api\\. Supported sources: csv, memory",
    ):
        validate_runtime_config(RuntimeConfig(replay_source="api"))


def test_runtime_config_unsupported_symbol_and_timeframe_fail_clearly() -> None:
    with pytest.raises(ValueError, match="Only XAUUSD is supported"):
        validate_runtime_config(RuntimeConfig(symbol="EURUSD", timeframe="M5"))

    with pytest.raises(ValueError, match="Unsupported timeframe: D1"):
        validate_runtime_config(RuntimeConfig(symbol="XAUUSD", timeframe="D1"))
