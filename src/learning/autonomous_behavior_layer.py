from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils import read_json_safe, write_json_atomic

_PAUSE_LOSS_STREAK = 3


def _closed_outcomes(trade_outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [outcome for outcome in trade_outcomes if str(outcome.get("status", "")).lower() == "closed"]


def _classify_regime(market_state: dict[str, Any]) -> dict[str, Any]:
    structure_state = str(market_state.get("structure_state", "range")).lower()
    volatility_ratio = float(market_state.get("volatility_ratio", 1.0))
    spread_ratio = float(market_state.get("spread_ratio", 1.0))
    stale_price_data = bool(market_state.get("stale_price_data", False))
    mt5_ready = bool(market_state.get("mt5_ready", True))

    if stale_price_data or not mt5_ready or spread_ratio >= 2.0:
        regime = "unstable"
    elif "trend" in structure_state:
        regime = "trend"
    elif volatility_ratio <= 0.85:
        regime = "compression"
    elif volatility_ratio >= 1.35:
        regime = "expansion"
    elif "range" in structure_state:
        regime = "range"
    else:
        regime = "unstable"

    confidence_multipliers = {
        "trend": 1.1,
        "range": 0.95,
        "compression": 0.8,
        "expansion": 0.75,
        "unstable": 0.5,
    }
    risk_multipliers = {
        "trend": 1.0,
        "range": 0.85,
        "compression": 0.7,
        "expansion": 0.65,
        "unstable": 0.4,
    }
    base_confidence = float(market_state.get("base_signal_confidence", 0.5))
    base_risk_size = float(market_state.get("base_risk_size", 1.0))
    adjusted_confidence = round(max(0.0, min(1.0, base_confidence * confidence_multipliers[regime])), 4)
    adjusted_risk_size = round(max(0.0, base_risk_size * risk_multipliers[regime]), 4)
    return {
        "regime": regime,
        "base_signal_confidence": base_confidence,
        "adjusted_signal_confidence": adjusted_confidence,
        "base_risk_size": base_risk_size,
        "adjusted_risk_size": adjusted_risk_size,
        "confidence_multiplier": confidence_multipliers[regime],
        "risk_multiplier": risk_multipliers[regime],
    }


def _loss_streak(closed: list[dict[str, Any]]) -> int:
    streak = 0
    for outcome in reversed(closed):
        if str(outcome.get("result", "")).lower() == "loss":
            streak += 1
            continue
        break
    return streak


def _drawdown_points(closed: list[dict[str, Any]]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for outcome in closed:
        cumulative += float(outcome.get("pnl_points", 0.0))
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return round(abs(max_drawdown), 4)


def _build_trade_review(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    regime: str,
) -> dict[str, Any]:
    reviews: list[dict[str, Any]] = []
    failure_counter: dict[str, int] = {}
    for outcome in closed:
        direction = str(outcome.get("direction", "WAIT")).upper()
        reasons = outcome.get("source_reasons", [])
        if not isinstance(reasons, list):
            reasons = []
        default_entry_reason = "unknown"
        if reasons:
            default_entry_reason = str(reasons[0])
        result = str(outcome.get("result", "unknown")).lower()
        pnl_points = float(outcome.get("pnl_points", 0.0))
        if result == "loss":
            failure_cause = str(outcome.get("failure_cause", "execution_failure")).strip() or "execution_failure"
        elif result == "flat":
            failure_cause = "weak_setup"
        else:
            failure_cause = "none"
        if failure_cause != "none":
            failure_counter[failure_cause] = failure_counter.get(failure_cause, 0) + 1
        reviews.append(
            {
                "trade_id": str(outcome.get("trade_id", "")),
                "entry_reason": str(outcome.get("entry_reason", default_entry_reason)),
                "exit_reason": str(outcome.get("exit_reason", result)),
                "regime": str(outcome.get("regime", regime)),
                "setup_type": str(outcome.get("setup_type", direction.lower())),
                "failure_cause": failure_cause,
                "result": result,
                "pnl_points": round(pnl_points, 4),
                "session": str(outcome.get("session", "unknown")),
            }
        )
    repeated_failure_patterns = [
        {"failure_cause": cause, "count": count} for cause, count in sorted(failure_counter.items()) if count >= 2
    ]
    trade_review_dir = memory_root / "trade_review"
    trade_review_dir.mkdir(parents=True, exist_ok=True)
    trade_review_path = trade_review_dir / "trade_reviews.json"
    write_json_atomic(
        trade_review_path,
        {
            "trade_reviews": reviews,
            "repeated_failure_patterns": repeated_failure_patterns,
        },
    )
    return {
        "trade_reviews": reviews,
        "repeated_failure_patterns": repeated_failure_patterns,
        "path": str(trade_review_path),
    }


def _strategy_comparison(
    *,
    autonomous_root: Path,
    closed: list[dict[str, Any]],
    mutation_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if closed:
        current_score = round(
            (
                sum(1.0 for outcome in closed if str(outcome.get("result", "")).lower() == "win")
                - sum(1.0 for outcome in closed if str(outcome.get("result", "")).lower() == "loss")
            )
            / max(1, len(closed)),
            4,
        )
    else:
        current_score = 0.0
    promoted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for candidate in mutation_candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        score = float(candidate.get("mutation_score", 0.0))
        replay_validation = candidate.get("replay_validation", {})
        if not isinstance(replay_validation, dict):
            replay_validation = {}
        replay_passed = bool(replay_validation.get("passed", False))
        if score > current_score and replay_passed:
            promoted.append(
                {
                    "candidate_id": candidate_id,
                    "decision": "promote",
                    "reason": "stronger_than_current_strategy",
                    "replay_validation_required": True,
                    "replay_validation_passed": True,
                }
            )
        else:
            quarantined.append(
                {
                    "candidate_id": candidate_id,
                    "decision": "quarantine",
                    "reason": "weaker_or_unvalidated_strategy_logic",
                    "replay_validation_required": True,
                    "replay_validation_passed": replay_passed,
                }
            )
    comparison = {
        "current_strategy_score": current_score,
        "promoted_strategies": promoted,
        "quarantined_strategies": quarantined,
    }
    strategy_path = autonomous_root / "strategy_comparison.json"
    write_json_atomic(strategy_path, comparison)
    comparison["path"] = str(strategy_path)
    return comparison


def _memory_maintenance(*, autonomous_root: Path, trade_review: dict[str, Any]) -> dict[str, Any]:
    trade_reviews = trade_review.get("trade_reviews", [])
    if not isinstance(trade_reviews, list):
        trade_reviews = []
    retained_reviews = trade_reviews[-120:]
    low_value_pattern_count = sum(1 for review in trade_reviews if str(review.get("result", "")).lower() == "flat")
    high_performance_patterns = [
        review for review in retained_reviews if str(review.get("result", "")).lower() == "win"
    ]
    deleted_stale_artifacts: list[str] = []
    for artifact in autonomous_root.glob("*.json"):
        if artifact.name.endswith(".stale.json"):
            artifact.unlink(missing_ok=True)
            deleted_stale_artifacts.append(str(artifact))
    maintenance = {
        "low_value_patterns_pruned": low_value_pattern_count,
        "history_compression": {
            "before": len(trade_reviews),
            "after": len(retained_reviews),
        },
        "deleted_stale_artifacts": deleted_stale_artifacts,
        "retained_high_performance_patterns": high_performance_patterns,
    }
    maintenance_path = autonomous_root / "memory_maintenance.json"
    write_json_atomic(maintenance_path, maintenance)
    maintenance["path"] = str(maintenance_path)
    return maintenance


def _environment_anomalies(
    *,
    autonomous_root: Path,
    market_state: dict[str, Any],
    closed: list[dict[str, Any]],
) -> dict[str, Any]:
    stale_price_data = bool(market_state.get("stale_price_data", False))
    mt5_readiness_failures = bool(not market_state.get("mt5_ready", True))
    abnormal_spreads = bool(float(market_state.get("spread_ratio", 1.0)) >= 1.8)
    repeated_execution_failures = sum(
        1 for outcome in closed[-5:] if str(outcome.get("failure_cause", "")).lower() in {"execution_failure", "mt5_reject"}
    ) >= 2
    slippage_deterioration = bool(float(market_state.get("slippage_ratio", 1.0)) >= 1.7)
    anomalies = {
        "stale_price_data": stale_price_data,
        "mt5_readiness_failures": mt5_readiness_failures,
        "abnormal_spreads": abnormal_spreads,
        "repeated_execution_failures": repeated_execution_failures,
        "slippage_deterioration": slippage_deterioration,
    }
    trigger_refusal = stale_price_data or mt5_readiness_failures
    trigger_pause = trigger_refusal or abnormal_spreads or repeated_execution_failures or slippage_deterioration
    payload = {
        "anomalies": anomalies,
        "trigger_refusal": trigger_refusal,
        "trigger_pause": trigger_pause,
    }
    path = autonomous_root / "environment_anomalies.json"
    write_json_atomic(path, payload)
    payload["path"] = str(path)
    return payload


def _behavior_adjustment(
    *,
    autonomous_root: Path,
    regime_payload: dict[str, Any],
    closed: list[dict[str, Any]],
    environment_anomalies: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    drawdown_points = _drawdown_points(closed)
    loss_streak = _loss_streak(closed)
    recent_setup_confidence = float(market_state.get("recent_setup_confidence", regime_payload["adjusted_signal_confidence"]))
    repeated_failures = sum(1 for outcome in closed[-5:] if str(outcome.get("result", "")).lower() == "loss")
    bad_regime = regime_payload.get("regime") in {"unstable", "expansion"}
    position_size_multiplier = 1.0
    if drawdown_points >= 2.0:
        position_size_multiplier *= 0.5
    elif drawdown_points >= 1.0:
        position_size_multiplier *= 0.75
    if loss_streak >= 2:
        position_size_multiplier *= 0.8
    refuse_weak_setups = recent_setup_confidence < 0.5
    tighten_execution = repeated_failures >= 2
    trading_enabled = not (bad_regime or environment_anomalies.get("trigger_pause", False))
    payload = {
        "position_size_multiplier": round(max(0.1, position_size_multiplier), 4),
        "drawdown_points": drawdown_points,
        "loss_streak": loss_streak,
        "refuse_weak_setups": refuse_weak_setups,
        "tighten_execution_after_failures": tighten_execution,
        "switch_off_trading_in_bad_regimes": bad_regime,
        "trading_enabled": trading_enabled,
    }
    path = autonomous_root / "behavior_adjustment.json"
    write_json_atomic(path, payload)
    payload["path"] = str(path)
    return payload


def _capital_survival(
    *,
    autonomous_root: Path,
    closed: list[dict[str, Any]],
    environment_anomalies: dict[str, Any],
) -> dict[str, Any]:
    consecutive_losses = _loss_streak(closed)
    drawdown_points = _drawdown_points(closed)
    pause_trading = consecutive_losses >= _PAUSE_LOSS_STREAK or bool(environment_anomalies.get("trigger_pause", False))
    reduce_risk = drawdown_points >= 1.0 or consecutive_losses >= 2
    survival_mode = drawdown_points >= 2.0 or consecutive_losses >= _PAUSE_LOSS_STREAK
    stable_recent_window = closed[-3:]
    stable_conditions = (
        not environment_anomalies.get("trigger_pause", False)
        and consecutive_losses == 0
        and any(str(item.get("result", "")).lower() == "win" for item in stable_recent_window)
    )
    payload = {
        "pause_after_consecutive_losses_n": _PAUSE_LOSS_STREAK,
        "consecutive_losses": consecutive_losses,
        "drawdown_points": drawdown_points,
        "pause_trading": pause_trading,
        "reduce_risk_after_drawdown": reduce_risk,
        "survival_mode": survival_mode,
        "resume_only_after_stable_conditions": stable_conditions,
        "risk_multiplier": 0.5 if survival_mode else 0.7 if reduce_risk else 1.0,
    }
    path = autonomous_root / "capital_survival.json"
    write_json_atomic(path, payload)
    payload["path"] = str(path)
    return payload


def _internal_rankings(
    *,
    autonomous_root: Path,
    trade_review: dict[str, Any],
    feature_contributors: dict[str, float],
) -> dict[str, Any]:
    trade_reviews = trade_review.get("trade_reviews", [])
    if not isinstance(trade_reviews, list):
        trade_reviews = []

    def _performance_by(key: str) -> list[dict[str, Any]]:
        score_map: dict[str, float] = {}
        count_map: dict[str, int] = {}
        for item in trade_reviews:
            label = str(item.get(key, "unknown"))
            score_map[label] = score_map.get(label, 0.0) + float(item.get("pnl_points", 0.0))
            count_map[label] = count_map.get(label, 0) + 1
        return [
            {"name": label, "score": round(score_map[label], 4), "samples": count_map[label]}
            for label in sorted(score_map, key=lambda name: (score_map[name], name), reverse=True)
        ]

    rankings = {
        "setup_performance": _performance_by("setup_type"),
        "session_performance": _performance_by("session"),
        "regime_performance": _performance_by("regime"),
        "detector_contribution": [
            {"name": name, "score": round(float(score), 4)}
            for name, score in sorted(feature_contributors.items(), key=lambda item: (item[1], item[0]), reverse=True)
        ],
    }
    path = autonomous_root / "internal_rankings.json"
    write_json_atomic(path, rankings)
    rankings["path"] = str(path)
    return rankings


def _research_generator(
    *,
    autonomous_root: Path,
    trade_review: dict[str, Any],
    rankings: dict[str, Any],
    strategy_comparison: dict[str, Any],
) -> dict[str, Any]:
    repeated_patterns = trade_review.get("repeated_failure_patterns", [])
    if not isinstance(repeated_patterns, list):
        repeated_patterns = []
    detector_ideas = [
        f"detector_for_{str(item.get('failure_cause', 'unknown')).lower()}" for item in repeated_patterns
    ] or ["detector_for_execution_quality_drift"]

    detector_contribution = rankings.get("detector_contribution", [])
    if not isinstance(detector_contribution, list):
        detector_contribution = []
    top_detectors = [item.get("name", "") for item in detector_contribution[:2] if isinstance(item, dict) and item.get("name")]
    feature_combinations = ["+".join(top_detectors)] if len(top_detectors) >= 2 else ["regime+execution_quality"]

    quarantined = strategy_comparison.get("quarantined_strategies", [])
    if not isinstance(quarantined, list):
        quarantined = []
    mutation_candidates = [
        {"candidate_id": item.get("candidate_id", ""), "source": "strategy_comparison"}
        for item in quarantined
        if isinstance(item, dict)
    ]
    replay_experiments = [
        {
            "experiment_id": f"replay_{index + 1}",
            "candidate_target": candidate.get("candidate_id", ""),
            "sandbox_governance": {
                "sandbox_status": "replay_only",
                "replay_validation_required": True,
                "promotion_allowed": False,
            },
        }
        for index, candidate in enumerate(mutation_candidates[:10])
    ] or [
        {
            "experiment_id": "replay_1",
            "candidate_target": "baseline_mutation",
            "sandbox_governance": {
                "sandbox_status": "replay_only",
                "replay_validation_required": True,
                "promotion_allowed": False,
            },
        }
    ]

    payload = {
        "new_detector_ideas": detector_ideas,
        "new_feature_combinations": feature_combinations,
        "mutation_candidates": mutation_candidates,
        "replay_experiments": replay_experiments,
    }
    path = autonomous_root / "research_generator.json"
    write_json_atomic(path, payload)
    payload["path"] = str(path)
    return payload


def _continuous_survival_loop(
    *,
    autonomous_root: Path,
    behavior_adjustment: dict[str, Any],
    capital_survival: dict[str, Any],
    environment_anomalies: dict[str, Any],
) -> dict[str, Any]:
    pause = (
        bool(environment_anomalies.get("trigger_pause", False))
        or bool(capital_survival.get("pause_trading", False))
        or not bool(behavior_adjustment.get("trading_enabled", True))
    )
    payload = {
        "loop": [
            "trade",
            "review_results",
            "detect_mistakes",
            "adjust_aggression",
            "resume_or_pause_trading",
        ],
        "decision": "pause" if pause else "resume",
        "reasons": {
            "behavior_adjustment": behavior_adjustment,
            "capital_survival": capital_survival,
            "environment_anomalies": environment_anomalies,
        },
    }
    path = autonomous_root / "continuous_survival_loop.json"
    write_json_atomic(path, payload)
    payload["path"] = str(path)
    return payload


def run_autonomous_behavior_layer(
    *,
    memory_root: Path,
    trade_outcomes: list[dict[str, Any]],
    market_state: dict[str, Any] | None = None,
    feature_contributors: dict[str, float] | None = None,
    mutation_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    market_state = market_state if isinstance(market_state, dict) else {}
    feature_contributors = feature_contributors if isinstance(feature_contributors, dict) else {}
    mutation_candidates = mutation_candidates if isinstance(mutation_candidates, list) else []
    closed = _closed_outcomes(trade_outcomes)
    autonomous_root = memory_root / "autonomous_behavior"
    autonomous_root.mkdir(parents=True, exist_ok=True)

    regime_payload = _classify_regime(market_state)
    regime_path = autonomous_root / "market_regime_classifier.json"
    write_json_atomic(regime_path, regime_payload)

    trade_review = _build_trade_review(memory_root=memory_root, closed=closed, regime=str(regime_payload["regime"]))
    strategy_comparison = _strategy_comparison(
        autonomous_root=autonomous_root,
        closed=closed,
        mutation_candidates=mutation_candidates,
    )
    memory_maintenance = _memory_maintenance(autonomous_root=autonomous_root, trade_review=trade_review)
    environment_anomalies = _environment_anomalies(
        autonomous_root=autonomous_root,
        market_state=market_state,
        closed=closed,
    )
    behavior_adjustment = _behavior_adjustment(
        autonomous_root=autonomous_root,
        regime_payload=regime_payload,
        closed=closed,
        environment_anomalies=environment_anomalies,
        market_state=market_state,
    )
    capital_survival = _capital_survival(
        autonomous_root=autonomous_root,
        closed=closed,
        environment_anomalies=environment_anomalies,
    )
    rankings = _internal_rankings(
        autonomous_root=autonomous_root,
        trade_review=trade_review,
        feature_contributors=feature_contributors,
    )
    research = _research_generator(
        autonomous_root=autonomous_root,
        trade_review=trade_review,
        rankings=rankings,
        strategy_comparison=strategy_comparison,
    )
    survival_loop = _continuous_survival_loop(
        autonomous_root=autonomous_root,
        behavior_adjustment=behavior_adjustment,
        capital_survival=capital_survival,
        environment_anomalies=environment_anomalies,
    )

    state_path = autonomous_root / "autonomous_behavior_state.json"
    previous_state = read_json_safe(state_path, default={"history": []})
    if not isinstance(previous_state, dict):
        previous_state = {"history": []}
    history = previous_state.get("history", [])
    if not isinstance(history, list):
        history = []
    snapshot = {
        "regime": regime_payload["regime"],
        "decision": survival_loop["decision"],
        "pause_trading": bool(capital_survival.get("pause_trading", False)),
        "trigger_refusal": bool(environment_anomalies.get("trigger_refusal", False)),
    }
    history.append(snapshot)
    write_json_atomic(state_path, {"history": history[-200:]})

    return {
        "market_regime_classifier": {**regime_payload, "path": str(regime_path)},
        "behavior_adjustment_engine": behavior_adjustment,
        "trade_review_engine": trade_review,
        "strategy_comparison_engine": strategy_comparison,
        "memory_maintenance_engine": memory_maintenance,
        "environment_anomaly_detection": environment_anomalies,
        "capital_survival_engine": capital_survival,
        "internal_ranking_systems": rankings,
        "research_generator": research,
        "continuous_survival_loop": survival_loop,
        "state_path": str(state_path),
    }
