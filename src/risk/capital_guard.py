from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils import clamp, read_json_safe, write_json_atomic


def volatility_scaling_factor(*, volatility_ratio: float, floor: float = 0.35, ceiling: float = 1.0) -> float:
    if volatility_ratio <= 1.0:
        return round(clamp(1.0 - ((volatility_ratio - 1.0) * 0.2), floor, ceiling), 4)
    reduction = 1.0 / max(1.0, volatility_ratio)
    return round(clamp(reduction, floor, ceiling), 4)


def compute_position_size(
    *,
    balance: float,
    risk_fraction: float,
    stop_loss_points: float,
    volatility_factor: float,
    minimum_size: float = 0.01,
    maximum_size: float = 1.0,
) -> float:
    if balance <= 0 or risk_fraction <= 0 or stop_loss_points <= 0:
        return round(minimum_size, 4)
    raw_size = (balance * risk_fraction) / stop_loss_points
    adjusted = raw_size * max(0.0, volatility_factor)
    return round(clamp(adjusted, minimum_size, maximum_size), 4)


def check_daily_loss_limit(*, daily_loss_points: float, max_daily_loss_points: float) -> dict[str, Any]:
    exceeded = daily_loss_points >= max_daily_loss_points
    return {
        "daily_loss_points": round(daily_loss_points, 4),
        "max_daily_loss_points": round(max_daily_loss_points, 4),
        "limit_exceeded": exceeded,
        "allowed_to_trade": not exceeded,
    }


def evaluate_capital_protection(
    *,
    memory_root: str,
    latest_bar_time: int,
    requested_volume: float,
    volatility_value: float,
    latest_outcome: dict[str, Any],
    stop_loss_points: float = 2.0,
    max_daily_loss_points: float = 3.0,
) -> dict[str, Any]:
    risk_root = Path(memory_root) / "risk_state"
    risk_root.mkdir(parents=True, exist_ok=True)
    tracker_path = risk_root / "daily_loss_tracker.json"
    state_path = risk_root / "capital_guard_state.json"

    tracker = read_json_safe(
        tracker_path,
        default={"trading_day": "", "daily_loss_points": 0.0, "last_trade_id": "", "trade_count": 0},
    )
    if not isinstance(tracker, dict):
        tracker = {"trading_day": "", "daily_loss_points": 0.0, "last_trade_id": "", "trade_count": 0}

    trading_day = str(latest_bar_time // 86400)
    if str(tracker.get("trading_day", "")) != trading_day:
        tracker = {"trading_day": trading_day, "daily_loss_points": 0.0, "last_trade_id": "", "trade_count": 0}

    latest_trade_id = str(latest_outcome.get("trade_id", ""))
    if latest_trade_id and latest_trade_id != str(tracker.get("last_trade_id", "")):
        if str(latest_outcome.get("status", "")).lower() == "closed":
            pnl_points = float(latest_outcome.get("pnl_points", 0.0))
            if pnl_points < 0:
                tracker["daily_loss_points"] = round(float(tracker.get("daily_loss_points", 0.0)) + abs(pnl_points), 4)
            tracker["trade_count"] = int(tracker.get("trade_count", 0)) + 1
        tracker["last_trade_id"] = latest_trade_id

    volatility_ratio = max(0.2, float(volatility_value))
    scale = volatility_scaling_factor(volatility_ratio=volatility_ratio)
    computed_size = compute_position_size(
        balance=10_000.0,
        risk_fraction=0.001,
        stop_loss_points=stop_loss_points,
        volatility_factor=scale,
        minimum_size=0.01,
        maximum_size=max(0.01, requested_volume),
    )
    effective_size = round(min(requested_volume, computed_size), 4)
    loss_check = check_daily_loss_limit(
        daily_loss_points=float(tracker.get("daily_loss_points", 0.0)),
        max_daily_loss_points=max_daily_loss_points,
    )
    guard_state = {
        "trading_day": trading_day,
        "requested_volume": round(requested_volume, 4),
        "effective_volume": effective_size,
        "volatility_ratio": round(volatility_ratio, 4),
        "volatility_scale": scale,
        "daily_loss_check": loss_check,
        "trade_refused": not bool(loss_check["allowed_to_trade"]),
    }
    write_json_atomic(tracker_path, tracker)
    write_json_atomic(state_path, guard_state)

    return {
        "effective_volume": effective_size,
        "daily_loss_check": loss_check,
        "trade_refused": bool(guard_state["trade_refused"]),
        "paths": {
            "capital_guard_state": str(state_path),
            "daily_loss_tracker": str(tracker_path),
        },
    }
