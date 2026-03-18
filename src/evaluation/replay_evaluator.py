from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Callable

from src.evaluation.blocker_effect_report import build_blocker_effect_report
from src.evaluation.module_contribution_report import build_module_contribution_report
from src.evaluation.session_report import build_session_report


PipelineRunner = Callable[[Any], dict[str, Any]]
ConfigFactory = Callable[..., Any]


def evaluate_replay(
    pipeline_runner: PipelineRunner,
    config_factory: ConfigFactory,
    *,
    symbol: str,
    timeframe: str,
    bars: int,
    replay_csv_path: str,
    sample_path: str,
    memory_root: str,
    generated_registry_path: str,
    meta_adaptive_profile_path: str,
    evolution_enabled: bool,
    evolution_registry_path: str,
    evolution_artifact_root: str,
    evolution_max_proposals: int,
    compact_output: bool,
    evaluation_steps: int,
    evaluation_stride: int,
    execution_spread_cost_points: float = 0.0,
    execution_commission_cost_points: float = 0.0,
    execution_slippage_cost_points: float = 0.0,
    knowledge_expansion_enabled: bool = False,
    knowledge_expansion_root: str = "memory/knowledge_expansion",
    knowledge_candidate_limit: int = 6,
) -> dict[str, Any]:
    """Run replay evaluation using the existing replay pipeline path only."""
    rows = _load_rows(Path(replay_csv_path))
    if len(rows) < bars:
        raise ValueError("Replay evaluation requires at least `bars` rows.")

    start_index = bars
    max_steps_available = max(0, ((len(rows) - start_index) // max(1, evaluation_stride)) + 1)
    steps = min(evaluation_steps, max_steps_available)
    execution_costs = _build_execution_costs(
        spread_cost_points=execution_spread_cost_points,
        commission_cost_points=execution_commission_cost_points,
        slippage_cost_points=execution_slippage_cost_points,
    )

    records: list[dict[str, Any]] = []

    for step in range(steps):
        end = start_index + (step * evaluation_stride)
        window = rows[:end]
        temp_csv = Path(memory_root) / f"evaluation_window_{step + 1}.csv"
        _write_rows(temp_csv, window)

        cfg = config_factory(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            sample_path=sample_path,
            memory_root=memory_root,
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(temp_csv),
            generated_registry_path=generated_registry_path,
            meta_adaptive_profile_path=meta_adaptive_profile_path,
            evolution_enabled=evolution_enabled,
            evolution_registry_path=evolution_registry_path,
            evolution_artifact_root=evolution_artifact_root,
            evolution_max_proposals=evolution_max_proposals,
            compact_output=False,
        )
        result = pipeline_runner(cfg)
        _apply_execution_costs_to_record(result, execution_costs)
        result["evaluation_step"] = step + 1
        records.append(result)

    signal_counts = {
        "total": len(records),
        "blocked": sum(1 for r in records if bool(r.get("signal", {}).get("blocked", False))),
    }
    action_distribution = _action_distribution(records)
    confidence_distribution = _confidence_distribution(records)

    return {
        "symbol": symbol,
        "mode": "replay_evaluation",
        "steps": len(records),
        "signal_counts": signal_counts,
        "action_distribution": action_distribution,
        "confidence_distribution": confidence_distribution,
        "blocker_effect_report": build_blocker_effect_report(records),
        "module_contribution_report": build_module_contribution_report(records),
        "session_report": build_session_report(records),
        "execution_costs": execution_costs,
        "execution_cost_impact": _build_execution_cost_impact(records, execution_costs),
        "records": records,
        "knowledge_expansion_config": {
            "enabled": knowledge_expansion_enabled,
            "root": knowledge_expansion_root,
            "candidate_limit": knowledge_candidate_limit,
        },
    }


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Replay CSV not found for evaluation: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Cannot write empty evaluation window.")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _action_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    dist = {"BUY": 0, "SELL": 0, "WAIT": 0}
    for record in records:
        action = str(record.get("signal", {}).get("action", "WAIT"))
        if action not in dist:
            action = "WAIT"
        dist[action] += 1
    return dist


def _confidence_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    bins = {"low": 0, "medium": 0, "high": 0}
    for record in records:
        confidence = float(record.get("signal", {}).get("confidence", 0.0))
        if confidence < 0.5:
            bins["low"] += 1
        elif confidence < 0.75:
            bins["medium"] += 1
        else:
            bins["high"] += 1
    return bins


def _build_execution_costs(
    *,
    spread_cost_points: float,
    commission_cost_points: float,
    slippage_cost_points: float,
) -> dict[str, float]:
    spread = _validate_non_negative_cost("execution_spread_cost_points", spread_cost_points)
    commission = _validate_non_negative_cost("execution_commission_cost_points", commission_cost_points)
    slippage = _validate_non_negative_cost("execution_slippage_cost_points", slippage_cost_points)
    total = round(spread + commission + slippage, 6)
    return {
        "spread_cost_points": spread,
        "commission_cost_points": commission,
        "slippage_cost_points": slippage,
        "total_cost_points": total,
    }


def _validate_non_negative_cost(name: str, value: float) -> float:
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{name} must be finite")
    if numeric_value < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return round(numeric_value, 6)


def _apply_execution_costs_to_record(record: dict[str, Any], execution_costs: dict[str, float]) -> None:
    # Replay outcomes use pnl_points in "points" units. We apply additive execution costs
    # in those same units so net points are deterministic:
    # net_pnl_points = gross_pnl_points - (spread + commission + slippage).
    latest_outcome = _extract_latest_trade_outcome(record)
    if not _outcome_is_closed_trade(latest_outcome):
        return

    gross = round(float(latest_outcome.get("pnl_points", 0.0)), 3)
    total_cost = round(float(execution_costs["total_cost_points"]), 3)
    net = round(gross - total_cost, 3)
    latest_outcome["pnl_points_gross"] = gross
    latest_outcome["pnl_points_net"] = net
    latest_outcome["execution_costs"] = {
        **execution_costs,
        "applied": True,
    }


def _extract_latest_trade_outcome(record: dict[str, Any]) -> dict[str, Any]:
    status_panel = record.get("status_panel", {})
    if not isinstance(status_panel, dict):
        return {}
    memory_result = status_panel.get("memory_result", {})
    if not isinstance(memory_result, dict):
        return {}
    latest_outcome = memory_result.get("latest_trade_outcome", {})
    if not isinstance(latest_outcome, dict):
        return {}
    return latest_outcome


def _outcome_is_closed_trade(outcome: dict[str, Any]) -> bool:
    status = str(outcome.get("status", "")).lower()
    direction = str(outcome.get("direction", "")).upper()
    return status == "closed" and direction in {"BUY", "SELL"}


def _build_execution_cost_impact(
    records: list[dict[str, Any]],
    execution_costs: dict[str, float],
) -> dict[str, int | float]:
    closed_trades = 0
    gross_pnl_points = 0.0
    net_pnl_points = 0.0

    for record in records:
        outcome = _extract_latest_trade_outcome(record)
        if not _outcome_is_closed_trade(outcome):
            continue
        gross = round(float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))), 3)
        net = round(float(outcome.get("pnl_points_net", gross)), 3)
        closed_trades += 1
        gross_pnl_points = round(gross_pnl_points + gross, 3)
        net_pnl_points = round(net_pnl_points + net, 3)

    return {
        "closed_trade_count": closed_trades,
        "gross_pnl_points": gross_pnl_points,
        "total_execution_cost_points": round(gross_pnl_points - net_pnl_points, 3),
        "net_pnl_points": net_pnl_points,
        "per_trade_total_cost_points": round(float(execution_costs["total_cost_points"]), 3),
    }
