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
) -> dict[str, Any]:
    csv_path = tmp_path / "replay.csv"
    _write_replay_csv(csv_path)
    return evaluate_replay(
        pipeline_runner=_pipeline_runner_from_pnls(pnls),
        config_factory=_identity_config_factory,
        symbol="XAUUSD",
        timeframe="M5",
        bars=5,
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
        evaluation_stride=1,
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
