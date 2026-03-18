from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from src.evaluation.replay_evaluator import evaluate_replay


def _write_replay_csv(path: Path, rows: int = 12) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        for index in range(rows):
            close = 2000.0 + (index * 0.1)
            writer.writerow(
                {
                    "time": 1700000000 + (index * 60),
                    "open": round(close - 0.1, 3),
                    "high": round(close + 0.2, 3),
                    "low": round(close - 0.2, 3),
                    "close": round(close, 3),
                    "tick_volume": 100 + index,
                }
            )


def _pipeline_runner_from_pnls(pnl_values: list[float]):
    cursor = {"index": 0}

    def _runner(_config: Any) -> dict[str, Any]:
        idx = min(cursor["index"], len(pnl_values) - 1)
        cursor["index"] += 1
        pnl_points = float(pnl_values[idx])
        return {
            "signal": {"action": "BUY", "confidence": 0.8, "blocked": False},
            "status_panel": {
                "memory_result": {
                    "latest_trade_outcome": {
                        "trade_id": f"trade_{cursor['index']}",
                        "status": "closed",
                        "direction": "BUY",
                        "pnl_points": pnl_points,
                    }
                }
            },
        }

    return _runner


def _identity_config_factory(**kwargs: Any) -> dict[str, Any]:
    """Return replay config kwargs unchanged for evaluate_replay test doubles."""
    return kwargs


def _evaluate_with_costs(
    tmp_path: Path,
    *,
    pnls: list[float],
    spread: float = 0.0,
    commission: float = 0.0,
    slippage: float = 0.0,
    bars: int = 5,
    evaluation_stride: int = 1,
    walk_forward_enabled: bool = False,
    walk_forward_context_bars: int = 5,
    walk_forward_test_bars: int = 3,
    walk_forward_step_bars: int = 3,
    csv_rows: int = 12,
) -> dict[str, Any]:
    csv_path = tmp_path / "replay.csv"
    _write_replay_csv(csv_path, rows=csv_rows)
    return evaluate_replay(
        pipeline_runner=_pipeline_runner_from_pnls(pnls),
        config_factory=_identity_config_factory,
        symbol="XAUUSD",
        timeframe="M5",
        bars=bars,
        replay_csv_path=str(csv_path),
        sample_path=str(csv_path),
        memory_root=str(tmp_path / "memory"),
        generated_registry_path=str(tmp_path / "memory" / "generated_code_registry.json"),
        meta_adaptive_profile_path=str(tmp_path / "memory" / "meta_adaptive_profile.json"),
        evolution_enabled=False,
        evolution_registry_path=str(tmp_path / "memory" / "evolution_registry.json"),
        evolution_artifact_root=str(tmp_path / "memory" / "evolution_artifacts"),
        evolution_max_proposals=1,
        compact_output=False,
        evaluation_steps=len(pnls),
        evaluation_stride=evaluation_stride,
        walk_forward_enabled=walk_forward_enabled,
        walk_forward_context_bars=walk_forward_context_bars,
        walk_forward_test_bars=walk_forward_test_bars,
        walk_forward_step_bars=walk_forward_step_bars,
        execution_spread_cost_points=spread,
        execution_commission_cost_points=commission,
        execution_slippage_cost_points=slippage,
    )


def test_zero_execution_cost_preserves_gross_pnl(tmp_path: Path) -> None:
    report = _evaluate_with_costs(tmp_path, pnls=[1.25])
    outcome = report["records"][0]["status_panel"]["memory_result"]["latest_trade_outcome"]
    impact = report["execution_cost_impact"]

    assert outcome["pnl_points"] == 1.25
    assert outcome["pnl_points_gross"] == 1.25
    assert outcome["pnl_points_net"] == 1.25
    assert impact["gross_pnl_points"] == 1.25
    assert impact["total_execution_cost_points"] == 0.0
    assert impact["net_pnl_points"] == 1.25


def test_spread_cost_reduces_net_pnl(tmp_path: Path) -> None:
    report = _evaluate_with_costs(tmp_path, pnls=[1.25], spread=0.2)
    outcome = report["records"][0]["status_panel"]["memory_result"]["latest_trade_outcome"]
    assert outcome["pnl_points_net"] == 1.05


def test_commission_cost_reduces_net_pnl(tmp_path: Path) -> None:
    report = _evaluate_with_costs(tmp_path, pnls=[1.25], commission=0.15)
    outcome = report["records"][0]["status_panel"]["memory_result"]["latest_trade_outcome"]
    assert outcome["pnl_points_net"] == 1.1


def test_slippage_cost_reduces_net_pnl(tmp_path: Path) -> None:
    report = _evaluate_with_costs(tmp_path, pnls=[1.25], slippage=0.1)
    outcome = report["records"][0]["status_panel"]["memory_result"]["latest_trade_outcome"]
    assert outcome["pnl_points_net"] == 1.15


def test_combined_execution_costs_reduce_performance_deterministically(tmp_path: Path) -> None:
    report = _evaluate_with_costs(tmp_path, pnls=[1.0, -0.5, 0.25], spread=0.1, commission=0.05, slippage=0.02)
    impact = report["execution_cost_impact"]

    assert impact["closed_trade_count"] == 3
    assert impact["gross_pnl_points"] == 0.75
    assert impact["total_execution_cost_points"] == 0.51
    assert impact["net_pnl_points"] == 0.24
    assert impact["per_trade_total_cost_points"] == 0.17


def test_invalid_execution_cost_config_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="execution_spread_cost_points must be >= 0"):
        _evaluate_with_costs(tmp_path, pnls=[1.0], spread=-0.01)


def test_walk_forward_disabled_preserves_standard_replay_behavior(tmp_path: Path) -> None:
    report = _evaluate_with_costs(tmp_path, pnls=[0.5, 0.5, 0.5], walk_forward_enabled=False)
    assert report["walk_forward_enabled"] is False
    assert report["cycle_count"] == 0
    assert report["steps"] == 3
    assert report["per_cycle_summary"] == []


def test_walk_forward_valid_config_creates_deterministic_sequential_cycles(tmp_path: Path) -> None:
    kwargs = {
        "pnls": [0.5] * 20,
        "bars": 5,
        "evaluation_stride": 2,
        "walk_forward_enabled": True,
        "walk_forward_context_bars": 6,
        "walk_forward_test_bars": 4,
        "walk_forward_step_bars": 3,
        "csv_rows": 18,
    }
    report_a = _evaluate_with_costs(tmp_path / "a", **kwargs)
    report_b = _evaluate_with_costs(tmp_path / "b", **kwargs)

    assert report_a["cycle_count"] == 3
    assert report_a["per_cycle_summary"] == report_b["per_cycle_summary"]
    assert report_a["per_cycle_summary"][0]["context_start_bar_index"] == 0
    assert report_a["per_cycle_summary"][0]["test_start_bar_index"] == 6
    assert report_a["per_cycle_summary"][1]["context_start_bar_index"] == 3
    assert report_a["per_cycle_summary"][1]["test_start_bar_index"] == 9


def test_walk_forward_impossible_config_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No walk-forward cycles can be built"):
        _evaluate_with_costs(
            tmp_path,
            pnls=[1.0, 1.0],
            bars=5,
            walk_forward_enabled=True,
            walk_forward_context_bars=10,
            walk_forward_test_bars=10,
            walk_forward_step_bars=5,
            csv_rows=12,
        )


def test_walk_forward_oos_summary_fields_are_present(tmp_path: Path) -> None:
    report = _evaluate_with_costs(
        tmp_path,
        pnls=[0.5] * 20,
        bars=5,
        walk_forward_enabled=True,
        walk_forward_context_bars=6,
        walk_forward_test_bars=4,
        walk_forward_step_bars=4,
        csv_rows=18,
    )
    for key in (
        "walk_forward_enabled",
        "cycle_count",
        "context_bars",
        "test_bars",
        "step_bars",
        "total_oos_closed_trades",
        "total_oos_gross_pnl_points",
        "total_oos_net_pnl_points",
        "oos_win_rate",
        "oos_max_drawdown",
        "per_cycle_summary",
    ):
        assert key in report
    assert report["walk_forward_enabled"] is True
    assert report["cycle_count"] > 0


def test_walk_forward_remains_compatible_with_execution_cost_model(tmp_path: Path) -> None:
    report = _evaluate_with_costs(
        tmp_path,
        pnls=[1.0] * 30,
        spread=0.1,
        commission=0.05,
        slippage=0.02,
        bars=5,
        walk_forward_enabled=True,
        walk_forward_context_bars=6,
        walk_forward_test_bars=3,
        walk_forward_step_bars=3,
        csv_rows=16,
    )
    expected_total_cost = round(report["total_oos_closed_trades"] * 0.17, 3)
    realized_total_cost = round(
        float(report["total_oos_gross_pnl_points"]) - float(report["total_oos_net_pnl_points"]),
        3,
    )
    assert realized_total_cost == expected_total_cost
