from __future__ import annotations

import json
from pathlib import Path

from run import RuntimeConfig, ensure_sample_data, run_pipeline
from src.learning.live_feedback import process_live_trade_feedback
from src.monitoring.system_state import update_system_monitor_state
from src.risk.capital_guard import (
    check_daily_loss_limit,
    compute_position_size,
    evaluate_capital_protection,
    volatility_scaling_factor,
)


def test_strategy_intelligence_signal_fields_and_artifacts(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    memory_root = tmp_path / "memory"

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )
    signal = output["signal"]

    assert "signal_score" in signal
    assert "confidence" in signal
    assert isinstance(signal["feature_contributors"], dict)
    assert (memory_root / "strategy_intelligence" / "signal_quality_registry.json").exists()
    assert (memory_root / "strategy_intelligence" / "signal_feature_scores.json").exists()
    assert (memory_root / "strategy_intelligence" / "strategy_confidence_state.json").exists()


def test_live_trade_feedback_loop_is_deterministic_and_quarantines_unsafe(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    outcomes = [
        {
            "trade_id": "trade_1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.8,
        }
    ]
    feature_contributors = {"setup_score": 0.9, "spread_state": 0.7}

    first = process_live_trade_feedback(
        memory_root=memory_root,
        trade_outcomes=outcomes,
        feature_contributors=feature_contributors,
        replay_scope="full_replay",
    )
    second = process_live_trade_feedback(
        memory_root=memory_root,
        trade_outcomes=outcomes,
        feature_contributors=feature_contributors,
        replay_scope="full_replay",
    )

    assert first["mutation_candidate"]["candidate_id"] == second["mutation_candidate"]["candidate_id"]
    assert first["mutation_candidate"]["replay_validation"]["required"] is True
    assert first["mutation_candidate"]["governance"]["quarantine_required"] is True
    assert Path(first["paths"]["trade_outcomes"]).exists()
    assert Path(first["paths"]["feature_attribution"]).exists()
    assert Path(first["paths"]["mutation_candidates"]).exists()


def test_capital_guard_enforces_daily_loss_limit() -> None:
    loss_check = check_daily_loss_limit(daily_loss_points=3.2, max_daily_loss_points=3.0)
    assert loss_check["limit_exceeded"] is True
    assert loss_check["allowed_to_trade"] is False


def test_adaptive_position_sizing_scales_with_volatility() -> None:
    low_vol_scale = volatility_scaling_factor(volatility_ratio=0.9)
    high_vol_scale = volatility_scaling_factor(volatility_ratio=2.5)
    assert high_vol_scale < low_vol_scale

    low_vol_size = compute_position_size(
        balance=10_000.0,
        risk_fraction=0.001,
        stop_loss_points=2.0,
        volatility_factor=low_vol_scale,
        maximum_size=0.05,
    )
    high_vol_size = compute_position_size(
        balance=10_000.0,
        risk_fraction=0.001,
        stop_loss_points=2.0,
        volatility_factor=high_vol_scale,
        maximum_size=0.05,
    )
    assert high_vol_size <= low_vol_size


def test_monitoring_state_updates_every_pipeline_run(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    monitor = update_system_monitor_state(
        memory_root=str(memory_root),
        execution_state={"mt5_quarantined": False, "mt5_auto_stop_active": False},
        controlled_execution={"open_position_state": {"status": "flat"}, "rollback_refusal_reasons": []},
        trade_outcomes=[
            {"trade_id": "a", "status": "closed", "result": "win", "pnl_points": 0.6},
            {"trade_id": "b", "status": "closed", "result": "loss", "pnl_points": -0.3},
        ],
        strategy_version="institutional_v1",
    )
    payload = json.loads(Path(monitor["paths"]["system_state"]).read_text(encoding="utf-8"))
    metrics = json.loads(Path(monitor["paths"]["performance_metrics"]).read_text(encoding="utf-8"))

    assert payload["strategy_version"] == "institutional_v1"
    assert "system_health" in payload
    assert metrics["win_rate"] == 0.5


def test_capital_guard_runtime_refuses_when_limit_exceeded(tmp_path: Path) -> None:
    memory_root = tmp_path / "memory"
    blocked = evaluate_capital_protection(
        memory_root=str(memory_root),
        latest_bar_time=4_000_000_000,
        requested_volume=0.05,
        volatility_value=1.8,
        latest_outcome={
            "trade_id": "loss_1",
            "status": "closed",
            "pnl_points": -3.2,
        },
    )
    assert blocked["trade_refused"] is True
    assert Path(blocked["paths"]["capital_guard_state"]).exists()
    assert Path(blocked["paths"]["daily_loss_tracker"]).exists()
