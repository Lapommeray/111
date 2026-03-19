from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils import read_json_safe, write_json_atomic


def update_system_monitor_state(
    *,
    memory_root: str,
    execution_state: dict[str, Any],
    controlled_execution: dict[str, Any],
    trade_outcomes: list[dict[str, Any]],
    strategy_version: str,
) -> dict[str, Any]:
    monitor_root = Path(memory_root) / "system_monitor"
    monitor_root.mkdir(parents=True, exist_ok=True)
    system_state_path = monitor_root / "system_state.json"
    trade_history_path = monitor_root / "trade_history.json"
    metrics_path = monitor_root / "performance_metrics.json"

    trade_history_payload = read_json_safe(trade_history_path, default={"trades": []})
    if not isinstance(trade_history_payload, dict):
        trade_history_payload = {"trades": []}
    existing_trades = trade_history_payload.get("trades", [])
    if not isinstance(existing_trades, list):
        existing_trades = []
    tail_outcomes = trade_outcomes[-20:]
    for outcome in tail_outcomes:
        trade_id = str(outcome.get("trade_id", ""))
        if trade_id and all(str(item.get("trade_id", "")) != trade_id for item in existing_trades):
            existing_trades.append(outcome)
    existing_trades = existing_trades[-200:]
    write_json_atomic(trade_history_path, {"trades": existing_trades})

    closed = [trade for trade in existing_trades if str(trade.get("status", "")).lower() == "closed"]
    wins = sum(1 for trade in closed if str(trade.get("result", "")).lower() == "win")
    losses = sum(1 for trade in closed if str(trade.get("result", "")).lower() == "loss")
    win_rate = round(wins / len(closed), 4) if closed else 0.0

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for trade in closed:
        cumulative += float(trade.get("pnl_points", 0.0))
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    drawdown = round(abs(max_drawdown), 4)

    performance_metrics = {
        "win_rate": win_rate,
        "drawdown": drawdown,
        "closed_trades": len(closed),
        "execution_failures": losses,
    }
    write_json_atomic(metrics_path, performance_metrics)

    system_health = "healthy"
    if bool(execution_state.get("mt5_quarantined", False)):
        system_health = "quarantined"
    elif bool(execution_state.get("mt5_auto_stop_active", False)):
        system_health = "auto_stop"
    elif bool(controlled_execution.get("rollback_refusal_reasons", [])):
        system_health = "degraded"

    open_position = dict(controlled_execution.get("open_position_state", {}))
    position_status = str(open_position.get("status", "")).lower()
    broker_position_confirmation = str(open_position.get("broker_position_confirmation", "")).lower()
    position_state_outcome = str(open_position.get("position_state_outcome", "")).lower()
    partial_exposure_unresolved = (
        position_status == "partial_exposure_unresolved"
        or position_state_outcome == "partial_fill_exposure_unresolved"
    )
    assumed_open_position = position_status == "open"
    broker_verified_open_position = (
        assumed_open_position and broker_position_confirmation == "confirmed"
    )
    system_state = {
        "current_position": open_position,
        "assumed_open_position": assumed_open_position,
        "broker_verified_open_position": broker_verified_open_position,
        "open_position_truth": (
            "broker_verified_open_position"
            if broker_verified_open_position
            else (
                "assumed_unverified_open_position"
                if assumed_open_position
                else (
                    "partial_exposure_unresolved"
                    if partial_exposure_unresolved
                    else "no_open_position"
                )
            )
        ),
        "partial_exposure_unresolved": partial_exposure_unresolved,
        "open_position_state_outcome": position_state_outcome,
        "open_position_broker_confirmation": broker_position_confirmation,
        "open_orders": [controlled_execution.get("order_request", {})]
        if broker_verified_open_position
        else [],
        "last_trades": existing_trades[-5:],
        "win_rate": performance_metrics["win_rate"],
        "drawdown": performance_metrics["drawdown"],
        "system_health": system_health,
        "execution_failures": performance_metrics["execution_failures"],
        "strategy_version": strategy_version,
    }
    write_json_atomic(system_state_path, system_state)

    return {
        "system_state": system_state,
        "paths": {
            "system_state": str(system_state_path),
            "trade_history": str(trade_history_path),
            "performance_metrics": str(metrics_path),
        },
    }
