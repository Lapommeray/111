from __future__ import annotations

import csv
import math
import shutil
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
    walk_forward_enabled: bool = False,
    walk_forward_context_bars: int = 220,
    walk_forward_test_bars: int = 60,
    walk_forward_step_bars: int = 60,
    execution_spread_cost_points: float = 0.0,
    execution_commission_cost_points: float = 0.0,
    execution_slippage_cost_points: float = 0.0,
    execution_realism_v2_enabled: bool = False,
    execution_latency_penalty_points: float = 0.0,
    execution_slippage_multiplier: float = 1.0,
    execution_no_fill_spread_threshold: float = 0.0,
    execution_min_fill_confidence: float = 0.0,
    knowledge_expansion_enabled: bool = False,
    knowledge_expansion_root: str = "memory/knowledge_expansion",
    knowledge_candidate_limit: int = 6,
) -> dict[str, Any]:
    """Run replay evaluation using the existing replay pipeline path only."""
    replay_memory_root = _prepare_replay_memory_root(memory_root)
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
    execution_realism_v2 = _build_execution_realism_v2_config(
        enabled=execution_realism_v2_enabled,
        latency_penalty_points=execution_latency_penalty_points,
        slippage_multiplier=execution_slippage_multiplier,
        no_fill_spread_threshold=execution_no_fill_spread_threshold,
        min_fill_confidence=execution_min_fill_confidence,
    )

    records: list[dict[str, Any]] = []
    per_cycle_summary: list[dict[str, Any]] = []
    cycle_count = 0
    oos_summary = _empty_walk_forward_oos_summary(
        walk_forward_enabled=walk_forward_enabled,
        context_bars=walk_forward_context_bars,
        test_bars=walk_forward_test_bars,
        step_bars=walk_forward_step_bars,
    )

    if not walk_forward_enabled:
        end_indexes = [start_index + (step * evaluation_stride) for step in range(steps)]
        records = _run_replay_steps(
            rows=rows,
            end_indexes=end_indexes,
            window_prefix="evaluation_window",
            pipeline_runner=pipeline_runner,
            config_factory=config_factory,
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            sample_path=sample_path,
            replay_memory_root=replay_memory_root,
            generated_registry_path=generated_registry_path,
            meta_adaptive_profile_path=meta_adaptive_profile_path,
            evolution_enabled=evolution_enabled,
            evolution_registry_path=evolution_registry_path,
            evolution_artifact_root=evolution_artifact_root,
            evolution_max_proposals=evolution_max_proposals,
            execution_costs=execution_costs,
            execution_realism_v2=execution_realism_v2,
        )
    else:
        cycles = _build_walk_forward_cycles(
            total_rows=len(rows),
            bars=bars,
            context_bars=walk_forward_context_bars,
            test_bars=walk_forward_test_bars,
            step_bars=walk_forward_step_bars,
            evaluation_stride=evaluation_stride,
        )
        for cycle_index, cycle in enumerate(cycles, start=1):
            end_indexes = list(
                range(
                    int(cycle["test_start_index"]) + 1,
                    int(cycle["test_end_index_exclusive"]) + 1,
                    max(1, evaluation_stride),
                )
            )
            if end_indexes and end_indexes[-1] != int(cycle["test_end_index_exclusive"]):
                end_indexes.append(int(cycle["test_end_index_exclusive"]))
            cycle_records = _run_replay_steps(
                rows=rows,
                end_indexes=end_indexes,
                window_prefix=f"evaluation_window_cycle_{cycle_index}",
                pipeline_runner=pipeline_runner,
                config_factory=config_factory,
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                sample_path=sample_path,
                replay_memory_root=replay_memory_root,
                generated_registry_path=generated_registry_path,
                meta_adaptive_profile_path=meta_adaptive_profile_path,
                evolution_enabled=evolution_enabled,
                evolution_registry_path=evolution_registry_path,
                evolution_artifact_root=evolution_artifact_root,
                evolution_max_proposals=evolution_max_proposals,
                execution_costs=execution_costs,
                execution_realism_v2=execution_realism_v2,
            )
            for record in cycle_records:
                record["walk_forward_cycle"] = cycle_index
            records.extend(cycle_records)
            per_cycle_summary.append(
                _build_walk_forward_cycle_summary(
                    cycle_index=cycle_index,
                    cycle=cycle,
                    cycle_records=cycle_records,
                )
            )
        cycle_count = len(cycles)
        oos_summary = _build_walk_forward_oos_summary(
            context_bars=walk_forward_context_bars,
            test_bars=walk_forward_test_bars,
            step_bars=walk_forward_step_bars,
            per_cycle_summary=per_cycle_summary,
        )

    signal_counts = {
        "total": len(records),
        "blocked": sum(1 for r in records if bool(r.get("signal", {}).get("blocked", False))),
    }
    action_distribution = _action_distribution(records)
    confidence_distribution = _confidence_distribution(records)

    execution_realism_v2_impact = _build_execution_realism_v2_impact(records, execution_realism_v2)
    analytics_summary = _build_analytics_summary(records)
    oos_analytics_summary = _build_oos_analytics_summary(records, walk_forward_enabled=walk_forward_enabled)
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
        "execution_realism_v2": execution_realism_v2_impact,
        "execution_realism_v2_enabled": execution_realism_v2_impact["execution_realism_v2_enabled"],
        "realism_v2_rules_applied": execution_realism_v2_impact["realism_v2_rules_applied"],
        "skipped_trade_count": execution_realism_v2_impact["skipped_trade_count"],
        "additional_realism_penalty_points": execution_realism_v2_impact["additional_realism_penalty_points"],
        "realism_adjusted_net_pnl_points": execution_realism_v2_impact["realism_adjusted_net_pnl_points"],
        "walk_forward_enabled": walk_forward_enabled,
        "cycle_count": cycle_count,
        "context_bars": walk_forward_context_bars,
        "test_bars": walk_forward_test_bars,
        "step_bars": walk_forward_step_bars,
        "total_oos_closed_trades": oos_summary["total_oos_closed_trades"],
        "total_oos_gross_pnl_points": oos_summary["total_oos_gross_pnl_points"],
        "total_oos_net_pnl_points": oos_summary["total_oos_net_pnl_points"],
        "total_oos_realism_adjusted_net_pnl_points": oos_summary["total_oos_realism_adjusted_net_pnl_points"],
        "total_oos_skipped_trades": oos_summary["total_oos_skipped_trades"],
        "total_oos_additional_realism_penalty_points": oos_summary["total_oos_additional_realism_penalty_points"],
        "oos_win_rate": oos_summary["oos_win_rate"],
        "oos_max_drawdown": oos_summary["oos_max_drawdown"],
        "oos_expectancy_points": oos_analytics_summary["expectancy_points"],
        "oos_profit_factor": oos_analytics_summary["profit_factor"],
        "oos_max_drawdown_points": oos_analytics_summary["max_drawdown_points"],
        "oos_average_realism_adjusted_net_pnl_points": oos_analytics_summary["average_realism_adjusted_net_pnl_points"],
        "analytics_summary": analytics_summary,
        "oos_analytics_summary": oos_analytics_summary,
        "per_cycle_summary": per_cycle_summary,
        "records": records,
        "replay_isolated": True,
        "replay_memory_root": str(replay_memory_root),
        "knowledge_expansion_config": {
            "enabled": knowledge_expansion_enabled,
            "root": knowledge_expansion_root,
            "candidate_limit": knowledge_candidate_limit,
        },
    }


def _run_replay_steps(
    *,
    rows: list[dict[str, str]],
    end_indexes: list[int],
    window_prefix: str,
    pipeline_runner: PipelineRunner,
    config_factory: ConfigFactory,
    symbol: str,
    timeframe: str,
    bars: int,
    sample_path: str,
    replay_memory_root: Path,
    generated_registry_path: str,
    meta_adaptive_profile_path: str,
    evolution_enabled: bool,
    evolution_registry_path: str,
    evolution_artifact_root: str,
    evolution_max_proposals: int,
    execution_costs: dict[str, float],
    execution_realism_v2: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for step_index, end in enumerate(end_indexes, start=1):
        window = rows[:end]
        step_root = replay_memory_root / "steps" / f"{window_prefix}_{step_index:04d}"
        temp_csv = step_root / "replay_window.csv"
        _write_rows(temp_csv, window)
        step_generated_registry_path = step_root / Path(generated_registry_path).name
        step_meta_adaptive_profile_path = step_root / Path(meta_adaptive_profile_path).name
        step_evolution_registry_path = step_root / Path(evolution_registry_path).name
        step_evolution_artifact_root = step_root / Path(evolution_artifact_root).name

        cfg = config_factory(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            sample_path=sample_path,
            memory_root=str(step_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(temp_csv),
            generated_registry_path=str(step_generated_registry_path),
            meta_adaptive_profile_path=str(step_meta_adaptive_profile_path),
            evolution_enabled=evolution_enabled,
            evolution_registry_path=str(step_evolution_registry_path),
            evolution_artifact_root=str(step_evolution_artifact_root),
            evolution_max_proposals=evolution_max_proposals,
            compact_output=False,
        )
        result = pipeline_runner(cfg)
        _apply_execution_costs_to_record(result, execution_costs)
        _apply_execution_realism_v2_to_record(result, execution_costs, execution_realism_v2)
        result["evaluation_step"] = step_index
        records.append(result)
    return records


def _build_walk_forward_cycles(
    *,
    total_rows: int,
    bars: int,
    context_bars: int,
    test_bars: int,
    step_bars: int,
    evaluation_stride: int,
) -> list[dict[str, int]]:
    if context_bars <= 0:
        raise ValueError("walk_forward_context_bars must be > 0")
    if test_bars <= 0:
        raise ValueError("walk_forward_test_bars must be > 0")
    if step_bars <= 0:
        raise ValueError("walk_forward_step_bars must be > 0")
    if test_bars < evaluation_stride:
        raise ValueError("walk_forward_test_bars must be >= evaluation_stride")
    if context_bars < bars:
        raise ValueError("walk_forward_context_bars must be >= bars")

    cycles: list[dict[str, int]] = []
    context_start = 0
    while True:
        context_end = context_start + context_bars
        test_end_exclusive = context_end + test_bars
        if test_end_exclusive > total_rows:
            break
        cycles.append(
            {
                "context_start_index": context_start,
                "context_end_index_exclusive": context_end,
                "test_start_index": context_end,
                "test_end_index_exclusive": test_end_exclusive,
            }
        )
        context_start += step_bars

    if not cycles:
        raise ValueError(
            "No walk-forward cycles can be built from replay rows using the configured context/test/step bars"
        )
    return cycles


def _closed_outcome_points(records: list[dict[str, Any]]) -> tuple[int, float, float, int, list[float]]:
    closed_trades = 0
    gross_pnl_points = 0.0
    net_pnl_points = 0.0
    wins = 0
    net_series: list[float] = []
    for record in records:
        outcome = _extract_latest_trade_outcome(record)
        if not _outcome_is_closed_trade(outcome):
            continue
        gross = round(float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))), 3)
        net = round(float(outcome.get("pnl_points_net", gross)), 3)
        result = str(outcome.get("result", "")).lower()
        closed_trades += 1
        gross_pnl_points = round(gross_pnl_points + gross, 3)
        net_pnl_points = round(net_pnl_points + net, 3)
        if result == "win":
            wins += 1
        net_series.append(net)
    return closed_trades, gross_pnl_points, net_pnl_points, wins, net_series


def _max_drawdown(points: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in points:
        cumulative = round(cumulative + float(value), 3)
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return round(abs(max_drawdown), 3)


def _build_walk_forward_cycle_summary(
    *,
    cycle_index: int,
    cycle: dict[str, int],
    cycle_records: list[dict[str, Any]],
) -> dict[str, Any]:
    closed_trades, gross_pnl_points, net_pnl_points, wins, net_series = _closed_outcome_points(cycle_records)
    skipped_trade_count = 0
    additional_realism_penalty_points = 0.0
    realism_adjusted_net_pnl_points = 0.0
    for record in cycle_records:
        outcome = _extract_latest_trade_outcome(record)
        if not _outcome_is_closed_trade(outcome):
            continue
        net = round(float(outcome.get("pnl_points_net", outcome.get("pnl_points", 0.0))), 3)
        realism_v2 = outcome.get("execution_realism_v2", {})
        if isinstance(realism_v2, dict):
            if bool(realism_v2.get("no_fill_applied", False)):
                skipped_trade_count += 1
            additional_realism_penalty_points = round(
                additional_realism_penalty_points + float(realism_v2.get("additional_penalty_points", 0.0)),
                3,
            )
            realism_adjusted_net_pnl_points = round(
                realism_adjusted_net_pnl_points + float(realism_v2.get("realism_adjusted_net_pnl_points", net)),
                3,
            )
        else:
            realism_adjusted_net_pnl_points = round(realism_adjusted_net_pnl_points + net, 3)
    return {
        "cycle_index": cycle_index,
        "context_start_bar_index": int(cycle["context_start_index"]),
        "context_end_bar_index": int(cycle["context_end_index_exclusive"]) - 1,
        "test_start_bar_index": int(cycle["test_start_index"]),
        "test_end_bar_index": int(cycle["test_end_index_exclusive"]) - 1,
        "forward_steps": len(cycle_records),
        "closed_trades": closed_trades,
        "wins": wins,
        "gross_pnl_points": gross_pnl_points,
        "net_pnl_points": net_pnl_points,
        "realism_adjusted_net_pnl_points": realism_adjusted_net_pnl_points,
        "skipped_trade_count": skipped_trade_count,
        "additional_realism_penalty_points": additional_realism_penalty_points,
        "win_rate": round((wins / closed_trades), 4) if closed_trades else 0.0,
        "max_drawdown": _max_drawdown(net_series),
    }


def _empty_walk_forward_oos_summary(
    *,
    walk_forward_enabled: bool,
    context_bars: int,
    test_bars: int,
    step_bars: int,
) -> dict[str, Any]:
    return {
        "walk_forward_enabled": walk_forward_enabled,
        "cycle_count": 0,
        "context_bars": context_bars,
        "test_bars": test_bars,
        "step_bars": step_bars,
        "total_oos_closed_trades": 0,
        "total_oos_gross_pnl_points": 0.0,
        "total_oos_net_pnl_points": 0.0,
        "total_oos_realism_adjusted_net_pnl_points": 0.0,
        "total_oos_skipped_trades": 0,
        "total_oos_additional_realism_penalty_points": 0.0,
        "oos_win_rate": 0.0,
        "oos_max_drawdown": 0.0,
    }


def _build_walk_forward_oos_summary(
    *,
    context_bars: int,
    test_bars: int,
    step_bars: int,
    per_cycle_summary: list[dict[str, Any]],
) -> dict[str, Any]:
    total_closed = sum(int(cycle.get("closed_trades", 0)) for cycle in per_cycle_summary)
    total_gross = round(sum(float(cycle.get("gross_pnl_points", 0.0)) for cycle in per_cycle_summary), 3)
    total_net = round(sum(float(cycle.get("net_pnl_points", 0.0)) for cycle in per_cycle_summary), 3)
    total_realism_adjusted_net = round(
        sum(float(cycle.get("realism_adjusted_net_pnl_points", cycle.get("net_pnl_points", 0.0))) for cycle in per_cycle_summary),
        3,
    )
    total_skipped = sum(int(cycle.get("skipped_trade_count", 0)) for cycle in per_cycle_summary)
    total_additional_realism_penalty = round(
        sum(float(cycle.get("additional_realism_penalty_points", 0.0)) for cycle in per_cycle_summary),
        3,
    )
    total_wins = sum(int(cycle.get("wins", 0)) for cycle in per_cycle_summary)
    max_drawdown_across_cycles = round(
        max((float(cycle.get("max_drawdown", 0.0)) for cycle in per_cycle_summary), default=0.0),
        3,
    )
    return {
        "walk_forward_enabled": True,
        "cycle_count": len(per_cycle_summary),
        "context_bars": context_bars,
        "test_bars": test_bars,
        "step_bars": step_bars,
        "total_oos_closed_trades": total_closed,
        "total_oos_gross_pnl_points": total_gross,
        "total_oos_net_pnl_points": total_net,
        "total_oos_realism_adjusted_net_pnl_points": total_realism_adjusted_net,
        "total_oos_skipped_trades": total_skipped,
        "total_oos_additional_realism_penalty_points": total_additional_realism_penalty,
        "oos_win_rate": round((total_wins / total_closed), 4) if total_closed else 0.0,
        "oos_max_drawdown": max_drawdown_across_cycles,
    }


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Replay CSV not found for evaluation: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _prepare_replay_memory_root(memory_root: str) -> Path:
    base = Path(memory_root).expanduser()
    parent = base.parent.resolve()
    sandbox = parent / f"{base.name}__replay_isolation"
    if sandbox.exists():
        if sandbox.is_file():
            raise RuntimeError(f"Replay isolation path is a file, expected directory: {sandbox}")
        _safe_rmtree(sandbox, expected_parent=parent)
    sandbox.mkdir(parents=True, exist_ok=True)
    return sandbox


def _safe_rmtree(path: Path, *, expected_parent: Path) -> None:
    resolved = path.resolve()
    if resolved.name.endswith("__replay_isolation") and resolved.parent == expected_parent.resolve():
        shutil.rmtree(resolved)
        return
    raise RuntimeError(f"Refusing to delete non-replay sandbox path: {resolved}")


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


def _build_execution_realism_v2_config(
    *,
    enabled: bool,
    latency_penalty_points: float,
    slippage_multiplier: float,
    no_fill_spread_threshold: float,
    min_fill_confidence: float,
) -> dict[str, Any]:
    latency = _validate_non_negative_cost("execution_latency_penalty_points", latency_penalty_points)
    no_fill_threshold = _validate_non_negative_cost(
        "execution_no_fill_spread_threshold",
        no_fill_spread_threshold,
    )
    slippage_multi = _validate_non_negative_cost("execution_slippage_multiplier", slippage_multiplier)
    if slippage_multi < 1.0:
        raise ValueError("execution_slippage_multiplier must be >= 1")
    min_conf_numeric = float(min_fill_confidence)
    if not math.isfinite(min_conf_numeric):
        raise ValueError("execution_min_fill_confidence must be finite")
    if min_conf_numeric < 0.0 or min_conf_numeric > 1.0:
        raise ValueError("execution_min_fill_confidence must be within [0, 1]")
    min_conf = round(min_conf_numeric, 6)
    return {
        "enabled": bool(enabled),
        "latency_penalty_points": latency,
        "slippage_multiplier": slippage_multi,
        "no_fill_spread_threshold": no_fill_threshold,
        "min_fill_confidence": min_conf,
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


def _apply_execution_realism_v2_to_record(
    record: dict[str, Any],
    execution_costs: dict[str, float],
    execution_realism_v2: dict[str, Any],
) -> None:
    if not bool(execution_realism_v2.get("enabled", False)):
        return
    latest_outcome = _extract_latest_trade_outcome(record)
    if not _outcome_is_closed_trade(latest_outcome):
        return

    spread_proxy = _extract_spread_proxy_points(record)
    signal_confidence = _extract_signal_confidence(record)
    execution_quality_confidence = _extract_execution_quality_confidence(record)
    # Prefer execution-quality confidence when available because it is a direct
    # execution-proxy signal; otherwise fall back to the trade signal confidence.
    confidence_proxy = (
        execution_quality_confidence
        if execution_quality_confidence is not None
        else signal_confidence
    )
    confidence_proxy = float(confidence_proxy)

    no_fill_threshold = float(execution_realism_v2["no_fill_spread_threshold"])
    no_fill_applied = (
        no_fill_threshold > 0.0
        and spread_proxy is not None
        and spread_proxy > no_fill_threshold
    )
    net = round(float(latest_outcome.get("pnl_points_net", latest_outcome.get("pnl_points", 0.0))), 3)
    additional_penalty_points = 0.0
    rules_triggered: list[str] = []
    calc_log: list[str] = []

    if no_fill_applied:
        rules_triggered.append("no_fill_spread_threshold")
        calc_log.append(
            f"spread_proxy={round(float(spread_proxy), 3)}, "
            f"threshold={round(no_fill_threshold, 3)} -> no_fill"
        )
        realism_adjusted_net = 0.0
    else:
        latency_penalty = round(float(execution_realism_v2["latency_penalty_points"]), 3)
        slippage_multiplier_penalty = round(
            float(execution_costs.get("slippage_cost_points", 0.0))
            * max(0.0, float(execution_realism_v2["slippage_multiplier"]) - 1.0),
            3,
        )
        confidence_penalty = 0.0
        min_fill_confidence = float(execution_realism_v2["min_fill_confidence"])
        if min_fill_confidence > 0.0 and confidence_proxy < min_fill_confidence:
            confidence_gap = round(min_fill_confidence - confidence_proxy, 6)
            # Keep the confidence penalty deterministic and bounded: we scale by
            # configured total execution cost, with a 0.1 minimum multiplier so the
            # penalty can still apply when fixed execution costs are near zero.
            confidence_penalty = round(confidence_gap * max(0.1, float(execution_costs.get("total_cost_points", 0.0))), 3)
            rules_triggered.append("confidence_penalty")
            calc_log.append(
                f"confidence_proxy={round(confidence_proxy, 4)}, "
                f"min_fill_confidence={round(min_fill_confidence, 4)} -> "
                f"confidence_penalty={confidence_penalty}"
            )
        if latency_penalty > 0.0:
            rules_triggered.append("latency_penalty")
            calc_log.append(f"latency_penalty_points={latency_penalty}")
        if slippage_multiplier_penalty > 0.0:
            rules_triggered.append("spread_sensitive_slippage_multiplier")
            calc_log.append(
                f"base_slippage_cost_points={round(float(execution_costs.get('slippage_cost_points', 0.0)), 3)}, "
                f"slippage_multiplier={round(float(execution_realism_v2['slippage_multiplier']), 3)} -> "
                f"slippage_multiplier_penalty={slippage_multiplier_penalty}"
            )
        additional_penalty_points = round(latency_penalty + slippage_multiplier_penalty + confidence_penalty, 3)
        realism_adjusted_net = round(net - additional_penalty_points, 3)

    latest_outcome["execution_realism_v2"] = {
        "enabled": True,
        "applied": True,
        "rules_triggered": sorted(set(rules_triggered)),
        "no_fill_applied": no_fill_applied,
        "proxy_values": {
            "spread_proxy_points": spread_proxy,
            "signal_confidence": round(signal_confidence, 4),
            "execution_quality_confidence": execution_quality_confidence,
            "confidence_proxy": round(confidence_proxy, 4),
        },
        "config": {
            "latency_penalty_points": float(execution_realism_v2["latency_penalty_points"]),
            "slippage_multiplier": float(execution_realism_v2["slippage_multiplier"]),
            "no_fill_spread_threshold": float(execution_realism_v2["no_fill_spread_threshold"]),
            "min_fill_confidence": float(execution_realism_v2["min_fill_confidence"]),
        },
        "additional_penalty_points": additional_penalty_points,
        "realism_adjusted_net_pnl_points": realism_adjusted_net,
        "calculation_log": calc_log,
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
        "total_execution_cost_points": round(closed_trades * float(execution_costs["total_cost_points"]), 3),
        "net_pnl_points": net_pnl_points,
        "per_trade_total_cost_points": round(float(execution_costs["total_cost_points"]), 3),
    }


def _extract_signal_confidence(record: dict[str, Any]) -> float:
    signal = record.get("signal", {})
    if not isinstance(signal, dict):
        return 0.0
    return round(float(signal.get("confidence", 0.0) or 0.0), 6)


def _extract_spread_proxy_points(record: dict[str, Any]) -> float | None:
    module_results = _extract_module_results(record)
    spread_state = module_results.get("spread_state", {})
    if not isinstance(spread_state, dict):
        return None
    payload = spread_state.get("payload", spread_state)
    if not isinstance(payload, dict):
        return None
    spread_points = payload.get("spread_points")
    if spread_points is None:
        return None
    return round(float(spread_points), 6)


def _extract_execution_quality_confidence(record: dict[str, Any]) -> float | None:
    module_results = _extract_module_results(record)
    execution_quality = module_results.get("execution_quality", {})
    if not isinstance(execution_quality, dict):
        return None
    payload = execution_quality.get("payload", execution_quality)
    if not isinstance(payload, dict):
        return None
    confidence = payload.get("confidence")
    if confidence is None:
        return None
    return round(float(confidence), 6)


def _extract_module_results(record: dict[str, Any]) -> dict[str, Any]:
    signal = record.get("signal", {})
    if not isinstance(signal, dict):
        return {}
    advanced_modules = signal.get("advanced_modules", {})
    if not isinstance(advanced_modules, dict):
        return {}
    module_results = advanced_modules.get("module_results", {})
    if not isinstance(module_results, dict):
        return {}
    return module_results


def _build_execution_realism_v2_impact(
    records: list[dict[str, Any]],
    execution_realism_v2: dict[str, Any],
) -> dict[str, Any]:
    rules_applied: set[str] = set()
    closed_trade_count = 0
    skipped_trade_count = 0
    gross_pnl_points = 0.0
    net_pnl_points = 0.0
    additional_realism_penalty_points = 0.0
    realism_adjusted_net_pnl_points = 0.0

    for record in records:
        outcome = _extract_latest_trade_outcome(record)
        if not _outcome_is_closed_trade(outcome):
            continue
        closed_trade_count += 1
        gross = round(float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))), 3)
        net = round(float(outcome.get("pnl_points_net", gross)), 3)
        realism_v2 = outcome.get("execution_realism_v2", {})
        gross_pnl_points = round(gross_pnl_points + gross, 3)
        net_pnl_points = round(net_pnl_points + net, 3)
        if isinstance(realism_v2, dict):
            for rule in realism_v2.get("rules_triggered", []):
                if isinstance(rule, str) and rule.strip():
                    rules_applied.add(rule)
            if bool(realism_v2.get("no_fill_applied", False)):
                skipped_trade_count += 1
            additional_realism_penalty_points = round(
                additional_realism_penalty_points + float(realism_v2.get("additional_penalty_points", 0.0)),
                3,
            )
            realism_adjusted_net_pnl_points = round(
                realism_adjusted_net_pnl_points + float(realism_v2.get("realism_adjusted_net_pnl_points", net)),
                3,
            )
        else:
            realism_adjusted_net_pnl_points = round(realism_adjusted_net_pnl_points + net, 3)

    return {
        "execution_realism_v2_enabled": bool(execution_realism_v2.get("enabled", False)),
        "realism_v2_rules_configured": [
            "latency_penalty",
            "spread_sensitive_slippage_multiplier",
            "no_fill_spread_threshold",
            "confidence_penalty",
        ],
        "realism_v2_rules_applied": sorted(rules_applied),
        "closed_trade_count": closed_trade_count,
        "skipped_trade_count": skipped_trade_count,
        "gross_pnl_points": gross_pnl_points,
        "net_pnl_points": net_pnl_points,
        "additional_realism_penalty_points": additional_realism_penalty_points,
        "realism_adjusted_net_pnl_points": realism_adjusted_net_pnl_points,
    }


def _build_oos_analytics_summary(
    records: list[dict[str, Any]],
    *,
    walk_forward_enabled: bool,
) -> dict[str, Any]:
    if not walk_forward_enabled:
        return {
            **_empty_analytics_summary(),
            "walk_forward_enabled": False,
        }
    return {
        **_build_analytics_summary(records),
        "walk_forward_enabled": True,
    }


def _build_analytics_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    gross_points: list[float] = []
    net_points: list[float] = []
    realism_adjusted_net_points: list[float] = []
    skipped_trade_count = 0

    for record in records:
        outcome = _extract_latest_trade_outcome(record)
        if not _outcome_is_closed_trade(outcome):
            continue
        gross = round(float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))), 3)
        net = round(float(outcome.get("pnl_points_net", gross)), 3)
        realism_adjusted_net = net
        realism_v2 = outcome.get("execution_realism_v2", {})
        if isinstance(realism_v2, dict):
            if bool(realism_v2.get("no_fill_applied", False)):
                skipped_trade_count += 1
            realism_adjusted_net = round(float(realism_v2.get("realism_adjusted_net_pnl_points", net)), 3)

        gross_points.append(gross)
        net_points.append(net)
        realism_adjusted_net_points.append(realism_adjusted_net)

    gross = _build_series_analytics(gross_points)
    net = _build_series_analytics(net_points)
    realism_adjusted = _build_series_analytics(realism_adjusted_net_points)

    return {
        "closed_trade_count": net["closed_trade_count"],
        "win_count": net["win_count"],
        "loss_count": net["loss_count"],
        "flat_count": net["flat_count"],
        "skipped_trade_count": skipped_trade_count,
        "win_rate": net["win_rate"],
        "average_gross_pnl_points": gross["average_pnl_points"],
        "average_net_pnl_points": net["average_pnl_points"],
        "average_realism_adjusted_net_pnl_points": realism_adjusted["average_pnl_points"],
        "expectancy_points": net["expectancy_points"],
        "profit_factor": net["profit_factor"],
        "max_drawdown_points": net["max_drawdown_points"],
        "average_win_points": net["average_win_points"],
        "average_loss_points": net["average_loss_points"],
        "payoff_ratio": net["payoff_ratio"],
        "best_trade_points": net["best_trade_points"],
        "worst_trade_points": net["worst_trade_points"],
        "consecutive_wins_max": net["consecutive_wins_max"],
        "consecutive_losses_max": net["consecutive_losses_max"],
        "series": {
            "gross": gross,
            "net": net,
            "realism_adjusted_net": {
                **realism_adjusted,
                "skipped_trade_count": skipped_trade_count,
            },
        },
    }


def _empty_analytics_summary() -> dict[str, Any]:
    empty_series = _build_series_analytics([])
    return {
        "closed_trade_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "flat_count": 0,
        "skipped_trade_count": 0,
        "win_rate": 0.0,
        "average_gross_pnl_points": 0.0,
        "average_net_pnl_points": 0.0,
        "average_realism_adjusted_net_pnl_points": 0.0,
        "expectancy_points": 0.0,
        "profit_factor": None,
        "max_drawdown_points": 0.0,
        "average_win_points": 0.0,
        "average_loss_points": 0.0,
        "payoff_ratio": None,
        "best_trade_points": 0.0,
        "worst_trade_points": 0.0,
        "consecutive_wins_max": 0,
        "consecutive_losses_max": 0,
        "series": {
            "gross": empty_series,
            "net": empty_series,
            "realism_adjusted_net": {
                **empty_series,
                "skipped_trade_count": 0,
            },
        },
    }


def _build_series_analytics(points: list[float]) -> dict[str, Any]:
    rounded_points = [round(float(value), 3) for value in points]
    closed_trade_count = len(rounded_points)
    wins = [value for value in rounded_points if value > 0.0]
    losses = [value for value in rounded_points if value < 0.0]
    flats = [value for value in rounded_points if value == 0.0]
    gross_wins = round(sum(wins), 3)
    gross_losses_abs = round(abs(sum(losses)), 3)
    average_loss_points = round((sum(losses) / len(losses)), 3) if losses else 0.0
    average_win_points = round((sum(wins) / len(wins)), 3) if wins else 0.0

    consecutive_wins_max = 0
    consecutive_losses_max = 0
    current_wins = 0
    current_losses = 0
    for value in rounded_points:
        if value > 0.0:
            current_wins += 1
            current_losses = 0
        elif value < 0.0:
            current_losses += 1
            current_wins = 0
        else:
            current_wins = 0
            current_losses = 0
        consecutive_wins_max = max(consecutive_wins_max, current_wins)
        consecutive_losses_max = max(consecutive_losses_max, current_losses)

    return {
        "closed_trade_count": closed_trade_count,
        "win_count": len(wins),
        "loss_count": len(losses),
        "flat_count": len(flats),
        "win_rate": round((len(wins) / closed_trade_count), 6) if closed_trade_count else 0.0,
        "average_pnl_points": round((sum(rounded_points) / closed_trade_count), 3) if closed_trade_count else 0.0,
        "expectancy_points": round((sum(rounded_points) / closed_trade_count), 3) if closed_trade_count else 0.0,
        "profit_factor": round(gross_wins / gross_losses_abs, 6) if gross_losses_abs > 0.0 else None,
        "max_drawdown_points": _max_drawdown(rounded_points),
        "average_win_points": average_win_points,
        "average_loss_points": average_loss_points,
        "payoff_ratio": round(average_win_points / abs(average_loss_points), 6) if average_loss_points < 0.0 else None,
        "best_trade_points": round(max(rounded_points), 3) if rounded_points else 0.0,
        "worst_trade_points": round(min(rounded_points), 3) if rounded_points else 0.0,
        "consecutive_wins_max": consecutive_wins_max,
        "consecutive_losses_max": consecutive_losses_max,
    }
