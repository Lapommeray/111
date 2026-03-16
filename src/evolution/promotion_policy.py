from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

from src.utils import write_json_atomic

STABILITY_VOLATILITY_CAP = 1_000_000.0


@dataclass(frozen=True)
class PromotionThresholds:
    minimum_replay_sample_size: int = 30
    minimum_expectancy_points: float = 0.05
    maximum_drawdown_points: float = 4.0
    minimum_stability_score: float = 0.55


def _compute_drawdown(points: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in points:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return round(max_drawdown, 4)


def _stability_score(points: list[float]) -> float:
    if not points:
        return 0.0
    mean = sum(points) / len(points)
    variance = sum((p - mean) ** 2 for p in points) / len(points)
    volatility = min(STABILITY_VOLATILITY_CAP, sqrt(variance))
    return round(max(0.0, min(1.0, 1.0 / (1.0 + volatility))), 4)


def evaluate_module_promotion_policy(
    *,
    memory_root: str,
    outcomes: list[dict[str, Any]],
    thresholds: PromotionThresholds | None = None,
) -> dict[str, Any]:
    policy = thresholds or PromotionThresholds()
    closed = [item for item in outcomes if str(item.get("status", "")).lower() == "closed"]
    pnl_points = [float(item.get("pnl_points", 0.0) or 0.0) for item in closed]
    sample_size = len(closed)
    expectancy = round((sum(pnl_points) / sample_size), 4) if sample_size else 0.0
    drawdown = _compute_drawdown(pnl_points)
    stability = _stability_score(pnl_points)

    failed_thresholds: list[str] = []
    if sample_size < policy.minimum_replay_sample_size:
        failed_thresholds.append("minimum_replay_sample_size")
    if expectancy < policy.minimum_expectancy_points:
        failed_thresholds.append("minimum_expectancy")
    if drawdown > policy.maximum_drawdown_points:
        failed_thresholds.append("acceptable_drawdown")
    if stability < policy.minimum_stability_score:
        failed_thresholds.append("stability_requirement")

    if "acceptable_drawdown" in failed_thresholds:
        promotion_state = "quarantined"
    elif failed_thresholds:
        promotion_state = "sandboxed"
    else:
        promotion_state = "eligible_for_promotion"

    payload = {
        "promotion_state": promotion_state,
        "failed_thresholds": failed_thresholds,
        "metrics": {
            "sample_size": sample_size,
            "expectancy_points": expectancy,
            "drawdown_points": drawdown,
            "stability_score": stability,
        },
        "thresholds": {
            "minimum_replay_sample_size": policy.minimum_replay_sample_size,
            "minimum_expectancy_points": policy.minimum_expectancy_points,
            "maximum_drawdown_points": policy.maximum_drawdown_points,
            "minimum_stability_score": policy.minimum_stability_score,
        },
        "optimization_priorities": [
            "maximize_expectancy",
            "minimize_drawdown",
            "prioritize_survival_over_win_rate",
            "prefer_stable_equity_curve_over_high_variance",
        ],
    }
    path = Path(memory_root) / "evolution_promotion_policy.json"
    write_json_atomic(path, payload)
    return {**payload, "path": str(path)}
