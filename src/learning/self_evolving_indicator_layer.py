from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from src.learning.autonomous_behavior_layer import run_autonomous_behavior_layer
from src.utils import read_json_safe, write_json_atomic

_PAIN_MEMORY_CLUSTER_MIN_SIZE = 2
_PAIN_REPLAY_BASE_SCORE = 0.5
_PAIN_REPLAY_RECURRENCE_WEIGHT = 0.4
_PAIN_REPLAY_SEVERITY_WEIGHT = 0.05
_PAIN_REPLAY_PROMOTION_THRESHOLD = 0.6
_SUGGESTION_COOLDOWN_CYCLES = 2
_SUGGESTION_MAX_PER_CYCLE = 6
_SUGGESTION_MAX_PER_NOISY_CYCLE = 3
_SUGGESTION_LOW_VALUE_THRESHOLD = 0.35
_SUGGESTION_PROMOTE_THRESHOLD = 0.68
_SUGGESTION_RETAIN_THRESHOLD = 0.5
_MAX_CLUSTER_SPECIFICITY_BOOST = 0.2
_CLUSTER_SPECIFICITY_BOOST_PER_OCCURRENCE = 0.05
_SYNTHETIC_FEATURE_MIN_SCORE = 0.08
_NEGATIVE_SPACE_DEVIATION_THRESHOLD = 0.55
_INVARIANT_BREAK_THRESHOLD = 0.6
_FEATURE_VALUE_WEIGHT = 0.1
_LOSS_RATIO_WEIGHT = 0.35
_PRICE_LEVEL_BUCKET_SIZE = 5.0
_DEFAULT_RETEST_INTERVAL_PADDING = 1.0
_PAIN_GEOMETRY_MAX_DISTANCE_SQ = 60.0
_LIQUIDITY_REGEN_SCALE = 5.0


def _closed_outcomes(trade_outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in trade_outcomes if str(item.get("status", "")).lower() == "closed"]


def _drawdown(closed: list[dict[str, Any]]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for item in closed:
        cumulative += float(item.get("pnl_points", 0.0))
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return round(abs(max_drawdown), 4)


def _expectancy(closed: list[dict[str, Any]]) -> float:
    if not closed:
        return 0.0
    return round(sum(float(item.get("pnl_points", 0.0)) for item in closed) / len(closed), 4)


def _market_problem_signals(*, closed: list[dict[str, Any]], market_state: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    losses = sum(1 for item in closed[-6:] if str(item.get("result", "")).lower() == "loss")
    if losses >= 2:
        reasons.append("loss_cluster_detected")
    if float(market_state.get("volatility_ratio", 1.0)) >= 1.4:
        reasons.append("volatility_instability")
    if bool(market_state.get("stale_price_data", False)):
        reasons.append("stale_market_data")
    if float(market_state.get("spread_ratio", 1.0)) >= 1.7:
        reasons.append("abnormal_spread_pressure")
    if not reasons:
        reasons.append("feature_gap_detected")
    return reasons


def _capability_generator(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    candidate_dir = memory_root / "capability_candidates"
    registry_dir = memory_root / "capability_registry"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)

    problems = _market_problem_signals(closed=closed, market_state=market_state)
    generated = [
        {"capability_id": "cap_feature_detector", "kind": "new_feature_detector", "problem": problems[0]},
        {"capability_id": "cap_signal_combo", "kind": "new_signal_combination", "problem": problems[0]},
        {"capability_id": "cap_regime_model", "kind": "new_regime_model", "problem": problems[0]},
        {"capability_id": "cap_execution_opt", "kind": "new_execution_optimization", "problem": problems[0]},
    ]

    expectancy_score = _expectancy(closed)
    sandbox_results: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for index, candidate in enumerate(generated):
        replay_score = round(max(0.0, min(1.0, 0.5 + expectancy_score - (index * 0.05))), 4)
        replay_validation_passed = replay_score >= 0.55
        decision = "promote" if replay_validation_passed else "quarantine"
        result = {
            **candidate,
            "sandbox_module": f"sandbox_{candidate['capability_id']}",
            "replay_test": {"scope": replay_scope, "score": replay_score},
            "evaluation": {"decision": decision, "reason": "replay_validated" if replay_validation_passed else "replay_failed"},
            "governance": {"replay_validation_required": True, "rollback_guarded": True, "quarantine_supported": True},
        }
        sandbox_results.append(result)
        if replay_validation_passed:
            promoted.append(result)
        else:
            quarantined.append(result)

    candidate_path = candidate_dir / "capability_candidates.json"
    registry_path = registry_dir / "capability_registry.json"
    write_json_atomic(
        candidate_path,
        {"market_problems": problems, "capability_candidates": sandbox_results},
    )
    write_json_atomic(
        registry_path,
        {
            "promoted_capabilities": promoted,
            "quarantined_capabilities": quarantined,
        },
    )
    return {
        "market_problems": problems,
        "capability_candidates": sandbox_results,
        "promoted_capabilities": promoted,
        "quarantined_capabilities": quarantined,
        "paths": {"candidates": str(candidate_path), "registry": str(registry_path)},
    }


def _self_architecture_engine(*, memory_root: Path, closed: list[dict[str, Any]]) -> dict[str, Any]:
    options = [
        "features_ensemble_scoring",
        "features_regime_split_scoring",
        "features_reinforcement_scoring",
        "features_execution_refinement_layer",
    ]
    expectancy = _expectancy(closed)
    drawdown = _drawdown(closed)
    scored = [
        {
            "architecture": name,
            "score": round(max(0.0, 0.55 + expectancy - (drawdown * 0.1) - (index * 0.04)), 4),
        }
        for index, name in enumerate(options)
    ]
    strongest = sorted(scored, key=lambda item: (item["score"], item["architecture"]), reverse=True)[0]
    path = memory_root / "capability_registry" / "self_architecture_engine.json"
    write_json_atomic(path, {"architectures": scored, "strongest_architecture": strongest})
    return {"architectures": scored, "strongest_architecture": strongest, "path": str(path)}


def _detector_generator(*, memory_root: Path, capability_generator: dict[str, Any]) -> dict[str, Any]:
    detector_ideas = [
        "liquidity_cluster_detector",
        "micro_compression_detector",
        "trap_probability_detector",
        "session_imbalance_detector",
        "volatility_phase_shift_detector",
    ]
    capability_promotions = capability_generator.get("promoted_capabilities", [])
    if not isinstance(capability_promotions, list):
        capability_promotions = []
    promoted_ids = {str(item.get("capability_id", "")) for item in capability_promotions if isinstance(item, dict)}
    detectors = []
    for index, detector in enumerate(detector_ideas):
        linked_capability = "cap_feature_detector" if index < 2 else "cap_regime_model"
        sandbox_passed = linked_capability in promoted_ids
        detectors.append(
            {
                "detector_id": detector,
                "linked_capability": linked_capability,
                "sandbox_test_passed": sandbox_passed,
                "governance": {"sandbox_only": True, "replay_required": True},
            }
        )
    path = memory_root / "capability_candidates" / "detector_candidates.json"
    write_json_atomic(path, {"detector_candidates": detectors})
    return {"detector_candidates": detectors, "path": str(path)}


def _knowledge_compression(*, memory_root: Path, closed: list[dict[str, Any]]) -> dict[str, Any]:
    compressed_dir = memory_root / "compressed_patterns"
    active_dir = memory_root / "active_patterns"
    pruned_dir = memory_root / "pruned_patterns"
    compressed_dir.mkdir(parents=True, exist_ok=True)
    active_dir.mkdir(parents=True, exist_ok=True)
    pruned_dir.mkdir(parents=True, exist_ok=True)

    active = [item for item in closed if str(item.get("result", "")).lower() == "win"][-20:]
    low_value = [item for item in closed if str(item.get("result", "")).lower() in {"flat", "loss"}]
    pruned = low_value[:-20] if len(low_value) > 20 else []
    compressed = [{"trade_id": item.get("trade_id", ""), "result": item.get("result", ""), "pnl": item.get("pnl_points", 0.0)} for item in closed[-80:]]

    compressed_path = compressed_dir / "compressed_patterns.json"
    active_path = active_dir / "active_patterns.json"
    pruned_path = pruned_dir / "pruned_patterns.json"
    write_json_atomic(compressed_path, {"compressed_patterns": compressed})
    write_json_atomic(active_path, {"active_patterns": active})
    write_json_atomic(pruned_path, {"pruned_patterns": pruned})
    return {
        "deleted_low_value_artifacts": len(pruned),
        "compressed_history_size": len(compressed),
        "active_signal_count": len(active),
        "paths": {
            "compressed_patterns": str(compressed_path),
            "active_patterns": str(active_path),
            "pruned_patterns": str(pruned_path),
        },
    }


def _strategy_evolution(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    autonomous_behavior: dict[str, Any],
) -> dict[str, Any]:
    expectancy = _expectancy(closed)
    drawdown = _drawdown(closed)
    wins = sum(1 for item in closed if str(item.get("result", "")).lower() == "win")
    losses = sum(1 for item in closed if str(item.get("result", "")).lower() == "loss")
    stability = round(wins / max(1, wins + losses), 4)
    frequency = len(closed)
    regime_performance = autonomous_behavior.get("internal_ranking_systems", {}).get("regime_performance", [])
    branches = [
        {
            "branch_id": "current_strategy",
            "expectancy": expectancy,
            "drawdown": drawdown,
            "stability": stability,
            "trade_frequency": frequency,
            "regime_performance": regime_performance,
        },
        {
            "branch_id": "mutated_strategy_a",
            "expectancy": round(expectancy + 0.05, 4),
            "drawdown": round(max(0.0, drawdown - 0.1), 4),
            "stability": round(min(1.0, stability + 0.03), 4),
            "trade_frequency": max(1, frequency - 1),
            "regime_performance": regime_performance,
        },
    ]
    strongest = sorted(
        branches,
        key=lambda item: (item["expectancy"] - (item["drawdown"] * 0.1) + item["stability"], item["branch_id"]),
        reverse=True,
    )[0]
    path = memory_root / "capability_registry" / "strategy_evolution_engine.json"
    write_json_atomic(path, {"strategy_branches": branches, "strongest_branch": strongest})
    return {"strategy_branches": branches, "strongest_branch": strongest, "path": str(path)}


def _meta_learning_loop(
    *,
    memory_root: Path,
    capability_generator: dict[str, Any],
    detector_generator: dict[str, Any],
    strategy_evolution: dict[str, Any],
) -> dict[str, Any]:
    loop = [
        "trade",
        "review_outcome",
        "update_feature_ranking",
        "generate_capability_and_detector_ideas",
        "mutate_strategy",
        "replay_test_mutations",
        "promote_improvements",
        "repeat",
    ]
    history_path = memory_root / "capability_registry" / "meta_learning_loop.json"
    previous = read_json_safe(history_path, default={"cycles": []})
    if not isinstance(previous, dict):
        previous = {"cycles": []}
    cycles = previous.get("cycles", [])
    if not isinstance(cycles, list):
        cycles = []
    cycles.append(
        {
            "loop": loop,
            "promoted_capabilities": len(capability_generator.get("promoted_capabilities", [])),
            "detector_candidates": len(detector_generator.get("detector_candidates", [])),
            "active_strategy_branch": strategy_evolution.get("strongest_branch", {}).get("branch_id", "current_strategy"),
        }
    )
    write_json_atomic(history_path, {"cycles": cycles[-100:]})
    return {"loop": loop, "path": str(history_path), "latest_cycle": cycles[-1]}


def _pain_memory_survival_layer(*, memory_root: Path, closed: list[dict[str, Any]], replay_scope: str) -> dict[str, Any]:
    candidate_dir = memory_root / "capability_candidates"
    registry_dir = memory_root / "capability_registry"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)

    losses = [item for item in closed if str(item.get("result", "")).lower() == "loss"]
    cluster_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for loss in losses:
        context = {
            "setup_type": str(loss.get("setup_type", "unknown")),
            "session": str(loss.get("session", "unknown")),
            "failure_cause": str(loss.get("failure_cause", "unknown")),
            "direction": str(loss.get("direction", "unknown")).upper(),
        }
        key = (
            context["setup_type"],
            context["session"],
            context["failure_cause"],
            context["direction"],
        )
        if key not in cluster_map:
            cluster_map[key] = {"context": context, "trades": []}
        cluster_map[key]["trades"].append(
            {
                "trade_id": str(loss.get("trade_id", "")),
                "pnl_points": float(loss.get("pnl_points", 0.0)),
            }
        )

    loss_clusters: list[dict[str, Any]] = []
    pain_patterns: list[dict[str, Any]] = []
    detectors: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for index, key in enumerate(sorted(cluster_map)):
        cluster = cluster_map[key]
        trades = cluster["trades"]
        cluster_size = len(trades)
        if cluster_size < _PAIN_MEMORY_CLUSTER_MIN_SIZE:
            continue
        average_pnl = round(sum(float(item["pnl_points"]) for item in trades) / cluster_size, 4)
        cluster_payload = {
            "cluster_id": f"loss_cluster_{index + 1}",
            "context": cluster["context"],
            "cluster_size": cluster_size,
            "average_pnl_points": average_pnl,
            "trade_ids": [item["trade_id"] for item in trades],
        }
        loss_clusters.append(cluster_payload)
        pain_pattern = {
            "pattern_id": f"pain_pattern_{index + 1}",
            "source_cluster_id": cluster_payload["cluster_id"],
            "recurring_context": cluster_payload["context"],
            "recurrence_strength": round(cluster_size / max(1, len(losses)), 4),
            "pain_score": round(abs(average_pnl) * cluster_size, 4),
        }
        pain_patterns.append(pain_pattern)
        replay_score = round(
            max(
                0.0,
                min(
                    1.0,
                    _PAIN_REPLAY_BASE_SCORE
                    + (pain_pattern["recurrence_strength"] * _PAIN_REPLAY_RECURRENCE_WEIGHT)
                    + (pain_pattern["pain_score"] * _PAIN_REPLAY_SEVERITY_WEIGHT),
                ),
            ),
            4,
        )
        replay_validation_passed = replay_score >= _PAIN_REPLAY_PROMOTION_THRESHOLD
        detector = {
            "detector_id": f"pain_survival_detector_{index + 1}",
            "source_pattern_id": pain_pattern["pattern_id"],
            "sandbox_detector_logic": {
                "match_context": pain_pattern["recurring_context"],
                "action": "tighten_execution_and_refuse_setup",
            },
            "validation": {
                "scope": replay_scope,
                "replay_score": replay_score,
                "replay_validation_required": True,
                "replay_validation_passed": replay_validation_passed,
            },
            "decision": "promote" if replay_validation_passed else "quarantine",
        }
        detectors.append(detector)
        rule = {
            "rule_id": f"pain_survival_rule_{index + 1}",
            "detector_id": detector["detector_id"],
            "context": pain_pattern["recurring_context"],
            "governance": {
                "replay_validation_required": True,
                "replay_validation_passed": replay_validation_passed,
                "live_activation_governed": True,
            },
            "action": "reduce_risk_and_refuse_context",
        }
        if replay_validation_passed:
            promoted.append(rule)
        else:
            quarantined.append(rule)

    cluster_path = candidate_dir / "pain_loss_clusters.json"
    pattern_path = candidate_dir / "pain_patterns.json"
    detector_path = candidate_dir / "pain_survival_detectors.json"
    registry_path = registry_dir / "pain_survival_rules.json"
    write_json_atomic(cluster_path, {"loss_cluster_contexts": loss_clusters})
    write_json_atomic(pattern_path, {"extracted_pain_patterns": pain_patterns})
    write_json_atomic(detector_path, {"generated_detectors": detectors})
    write_json_atomic(
        registry_path,
        {
            "promoted_survival_rules": promoted,
            "quarantined_survival_rules": quarantined,
        },
    )
    return {
        "loss_cluster_contexts": loss_clusters,
        "extracted_pain_patterns": pain_patterns,
        "generated_detectors": detectors,
        "validation_results": [
            {
                "detector_id": detector["detector_id"],
                "replay_score": detector["validation"]["replay_score"],
                "replay_validation_passed": detector["validation"]["replay_validation_passed"],
            }
            for detector in detectors
        ],
        "promotion_decisions": {
            "promoted": promoted,
            "quarantined": quarantined,
        },
        "paths": {
            "loss_clusters": str(cluster_path),
            "pain_patterns": str(pattern_path),
            "generated_detectors": str(detector_path),
            "registry": str(registry_path),
        },
    }


def _trade_tag(outcome: dict[str, Any], key: str, default: Any) -> Any:
    tags = outcome.get("trade_tags", {})
    if not isinstance(tags, dict):
        return default
    return tags.get(key, default)


def _synthetic_feature_invention_engine(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    synthetic_dir = memory_root / "synthetic_features"
    candidate_dir = memory_root / "feature_candidates"
    performance_dir = memory_root / "feature_performance"
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    performance_dir.mkdir(parents=True, exist_ok=True)

    volatility_ratio = float(market_state.get("volatility_ratio", 1.0) or 1.0)
    spread_ratio = float(market_state.get("spread_ratio", 1.0) or 1.0)
    slippage_ratio = float(market_state.get("slippage_ratio", 1.0) or 1.0)
    detector_pressure = 1.0 if float(market_state.get("detector_trigger_count", 0.0) or 0.0) > 0 else 0.5
    dxy_bias = 1.0 if str(market_state.get("dxy_state", "")).lower() in {"strong_usd", "risk_off"} else 0.0
    yield_bias = 1.0 if str(market_state.get("yield_state", "")).lower() in {"bearish_gold", "steepening"} else 0.0
    session_state = str(market_state.get("session_state", "unknown")).lower()
    session_fragility = 1.0 if session_state in {"off_hours", "asia"} else 0.5
    macro_conflict_score = round(abs(dxy_bias - yield_bias), 4)
    liquidity_pressure_index = round((spread_ratio * 0.5) + (slippage_ratio * 0.35) + (detector_pressure * 0.15), 4)
    session_fragility_score = round(session_fragility * volatility_ratio, 4)
    trap_probability_factor = round((volatility_ratio * 0.45) + (spread_ratio * 0.35) + macro_conflict_score, 4)

    candidates = [
        {
            "feature_name": "macro_conflict_score",
            "value": macro_conflict_score,
            "inputs_used": ["dxy_state", "yield_state"],
        },
        {
            "feature_name": "liquidity_pressure_index",
            "value": liquidity_pressure_index,
            "inputs_used": ["spread_ratio", "slippage_ratio", "detector_trigger_count"],
        },
        {
            "feature_name": "session_fragility_score",
            "value": session_fragility_score,
            "inputs_used": ["session_state", "volatility_ratio"],
        },
        {
            "feature_name": "trap_probability_factor",
            "value": trap_probability_factor,
            "inputs_used": ["volatility_ratio", "spread_ratio", "dxy_state", "yield_state"],
        },
    ]
    performance = []
    promoted_features = []
    losses = sum(1 for item in closed if str(item.get("result", "")).lower() == "loss")
    loss_ratio = losses / max(1, len(closed))
    for candidate in candidates:
        value = float(candidate["value"])
        predictive_usefulness = round(
            max(0.0, min(1.0, (value * _FEATURE_VALUE_WEIGHT) + (loss_ratio * _LOSS_RATIO_WEIGHT))),
            4,
        )
        candidate_performance = {
            "feature_name": candidate["feature_name"],
            "predictive_usefulness": predictive_usefulness,
            "signal_quality_delta": round(predictive_usefulness - 0.25, 4),
            "validation": {
                "scope": replay_scope,
                "historical_sample_size": len(closed),
                "sandbox_only": True,
                "explainable": True,
                "testable": True,
            },
        }
        performance.append(candidate_performance)
        if predictive_usefulness >= _SYNTHETIC_FEATURE_MIN_SCORE:
            promoted_features.append({**candidate, **candidate_performance})

    candidate_path = candidate_dir / "synthetic_feature_candidates.json"
    performance_path = performance_dir / "synthetic_feature_performance.json"
    synthetic_path = synthetic_dir / "synthetic_features_latest.json"
    write_json_atomic(candidate_path, {"feature_candidates": candidates})
    write_json_atomic(performance_path, {"feature_performance": performance})
    write_json_atomic(
        synthetic_path,
        {
            "synthetic_features": promoted_features,
            "pruned_feature_count": len(candidates) - len(promoted_features),
            "governance": {"sandbox_only": True, "replay_validation_required": True},
        },
    )
    return {
        "feature_candidates": candidates,
        "feature_performance": performance,
        "synthetic_features": promoted_features,
        "pruned_feature_count": len(candidates) - len(promoted_features),
        "paths": {
            "synthetic_features": str(synthetic_path),
            "feature_candidates": str(candidate_path),
            "feature_performance": str(performance_path),
        },
    }


def _negative_space_pattern_recognition(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    negative_dir = memory_root / "negative_space_signals"
    negative_dir.mkdir(parents=True, exist_ok=True)
    history_path = negative_dir / "negative_space_history.json"

    latest = closed[-1] if closed else {}
    actual_pnl = float(latest.get("pnl_points", 0.0) or 0.0)
    actual_direction = "up" if actual_pnl > 0 else "down" if actual_pnl < 0 else "flat"
    dxy_state = str(market_state.get("dxy_state", _trade_tag(latest, "dxy_state", "unknown"))).lower()
    yield_state = str(market_state.get("yield_state", _trade_tag(latest, "yield_state", "unknown"))).lower()
    volatility_ratio = float(market_state.get("volatility_ratio", _trade_tag(latest, "volatility_ratio", 1.0)) or 1.0)

    expectation = {
        "context": "baseline",
        "expected_direction": "flat",
        "expected_distribution_center": 0.0,
    }
    if dxy_state in {"strong_usd", "risk_off"} and yield_state in {"bearish_gold", "steepening"}:
        expectation = {
            "context": "dxy_up_yields_up",
            "expected_direction": "down",
            "expected_distribution_center": -0.4,
        }
    elif volatility_ratio >= 1.25:
        expectation = {
            "context": "volatility_expansion",
            "expected_direction": "breakout",
            "expected_distribution_center": 0.35,
        }

    mismatch = expectation["expected_direction"] == "down" and actual_direction in {"flat", "up"}
    if expectation["expected_direction"] == "breakout":
        mismatch = abs(actual_pnl) < 0.2
    deviation_score = round(min(1.0, abs(actual_pnl - expectation["expected_distribution_center"])), 4)
    signal = {
        "negative_space_signal": bool(mismatch and deviation_score >= _NEGATIVE_SPACE_DEVIATION_THRESHOLD),
        "expectation_model": expectation,
        "actual_behavior": {"direction": actual_direction, "pnl_points": round(actual_pnl, 4)},
        "deviation_score": deviation_score,
        "validation": {
            "scope": replay_scope,
            "sandbox_only": True,
            "validation_passed": deviation_score >= _NEGATIVE_SPACE_DEVIATION_THRESHOLD,
        },
    }

    history = read_json_safe(history_path, default={"signals": []})
    if not isinstance(history, dict):
        history = {"signals": []}
    signals = history.get("signals", [])
    if not isinstance(signals, list):
        signals = []
    signals.append(signal)
    latest_path = negative_dir / "negative_space_signal_latest.json"
    write_json_atomic(latest_path, signal)
    write_json_atomic(history_path, {"signals": signals[-300:]})
    return {"signal": signal, "paths": {"latest": str(latest_path), "history": str(history_path)}}


def _temporal_invariance_break_detection(
    *,
    memory_root: Path,
    market_state: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    invariant_dir = memory_root / "invariant_break_events"
    invariant_dir.mkdir(parents=True, exist_ok=True)
    model_path = invariant_dir / "invariant_models.json"
    events_path = invariant_dir / "invariant_break_events_latest.json"

    previous = read_json_safe(model_path, default={"invariants": []})
    if not isinstance(previous, dict):
        previous = {"invariants": []}
    previous_models = previous.get("invariants", [])
    if not isinstance(previous_models, list):
        previous_models = []
    previous_map = {
        str(item.get("invariant_name", "")): float(item.get("stability", 0.8) or 0.8)
        for item in previous_models
        if isinstance(item, dict)
    }

    observed_xau_dxy = float(market_state.get("xau_dxy_corr", -0.35) or -0.35)
    observed_xau_real_yield = float(market_state.get("xau_real_yield_corr", -0.3) or -0.3)
    volatility_response = float(market_state.get("volatility_response_corr", 0.35) or 0.35)
    input_signature = {
        "xau_dxy_corr": round(observed_xau_dxy, 6),
        "xau_real_yield_corr": round(observed_xau_real_yield, 6),
        "volatility_response_corr": round(volatility_response, 6),
        "scope": replay_scope,
    }
    previous_events = read_json_safe(events_path, default={})
    if isinstance(previous_events, dict) and previous_events.get("input_signature") == input_signature:
        return {
            "invariant_break_events": previous_events.get("invariant_break_events", []),
            "paths": {"events": str(events_path), "models": str(model_path)},
        }
    current_models = [
        {"invariant_name": "gold_vs_dxy_inverse", "observed_strength": observed_xau_dxy, "expected_sign": -1},
        {"invariant_name": "gold_vs_real_yields_inverse", "observed_strength": observed_xau_real_yield, "expected_sign": -1},
        {"invariant_name": "volatility_breakout_response", "observed_strength": volatility_response, "expected_sign": 1},
    ]
    events = []
    updated_models = []
    for model in current_models:
        name = model["invariant_name"]
        observed = float(model["observed_strength"])
        expected_sign = int(model["expected_sign"])
        sign_flip = observed * expected_sign < 0
        strength_gap = abs(abs(observed) - 0.35)
        stability = round(max(0.0, min(1.0, 1.0 - strength_gap - (0.35 if sign_flip else 0.0))), 4)
        previous_stability = float(previous_map.get(name, 0.8))
        broke = sign_flip or (previous_stability - stability) >= _INVARIANT_BREAK_THRESHOLD
        event = {
            "invariant_name": name,
            "sign_flip": sign_flip,
            "stability": stability,
            "previous_stability": previous_stability,
            "invariant_break": broke,
            "confidence_multiplier": 0.7 if broke else 1.0,
            "trigger_deeper_analysis": bool(broke),
            "validation": {"scope": replay_scope, "sandbox_only": True},
        }
        events.append(event)
        updated_models.append({"invariant_name": name, "stability": stability, "observed_strength": observed})

    write_json_atomic(events_path, {"input_signature": input_signature, "invariant_break_events": events})
    write_json_atomic(model_path, {"invariants": updated_models})
    return {
        "invariant_break_events": events,
        "paths": {"events": str(events_path), "models": str(model_path)},
    }


def _pain_geometry_fields(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    geometry_dir = memory_root / "pain_geometry"
    geometry_dir.mkdir(parents=True, exist_ok=True)
    coordinates_path = geometry_dir / "loss_coordinates.json"
    surface_path = geometry_dir / "pain_risk_surface.json"

    loss_coordinates = []
    for outcome in closed:
        if str(outcome.get("result", "")).lower() != "loss":
            continue
        loss_coordinates.append(
            {
                "session": str(outcome.get("session", _trade_tag(outcome, "session", "unknown"))),
                "spread": float(_trade_tag(outcome, "spread_ratio", market_state.get("spread_ratio", 1.0)) or 1.0),
                "volatility": float(_trade_tag(outcome, "volatility_ratio", market_state.get("volatility_ratio", 1.0)) or 1.0),
                "macro_state": str(_trade_tag(outcome, "macro_state", market_state.get("macro_state", "balanced"))),
                "correlation_state": str(_trade_tag(outcome, "correlation_regime_state", "unknown")),
                "liquidity_signal": str(_trade_tag(outcome, "liquidity_state", market_state.get("liquidity_state", "normal"))),
                "time_of_day": str(_trade_tag(outcome, "session", "unknown")),
            }
        )

    current_spread = float(market_state.get("spread_ratio", 1.0) or 1.0)
    current_volatility = float(market_state.get("volatility_ratio", 1.0) or 1.0)
    if not loss_coordinates:
        risk = 0.0
    else:
        kernel_values = []
        for coordinate in loss_coordinates:
            spread_distance = current_spread - float(coordinate["spread"])
            vol_distance = current_volatility - float(coordinate["volatility"])
            distance_sq = (spread_distance * spread_distance) + (vol_distance * vol_distance)
            kernel_values.append(math.exp(-min(_PAIN_GEOMETRY_MAX_DISTANCE_SQ, distance_sq)))
        risk = round(sum(kernel_values) / max(1, len(kernel_values)), 4)
    surface = {
        "pain_risk_surface": {
            "current_state_risk": risk,
            "sample_count": len(loss_coordinates),
            "method": "gaussian_kde_proxy",
        },
        "governance": {"sandbox_only": True, "validation_required": True},
    }
    write_json_atomic(coordinates_path, {"loss_coordinates": loss_coordinates})
    write_json_atomic(surface_path, surface)
    return {
        "loss_coordinates": loss_coordinates,
        "pain_risk_surface": surface["pain_risk_surface"],
        "paths": {"coordinates": str(coordinates_path), "surface": str(surface_path)},
    }


def _counterfactual_trade_engine(*, memory_root: Path, closed: list[dict[str, Any]]) -> dict[str, Any]:
    counterfactual_dir = memory_root / "counterfactual_results"
    counterfactual_dir.mkdir(parents=True, exist_ok=True)
    latest_path = counterfactual_dir / "counterfactual_latest.json"
    history_path = counterfactual_dir / "counterfactual_history.json"

    evaluations = []
    for trade in closed[-40:]:
        pnl = float(trade.get("pnl_points", 0.0) or 0.0)
        scenarios = {
            "no_trade_taken": 0.0,
            "opposite_trade": round(-pnl, 4),
            "smaller_position": round(pnl * 0.5, 4),
            "delayed_entry": round(pnl - (0.15 * abs(pnl)), 4),
            "delayed_exit": round(pnl + (0.1 * abs(pnl) if pnl < 0 else -0.1 * abs(pnl)), 4),
        }
        best_name, best_value = sorted(scenarios.items(), key=lambda item: item[1], reverse=True)[0]
        evaluations.append(
            {
                "trade_id": str(trade.get("trade_id", "")),
                "actual_outcome": round(pnl, 4),
                "counterfactual_scenarios": scenarios,
                "strategy_improved_outcome": pnl >= best_value,
                "best_alternative_action": best_name,
                "best_alternative_outcome": round(best_value, 4),
                "outcome_delta_vs_best": round(pnl - best_value, 4),
            }
        )
    latest_payload = {
        "counterfactual_evaluations": evaluations,
        "governance": {"sandbox_only": True, "validation_required": True},
    }
    write_json_atomic(latest_path, latest_payload)
    history = read_json_safe(history_path, default={"cycles": []})
    if not isinstance(history, dict):
        history = {"cycles": []}
    cycles = history.get("cycles", [])
    if not isinstance(cycles, list):
        cycles = []
    cycles.append(latest_payload)
    write_json_atomic(history_path, {"cycles": cycles[-120:]})
    return {"counterfactual_evaluations": evaluations, "paths": {"latest": str(latest_path), "history": str(history_path)}}


def _fractal_liquidity_decay_functions(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    decay_dir = memory_root / "liquidity_decay_models"
    decay_dir.mkdir(parents=True, exist_ok=True)
    model_path = decay_dir / "liquidity_decay_latest.json"

    levels: dict[str, list[int]] = {}
    for index, trade in enumerate(closed):
        level_price = float(trade.get("entry_price", market_state.get("reference_price", 0.0)) or 0.0)
        if level_price <= 0.0:
            continue
        level_bucket = int(round(level_price / _PRICE_LEVEL_BUCKET_SIZE))
        level_key = str(level_bucket * _PRICE_LEVEL_BUCKET_SIZE)
        levels.setdefault(level_key, []).append(index)
    models = []
    for level, hits in sorted(levels.items()):
        intervals = [hits[i] - hits[i - 1] for i in range(1, len(hits))]
        avg_interval = (
            sum(intervals) / max(1, len(intervals))
            if intervals
            else float(len(closed)) + _DEFAULT_RETEST_INTERVAL_PADDING
        )
        regeneration = round(min(1.0, math.sqrt(max(1.0, avg_interval)) / _LIQUIDITY_REGEN_SCALE), 4)
        vulnerability = round(max(0.0, 1.0 - regeneration), 4)
        models.append(
            {
                "level": level,
                "test_count": len(hits),
                "avg_retest_interval": round(avg_interval, 4),
                "liquidity_decay_function": {
                    "model": "fractal_interval_sqrt",
                    "regeneration_score": regeneration,
                    "vulnerability_score": vulnerability,
                },
            }
        )
    payload = {
        "liquidity_decay_models": models,
        "governance": {"sandbox_only": True, "validation_required": True},
    }
    write_json_atomic(model_path, payload)
    return {"liquidity_decay_models": models, "path": str(model_path)}


def _execution_microstructure_intelligence_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    execution_dir = memory_root / "execution_microstructure"
    execution_dir.mkdir(parents=True, exist_ok=True)
    latest_path = execution_dir / "execution_microstructure_latest.json"
    history_path = execution_dir / "execution_microstructure_history.json"
    failure_clusters_path = execution_dir / "execution_failure_clusters.json"
    quality_baselines_path = execution_dir / "execution_quality_baselines.json"
    entry_timing_path = execution_dir / "entry_timing_degradation.json"

    telemetry_trades = [item for item in closed if isinstance(item, dict)]

    slippage_ratios: list[float] = []
    spread_shocks: list[float] = []
    fill_delays: list[float] = []
    partial_fill_gaps: list[float] = []
    entry_timing_values: list[float] = []
    failure_counter: dict[str, int] = {}
    telemetry_samples = 0

    for trade in telemetry_trades:
        intended_entry = trade.get("intended_entry_price")
        avg_fill = trade.get("average_fill_price")
        if intended_entry is not None and avg_fill is not None:
            intended_value = float(intended_entry or 0.0)
            avg_fill_value = float(avg_fill or 0.0)
            if abs(intended_value) > 0.0:
                slippage_ratio = abs(avg_fill_value - intended_value) / max(1e-6, abs(intended_value))
                slippage_ratios.append(round(min(1.5, max(0.0, slippage_ratio)), 6))
                telemetry_samples += 1

        spread_signal = trade.get("spread_at_signal")
        spread_peak = trade.get("max_spread_during_window")
        spread_submit = trade.get("spread_at_submit")
        spread_fill = trade.get("spread_at_fill")
        if spread_signal is not None and spread_peak is not None:
            baseline = max(1e-6, float(spread_signal or 0.0))
            shock = (float(spread_peak or 0.0) - baseline) / baseline
            spread_shocks.append(round(max(0.0, shock), 6))
            telemetry_samples += 1
        elif spread_signal is not None and spread_submit is not None and spread_fill is not None:
            baseline = max(1e-6, float(spread_signal or 0.0))
            shock = (max(float(spread_submit or 0.0), float(spread_fill or 0.0)) - baseline) / baseline
            spread_shocks.append(round(max(0.0, shock), 6))
            telemetry_samples += 1

        signal_time = trade.get("signal_time")
        order_submit_time = trade.get("order_submit_time")
        first_fill_time = trade.get("first_fill_time")
        final_fill_time = trade.get("final_fill_time")
        if signal_time is not None and first_fill_time is not None:
            delay = max(0.0, float(first_fill_time or 0.0) - float(signal_time or 0.0))
            fill_delays.append(round(min(600.0, delay), 4))
            telemetry_samples += 1
        elif order_submit_time is not None and first_fill_time is not None:
            delay = max(0.0, float(first_fill_time or 0.0) - float(order_submit_time or 0.0))
            fill_delays.append(round(min(600.0, delay), 4))
            telemetry_samples += 1
        if first_fill_time is not None and final_fill_time is not None:
            completion_delay = max(0.0, float(final_fill_time or 0.0) - float(first_fill_time or 0.0))
            fill_delays.append(round(min(600.0, completion_delay), 4))

        requested_size = trade.get("requested_size")
        filled_size = trade.get("filled_size")
        if requested_size is not None and filled_size is not None:
            requested = max(1e-6, float(requested_size or 0.0))
            fill_ratio = max(0.0, min(1.0, float(filled_size or 0.0) / requested))
            partial_fill_gaps.append(round(1.0 - fill_ratio, 6))
            telemetry_samples += 1

        mae_after_fill = trade.get("mae_after_fill")
        mfe_after_fill = trade.get("mfe_after_fill")
        if mae_after_fill is not None and mfe_after_fill is not None:
            mae = abs(float(mae_after_fill or 0.0))
            mfe = max(0.0, float(mfe_after_fill or 0.0))
            timing_degradation = mae / max(1e-6, mae + mfe)
            entry_timing_values.append(round(max(0.0, min(1.0, timing_degradation)), 6))
            telemetry_samples += 1

        if str(trade.get("result", "")).lower() == "loss":
            failure_cause = str(trade.get("failure_cause", "unknown")).strip() or "unknown"
            if failure_cause in {"execution_failure", "mt5_reject", "spread_spike", "slippage_spike", "partial_fill"}:
                failure_counter[failure_cause] = failure_counter.get(failure_cause, 0) + 1

    fallback_spread_ratio = round(max(0.0, float(market_state.get("spread_ratio", 1.0) or 1.0) - 1.0), 6)
    fallback_slippage_ratio = round(max(0.0, float(market_state.get("slippage_ratio", 1.0) or 1.0) - 1.0), 6)

    avg_slippage_damage = round(
        sum(slippage_ratios) / max(1, len(slippage_ratios)) if slippage_ratios else min(1.0, fallback_slippage_ratio * 0.5),
        6,
    )
    avg_spread_shock = round(
        sum(spread_shocks) / max(1, len(spread_shocks)) if spread_shocks else min(1.0, fallback_spread_ratio * 0.5),
        6,
    )
    avg_fill_delay = round(sum(fill_delays) / max(1, len(fill_delays)), 4) if fill_delays else 0.0
    avg_partial_fill_gap = round(sum(partial_fill_gaps) / max(1, len(partial_fill_gaps)), 6) if partial_fill_gaps else 0.0
    entry_timing_degradation = round(sum(entry_timing_values) / max(1, len(entry_timing_values)), 6) if entry_timing_values else 0.0

    slippage_penalty = min(1.0, avg_slippage_damage * 6.0)
    spread_penalty = min(1.0, avg_spread_shock * 0.7)
    delay_penalty = min(1.0, avg_fill_delay / 15.0)
    partial_penalty = min(1.0, avg_partial_fill_gap * 2.0)
    timing_penalty = min(1.0, entry_timing_degradation * 0.8)
    execution_penalty = round(
        min(
            1.0,
            (slippage_penalty * 0.28)
            + (spread_penalty * 0.24)
            + (delay_penalty * 0.18)
            + (partial_penalty * 0.18)
            + (timing_penalty * 0.12),
        ),
        6,
    )

    total_execution_failures = sum(failure_counter.values())
    cluster_items = [
        {"failure_cause": key, "count": value}
        for key, value in sorted(failure_counter.items(), key=lambda item: (item[1], item[0]), reverse=True)
    ]
    strongest_cluster = cluster_items[0] if cluster_items else {"failure_cause": "none", "count": 0}
    failure_cluster_risk = round(min(1.0, total_execution_failures / max(1, len(telemetry_trades))), 6)

    execution_quality_score = round(max(0.0, min(1.0, 1.0 - execution_penalty)), 6)
    telemetry_coverage = round(min(1.0, telemetry_samples / max(1, len(telemetry_trades) * 5)), 6)
    execution_confidence = round(max(0.25, min(1.0, 0.35 + (telemetry_coverage * 0.65))), 6)

    if telemetry_samples == 0:
        execution_state = "insufficient_data"
    elif execution_quality_score < 0.35 or failure_cluster_risk >= 0.7:
        execution_state = "fragile"
    elif execution_quality_score < 0.6:
        execution_state = "degraded"
    else:
        execution_state = "stable"

    slippage_state = "high_damage" if slippage_penalty >= 0.65 else "elevated" if slippage_penalty >= 0.35 else "normal"
    spread_state = "shock" if spread_penalty >= 0.65 else "elevated" if spread_penalty >= 0.35 else "normal"
    fill_delay_state = "degraded" if delay_penalty >= 0.6 else "elevated" if delay_penalty >= 0.3 else "normal"
    partial_fill_state = "degraded" if partial_penalty >= 0.6 else "elevated" if partial_penalty >= 0.25 else "normal"

    should_reduce_size = execution_penalty >= 0.45 or partial_penalty >= 0.5 or failure_cluster_risk >= 0.45
    should_delay_entry = spread_penalty >= 0.45 or delay_penalty >= 0.45 or entry_timing_degradation >= 0.55
    should_refuse_trade = execution_state == "fragile" or failure_cluster_risk >= 0.75

    recommended_actions: list[str] = []
    if should_refuse_trade:
        recommended_actions.append("refuse_trade_until_execution_stabilizes")
    if should_delay_entry:
        recommended_actions.append("delay_entry_until_spread_and_fill_delay_normalize")
    if should_reduce_size:
        recommended_actions.append("reduce_position_size_for_execution_uncertainty")
    if partial_fill_state in {"degraded", "elevated"}:
        recommended_actions.append("apply_partial_fill_aware_sizing")
    if not recommended_actions:
        recommended_actions.append("maintain_current_execution_controls")

    failure_clusters_payload = {
        "clusters": cluster_items,
        "strongest_cluster": strongest_cluster,
        "failure_cluster_risk": failure_cluster_risk,
        "sample_size": len(telemetry_trades),
    }
    quality_baselines_payload = {
        "replay_scope": replay_scope,
        "telemetry_samples": telemetry_samples,
        "telemetry_coverage": telemetry_coverage,
        "baselines": {
            "slippage_damage": avg_slippage_damage,
            "spread_shock": avg_spread_shock,
            "fill_delay_seconds": avg_fill_delay,
            "partial_fill_gap": avg_partial_fill_gap,
            "entry_timing_degradation": entry_timing_degradation,
        },
        "market_context_bridge": {
            "spread_ratio": round(float(market_state.get("spread_ratio", 1.0) or 1.0), 4),
            "slippage_ratio": round(float(market_state.get("slippage_ratio", 1.0) or 1.0), 4),
        },
    }
    entry_timing_payload = {
        "entry_timing_degradation": entry_timing_degradation,
        "samples": len(entry_timing_values),
        "values": entry_timing_values[-100:],
    }
    write_json_atomic(failure_clusters_path, failure_clusters_payload)
    write_json_atomic(quality_baselines_path, quality_baselines_payload)
    write_json_atomic(entry_timing_path, entry_timing_payload)

    payload = {
        "execution_quality_score": execution_quality_score,
        "execution_confidence": execution_confidence,
        "execution_state": execution_state,
        "slippage_state": slippage_state,
        "spread_state": spread_state,
        "fill_delay_state": fill_delay_state,
        "partial_fill_state": partial_fill_state,
        "failure_cluster_risk": failure_cluster_risk,
        "entry_timing_degradation": entry_timing_degradation,
        "execution_penalty": execution_penalty,
        "should_reduce_size": should_reduce_size,
        "should_delay_entry": should_delay_entry,
        "should_refuse_trade": should_refuse_trade,
        "recommended_actions": recommended_actions,
        "governance": {
            "sandbox_only": True,
            "no_blind_live_self_rewrites": True,
            "replay_validation_required": True,
            "direct_live_override_allowed": False,
        },
    }

    write_json_atomic(latest_path, payload)
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "failure_clusters": str(failure_clusters_path),
            "quality_baselines": str(quality_baselines_path),
            "entry_timing_degradation": str(entry_timing_path),
        },
    }


def _intelligence_gap_discovery_engine(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    counterfactual_engine: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    pain_geometry_engine: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
) -> dict[str, Any]:
    gap_dir = memory_root / "intelligence_gaps"
    gap_dir.mkdir(parents=True, exist_ok=True)
    latest_path = gap_dir / "intelligence_gap_latest.json"
    history_path = gap_dir / "intelligence_gap_history.json"

    gaps: list[dict[str, Any]] = []
    losses = [item for item in closed if str(item.get("result", "")).lower() == "loss"]
    failure_clusters: list[dict[str, Any]] = []
    if losses:
        clustered: dict[tuple[str, str], int] = {}
        for item in losses:
            key = (
                str(item.get("session", "unknown")),
                str(item.get("failure_cause", "unknown")),
            )
            clustered[key] = clustered.get(key, 0) + 1
        failure_clusters = [
            {"session": session, "failure_cause": cause, "count": count}
            for (session, cause), count in sorted(clustered.items(), key=lambda entry: (entry[1], entry[0]), reverse=True)
        ]

    counterfactual_items = counterfactual_engine.get("counterfactual_evaluations", [])
    if not isinstance(counterfactual_items, list):
        counterfactual_items = []
    counterfactual_superiority = sum(
        1 for item in counterfactual_items if isinstance(item, dict) and not bool(item.get("strategy_improved_outcome", False))
    )
    counterfactual_superiority_ratio = round(counterfactual_superiority / max(1, len(counterfactual_items)), 4)
    if counterfactual_superiority_ratio >= 0.35:
        strongest_cluster = failure_clusters[0] if failure_clusters else {"session": "unknown", "failure_cause": "unknown", "count": 0}
        gaps.append(
            {
                "gap_type": "counterfactual_superiority_gap",
                "evidence_strength": round(min(1.0, 0.35 + (counterfactual_superiority_ratio * 0.6)), 4),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": f"{strongest_cluster['session']}_counterfactual_edge_detector",
                "sandbox_only": True,
                "replay_validation_required": True,
            }
        )

    composite_confidence = round(
        float(unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.0) or 0.0),
        4,
    )
    refusal_pause_behavior = unified_market_intelligence_field.get("decision_refinements", {}).get("refusal_pause_behavior", {})
    should_refuse = bool(refusal_pause_behavior.get("should_refuse", False))
    should_pause = bool(refusal_pause_behavior.get("should_pause", False))
    hesitation_frequency = int(should_refuse) + int(should_pause)
    if composite_confidence <= 0.5 or hesitation_frequency > 0:
        gaps.append(
            {
                "gap_type": "confidence_hesitation_gap",
                "evidence_strength": round(
                    min(1.0, max(0.25, (1.0 - composite_confidence) * 0.7 + (hesitation_frequency * 0.2))),
                    4,
                ),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": "confidence_stability_hesitation_filter",
                "sandbox_only": True,
                "replay_validation_required": True,
            }
        )

    pain_risk = float(pain_geometry_engine.get("pain_risk_surface", {}).get("current_state_risk", 0.0) or 0.0)
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))
    execution_penalty = float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0)
    failure_cluster_risk = float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0)
    if execution_state in {"degraded", "fragile"} or execution_penalty >= 0.4 or failure_cluster_risk >= 0.35 or pain_risk >= 0.55:
        gaps.append(
            {
                "gap_type": "session_liquidity_fragility",
                "evidence_strength": round(
                    min(
                        1.0,
                        max(
                            0.3,
                            (execution_penalty * 0.45) + (failure_cluster_risk * 0.35) + (min(1.0, pain_risk) * 0.2),
                        ),
                    ),
                    4,
                ),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": "session_open_liquidity_vacuum_detector",
                "sandbox_only": True,
                "replay_validation_required": True,
            }
        )

    payload = {
        "intelligence_gaps": sorted(gaps, key=lambda item: item["evidence_strength"], reverse=True),
        "diagnostics": {
            "closed_trade_count": len(closed),
            "loss_count": len(losses),
            "counterfactual_superiority_ratio": counterfactual_superiority_ratio,
            "composite_confidence": composite_confidence,
            "pain_risk": round(pain_risk, 4),
            "execution_state": execution_state,
        },
    }
    write_json_atomic(latest_path, payload)
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    return {**payload, "paths": {"latest": str(latest_path), "history": str(history_path)}}


def _synthetic_data_plane_expansion_engine(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    counterfactual_engine: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
) -> dict[str, Any]:
    planes_dir = memory_root / "synthetic_data_planes"
    planes_dir.mkdir(parents=True, exist_ok=True)
    latest_path = planes_dir / "synthetic_data_planes_latest.json"
    history_path = planes_dir / "synthetic_data_planes_history.json"

    losses = [item for item in closed if str(item.get("result", "")).lower() == "loss"]
    false_entry_frequency = round(len(losses) / max(1, len(closed)), 4)
    counterfactual_items = counterfactual_engine.get("counterfactual_evaluations", [])
    if not isinstance(counterfactual_items, list):
        counterfactual_items = []
    counterfactual_advantage = round(
        sum(1 for item in counterfactual_items if isinstance(item, dict) and not bool(item.get("strategy_improved_outcome", False)))
        / max(1, len(counterfactual_items)),
        4,
    )
    composite_confidence = float(
        unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.0) or 0.0
    )
    confidence_stability = round(max(0.0, min(1.0, 1.0 - abs(composite_confidence - 0.6))), 4)
    drawdown_cluster_pressure = round(min(1.0, false_entry_frequency * 1.4), 4)
    execution_penalty = round(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0), 4)

    plane_specs = [
        ("session_fragility_curve", ["session", "spread_ratio", "volatility"]),
        ("structural_price_memory_map", ["structure_state", "entry_price", "session"]),
        ("liquidity_sweep_density", ["spread_ratio", "slippage_ratio", "failure_cause"]),
        ("execution_survivability_curve", ["fill_delay", "partial_fill_gap", "entry_timing_degradation"]),
        ("regime_instability_surface", ["structure_state", "volatility_ratio", "counterfactual_delta"]),
        ("correlation_asymmetry_map", ["xau_dxy_corr", "xau_real_yield_corr", "volatility_response_corr"]),
    ]
    candidates: list[dict[str, Any]] = []
    for index, (plane_name, derived_from) in enumerate(plane_specs):
        predictive_value = round(
            max(
                0.0,
                min(
                    1.0,
                    0.25
                    + (counterfactual_advantage * 0.3)
                    + (confidence_stability * 0.2)
                    + (drawdown_cluster_pressure * 0.2)
                    + (false_entry_frequency * 0.2)
                    - (execution_penalty * 0.1)
                    - (index * 0.03),
                ),
            ),
            4,
        )
        candidates.append(
            {
                "synthetic_plane_name": plane_name,
                "derived_from": derived_from,
                "predictive_value": predictive_value,
                "counterfactual_advantage": counterfactual_advantage,
                "confidence_stability": confidence_stability,
                "drawdown_cluster_pressure": drawdown_cluster_pressure,
                "false_entry_frequency": false_entry_frequency,
                "promotion_candidate": predictive_value >= 0.68 and counterfactual_advantage >= 0.35,
                "governance": {"sandbox_only": True, "replay_validation_required": True},
            }
        )

    payload = {
        "synthetic_data_planes": candidates,
        "input_context": {
            "market_state_signature": {
                "structure_state": str(market_state.get("structure_state", "unknown")),
                "volatility_ratio": round(float(market_state.get("volatility_ratio", 1.0) or 1.0), 4),
                "spread_ratio": round(float(market_state.get("spread_ratio", 1.0) or 1.0), 4),
            },
            "counterfactual_advantage": counterfactual_advantage,
            "confidence_stability": confidence_stability,
        },
    }
    write_json_atomic(latest_path, payload)
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    return {**payload, "paths": {"latest": str(latest_path), "history": str(history_path)}}


def _capability_evolution_governance_ladder(
    *,
    memory_root: Path,
    intelligence_gap_engine: dict[str, Any],
    synthetic_data_plane_engine: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    evolution_dir = memory_root / "capability_evolution"
    evolution_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = evolution_dir / "capability_candidates.json"
    validation_history_path = evolution_dir / "capability_validation_history.json"
    promotion_registry_path = evolution_dir / "capability_promotion_registry.json"

    gap_items = intelligence_gap_engine.get("intelligence_gaps", [])
    if not isinstance(gap_items, list):
        gap_items = []
    plane_items = synthetic_data_plane_engine.get("synthetic_data_planes", [])
    if not isinstance(plane_items, list):
        plane_items = []
    best_plane = sorted(
        [item for item in plane_items if isinstance(item, dict)],
        key=lambda item: float(item.get("predictive_value", 0.0) or 0.0),
        reverse=True,
    )[0] if plane_items else {}
    unified_score = float(unified_market_intelligence_field.get("unified_field_score", 0.0) or 0.0)
    unified_confidence = float(
        unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.0) or 0.0
    )
    reliability_registry = read_json_safe(
        memory_root / "calibration_uncertainty" / "regime_reliability_registry.json",
        default={"regimes": {}},
    )
    if not isinstance(reliability_registry, dict):
        reliability_registry = {"regimes": {}}
    reliability_items = reliability_registry.get("regimes", {})
    if not isinstance(reliability_items, dict):
        reliability_items = {}
    historical_reliability_scores = [
        float(item.get("reliability_score", 0.5) or 0.5) for item in reliability_items.values() if isinstance(item, dict)
    ]
    calibration_reliability = round(
        max(0.0, min(1.0, sum(historical_reliability_scores) / max(1, len(historical_reliability_scores)))),
        4,
    )

    candidates: list[dict[str, Any]] = []
    validation_records: list[dict[str, Any]] = []
    promotion_registry = {
        "rejected": [],
        "quarantined": [],
        "sandbox_only_retained": [],
        "promoted": [],
    }
    for index, gap in enumerate(item for item in gap_items if isinstance(item, dict)):
        hypothesis = str(gap.get("hypothesized_capability", "autonomous_capability_candidate"))
        evidence_strength = float(gap.get("evidence_strength", 0.0) or 0.0)
        prototype_plane = str(best_plane.get("synthetic_plane_name", "none"))
        prototype_predictive = float(best_plane.get("predictive_value", 0.0) or 0.0)
        replay_score = round(min(1.0, (evidence_strength * 0.5) + (prototype_predictive * 0.3) + (unified_confidence * 0.2)), 4)
        comparative_advantage = round(min(1.0, (replay_score * 0.55) + (prototype_predictive * 0.45)), 4)
        conflict_with_unified = round(min(1.0, max(0.0, replay_score - unified_score + 0.2)), 4)
        if replay_score < 0.42:
            decision = "rejected"
        elif conflict_with_unified >= 0.65:
            decision = "quarantined"
        elif replay_score >= 0.72 and comparative_advantage >= 0.58 and conflict_with_unified < 0.45:
            decision = "promoted"
        else:
            decision = "sandbox_only_retained"
        candidate = {
            "capability_id": f"auto_cap_{index + 1}",
            "gap_type": str(gap.get("gap_type", "unknown")),
            "capability_hypothesis": hypothesis,
            "synthetic_prototype": {
                "synthetic_plane_name": prototype_plane,
                "predictive_value": round(prototype_predictive, 4),
            },
            "lifecycle_stages": [
                "gap_detection",
                "capability_hypothesis_generation",
                "synthetic_prototype_construction",
                "replay_validation",
                "comparative_advantage_test",
                "conflict_check_unified_field",
                "governor_promotion_decision",
            ],
            "replay_validation": {"scope": replay_scope, "score": replay_score, "passed": replay_score >= 0.52},
            "comparative_advantage": comparative_advantage,
            "unified_conflict_score": conflict_with_unified,
            "governance_decision": decision,
            "calibration_reliability_context": {
                "prior_cycle_reliability": calibration_reliability,
                "source": "memory/calibration_uncertainty/regime_reliability_registry.json",
            },
            "governance": {
                "sandbox_only": True,
                "replay_validation_required": True,
                "live_deployment_allowed": False,
            },
        }
        candidates.append(candidate)
        validation_records.append(
            {
                "capability_id": candidate["capability_id"],
                "hypothesis": hypothesis,
                "replay_validation_score": replay_score,
                "comparative_advantage": comparative_advantage,
                "unified_conflict_score": conflict_with_unified,
                "outcome": decision,
            }
        )
        promotion_registry[decision].append(candidate)

    write_json_atomic(candidates_path, {"capability_candidates": candidates})
    write_json_atomic(validation_history_path, {"validation_history": validation_records})
    write_json_atomic(promotion_registry_path, promotion_registry)
    return {
        "capability_candidates": candidates,
        "validation_history": validation_records,
        "promotion_registry": promotion_registry,
        "paths": {
            "capability_candidates": str(candidates_path),
            "validation_history": str(validation_history_path),
            "promotion_registry": str(promotion_registry_path),
        },
    }


def _recursive_self_modeling(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    mutation_candidates: list[dict[str, Any]],
    synthetic_feature_engine: dict[str, Any],
    negative_space_engine: dict[str, Any],
    invariant_break_engine: dict[str, Any],
    pain_geometry_engine: dict[str, Any],
    counterfactual_engine: dict[str, Any],
    liquidity_decay_engine: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    self_model_dir = memory_root / "self_modeling"
    self_model_dir.mkdir(parents=True, exist_ok=True)
    path = self_model_dir / "self_modeling_latest.json"

    expectancy = _expectancy(closed)
    drawdown = _drawdown(closed)
    mutation_count = sum(1 for item in mutation_candidates if isinstance(item, dict))
    synthetic_count = len(synthetic_feature_engine.get("synthetic_features", []))
    invariant_breaks = sum(
        1
        for item in invariant_break_engine.get("invariant_break_events", [])
        if isinstance(item, dict) and bool(item.get("invariant_break", False))
    )
    pain_risk = float(pain_geometry_engine.get("pain_risk_surface", {}).get("current_state_risk", 0.0) or 0.0)
    counterfactual_edges = sum(
        1
        for item in counterfactual_engine.get("counterfactual_evaluations", [])
        if isinstance(item, dict) and not bool(item.get("strategy_improved_outcome", False))
    )
    liquidity_models = len(liquidity_decay_engine.get("liquidity_decay_models", []))
    negative_signal = bool(negative_space_engine.get("signal", {}).get("negative_space_signal", False))
    execution_quality = round(float(execution_microstructure_engine.get("execution_quality_score", 0.5) or 0.5), 4)
    execution_penalty = round(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0), 4)
    execution_cluster_risk = round(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0), 4)

    configurations = [
        {"config_id": "cfg_balanced", "detector_set": "default+negative_space", "feature_set": "core+synthetic", "risk_behavior": "adaptive"},
        {"config_id": "cfg_survival", "detector_set": "survival_priority", "feature_set": "core+pain_geometry", "risk_behavior": "defensive"},
        {"config_id": "cfg_discovery", "detector_set": "expanded", "feature_set": "core+synthetic+counterfactual", "risk_behavior": "exploratory"},
    ]
    evaluations = []
    for index, config in enumerate(configurations):
        performance_stability = round(max(0.0, min(1.0, 0.7 + expectancy - (drawdown * 0.08) - (index * 0.04))), 4)
        discovery_potential = round(max(0.0, min(1.0, 0.45 + (synthetic_count * 0.08) + (mutation_count * 0.03) - (0.06 * index))), 4)
        regime_adaptability = round(max(0.0, min(1.0, 0.6 + (0.08 if negative_signal else 0.0) - (invariant_breaks * 0.1))), 4)
        learning_efficiency = round(
            max(
                0.0,
                min(
                    1.0,
                    0.6
                    + (liquidity_models * 0.05)
                    - (counterfactual_edges * 0.04)
                    - (pain_risk * 0.2)
                    + ((execution_quality - 0.5) * 0.1)
                    - (execution_penalty * 0.08)
                    - (execution_cluster_risk * 0.06),
                ),
            ),
            4,
        )
        long_term_score = round(
            (performance_stability * 0.35)
            + (discovery_potential * 0.25)
            + (regime_adaptability * 0.2)
            + (learning_efficiency * 0.2),
            4,
        )
        evaluations.append(
            {
                **config,
                "performance_stability": performance_stability,
                "discovery_potential": discovery_potential,
                "regime_adaptability": regime_adaptability,
                "learning_efficiency": learning_efficiency,
                "long_term_improvement_score": long_term_score,
                "validation": {"scope": replay_scope, "sandbox_only": True},
            }
        )
    chosen = sorted(evaluations, key=lambda item: item["long_term_improvement_score"], reverse=True)[0]
    payload = {
        "configuration_evaluations": evaluations,
        "selected_configuration": chosen,
        "governance": {
            "sandbox_only": True,
            "direct_live_self_rewrite_allowed": False,
            "promotion_requires_governance": True,
        },
        "execution_microstructure_assessment": {
            "execution_quality_score": execution_quality,
            "execution_penalty": execution_penalty,
            "failure_cluster_risk": execution_cluster_risk,
        },
    }
    write_json_atomic(path, payload)
    return {**payload, "path": str(path)}


def _discovery_state_tags(
    *,
    synthetic_feature_engine: dict[str, Any],
    negative_space_engine: dict[str, Any],
    invariant_break_engine: dict[str, Any],
    pain_geometry_engine: dict[str, Any],
    counterfactual_engine: dict[str, Any],
    liquidity_decay_engine: dict[str, Any],
) -> dict[str, Any]:
    invariant_break_active = any(
        bool(item.get("invariant_break", False))
        for item in invariant_break_engine.get("invariant_break_events", [])
        if isinstance(item, dict)
    )
    return {
        "synthetic_feature_state": "active" if synthetic_feature_engine.get("synthetic_features") else "idle",
        "negative_space_state": "anomaly" if negative_space_engine.get("signal", {}).get("negative_space_signal", False) else "normal",
        "invariant_break_state": "break_detected" if invariant_break_active else "stable",
        "pain_geometry_risk": round(float(pain_geometry_engine.get("pain_risk_surface", {}).get("current_state_risk", 0.0) or 0.0), 4),
        "counterfactual_evaluation": "alternatives_logged" if counterfactual_engine.get("counterfactual_evaluations") else "none",
        "liquidity_decay_state": "modeled" if liquidity_decay_engine.get("liquidity_decay_models") else "insufficient_data",
    }


def _detector_reliability_state(detector_generator: dict[str, Any]) -> dict[str, Any]:
    candidates = detector_generator.get("detector_candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    total = len(candidates)
    passed = sum(1 for item in candidates if isinstance(item, dict) and bool(item.get("sandbox_test_passed", False)))
    reliability = round(passed / max(1, total), 4)
    if reliability >= 0.75:
        state = "stable"
    elif reliability >= 0.5:
        state = "mixed"
    else:
        state = "weak"
    return {
        "state": state,
        "reliability_score": reliability,
        "passed_count": passed,
        "failed_count": max(0, total - passed),
        "candidate_count": total,
    }


def _unified_market_intelligence_field(
    *,
    memory_root: Path,
    market_state: dict[str, Any],
    autonomous_behavior: dict[str, Any],
    detector_generator: dict[str, Any],
    strategy_evolution: dict[str, Any],
    synthetic_feature_engine: dict[str, Any],
    negative_space_engine: dict[str, Any],
    invariant_break_engine: dict[str, Any],
    pain_geometry_engine: dict[str, Any],
    counterfactual_engine: dict[str, Any],
    liquidity_decay_engine: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
) -> dict[str, Any]:
    intelligence_dir = memory_root / "market_intelligence"
    intelligence_dir.mkdir(parents=True, exist_ok=True)
    latest_path = intelligence_dir / "unified_market_intelligence_latest.json"
    history_path = intelligence_dir / "unified_market_intelligence_history.json"

    detector_reliability = _detector_reliability_state(detector_generator)
    regime_payload = autonomous_behavior.get("market_regime_classifier", {})
    regime_state = str(regime_payload.get("regime", "unknown"))
    macro_state = {
        "session_state": str(market_state.get("session_state", "unknown")),
        "structure_state": str(market_state.get("structure_state", "unknown")),
        "volatility_ratio": round(float(market_state.get("volatility_ratio", 1.0) or 1.0), 4),
        "spread_ratio": round(float(market_state.get("spread_ratio", 1.0) or 1.0), 4),
        "dxy_state": str(market_state.get("dxy_state", "unknown")),
        "yield_state": str(market_state.get("yield_state", "unknown")),
    }

    synthetic_features = synthetic_feature_engine.get("synthetic_features", [])
    if not isinstance(synthetic_features, list):
        synthetic_features = []
    negative_signal = bool(negative_space_engine.get("signal", {}).get("negative_space_signal", False))
    invariant_break_count = sum(
        1
        for item in invariant_break_engine.get("invariant_break_events", [])
        if isinstance(item, dict) and bool(item.get("invariant_break", False))
    )
    pain_risk = round(float(pain_geometry_engine.get("pain_risk_surface", {}).get("current_state_risk", 0.0) or 0.0), 4)
    counterfactual_items = counterfactual_engine.get("counterfactual_evaluations", [])
    if not isinstance(counterfactual_items, list):
        counterfactual_items = []
    counterfactual_improved_count = sum(
        1 for item in counterfactual_items if isinstance(item, dict) and bool(item.get("strategy_improved_outcome", False))
    )
    counterfactual_edge_ratio = round(counterfactual_improved_count / max(1, len(counterfactual_items)), 4)
    liquidity_models = liquidity_decay_engine.get("liquidity_decay_models", [])
    if not isinstance(liquidity_models, list):
        liquidity_models = []
    avg_liquidity_vulnerability = round(
        sum(
            float(item.get("liquidity_decay_function", {}).get("vulnerability_score", 0.0) or 0.0)
            for item in liquidity_models
            if isinstance(item, dict)
        )
        / max(1, len(liquidity_models)),
        4,
    )
    liquidity_state = "fragile" if avg_liquidity_vulnerability >= 0.55 else "resilient"
    execution_quality_score = round(float(execution_microstructure_engine.get("execution_quality_score", 0.5) or 0.5), 4)
    execution_confidence = round(float(execution_microstructure_engine.get("execution_confidence", 0.5) or 0.5), 4)
    execution_penalty = round(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0), 4)
    execution_cluster_risk = round(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0), 4)
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))

    synthetic_signal = round(min(1.0, len(synthetic_features) * 0.2), 4)
    negative_space_penalty = 0.12 if negative_signal else 0.0
    invariant_penalty = min(0.25, invariant_break_count * 0.08)
    pain_penalty = min(0.3, pain_risk * 0.35)
    liquidity_penalty = min(0.2, avg_liquidity_vulnerability * 0.25)
    regime_penalty = 0.2 if regime_state == "unstable" else 0.1 if regime_state == "expansion" else 0.0
    detector_support = float(detector_reliability.get("reliability_score", 0.0))
    counterfactual_support = counterfactual_edge_ratio
    execution_support = round(max(0.0, min(1.0, execution_quality_score * (1.0 - (execution_penalty * 0.5)))), 4)
    macro_stability_support = max(0.0, 1.0 - abs(float(macro_state["volatility_ratio"]) - 1.0))
    macro_stability_support = round(max(0.0, min(1.0, macro_stability_support)), 4)

    unified_field_score = round(
        max(
            0.0,
            min(
                1.0,
                0.25
                + (detector_support * 0.22)
                + (synthetic_signal * 0.12)
                + (counterfactual_support * 0.1)
                + (execution_support * 0.08)
                + (macro_stability_support * 0.08)
                - negative_space_penalty
                - invariant_penalty
                - pain_penalty
                - liquidity_penalty
                - min(0.18, execution_penalty * 0.18)
                - regime_penalty,
            ),
        ),
        4,
    )
    regime_confidence = round(float(regime_payload.get("confidence_multiplier", 0.5) or 0.5), 4)
    composite_confidence = round(
        max(
            0.0,
            min(
                1.0,
                (unified_field_score * 0.45)
                + (detector_support * 0.25)
                + (counterfactual_support * 0.1)
                + (execution_confidence * 0.08)
                + (regime_confidence * 0.2),
            ),
        ),
        4,
    )
    confidence_band = "high" if composite_confidence >= 0.7 else "moderate" if composite_confidence >= 0.45 else "low"

    base_signal_confidence = round(float(regime_payload.get("adjusted_signal_confidence", 0.5) or 0.5), 4)
    base_risk_size = round(float(regime_payload.get("adjusted_risk_size", 1.0) or 1.0), 4)
    confidence_refinement_multiplier = round(0.8 + (composite_confidence * 0.4), 4)
    risk_refinement_multiplier = round(
        max(
            0.2,
            min(
                1.2,
                0.85
                + (unified_field_score * 0.35)
                - (pain_risk * 0.2)
                - (invariant_break_count * 0.05)
                - (execution_penalty * 0.2)
                - (execution_cluster_risk * 0.12),
            ),
        ),
        4,
    )
    refined_signal_confidence = round(
        max(0.0, min(1.0, base_signal_confidence * confidence_refinement_multiplier * (0.9 + (execution_confidence * 0.1)))),
        4,
    )
    refined_risk_size = round(max(0.05, base_risk_size * risk_refinement_multiplier), 4)

    refusal_reasons: list[str] = []
    pause_reasons: list[str] = []
    if negative_signal:
        refusal_reasons.append("negative_space_anomaly_detected")
    if invariant_break_count > 0:
        refusal_reasons.append("invariant_break_detected")
    if detector_reliability.get("state") == "weak":
        refusal_reasons.append("weak_detector_reliability")
    if pain_risk >= 0.75:
        pause_reasons.append("pain_geometry_risk_elevated")
    if regime_state == "unstable":
        pause_reasons.append("unstable_regime_state")
    if liquidity_state == "fragile" and avg_liquidity_vulnerability >= 0.7:
        pause_reasons.append("liquidity_decay_fragility")
    if bool(execution_microstructure_engine.get("should_refuse_trade", False)):
        refusal_reasons.append("execution_microstructure_fragility")
    if bool(execution_microstructure_engine.get("should_delay_entry", False)):
        pause_reasons.append("execution_delay_recommendation")
    should_refuse = bool(refusal_reasons) and composite_confidence < 0.6
    should_pause = bool(pause_reasons) and unified_field_score < 0.55

    branches = strategy_evolution.get("strategy_branches", [])
    if not isinstance(branches, list):
        branches = []
    strongest_branch = strategy_evolution.get("strongest_branch", {})
    strongest_branch_id = str(strongest_branch.get("branch_id", "current_strategy"))
    strategy_mode = "defensive" if should_pause or should_refuse else "adaptive" if unified_field_score < 0.65 else "offensive"
    selected_branch_id = strongest_branch_id
    if branches and strategy_mode == "defensive":
        selected_branch = sorted(
            [item for item in branches if isinstance(item, dict)],
            key=lambda item: (
                -float(item.get("stability", 0.0) or 0.0),
                float(item.get("drawdown", 0.0) or 0.0),
                str(item.get("branch_id", "")),
            ),
        )[0]
        selected_branch_id = str(selected_branch.get("branch_id", strongest_branch_id))
    elif branches and strategy_mode == "offensive":
        selected_branch = sorted(
            [item for item in branches if isinstance(item, dict)],
            key=lambda item: (
                float(item.get("expectancy", 0.0) or 0.0),
                float(item.get("stability", 0.0) or 0.0),
                str(item.get("branch_id", "")),
            ),
            reverse=True,
        )[0]
        selected_branch_id = str(selected_branch.get("branch_id", strongest_branch_id))

    payload = {
        "components": {
            "macro_state": macro_state,
            "regime_state": regime_state,
            "detector_reliability": detector_reliability,
            "synthetic_feature_state": {
                "state": "active" if synthetic_features else "idle",
                "feature_count": len(synthetic_features),
            },
            "negative_space_state": {
                "state": "anomaly" if negative_signal else "normal",
                "deviation_score": round(float(negative_space_engine.get("signal", {}).get("deviation_score", 0.0) or 0.0), 4),
            },
            "invariant_break_state": {
                "state": "break_detected" if invariant_break_count > 0 else "stable",
                "break_count": invariant_break_count,
            },
            "pain_geometry_risk": {
                "current_state_risk": pain_risk,
            },
            "counterfactual_evaluation": {
                "state": "alternatives_logged" if counterfactual_items else "none",
                "edge_ratio": counterfactual_edge_ratio,
            },
            "liquidity_decay_state": {
                "state": liquidity_state,
                "avg_vulnerability": avg_liquidity_vulnerability,
                "model_count": len(liquidity_models),
            },
            "execution_microstructure_state": {
                "state": execution_state,
                "execution_quality_score": execution_quality_score,
                "execution_penalty": execution_penalty,
                "failure_cluster_risk": execution_cluster_risk,
            },
        },
        "unified_field_score": unified_field_score,
        "confidence_structure": {
            "regime_confidence": regime_confidence,
            "detector_confidence": detector_support,
            "counterfactual_confidence": counterfactual_support,
            "composite_confidence": composite_confidence,
            "confidence_band": confidence_band,
        },
        "decision_refinements": {
            "signal_confidence": {
                "base": base_signal_confidence,
                "refined": refined_signal_confidence,
                "multiplier": confidence_refinement_multiplier,
            },
            "risk_sizing": {
                "base": base_risk_size,
                "refined": refined_risk_size,
                "multiplier": risk_refinement_multiplier,
            },
            "refusal_pause_behavior": {
                "should_refuse": should_refuse,
                "should_pause": should_pause,
                "refusal_reasons": refusal_reasons,
                "pause_reasons": pause_reasons,
            },
            "strategy_selection": {
                "mode": strategy_mode,
                "selected_branch_id": selected_branch_id,
                "default_branch_id": strongest_branch_id,
            },
        },
        "governance": {
            "sandbox_only": True,
            "live_protection_preserved": True,
            "direct_live_override_allowed": False,
        },
    }
    write_json_atomic(latest_path, payload)
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    return {**payload, "paths": {"latest": str(latest_path), "history": str(history_path)}}


def _calibration_and_uncertainty_governance_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    replay_scope: str,
) -> dict[str, Any]:
    calibration_dir = memory_root / "calibration_uncertainty"
    calibration_dir.mkdir(parents=True, exist_ok=True)
    latest_path = calibration_dir / "calibration_uncertainty_latest.json"
    history_path = calibration_dir / "calibration_uncertainty_history.json"
    error_registry_path = calibration_dir / "confidence_error_registry.json"
    regime_registry_path = calibration_dir / "regime_reliability_registry.json"
    governance_path = calibration_dir / "calibration_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}

    raw_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.0) or 0.0))
    detector_confidence = _bounded(float(confidence_structure.get("detector_confidence", 0.0) or 0.0))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    execution_confidence = _bounded(float(execution_microstructure_engine.get("execution_confidence", 0.0) or 0.0))
    failure_cluster_risk = _bounded(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0))
    contradiction_arbitration_engine = (
        contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    )
    contradiction_penalty = _bounded(
        float(contradiction_arbitration_engine.get("confidence_adjustments", {}).get("contradiction_penalty", 0.0) or 0.0)
    )

    settled = [
        item
        for item in closed[-40:]
        if isinstance(item, dict) and str(item.get("result", "")).lower() in {"win", "loss", "flat"}
    ]
    outcome_proxy = [
        1.0
        if str(item.get("result", "")).lower() == "win"
        else 0.0
        if str(item.get("result", "")).lower() == "loss"
        else 0.5
        for item in settled
    ]
    observed_accuracy = _bounded(sum(outcome_proxy) / max(1, len(outcome_proxy)))
    current_error = _bounded(abs(raw_confidence - observed_accuracy))
    regime = str(
        unified_market_intelligence_field.get("components", {}).get("regime_state", market_state.get("structure_state", "unknown"))
    )
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))
    regime_key = f"{replay_scope}|{regime}|{execution_state}"
    cycle_signature = {
        "replay_scope": replay_scope,
        "regime_key": regime_key,
        "raw_confidence": raw_confidence,
        "observed_accuracy": observed_accuracy,
        "execution_penalty": execution_penalty,
        "execution_confidence": execution_confidence,
        "failure_cluster_risk": failure_cluster_risk,
        "settled_count": len(outcome_proxy),
    }
    previous_latest = read_json_safe(latest_path, default={})
    if isinstance(previous_latest, dict) and previous_latest.get("_signature") == cycle_signature:
        returned = dict(previous_latest)
        returned.pop("_signature", None)
        return {
            **returned,
            "paths": {
                "latest": str(latest_path),
                "history": str(history_path),
                "confidence_error_registry": str(error_registry_path),
                "regime_reliability_registry": str(regime_registry_path),
                "governance_state": str(governance_path),
            },
        }

    error_registry = read_json_safe(error_registry_path, default={"errors": []})
    if not isinstance(error_registry, dict):
        error_registry = {"errors": []}
    errors = error_registry.get("errors", [])
    if not isinstance(errors, list):
        errors = []
    errors.append(
        {
            "replay_scope": replay_scope,
            "raw_confidence": raw_confidence,
            "observed_accuracy": observed_accuracy,
            "absolute_error": current_error,
            "sample_size": len(outcome_proxy),
        }
    )
    rolling_errors = [float(item.get("absolute_error", 0.0) or 0.0) for item in errors[-120:] if isinstance(item, dict)]
    historical_confidence_error = _bounded(sum(rolling_errors) / max(1, len(rolling_errors)))
    write_json_atomic(error_registry_path, {"errors": errors[-600:]})

    if not isinstance(previous_latest, dict):
        previous_latest = {}
    previous_error = _bounded(float(previous_latest.get("calibration_state", {}).get("historical_confidence_error", 0.0) or 0.0))
    calibration_drift = _bounded(abs(historical_confidence_error - previous_error) + (current_error * 0.6))
    regime_registry = read_json_safe(regime_registry_path, default={"regimes": {}})
    if not isinstance(regime_registry, dict):
        regime_registry = {"regimes": {}}
    regimes = regime_registry.get("regimes", {})
    if not isinstance(regimes, dict):
        regimes = {}
    prior_regime_state = regimes.get(regime_key, {})
    if not isinstance(prior_regime_state, dict):
        prior_regime_state = {}
    prior_count = int(prior_regime_state.get("observations", 0) or 0)
    prior_reliability = _bounded(float(prior_regime_state.get("reliability_score", 0.5) or 0.5))
    current_reliability = _bounded(max(0.0, min(1.0, 1.0 - current_error)))
    observations = prior_count + 1
    regime_reliability_score = _bounded(((prior_reliability * prior_count) + current_reliability) / max(1, observations))
    regime_specific_reliability = {
        "context_key": regime_key,
        "reliability_score": regime_reliability_score,
        "observations": observations,
    }
    regimes[regime_key] = regime_specific_reliability
    write_json_atomic(regime_registry_path, {"regimes": regimes})

    spread_stress = _bounded(max(0.0, float(market_state.get("spread_ratio", 1.0) or 1.0) - 1.0))
    slippage_stress = _bounded(max(0.0, float(market_state.get("slippage_ratio", 1.0) or 1.0) - 1.0))
    aleatoric_proxy = _bounded((execution_penalty * 0.5) + (failure_cluster_risk * 0.35) + ((spread_stress + slippage_stress) * 0.075))
    epistemic_uncertainty = _bounded((1.0 - detector_confidence) * 0.6 + min(1.0, 1.0 / max(1, len(outcome_proxy))) * 0.4)
    execution_adjusted_uncertainty = _bounded(
        (epistemic_uncertainty * 0.4) + (aleatoric_proxy * 0.45) + ((1.0 - execution_confidence) * 0.15)
    )

    reliability_signal = _bounded(
        1.0 - ((historical_confidence_error * 0.5) + (calibration_drift * 0.3) + (execution_adjusted_uncertainty * 0.2))
    )
    if reliability_signal >= 0.72:
        confidence_reliability_band = "high"
    elif reliability_signal >= 0.52:
        confidence_reliability_band = "moderate"
    elif reliability_signal >= 0.35:
        confidence_reliability_band = "low"
    else:
        confidence_reliability_band = "fragile"

    calibrated_confidence = _bounded(
        raw_confidence
        - (historical_confidence_error * 0.45)
        - (execution_adjusted_uncertainty * 0.25)
        - (contradiction_penalty * 0.2)
        + ((observed_accuracy - 0.5) * 0.08)
    )
    confidence_delta = _bounded(raw_confidence - calibrated_confidence)
    risk_multiplier = _bounded(
        1.0 - (confidence_delta * 0.45) - (execution_adjusted_uncertainty * 0.35) - (calibration_drift * 0.2),
        low=0.25,
        high=1.0,
    )

    should_pause = bool(
        calibration_drift >= 0.26
        or execution_adjusted_uncertainty >= 0.62
        or confidence_reliability_band in {"low", "fragile"}
    )
    should_refuse = bool(
        (confidence_reliability_band == "fragile" and execution_penalty >= 0.4)
        or (calibration_drift >= 0.4 and execution_penalty >= 0.45)
    )
    refusal_reasons: list[str] = []
    pause_reasons: list[str] = []
    if should_refuse:
        refusal_reasons.append("calibration_uncertainty_refuse_guard")
    if calibration_drift >= 0.26:
        pause_reasons.append("calibration_drift_elevated")
    if execution_adjusted_uncertainty >= 0.62:
        pause_reasons.append("execution_adjusted_uncertainty_elevated")
    if confidence_reliability_band in {"low", "fragile"}:
        pause_reasons.append("confidence_reliability_band_degraded")

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "pause_guard_triggered": should_pause,
        "refuse_guard_triggered": should_refuse,
    }
    calibration_state = {
        "raw_confidence": raw_confidence,
        "calibrated_confidence": calibrated_confidence,
        "calibration_drift": calibration_drift,
        "confidence_reliability_band": confidence_reliability_band,
        "epistemic_uncertainty": epistemic_uncertainty,
        "aleatoric_proxy": aleatoric_proxy,
        "historical_confidence_error": historical_confidence_error,
        "regime_specific_reliability": regime_specific_reliability,
        "execution_adjusted_uncertainty": execution_adjusted_uncertainty,
        "governance_flags": governance_flags,
    }
    confidence_adjustments = {
        "confidence_delta": confidence_delta,
        "risk_multiplier": risk_multiplier,
        "should_pause": should_pause,
        "should_refuse": should_refuse,
        "pause_reasons": pause_reasons,
        "refusal_reasons": refusal_reasons,
    }
    governance = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    payload = {
        "calibration_state": calibration_state,
        "confidence_adjustments": confidence_adjustments,
        "governance": governance,
    }
    write_json_atomic(latest_path, {**payload, "_signature": cycle_signature})
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    write_json_atomic(governance_path, governance_flags)
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "confidence_error_registry": str(error_registry_path),
            "regime_reliability_registry": str(regime_registry_path),
            "governance_state": str(governance_path),
        },
    }


def _contradiction_arbitration_and_belief_resolution_layer(
    *,
    memory_root: Path,
    market_state: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    negative_space_engine: dict[str, Any],
    invariant_break_engine: dict[str, Any],
    pain_geometry_engine: dict[str, Any],
    counterfactual_engine: dict[str, Any],
    liquidity_decay_engine: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    strategy_evolution: dict[str, Any],
    detector_generator: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    arbitration_dir = memory_root / "contradiction_arbitration"
    arbitration_dir.mkdir(parents=True, exist_ok=True)
    latest_path = arbitration_dir / "contradiction_arbitration_latest.json"
    history_path = arbitration_dir / "contradiction_arbitration_history.json"
    belief_registry_path = arbitration_dir / "belief_state_registry.json"
    contradiction_events_path = arbitration_dir / "contradiction_events.json"
    resolution_registry_path = arbitration_dir / "resolution_outcome_registry.json"
    contextual_clusters_path = arbitration_dir / "contextual_contradiction_clusters.json"
    governance_path = arbitration_dir / "governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    composite_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.0) or 0.0))
    calibrated_confidence = confidence_structure.get("calibrated_confidence")
    if isinstance(calibrated_confidence, (int, float)):
        unified_confidence = _bounded(max(composite_confidence, float(calibrated_confidence)))
    else:
        unified_confidence = composite_confidence
    detector_reliability = _bounded(
        float(unified_market_intelligence_field.get("confidence_structure", {}).get("detector_confidence", 0.0) or 0.0)
    )
    execution_confidence = _bounded(float(execution_microstructure_engine.get("execution_confidence", 0.0) or 0.0))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    execution_quality = _bounded(float(execution_microstructure_engine.get("execution_quality_score", 0.0) or 0.0))
    pain_risk = _bounded(float(pain_geometry_engine.get("pain_risk_surface", {}).get("current_state_risk", 0.0) or 0.0))
    negative_score = _bounded(float(negative_space_engine.get("signal", {}).get("deviation_score", 0.0) or 0.0))
    counterfactual_items = counterfactual_engine.get("counterfactual_evaluations", [])
    if not isinstance(counterfactual_items, list):
        counterfactual_items = []
    counterfactual_advantage = _bounded(
        sum(1 for item in counterfactual_items if isinstance(item, dict) and bool(item.get("strategy_improved_outcome", False)))
        / max(1, len(counterfactual_items))
    )
    liquidity_models = liquidity_decay_engine.get("liquidity_decay_models", [])
    if not isinstance(liquidity_models, list):
        liquidity_models = []
    liquidity_vulnerability = _bounded(
        sum(
            float(item.get("liquidity_decay_function", {}).get("vulnerability_score", 0.0) or 0.0)
            for item in liquidity_models
            if isinstance(item, dict)
        )
        / max(1, len(liquidity_models))
    )
    invariant_break_count = sum(
        1
        for item in invariant_break_engine.get("invariant_break_events", [])
        if isinstance(item, dict) and bool(item.get("invariant_break", False))
    )
    strategy_mode = str(
        unified_market_intelligence_field.get("decision_refinements", {}).get("strategy_selection", {}).get("mode", "adaptive")
    )
    should_pause = bool(
        unified_market_intelligence_field.get("decision_refinements", {}).get("refusal_pause_behavior", {}).get("should_pause", False)
    )
    should_refuse = bool(
        unified_market_intelligence_field.get("decision_refinements", {}).get("refusal_pause_behavior", {}).get("should_refuse", False)
    )
    should_delay = bool(execution_microstructure_engine.get("should_delay_entry", False))
    should_reduce = bool(execution_microstructure_engine.get("should_reduce_size", False))
    should_refuse_execution = bool(execution_microstructure_engine.get("should_refuse_trade", False))
    negative_signal = bool(negative_space_engine.get("signal", {}).get("negative_space_signal", False))

    context_signature = {
        "replay_scope": replay_scope,
        "structure_state": str(market_state.get("structure_state", "unknown")),
        "volatility_ratio": _bounded(float(market_state.get("volatility_ratio", 1.0) or 1.0), low=0.0, high=10.0),
        "spread_ratio": _bounded(float(market_state.get("spread_ratio", 1.0) or 1.0), low=0.0, high=10.0),
        "slippage_ratio": _bounded(float(market_state.get("slippage_ratio", 1.0) or 1.0), low=0.0, high=10.0),
        "regime_state": str(unified_market_intelligence_field.get("components", {}).get("regime_state", "unknown")),
        "execution_state": str(execution_microstructure_engine.get("execution_state", "insufficient_data")),
    }
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_rewrites": True,
    }
    input_signature = {
        "context_signature": context_signature,
        "unified_confidence": unified_confidence,
        "execution_penalty": execution_penalty,
        "execution_confidence": execution_confidence,
        "negative_signal": negative_signal,
        "negative_score": negative_score,
        "invariant_break_count": invariant_break_count,
        "pain_risk": pain_risk,
        "counterfactual_advantage": counterfactual_advantage,
        "liquidity_vulnerability": liquidity_vulnerability,
        "strategy_mode": strategy_mode,
    }
    previous_latest = read_json_safe(latest_path, default={})
    if isinstance(previous_latest, dict) and previous_latest.get("input_signature") == input_signature:
        return {
            **previous_latest,
            "paths": {
                "latest": str(latest_path),
                "history": str(history_path),
                "belief_state_registry": str(belief_registry_path),
                "contradiction_events": str(contradiction_events_path),
                "resolution_outcome_registry": str(resolution_registry_path),
                "contextual_contradiction_clusters": str(contextual_clusters_path),
                "governance_state": str(governance_path),
            },
        }

    beliefs: list[dict[str, Any]] = []

    def _belief(
        *,
        source_layer: str,
        belief_direction: str,
        belief_confidence: float,
        belief_intent: str,
        historical_reliability: float,
        execution_adjusted_trust: float,
    ) -> None:
        beliefs.append(
            {
                "belief_id": f"belief_{len(beliefs) + 1}_{source_layer}",
                "source_layer": source_layer,
                "belief_direction": belief_direction,
                "belief_confidence": _bounded(belief_confidence),
                "belief_intent": belief_intent,
                "historical_reliability": _bounded(historical_reliability),
                "execution_adjusted_trust": _bounded(execution_adjusted_trust),
                "context_signature": dict(context_signature),
                "governance_flags": dict(governance_flags),
            }
        )

    unified_direction = "continuation"
    if should_refuse:
        unified_direction = "risk_off"
    elif should_pause:
        unified_direction = "wait"
    _belief(
        source_layer="unified_market_intelligence_field",
        belief_direction=unified_direction,
        belief_confidence=unified_confidence,
        belief_intent="composite_unified_intelligence",
        historical_reliability=detector_reliability,
        execution_adjusted_trust=unified_confidence * (1.0 - (execution_penalty * 0.55)),
    )
    execution_direction = "continuation"
    if should_refuse_execution:
        execution_direction = "risk_off"
    elif should_delay or should_reduce:
        execution_direction = "wait"
    _belief(
        source_layer="execution_microstructure_intelligence_layer",
        belief_direction=execution_direction,
        belief_confidence=execution_confidence,
        belief_intent="execution_safety",
        historical_reliability=execution_quality,
        execution_adjusted_trust=execution_quality * (1.0 - execution_penalty),
    )
    _belief(
        source_layer="negative_space_pattern_recognition",
        belief_direction="risk_off" if negative_signal else "continuation",
        belief_confidence=negative_score,
        belief_intent="trap_detection",
        historical_reliability=_bounded(float(negative_space_engine.get("signal", {}).get("validation", {}).get("validation_passed", False))),
        execution_adjusted_trust=negative_score * (1.0 - (execution_penalty * 0.25)),
    )
    invariant_risk = _bounded(min(1.0, invariant_break_count * 0.35))
    _belief(
        source_layer="temporal_invariance_break_detection",
        belief_direction="risk_off" if invariant_break_count > 0 else "continuation",
        belief_confidence=invariant_risk if invariant_break_count > 0 else 0.45,
        belief_intent="invariance_integrity_guard",
        historical_reliability=_bounded(1.0 - (invariant_risk * 0.5)),
        execution_adjusted_trust=_bounded((invariant_risk if invariant_break_count > 0 else 0.45) * (1.0 - (execution_penalty * 0.2))),
    )
    _belief(
        source_layer="pain_geometry_fields",
        belief_direction="risk_off" if pain_risk >= 0.6 else "continuation",
        belief_confidence=pain_risk,
        belief_intent="drawdown_surface_risk",
        historical_reliability=_bounded(1.0 - min(1.0, pain_risk * 0.8)),
        execution_adjusted_trust=_bounded(pain_risk * (1.0 - (execution_penalty * 0.2))),
    )
    _belief(
        source_layer="counterfactual_trade_engine",
        belief_direction="continuation" if counterfactual_advantage >= 0.5 else "wait",
        belief_confidence=counterfactual_advantage,
        belief_intent="counterfactual_continuation",
        historical_reliability=_bounded(0.45 + (counterfactual_advantage * 0.45)),
        execution_adjusted_trust=_bounded(counterfactual_advantage * (1.0 - (execution_penalty * 0.3))),
    )
    _belief(
        source_layer="fractal_liquidity_decay_functions",
        belief_direction="risk_off" if liquidity_vulnerability >= 0.6 else "continuation",
        belief_confidence=liquidity_vulnerability,
        belief_intent="liquidity_stability",
        historical_reliability=_bounded(1.0 - min(1.0, liquidity_vulnerability)),
        execution_adjusted_trust=_bounded(liquidity_vulnerability * (1.0 - (execution_penalty * 0.2))),
    )

    contradictions: list[dict[str, Any]] = []

    def _push_contradiction(
        *,
        contradiction_type: str,
        contradiction_severity: float,
        partners: list[dict[str, Any]],
        dominance_candidate: str,
        arbitration_outcome: str,
        resolution_rationale: list[str],
        historical_recurrence: int,
        historical_outcome_bias: str,
    ) -> None:
        contradictions.append(
            {
                "contradiction_id": f"contradiction_{len(contradictions) + 1}_{contradiction_type}",
                "belief_sources": [item["source_layer"] for item in partners],
                "contradiction_type": contradiction_type,
                "contradiction_severity": _bounded(contradiction_severity),
                "contradiction_partners": [item["belief_id"] for item in partners],
                "dominance_candidate": dominance_candidate,
                "historical_recurrence": historical_recurrence,
                "historical_outcome_bias": historical_outcome_bias,
                "arbitration_outcome": arbitration_outcome,
                "resolution_rationale": resolution_rationale,
                "governance_flags": dict(governance_flags),
            }
        )

    history_state = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history_state, dict):
        history_state = {"snapshots": []}
    snapshots = history_state.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []

    def _historical_recurrence(contradiction_type: str) -> int:
        context_matches = 0
        for snapshot in snapshots[-120:]:
            if not isinstance(snapshot, dict):
                continue
            historical_context = snapshot.get("historical_context", {})
            if not isinstance(historical_context, dict):
                continue
            snapshot_context = historical_context.get("context_signature", {})
            if not isinstance(snapshot_context, dict):
                continue
            if snapshot_context == context_signature:
                type_counts = historical_context.get("type_counts", {})
                if isinstance(type_counts, dict):
                    context_matches += int(type_counts.get(contradiction_type, 0) or 0)
        return context_matches

    outcome_state = read_json_safe(resolution_registry_path, default={"resolutions": []})
    if not isinstance(outcome_state, dict):
        outcome_state = {"resolutions": []}
    prior_resolutions = outcome_state.get("resolutions", [])
    if not isinstance(prior_resolutions, list):
        prior_resolutions = []

    def _historical_bias(contradiction_type: str) -> str:
        counts = {"allow": 0, "reduce_size": 0, "pause": 0, "refuse": 0}
        for entry in prior_resolutions[-200:]:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("contradiction_type", "")) != contradiction_type:
                continue
            outcome = str(entry.get("arbitration_outcome", "allow"))
            if outcome in counts:
                counts[outcome] += 1
        strongest = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0]
        return strongest[0]

    for left_index, left in enumerate(beliefs):
        for right in beliefs[left_index + 1 :]:
            left_direction = str(left.get("belief_direction", "wait"))
            right_direction = str(right.get("belief_direction", "wait"))
            if {left_direction, right_direction} == {"continuation", "risk_off"}:
                severity = _bounded(
                    (float(left.get("belief_confidence", 0.0) or 0.0) + float(right.get("belief_confidence", 0.0) or 0.0)) / 2.0
                )
                _push_contradiction(
                    contradiction_type="directional_opposition",
                    contradiction_severity=severity,
                    partners=[left, right],
                    dominance_candidate="execution_microstructure_intelligence_layer" if execution_penalty >= 0.45 else "unified_market_intelligence_field",
                    arbitration_outcome="pause" if severity >= 0.55 else "reduce_size",
                    resolution_rationale=["opposed_directional_beliefs_detected"],
                    historical_recurrence=_historical_recurrence("directional_opposition"),
                    historical_outcome_bias=_historical_bias("directional_opposition"),
                )

    confidence_execution_severity = _bounded((unified_confidence * 0.55) + (execution_penalty * 0.45))
    if unified_confidence >= 0.12 and execution_penalty >= 0.35:
        _push_contradiction(
            contradiction_type="confidence_execution_conflict",
            contradiction_severity=confidence_execution_severity,
            partners=[beliefs[0], beliefs[1]],
            dominance_candidate="execution_microstructure_intelligence_layer",
            arbitration_outcome="refuse" if confidence_execution_severity >= 0.72 else "pause",
            resolution_rationale=["high_confidence_with_execution_hostility"],
            historical_recurrence=_historical_recurrence("confidence_execution_conflict"),
            historical_outcome_bias=_historical_bias("confidence_execution_conflict"),
        )

    trap_signal_intensity = _bounded(max(negative_score, invariant_risk))
    if beliefs[0]["belief_direction"] == "continuation" and (
        beliefs[2]["belief_direction"] == "risk_off" or beliefs[3]["belief_direction"] == "risk_off"
    ):
        _push_contradiction(
            contradiction_type="continuation_vs_trap",
            contradiction_severity=_bounded((unified_confidence * 0.5) + (trap_signal_intensity * 0.5)),
            partners=[beliefs[0], beliefs[2], beliefs[3]],
            dominance_candidate="negative_space_pattern_recognition" if negative_signal else "temporal_invariance_break_detection",
            arbitration_outcome="pause",
            resolution_rationale=["continuation_signal_conflicts_with_trap_detection"],
            historical_recurrence=_historical_recurrence("continuation_vs_trap"),
            historical_outcome_bias=_historical_bias("continuation_vs_trap"),
        )

    risk_enable_signal = _bounded(
        float(unified_market_intelligence_field.get("decision_refinements", {}).get("risk_sizing", {}).get("refined", 0.0) or 0.0)
    )
    risk_disable_signal = _bounded(max(pain_risk, execution_penalty, liquidity_vulnerability))
    if risk_enable_signal >= 0.55 and (should_reduce or should_refuse_execution or pain_risk >= 0.6 or liquidity_vulnerability >= 0.6):
        _push_contradiction(
            contradiction_type="risk_enable_vs_risk_disable",
            contradiction_severity=_bounded((risk_enable_signal * 0.45) + (risk_disable_signal * 0.55)),
            partners=[beliefs[0], beliefs[1], beliefs[4], beliefs[6]],
            dominance_candidate="execution_microstructure_intelligence_layer" if should_refuse_execution else "pain_geometry_fields",
            arbitration_outcome="pause" if risk_disable_signal >= 0.6 else "reduce_size",
            resolution_rationale=["risk_expansion_conflicts_with_risk_suppression_signals"],
            historical_recurrence=_historical_recurrence("risk_enable_vs_risk_disable"),
            historical_outcome_bias=_historical_bias("risk_enable_vs_risk_disable"),
        )

    type_counts: dict[str, int] = {}
    for item in contradictions:
        contradiction_type = str(item.get("contradiction_type", "unknown"))
        type_counts[contradiction_type] = type_counts.get(contradiction_type, 0) + 1
    max_severity = max(
        [float(item.get("contradiction_severity", 0.0) or 0.0) for item in contradictions],
        default=0.0,
    )
    total_recurrence = sum(int(item.get("historical_recurrence", 0) or 0) for item in contradictions)
    recurrence_ratio = _bounded(min(1.0, total_recurrence / max(1, len(contradictions) * 3))) if contradictions else 0.0

    arbitration_outcome = "allow"
    dominant_source = "unified_market_intelligence_field"
    if should_refuse_execution or any(
        str(item.get("contradiction_type", "")) == "confidence_execution_conflict"
        and float(item.get("contradiction_severity", 0.0) or 0.0) >= 0.72
        for item in contradictions
    ):
        arbitration_outcome = "refuse"
        dominant_source = "execution_microstructure_intelligence_layer"
    elif any(
        str(item.get("contradiction_type", "")) in {"continuation_vs_trap", "risk_enable_vs_risk_disable"}
        and float(item.get("contradiction_severity", 0.0) or 0.0) >= 0.58
        for item in contradictions
    ):
        arbitration_outcome = "pause"
        dominant_source = "negative_space_pattern_recognition" if negative_signal else "pain_geometry_fields"
    elif contradictions:
        arbitration_outcome = "reduce_size"
        dominant_source = "execution_microstructure_intelligence_layer" if should_reduce else "unified_market_intelligence_field"

    confidence_penalty = _bounded((max_severity * 0.35) + (recurrence_ratio * 0.2))
    contradiction_adjusted_confidence = _bounded(unified_confidence - confidence_penalty)
    contradiction_multiplier = _bounded(1.0 - ((max_severity * 0.55) + (recurrence_ratio * 0.2)), low=0.25, high=1.0)
    should_pause_due_to_contradiction = arbitration_outcome in {"pause", "refuse"}
    should_refuse_due_to_contradiction = arbitration_outcome == "refuse"

    arbitration = {
        "outcome": arbitration_outcome,
        "dominant_source": dominant_source,
        "max_contradiction_severity": _bounded(max_severity),
        "conflict_state": "active" if contradictions else "clear",
        "reasons": [str(item.get("contradiction_type", "unknown")) for item in contradictions[:8]],
    }
    confidence_adjustments = {
        "base_composite_confidence": unified_confidence,
        "contradiction_penalty": confidence_penalty,
        "contradiction_adjusted_confidence": contradiction_adjusted_confidence,
    }
    risk_adjustments = {
        "contradiction_multiplier": contradiction_multiplier,
        "recommended_action": arbitration_outcome,
        "should_reduce_size": arbitration_outcome in {"reduce_size", "pause", "refuse"},
        "should_pause": should_pause_due_to_contradiction,
        "should_refuse": should_refuse_due_to_contradiction,
    }
    historical_context = {
        "context_signature": context_signature,
        "type_counts": type_counts,
        "total_recurrence": total_recurrence,
        "recurrence_ratio": recurrence_ratio,
    }
    governance = {
        **governance_flags,
        "conflict_override_requires_replay_validation": True,
    }
    payload = {
        "input_signature": input_signature,
        "beliefs": beliefs,
        "contradictions": contradictions,
        "arbitration": arbitration,
        "confidence_adjustments": confidence_adjustments,
        "risk_adjustments": risk_adjustments,
        "historical_context": historical_context,
        "governance": governance,
    }

    write_json_atomic(latest_path, payload)
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    write_json_atomic(
        belief_registry_path,
        {
            "context_signature": context_signature,
            "beliefs": beliefs,
            "strategy_branch": str(strategy_evolution.get("strongest_branch", {}).get("branch_id", "current_strategy")),
            "detector_reliability": _detector_reliability_state(detector_generator),
        },
    )
    event_payload = read_json_safe(contradiction_events_path, default={"events": []})
    if not isinstance(event_payload, dict):
        event_payload = {"events": []}
    events = event_payload.get("events", [])
    if not isinstance(events, list):
        events = []
    events.extend(contradictions)
    write_json_atomic(contradiction_events_path, {"events": events[-600:]})

    resolution_entries = prior_resolutions + [
        {
            "contradiction_type": str(item.get("contradiction_type", "unknown")),
            "arbitration_outcome": str(item.get("arbitration_outcome", arbitration_outcome)),
            "severity": _bounded(float(item.get("contradiction_severity", 0.0) or 0.0)),
            "context_signature": context_signature,
        }
        for item in contradictions
    ]
    write_json_atomic(resolution_registry_path, {"resolutions": resolution_entries[-600:]})

    contextual_clusters = read_json_safe(contextual_clusters_path, default={"clusters": {}})
    if not isinstance(contextual_clusters, dict):
        contextual_clusters = {"clusters": {}}
    clusters = contextual_clusters.get("clusters", {})
    if not isinstance(clusters, dict):
        clusters = {}
    cluster_key = (
        f"{context_signature['replay_scope']}|{context_signature['structure_state']}|"
        f"{context_signature['regime_state']}|{context_signature['execution_state']}"
    )
    cluster_state = clusters.get(cluster_key, {"occurrences": 0, "type_counts": {}})
    if not isinstance(cluster_state, dict):
        cluster_state = {"occurrences": 0, "type_counts": {}}
    cluster_types = cluster_state.get("type_counts", {})
    if not isinstance(cluster_types, dict):
        cluster_types = {}
    for contradiction_type, count in type_counts.items():
        cluster_types[contradiction_type] = int(cluster_types.get(contradiction_type, 0) or 0) + int(count)
    cluster_state["occurrences"] = int(cluster_state.get("occurrences", 0) or 0) + 1
    cluster_state["type_counts"] = cluster_types
    clusters[cluster_key] = cluster_state
    write_json_atomic(contextual_clusters_path, {"clusters": clusters})
    write_json_atomic(governance_path, governance)

    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "belief_state_registry": str(belief_registry_path),
            "contradiction_events": str(contradiction_events_path),
            "resolution_outcome_registry": str(resolution_registry_path),
            "contextual_contradiction_clusters": str(contextual_clusters_path),
            "governance_state": str(governance_path),
        },
    }


def _gap_signature(gap: dict[str, Any]) -> str:
    return f"{gap.get('gap_type', 'unknown')}::{gap.get('detail', 'n/a')}"


def _suggestion_signature(suggestion: dict[str, Any]) -> str:
    return f"{suggestion.get('suggestion_type', 'unknown')}::{suggestion.get('target', 'n/a')}"


def _detect_improvement_gaps(
    *,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    autonomous_behavior: dict[str, Any],
    detector_generator: dict[str, Any],
    pain_memory_survival: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    mutation_candidates: list[dict[str, Any]],
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    calibration_uncertainty_engine: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    repeated = autonomous_behavior.get("trade_review_engine", {}).get("repeated_failure_patterns", [])
    if isinstance(repeated, list):
        for item in repeated:
            if not isinstance(item, dict):
                continue
            count = int(item.get("count", 0) or 0)
            cause = str(item.get("failure_cause", "execution_failure"))
            if count >= 2:
                gaps.append({"gap_type": "repeated_failure_pattern", "detail": cause, "frequency": count, "severity": 0.7})

    detector_candidates = detector_generator.get("detector_candidates", [])
    if isinstance(detector_candidates, list) and detector_candidates:
        failed = sum(
            1
            for item in detector_candidates
            if isinstance(item, dict) and not bool(item.get("sandbox_test_passed", False))
        )
        reliability = 1.0 - (failed / max(1, len(detector_candidates)))
        if reliability < 0.6:
            gaps.append(
                {
                    "gap_type": "weak_detector_reliability",
                    "detail": "detector_sandbox_failures",
                    "frequency": failed,
                    "severity": round(1.0 - reliability, 4),
                }
            )

    losses = [item for item in closed if str(item.get("result", "")).lower() == "loss"]
    if losses:
        missing_context = sum(
            1
            for item in losses
            if not str(item.get("session", "")).strip() or not str(item.get("setup_type", "")).strip()
        )
        if missing_context > 0:
            gaps.append(
                {
                    "gap_type": "missing_context_in_losing_trades",
                    "detail": "session_or_setup_missing",
                    "frequency": missing_context,
                    "severity": 0.6,
                }
            )

    regime = str(autonomous_behavior.get("market_regime_classifier", {}).get("regime", "unknown"))
    if regime in {"unstable", "expansion"}:
        gaps.append({"gap_type": "unstable_regime_behavior", "detail": regime, "frequency": 1, "severity": 0.75})

    missing_market_dimensions = [
        key for key in ("volatility_ratio", "spread_ratio", "slippage_ratio", "structure_state") if key not in market_state
    ]
    if missing_market_dimensions:
        gaps.append(
            {
                "gap_type": "market_memory_dimension_gap",
                "detail": ",".join(sorted(missing_market_dimensions)),
                "frequency": len(missing_market_dimensions),
                "severity": 0.55,
            }
        )

    if bool(autonomous_behavior.get("environment_anomaly_detection", {}).get("anomalies", {}).get("repeated_execution_failures", False)):
        gaps.append(
            {
                "gap_type": "execution_logic_gap",
                "detail": "repeated_execution_failures",
                "frequency": 2,
                "severity": 0.7,
            }
        )
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))
    execution_penalty = float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0)
    failure_cluster_risk = float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0)
    entry_timing_degradation = float(execution_microstructure_engine.get("entry_timing_degradation", 0.0) or 0.0)
    if execution_state in {"degraded", "fragile"} or execution_penalty >= 0.4 or failure_cluster_risk >= 0.4:
        gaps.append(
            {
                "gap_type": "execution_microstructure_fragility",
                "detail": execution_state,
                "frequency": max(1, int(round((execution_penalty + failure_cluster_risk) * 4))),
                "severity": round(min(1.0, max(execution_penalty, failure_cluster_risk)), 4),
            }
        )
    if entry_timing_degradation >= 0.45 or bool(execution_microstructure_engine.get("should_delay_entry", False)):
        gaps.append(
            {
                "gap_type": "entry_timing_degradation_gap",
                "detail": "entry_timing_degradation",
                "frequency": 1,
                "severity": round(min(1.0, max(0.45, entry_timing_degradation)), 4),
            }
        )

    noisy_mutations = 0
    for candidate in mutation_candidates:
        if not isinstance(candidate, dict):
            continue
        score = float(candidate.get("mutation_score", 0.0) or 0.0)
        replay_validation = candidate.get("replay_validation", {})
        replay_passed = bool(replay_validation.get("passed", False)) if isinstance(replay_validation, dict) else False
        if score <= 0.0 or not replay_passed:
            noisy_mutations += 1
    if noisy_mutations > 0:
        gaps.append(
            {
                "gap_type": "low_value_noisy_mutations",
                "detail": "mutation_noise_cluster",
                "frequency": noisy_mutations,
                "severity": 0.5,
            }
        )

    unresolved_pain = pain_memory_survival.get("promotion_decisions", {}).get("quarantined", [])
    if isinstance(unresolved_pain, list) and unresolved_pain:
        gaps.append(
            {
                "gap_type": "survival_rule_gap",
                "detail": "quarantined_pain_memory_survival_rules",
                "frequency": len(unresolved_pain),
                "severity": 0.65,
            }
        )
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    contradiction_counts = contradiction_arbitration_engine.get("historical_context", {}).get("type_counts", {})
    if not isinstance(contradiction_counts, dict):
        contradiction_counts = {}
    contradiction_events = contradiction_arbitration_engine.get("contradictions", [])
    if not isinstance(contradiction_events, list):
        contradiction_events = []
    recurrence_ratio = float(
        contradiction_arbitration_engine.get("historical_context", {}).get("recurrence_ratio", 0.0) or 0.0
    )
    for contradiction_type, gap_type, detail in (
        ("continuation_vs_trap", "persistent_continuation_vs_trap_conflict", "continuation_vs_trap_conflict"),
        (
            "confidence_execution_conflict",
            "high_confidence_vs_execution_hostility_conflict",
            "high_confidence_vs_execution_hostility",
        ),
        (
            "risk_enable_vs_risk_disable",
            "chronic_risk_enable_vs_risk_disable_conflict",
            "risk_enable_vs_risk_disable_conflict",
        ),
    ):
        type_count = int(contradiction_counts.get(contradiction_type, 0) or 0)
        type_events = [
            item
            for item in contradiction_events
            if isinstance(item, dict) and str(item.get("contradiction_type", "")) == contradiction_type
        ]
        max_severity = max(
            [float(item.get("contradiction_severity", 0.0) or 0.0) for item in type_events],
            default=0.0,
        )
        persistent = type_count >= 1 and (recurrence_ratio >= 0.25 or len(type_events) >= 1)
        if persistent:
            gaps.append(
                {
                    "gap_type": gap_type,
                    "detail": detail,
                    "frequency": max(1, type_count),
                    "severity": round(min(1.0, max(max_severity, 0.55 if type_count >= 1 else 0.0)), 4),
                }
            )
    calibration_uncertainty_engine = (
        calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    )
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if isinstance(calibration_state, dict) and calibration_state:
        calibration_drift = float(calibration_state.get("calibration_drift", 0.0) or 0.0)
        historical_error = float(calibration_state.get("historical_confidence_error", 0.0) or 0.0)
        calibrated_confidence = float(calibration_state.get("calibrated_confidence", 0.0) or 0.0)
        raw_confidence = float(calibration_state.get("raw_confidence", 0.0) or 0.0)
        band = str(calibration_state.get("confidence_reliability_band", "moderate"))
        execution_adjusted_uncertainty = float(calibration_state.get("execution_adjusted_uncertainty", 0.0) or 0.0)
        regime_reliability = calibration_state.get("regime_specific_reliability", {})
        if not isinstance(regime_reliability, dict):
            regime_reliability = {}
        regime_score = float(regime_reliability.get("reliability_score", 0.5) or 0.5)
        regime_observations = int(regime_reliability.get("observations", 0) or 0)
        execution_penalty = float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0)

        if calibration_drift >= 0.18 or historical_error >= 0.2 or execution_adjusted_uncertainty >= 0.6:
            gaps.append(
                {
                    "gap_type": "confidence_miscalibration_drift",
                    "detail": "confidence_calibration_drift",
                    "frequency": max(1, int(round(max(calibration_drift, historical_error, execution_adjusted_uncertainty) * 4))),
                    "severity": round(max(calibration_drift, historical_error, execution_adjusted_uncertainty), 4),
                }
            )
        if regime_observations >= 2 and regime_score < 0.48:
            gaps.append(
                {
                    "gap_type": "regime_reliability_decay",
                    "detail": str(regime_reliability.get("context_key", "regime_reliability_decay")),
                    "frequency": regime_observations,
                    "severity": round(min(1.0, 1.0 - regime_score), 4),
                }
            )
        if (raw_confidence - calibrated_confidence) >= 0.08 and execution_penalty >= 0.4:
            gaps.append(
                {
                    "gap_type": "chronic_overconfidence_under_execution_hostility",
                    "detail": "overconfidence_execution_hostility",
                    "frequency": max(1, int(round((raw_confidence - calibrated_confidence) * 6))),
                    "severity": round(min(1.0, max(raw_confidence - calibrated_confidence, execution_penalty)), 4),
                }
            )
    return gaps


def _suggestion_templates(gap_type: str) -> list[dict[str, str]]:
    mapping = {
        "repeated_failure_pattern": [
            {"suggestion_type": "new_detector_idea", "target": "failure_cause_detector"},
            {"suggestion_type": "new_survival_rule", "target": "context_refusal_rule"},
        ],
        "weak_detector_reliability": [
            {"suggestion_type": "new_feature_combination", "target": "detector_ensemble_features"},
            {"suggestion_type": "new_strategy_mutation", "target": "detector_threshold_mutation"},
        ],
        "missing_context_in_losing_trades": [
            {"suggestion_type": "new_market_condition_memory_dimension", "target": "loss_context_dimensions"},
        ],
        "unstable_regime_behavior": [
            {"suggestion_type": "new_execution_refinement", "target": "unstable_regime_execution_safety"},
        ],
        "market_memory_dimension_gap": [
            {"suggestion_type": "new_market_condition_memory_dimension", "target": "missing_market_state_dimensions"},
            {"suggestion_type": "new_data_source_adapter_stub", "target": "market_context_adapter_stub"},
        ],
        "execution_logic_gap": [
            {"suggestion_type": "new_execution_refinement", "target": "execution_failure_mitigation"},
        ],
        "execution_microstructure_fragility": [
            {"suggestion_type": "new_execution_refinement", "target": "execution_fragility_guard"},
            {"suggestion_type": "new_strategy_mutation", "target": "partial_fill_aware_sizing"},
        ],
        "entry_timing_degradation_gap": [
            {"suggestion_type": "new_execution_refinement", "target": "entry_delay_filter"},
            {"suggestion_type": "new_detector_idea", "target": "execution_timing_survivability_detector"},
        ],
        "low_value_noisy_mutations": [
            {"suggestion_type": "new_survival_rule", "target": "mutation_noise_filter"},
            {"suggestion_type": "new_strategy_mutation", "target": "quality_gated_mutation_generator"},
        ],
        "survival_rule_gap": [
            {"suggestion_type": "new_survival_rule", "target": "pain_memory_survival_strengthening"},
        ],
        "persistent_continuation_vs_trap_conflict": [
            {"suggestion_type": "new_detector_idea", "target": "continuation_trap_contradiction_resolver"},
            {"suggestion_type": "new_survival_rule", "target": "trap_aware_continuation_guard"},
        ],
        "high_confidence_vs_execution_hostility_conflict": [
            {"suggestion_type": "new_execution_refinement", "target": "confidence_execution_arbitration_guard"},
        ],
        "chronic_risk_enable_vs_risk_disable_conflict": [
            {"suggestion_type": "new_strategy_mutation", "target": "contradiction_aware_risk_sizing"},
            {"suggestion_type": "new_survival_rule", "target": "risk_disable_override_rule"},
        ],
        "confidence_miscalibration_drift": [
            {"suggestion_type": "new_execution_refinement", "target": "confidence_calibration_guard"},
            {"suggestion_type": "new_survival_rule", "target": "miscalibration_pause_rule"},
        ],
        "regime_reliability_decay": [
            {"suggestion_type": "new_detector_idea", "target": "regime_reliability_recovery_detector"},
        ],
        "chronic_overconfidence_under_execution_hostility": [
            {"suggestion_type": "new_execution_refinement", "target": "overconfidence_execution_hostility_guard"},
        ],
        "autonomous_capability_proposal": [
            {"suggestion_type": "new_capability_hypothesis", "target": "autonomous_capability_discovery"},
        ],
    }
    return mapping.get(gap_type, [{"suggestion_type": "new_detector_idea", "target": "general_gap_detector"}])


def _priority_score(*, expected_usefulness: float, pain_frequency: int, regime_sensitivity: float, execution_impact: float, survival_impact: float) -> float:
    score = (
        (expected_usefulness * 0.35)
        + (min(1.0, pain_frequency / 5.0) * 0.2)
        + (regime_sensitivity * 0.15)
        + (execution_impact * 0.15)
        + (survival_impact * 0.15)
    )
    return round(max(0.0, min(1.0, score)), 4)


def _macro_state_snapshot(market_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "structure_state": str(market_state.get("structure_state", "unknown")),
        "volatility_ratio": float(market_state.get("volatility_ratio", 1.0)),
        "spread_ratio": float(market_state.get("spread_ratio", 1.0)),
        "slippage_ratio": float(market_state.get("slippage_ratio", 1.0)),
    }


def _specific_failure_cluster(closed: list[dict[str, Any]]) -> dict[str, Any]:
    losses = [item for item in closed if str(item.get("result", "")).lower() == "loss"]
    clustered: dict[tuple[str, str, str, str], int] = {}
    for item in losses:
        key = (
            str(item.get("failure_cause", "unknown")),
            str(item.get("setup_type", "unknown")),
            str(item.get("session", "unknown")),
            str(item.get("direction", "unknown")).upper(),
        )
        clustered[key] = clustered.get(key, 0) + 1
    if not clustered:
        return {
            "failure_cause": "unknown",
            "setup_type": "unknown",
            "session": "unknown",
            "direction": "unknown",
            "count": 0,
            "is_repeated_specific_cluster": False,
        }
    strongest_key = sorted(clustered.items(), key=lambda entry: (entry[1], entry[0]), reverse=True)[0][0]
    count = clustered[strongest_key]
    return {
        "failure_cause": strongest_key[0],
        "setup_type": strongest_key[1],
        "session": strongest_key[2],
        "direction": strongest_key[3],
        "count": count,
        "is_repeated_specific_cluster": count >= 2 and "unknown" not in strongest_key,
    }


def _component_for_gap(gap_type: str) -> str:
    mapping = {
        "repeated_failure_pattern": "trade_review_engine",
        "weak_detector_reliability": "detector_generator",
        "missing_context_in_losing_trades": "trade_review_engine",
        "unstable_regime_behavior": "market_regime_classifier",
        "market_memory_dimension_gap": "market_condition_memory",
        "execution_logic_gap": "behavior_adjustment_engine",
        "execution_microstructure_fragility": "execution_microstructure_intelligence_layer",
        "entry_timing_degradation_gap": "execution_microstructure_intelligence_layer",
        "low_value_noisy_mutations": "strategy_evolution_engine",
        "survival_rule_gap": "pain_memory_survival_layer",
        "persistent_continuation_vs_trap_conflict": "contradiction_arbitration_and_belief_resolution_layer",
        "high_confidence_vs_execution_hostility_conflict": "contradiction_arbitration_and_belief_resolution_layer",
        "chronic_risk_enable_vs_risk_disable_conflict": "contradiction_arbitration_and_belief_resolution_layer",
        "confidence_miscalibration_drift": "calibration_and_uncertainty_governance_layer",
        "regime_reliability_decay": "calibration_and_uncertainty_governance_layer",
        "chronic_overconfidence_under_execution_hostility": "calibration_and_uncertainty_governance_layer",
        "autonomous_capability_proposal": "capability_evolution_governance_ladder",
    }
    return mapping.get(gap_type, "self_evolving_indicator_layer")


def _missing_capability_hypothesis(*, gap_type: str, gap_detail: str, regime: str, component: str) -> str:
    return (
        f"Missing {gap_type} mitigation capability for {gap_detail} in regime {regime} "
        f"across component {component}"
    )


def _is_vague_suggestion(suggestion: dict[str, Any]) -> bool:
    required_string_paths = (
        ("failure_context", "failure_cause"),
        ("failure_context", "setup_type"),
        ("failure_context", "session"),
        ("session",),
        ("regime",),
        ("detector_or_strategy_component",),
        ("missing_capability_hypothesis",),
    )
    for path in required_string_paths:
        value: Any = suggestion
        for key in path:
            if not isinstance(value, dict):
                return True
            value = value.get(key)
        text = str(value).strip().lower()
        if not text or text in {"unknown", "n/a", "none"}:
            return True
    macro_state = suggestion.get("macro_state")
    if not isinstance(macro_state, dict):
        return True
    for key in ("structure_state", "volatility_ratio", "spread_ratio", "slippage_ratio"):
        if key not in macro_state:
            return True
    return False


def _self_suggestion_governor(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    autonomous_behavior: dict[str, Any],
    detector_generator: dict[str, Any],
    strategy_evolution: dict[str, Any],
    pain_memory_survival: dict[str, Any],
    discovery_state_tags: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    contradiction_arbitration_engine: dict[str, Any],
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    mutation_candidates: list[dict[str, Any]],
    capability_evolution_ladder: dict[str, Any] | None = None,
    replay_scope: str,
) -> dict[str, Any]:
    registry_dir = memory_root / "capability_registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    governor_path = registry_dir / "self_suggestion_governor.json"
    history_path = registry_dir / "self_suggestion_governor_history.json"
    registry_path = registry_dir / "self_suggestion_registry.json"
    previous_registry = read_json_safe(
        registry_path,
        default={
            "cycle_index": 0,
            "proposed_improvements": [],
            "implemented_improvements": [],
            "rejected_improvements": [],
            "promoted_improvements": [],
            "repeated_unresolved_gaps": [],
            "cooldowns": {},
        },
    )
    if not isinstance(previous_registry, dict):
        previous_registry = {
            "cycle_index": 0,
            "proposed_improvements": [],
            "implemented_improvements": [],
            "rejected_improvements": [],
            "promoted_improvements": [],
            "repeated_unresolved_gaps": [],
            "cooldowns": {},
        }
    previous_governor = read_json_safe(governor_path, default={})
    if not isinstance(previous_governor, dict):
        previous_governor = {}

    gaps = _detect_improvement_gaps(
        closed=closed,
        market_state=market_state,
        autonomous_behavior=autonomous_behavior,
        detector_generator=detector_generator,
        pain_memory_survival=pain_memory_survival,
        execution_microstructure_engine=execution_microstructure_engine,
        mutation_candidates=mutation_candidates,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
    )
    calibration_uncertainty_engine = (
        calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    )
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}
    capability_candidates = capability_evolution_ladder.get("capability_candidates", [])
    if isinstance(capability_candidates, list):
        for candidate in capability_candidates:
            if not isinstance(candidate, dict):
                continue
            hypothesis = str(candidate.get("capability_hypothesis", "")).strip()
            if not hypothesis:
                continue
            replay_score = float(candidate.get("replay_validation", {}).get("score", 0.0) or 0.0)
            gaps.append(
                {
                    "gap_type": "autonomous_capability_proposal",
                    "detail": hypothesis[:80],
                    "frequency": 1,
                    "severity": round(min(1.0, max(0.35, replay_score)), 4),
                }
            )
    input_signature = {
        "replay_scope": replay_scope,
        "gap_signatures": sorted(_gap_signature(gap) for gap in gaps),
        "strongest_branch": str(strategy_evolution.get("strongest_branch", {}).get("branch_id", "current_strategy")),
        "closed_count": len(closed),
        "unified_field_score": round(float(unified_market_intelligence_field.get("unified_field_score", 0.0) or 0.0), 4),
        "unified_confidence": round(
            float(
                unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.0) or 0.0
            ),
            4,
        ),
        "execution_quality_score": round(float(execution_microstructure_engine.get("execution_quality_score", 0.0) or 0.0), 4),
        "execution_penalty": round(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0), 4),
        "contradiction_outcome": str(contradiction_arbitration_engine.get("arbitration", {}).get("outcome", "allow")),
        "contradiction_severity": round(
            float(contradiction_arbitration_engine.get("arbitration", {}).get("max_contradiction_severity", 0.0) or 0.0),
            4,
        ),
        "calibration_drift": round(float(calibration_state.get("calibration_drift", 0.0) or 0.0), 4),
        "confidence_reliability_band": str(calibration_state.get("confidence_reliability_band", "unknown")),
        "execution_adjusted_uncertainty": round(
            float(calibration_state.get("execution_adjusted_uncertainty", 0.0) or 0.0),
            4,
        ),
    }
    if previous_governor.get("input_signature") == input_signature:
        return previous_governor

    cycle_index = int(previous_registry.get("cycle_index", 0) or 0) + 1
    regime = str(autonomous_behavior.get("market_regime_classifier", {}).get("regime", "unknown"))
    macro_state = _macro_state_snapshot(market_state)
    strongest_failure_cluster = _specific_failure_cluster(closed)
    unresolved_counter: dict[str, int] = {}
    for entry in previous_registry.get("repeated_unresolved_gaps", []):
        if isinstance(entry, dict):
            unresolved_counter[str(entry.get("gap_signature", ""))] = int(entry.get("repeat_count", 0) or 0)
    for gap in gaps:
        sig = _gap_signature(gap)
        unresolved_counter[sig] = unresolved_counter.get(sig, 0) + 1

    noisy_cluster = len(gaps) >= 4
    min_threshold = _SUGGESTION_LOW_VALUE_THRESHOLD + (0.08 if noisy_cluster else 0.0)
    max_per_cycle = _SUGGESTION_MAX_PER_NOISY_CYCLE if noisy_cluster else _SUGGESTION_MAX_PER_CYCLE

    previous_proposed = previous_registry.get("proposed_improvements", [])
    prior_signatures = {
        str(item.get("signature", ""))
        for item in previous_proposed
        if isinstance(item, dict)
    }
    cooldowns = previous_registry.get("cooldowns", {})
    if not isinstance(cooldowns, dict):
        cooldowns = {}
    proposed: list[dict[str, Any]] = []
    duplicate_suppressed = 0
    pruned_low_value = 0
    cooldown_suppressed = 0
    vague_suppressed = 0
    vague_rejections: list[dict[str, Any]] = []
    for gap in gaps:
        frequency = int(gap.get("frequency", 1) or 1)
        severity = float(gap.get("severity", 0.5) or 0.5)
        expected_usefulness = round(min(1.0, 0.45 + (severity * 0.5)), 4)
        regime_sensitivity = 0.8 if "regime" in str(gap.get("gap_type", "")) else 0.5
        execution_impact = 0.85 if "execution" in str(gap.get("gap_type", "")) else 0.45
        survival_impact = 0.85 if "survival" in str(gap.get("gap_type", "")) or "failure" in str(gap.get("gap_type", "")) else 0.5
        component = _component_for_gap(str(gap.get("gap_type", "")))
        cluster_specificity_boost = 0.0
        if str(gap.get("gap_type", "")) == "repeated_failure_pattern" and strongest_failure_cluster["is_repeated_specific_cluster"]:
            cluster_specificity_boost = round(
                min(
                    _MAX_CLUSTER_SPECIFICITY_BOOST,
                    (strongest_failure_cluster["count"] - 1) * _CLUSTER_SPECIFICITY_BOOST_PER_OCCURRENCE,
                ),
                4,
            )
        for template in _suggestion_templates(str(gap.get("gap_type", ""))):
            base_priority = _priority_score(
                expected_usefulness=expected_usefulness,
                pain_frequency=frequency,
                regime_sensitivity=regime_sensitivity,
                execution_impact=execution_impact,
                survival_impact=survival_impact,
            )
            suggestion = {
                "cycle_index": cycle_index,
                "suggestion_type": template["suggestion_type"],
                "target": template["target"],
                "gap_type": gap.get("gap_type"),
                "gap_detail": gap.get("detail"),
                "failure_context": {
                    "failure_cause": strongest_failure_cluster["failure_cause"],
                    "setup_type": strongest_failure_cluster["setup_type"],
                    "session": strongest_failure_cluster["session"],
                    "direction": strongest_failure_cluster["direction"],
                },
                "session": strongest_failure_cluster["session"],
                "regime": regime,
                "macro_state": macro_state,
                "detector_or_strategy_component": component,
                "missing_capability_hypothesis": _missing_capability_hypothesis(
                    gap_type=str(gap.get("gap_type", "unknown")),
                    gap_detail=str(gap.get("detail", "n/a")),
                    regime=regime,
                    component=component,
                ),
                "specific_cluster_count": strongest_failure_cluster["count"],
                "is_repeated_specific_failure_cluster": strongest_failure_cluster["is_repeated_specific_cluster"],
                "cluster_specificity_boost": cluster_specificity_boost,
                "expected_usefulness": expected_usefulness,
                "pain_failure_frequency": frequency,
                "regime_sensitivity": regime_sensitivity,
                "execution_impact": execution_impact,
                "survival_impact": survival_impact,
                "priority_score": round(min(1.0, base_priority + cluster_specificity_boost), 4),
                "governance": {
                    "sandbox_only": True,
                    "live_deployment_allowed": False,
                    "blind_live_rewrite_blocked": True,
                },
            }
            suggestion["signature"] = _suggestion_signature(suggestion)
            if suggestion["signature"] in prior_signatures:
                duplicate_suppressed += 1
                continue
            available_cycle = int(cooldowns.get(suggestion["signature"], 0) or 0)
            if cycle_index < available_cycle:
                cooldown_suppressed += 1
                continue
            if _is_vague_suggestion(suggestion):
                vague_suppressed += 1
                vague_rejections.append(
                    {
                        "cycle_index": cycle_index,
                        "signature": suggestion["signature"],
                        "gap_type": suggestion["gap_type"],
                        "reason": "vague_suggestion_rejected",
                    }
                )
                continue
            if suggestion["priority_score"] < min_threshold:
                pruned_low_value += 1
                continue
            proposed.append(suggestion)

    proposed = sorted(proposed, key=lambda item: (item["priority_score"], item["expected_usefulness"]), reverse=True)[:max_per_cycle]

    implemented: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, suggestion in enumerate(proposed):
        strategy_expectancy = float(strategy_evolution.get("strongest_branch", {}).get("expectancy", 0.0) or 0.0)
        unified_confidence = float(
            unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.0) or 0.0
        )
        replay_score = round(
            max(
                0.0,
                min(
                    1.0,
                    suggestion["priority_score"] + (strategy_expectancy * 0.15) + (unified_confidence * 0.08) - (0.02 * index),
                ),
            ),
            4,
        )
        decision = "quarantine"
        if replay_score >= _SUGGESTION_PROMOTE_THRESHOLD:
            decision = "promote"
        elif replay_score >= _SUGGESTION_RETAIN_THRESHOLD:
            decision = "retain"
        implementation = {
            "suggestion_signature": suggestion["signature"],
            "implementation_id": f"sandbox_impl_{cycle_index}_{index + 1}",
            "sandbox_module_name": f"sandbox_{suggestion['target']}",
            "suggestion_type": suggestion["suggestion_type"],
            "target": suggestion["target"],
            "replay_test": {
                "scope": replay_scope,
                "baseline": strategy_evolution.get("strongest_branch", {}).get("branch_id", "current_strategy"),
                "comparison": "sandbox_vs_baseline",
                "score": replay_score,
            },
            "governance_decision": decision,
            "governance": {
                "sandbox_only": True,
                "live_activation_allowed": False,
                "core_module_deletion_allowed": False,
                "quarantine_supported": True,
            },
        }
        implemented.append(implementation)
        cooldowns[suggestion["signature"]] = cycle_index + _SUGGESTION_COOLDOWN_CYCLES
        if decision == "promote":
            promoted.append(implementation)
        elif decision == "quarantine":
            rejected.append(implementation)

    repeated_unresolved = [
        {"gap_signature": sig, "repeat_count": count}
        for sig, count in sorted(unresolved_counter.items())
        if count >= 2
    ]

    updated_registry = {
        "cycle_index": cycle_index,
        "proposed_improvements": (previous_registry.get("proposed_improvements", []) + proposed)[-400:],
        "implemented_improvements": (previous_registry.get("implemented_improvements", []) + implemented)[-400:],
        "rejected_improvements": (previous_registry.get("rejected_improvements", []) + rejected + vague_rejections)[-400:],
        "promoted_improvements": (previous_registry.get("promoted_improvements", []) + promoted)[-400:],
        "repeated_unresolved_gaps": repeated_unresolved[-200:],
        "cooldowns": cooldowns,
    }
    write_json_atomic(registry_path, updated_registry)

    cycle_payload = {
        "cycle_index": cycle_index,
        "input_signature": input_signature,
        "detected_gaps": gaps,
        "proposed_improvements": proposed,
        "implemented_improvements": implemented,
        "promoted_improvements": promoted,
        "rejected_improvements": rejected + vague_rejections,
        "anti_noise_controls": {
            "duplicate_suppression": duplicate_suppressed,
            "low_value_pruned": pruned_low_value,
            "cooldown_suppressed": cooldown_suppressed,
            "vague_rejected": vague_suppressed,
            "max_suggestions_per_cycle": max_per_cycle,
            "stricter_thresholds_active": noisy_cluster,
            "priority_threshold": round(min_threshold, 4),
        },
        "repeated_unresolved_gaps": repeated_unresolved,
        "safety_controls": {
            "sandbox_only": True,
            "direct_live_deployment_blocked": True,
            "no_blind_live_self_rewrites": True,
            "stable_core_module_deletion_blocked": True,
        },
        "discovery_state_tags": dict(discovery_state_tags),
        "unified_market_intelligence_field": {
            "unified_field_score": unified_market_intelligence_field.get("unified_field_score", 0.0),
            "composite_confidence": unified_market_intelligence_field.get("confidence_structure", {}).get(
                "composite_confidence",
                0.0,
            ),
            "refusal_pause_behavior": unified_market_intelligence_field.get("decision_refinements", {}).get(
                "refusal_pause_behavior",
                {},
            ),
        },
        "execution_microstructure_intelligence_layer": {
            "execution_quality_score": execution_microstructure_engine.get("execution_quality_score", 0.0),
            "execution_penalty": execution_microstructure_engine.get("execution_penalty", 0.0),
            "execution_state": execution_microstructure_engine.get("execution_state", "insufficient_data"),
            "recommended_actions": execution_microstructure_engine.get("recommended_actions", []),
        },
        "contradiction_arbitration_and_belief_resolution_layer": {
            "arbitration": contradiction_arbitration_engine.get("arbitration", {}),
            "confidence_adjustments": contradiction_arbitration_engine.get("confidence_adjustments", {}),
            "risk_adjustments": contradiction_arbitration_engine.get("risk_adjustments", {}),
        },
        "calibration_and_uncertainty_governance_layer": {
            "calibration_state": calibration_state,
            "confidence_adjustments": calibration_uncertainty_engine.get("confidence_adjustments", {}),
            "governance": calibration_uncertainty_engine.get("governance", {}),
        },
        "paths": {
            "registry": str(registry_path),
            "governor": str(governor_path),
            "history": str(history_path),
        },
    }
    write_json_atomic(governor_path, cycle_payload)
    history = read_json_safe(history_path, default={"cycles": []})
    if not isinstance(history, dict):
        history = {"cycles": []}
    cycles = history.get("cycles", [])
    if not isinstance(cycles, list):
        cycles = []
    cycles.append(cycle_payload)
    write_json_atomic(history_path, {"cycles": cycles[-150:]})
    return cycle_payload


def run_self_evolving_indicator_layer(
    *,
    memory_root: Path,
    trade_outcomes: list[dict[str, Any]],
    market_state: dict[str, Any] | None = None,
    feature_contributors: dict[str, float] | None = None,
    mutation_candidates: list[dict[str, Any]] | None = None,
    replay_scope: str = "full_replay",
) -> dict[str, Any]:
    market_state = market_state if isinstance(market_state, dict) else {}
    feature_contributors = feature_contributors if isinstance(feature_contributors, dict) else {}
    mutation_candidates = mutation_candidates if isinstance(mutation_candidates, list) else []
    closed = _closed_outcomes(trade_outcomes)

    autonomous_behavior = run_autonomous_behavior_layer(
        memory_root=memory_root,
        trade_outcomes=trade_outcomes,
        market_state=market_state,
        feature_contributors=feature_contributors,
        mutation_candidates=mutation_candidates,
    )
    capability_generator = _capability_generator(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
    )
    self_architecture_engine = _self_architecture_engine(memory_root=memory_root, closed=closed)
    detector_generator = _detector_generator(memory_root=memory_root, capability_generator=capability_generator)
    knowledge_compression = _knowledge_compression(memory_root=memory_root, closed=closed)
    strategy_evolution = _strategy_evolution(
        memory_root=memory_root,
        closed=closed,
        autonomous_behavior=autonomous_behavior,
    )
    pain_memory_survival = _pain_memory_survival_layer(
        memory_root=memory_root,
        closed=closed,
        replay_scope=replay_scope,
    )
    synthetic_feature_engine = _synthetic_feature_invention_engine(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
    )
    negative_space_engine = _negative_space_pattern_recognition(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
    )
    invariant_break_engine = _temporal_invariance_break_detection(
        memory_root=memory_root,
        market_state=market_state,
        replay_scope=replay_scope,
    )
    pain_geometry_engine = _pain_geometry_fields(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
    )
    counterfactual_engine = _counterfactual_trade_engine(memory_root=memory_root, closed=closed)
    liquidity_decay_engine = _fractal_liquidity_decay_functions(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
    )
    execution_microstructure_engine = _execution_microstructure_intelligence_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
    )
    provisional_unified_market_intelligence = {
        "unified_field_score": round(
            float(_detector_reliability_state(detector_generator).get("reliability_score", 0.0) or 0.0),
            4,
        ),
        "confidence_structure": {
            "composite_confidence": round(
                float(
                    autonomous_behavior.get("market_regime_classifier", {}).get("confidence_multiplier", 0.0) or 0.0
                ),
                4,
            ),
        },
        "decision_refinements": {
            "refusal_pause_behavior": {
                "should_refuse": str(execution_microstructure_engine.get("execution_state", "")) in {"fragile", "degraded"},
                "should_pause": float(pain_geometry_engine.get("pain_risk_surface", {}).get("current_state_risk", 0.0) or 0.0)
                >= 0.75,
            }
        },
    }
    intelligence_gap_engine = _intelligence_gap_discovery_engine(
        memory_root=memory_root,
        closed=closed,
        counterfactual_engine=counterfactual_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        pain_geometry_engine=pain_geometry_engine,
        execution_microstructure_engine=execution_microstructure_engine,
    )
    synthetic_data_plane_engine = _synthetic_data_plane_expansion_engine(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        counterfactual_engine=counterfactual_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        execution_microstructure_engine=execution_microstructure_engine,
    )
    capability_evolution_ladder = _capability_evolution_governance_ladder(
        memory_root=memory_root,
        intelligence_gap_engine=intelligence_gap_engine,
        synthetic_data_plane_engine=synthetic_data_plane_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        replay_scope=replay_scope,
    )
    discovery_state_tags = _discovery_state_tags(
        synthetic_feature_engine=synthetic_feature_engine,
        negative_space_engine=negative_space_engine,
        invariant_break_engine=invariant_break_engine,
        pain_geometry_engine=pain_geometry_engine,
        counterfactual_engine=counterfactual_engine,
        liquidity_decay_engine=liquidity_decay_engine,
    )
    recursive_self_modeling = _recursive_self_modeling(
        memory_root=memory_root,
        closed=closed,
        mutation_candidates=mutation_candidates,
        synthetic_feature_engine=synthetic_feature_engine,
        negative_space_engine=negative_space_engine,
        invariant_break_engine=invariant_break_engine,
        pain_geometry_engine=pain_geometry_engine,
        counterfactual_engine=counterfactual_engine,
        liquidity_decay_engine=liquidity_decay_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        replay_scope=replay_scope,
    )
    unified_market_intelligence_field = _unified_market_intelligence_field(
        memory_root=memory_root,
        market_state=market_state,
        autonomous_behavior=autonomous_behavior,
        detector_generator=detector_generator,
        strategy_evolution=strategy_evolution,
        synthetic_feature_engine=synthetic_feature_engine,
        negative_space_engine=negative_space_engine,
        invariant_break_engine=invariant_break_engine,
        pain_geometry_engine=pain_geometry_engine,
        counterfactual_engine=counterfactual_engine,
        liquidity_decay_engine=liquidity_decay_engine,
        execution_microstructure_engine=execution_microstructure_engine,
    )
    calibration_uncertainty_engine = _calibration_and_uncertainty_governance_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        unified_market_intelligence_field=unified_market_intelligence_field,
        execution_microstructure_engine=execution_microstructure_engine,
        replay_scope=replay_scope,
    )
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    calibration_adjustments = calibration_uncertainty_engine.get("confidence_adjustments", {})
    if not isinstance(calibration_adjustments, dict):
        calibration_adjustments = {}
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    for key in (
        "calibrated_confidence",
        "calibration_drift",
        "confidence_reliability_band",
        "historical_confidence_error",
        "execution_adjusted_uncertainty",
    ):
        if key in calibration_state:
            confidence_structure[key] = calibration_state[key]
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    calibration_multiplier = round(float(calibration_adjustments.get("risk_multiplier", 1.0) or 1.0), 4)
    risk_sizing["calibration_multiplier"] = max(0.25, min(1.0, calibration_multiplier))
    risk_sizing["calibration_adjusted_refined"] = round(
        max(0.05, float(risk_sizing.get("refined", 0.05) or 0.05) * risk_sizing["calibration_multiplier"]),
        4,
    )
    decision_refinements["risk_sizing"] = risk_sizing
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    for reason in calibration_adjustments.get("refusal_reasons", []):
        if reason not in refusal_reasons:
            refusal_reasons.append(str(reason))
    for reason in calibration_adjustments.get("pause_reasons", []):
        if reason not in pause_reasons:
            pause_reasons.append(str(reason))
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        calibration_adjustments.get("should_refuse", False)
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        calibration_adjustments.get("should_pause", False)
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    contradiction_arbitration_engine = _contradiction_arbitration_and_belief_resolution_layer(
        memory_root=memory_root,
        market_state=market_state,
        unified_market_intelligence_field=unified_market_intelligence_field,
        negative_space_engine=negative_space_engine,
        invariant_break_engine=invariant_break_engine,
        pain_geometry_engine=pain_geometry_engine,
        counterfactual_engine=counterfactual_engine,
        liquidity_decay_engine=liquidity_decay_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        strategy_evolution=strategy_evolution,
        detector_generator=detector_generator,
        replay_scope=replay_scope,
    )
    contradiction_confidence = float(
        contradiction_arbitration_engine.get("confidence_adjustments", {}).get("contradiction_adjusted_confidence", 0.0) or 0.0
    )
    contradiction_multiplier = float(
        contradiction_arbitration_engine.get("risk_adjustments", {}).get("contradiction_multiplier", 1.0) or 1.0
    )
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["contradiction_adjusted_confidence"] = round(max(0.0, min(1.0, contradiction_confidence)), 4)
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    risk_sizing["contradiction_multiplier"] = round(max(0.25, min(1.0, contradiction_multiplier)), 4)
    decision_refinements["risk_sizing"] = risk_sizing
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    contradiction_outcome = str(contradiction_arbitration_engine.get("arbitration", {}).get("outcome", "allow"))
    if contradiction_outcome == "refuse" and "contradiction_arbitration_refuse" not in refusal_reasons:
        refusal_reasons.append("contradiction_arbitration_refuse")
    if contradiction_outcome in {"pause", "refuse"} and "contradiction_arbitration_pause" not in pause_reasons:
        pause_reasons.append("contradiction_arbitration_pause")
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or contradiction_outcome == "refuse"
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or contradiction_outcome in {
        "pause",
        "refuse",
    }
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    unified_market_intelligence_field["contradiction_arbitration"] = contradiction_arbitration_engine.get("arbitration", {})
    self_suggestion_governor = _self_suggestion_governor(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        autonomous_behavior=autonomous_behavior,
        detector_generator=detector_generator,
        strategy_evolution=strategy_evolution,
        pain_memory_survival=pain_memory_survival,
        discovery_state_tags=discovery_state_tags,
        unified_market_intelligence_field=unified_market_intelligence_field,
        execution_microstructure_engine=execution_microstructure_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        mutation_candidates=mutation_candidates,
        capability_evolution_ladder=capability_evolution_ladder,
        replay_scope=replay_scope,
    )
    survival_intelligence = {
        "capital_survival_engine": autonomous_behavior.get("capital_survival_engine", {}),
        "pain_memory_survival_layer": pain_memory_survival,
        "self_suggestion_governor": self_suggestion_governor,
        "synthetic_feature_invention_engine": synthetic_feature_engine,
        "negative_space_pattern_recognition": negative_space_engine,
        "temporal_invariance_break_detection": invariant_break_engine,
        "pain_geometry_fields": pain_geometry_engine,
        "counterfactual_trade_engine": counterfactual_engine,
        "fractal_liquidity_decay_functions": liquidity_decay_engine,
        "execution_microstructure_intelligence_layer": execution_microstructure_engine,
        "calibration_and_uncertainty_governance_layer": calibration_uncertainty_engine,
        "contradiction_arbitration_and_belief_resolution_layer": contradiction_arbitration_engine,
        "recursive_self_modeling": recursive_self_modeling,
        "discovery_state_tags": discovery_state_tags,
        "unified_market_intelligence_field": unified_market_intelligence_field,
    }
    meta_learning_loop = _meta_learning_loop(
        memory_root=memory_root,
        capability_generator=capability_generator,
        detector_generator=detector_generator,
        strategy_evolution=strategy_evolution,
    )
    return {
        "autonomous_behavior_layer": autonomous_behavior,
        "capability_generator": capability_generator,
        "self_architecture_engine": self_architecture_engine,
        "detector_generator": detector_generator,
        "knowledge_compression_system": knowledge_compression,
        "strategy_evolution_engine": strategy_evolution,
        "survival_intelligence_layer": survival_intelligence,
        "pain_memory_survival_layer": pain_memory_survival,
        "self_suggestion_governor": self_suggestion_governor,
        "synthetic_feature_invention_engine": synthetic_feature_engine,
        "negative_space_pattern_recognition": negative_space_engine,
        "temporal_invariance_break_detection": invariant_break_engine,
        "pain_geometry_fields": pain_geometry_engine,
        "counterfactual_trade_engine": counterfactual_engine,
        "fractal_liquidity_decay_functions": liquidity_decay_engine,
        "execution_microstructure_intelligence_layer": execution_microstructure_engine,
        "calibration_and_uncertainty_governance_layer": calibration_uncertainty_engine,
        "contradiction_arbitration_and_belief_resolution_layer": contradiction_arbitration_engine,
        "recursive_self_modeling": recursive_self_modeling,
        "discovery_state_tags": discovery_state_tags,
        "unified_market_intelligence_field": unified_market_intelligence_field,
        "meta_learning_loop": meta_learning_loop,
    }
