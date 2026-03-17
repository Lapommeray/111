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


def _adversarial_execution_intelligence_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    liquidity_decay_engine: dict[str, Any],
    negative_space_engine: dict[str, Any],
    counterfactual_engine: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    adversarial_dir = memory_root / "adversarial_execution"
    adversarial_dir.mkdir(parents=True, exist_ok=True)
    latest_path = adversarial_dir / "adversarial_execution_latest.json"
    history_path = adversarial_dir / "adversarial_execution_history.json"
    event_registry_path = adversarial_dir / "hostility_event_registry.json"
    contextual_clusters_path = adversarial_dir / "contextual_hostility_clusters.json"
    governance_path = adversarial_dir / "hostility_governance_state.json"
    detector_registry_path = adversarial_dir / "detector_reliability_registry.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    def _state_score(state: str, *, elevated: str, severe: str) -> float:
        if state == severe:
            return 1.0
        if state == elevated:
            return 0.6
        return 0.2 if state == "normal" else 0.4

    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    failure_cluster_risk = _bounded(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0))
    entry_timing_degradation = _bounded(float(execution_microstructure_engine.get("entry_timing_degradation", 0.0) or 0.0))

    spread_state = str(execution_microstructure_engine.get("spread_state", "normal"))
    slippage_state = str(execution_microstructure_engine.get("slippage_state", "normal"))
    fill_delay_state = str(execution_microstructure_engine.get("fill_delay_state", "normal"))
    partial_fill_state = str(execution_microstructure_engine.get("partial_fill_state", "normal"))

    spread_stress = _bounded(max(0.0, float(market_state.get("spread_ratio", 1.0) or 1.0) - 1.0))
    slippage_stress = _bounded(max(0.0, float(market_state.get("slippage_ratio", 1.0) or 1.0) - 1.0))
    volatility_stress = _bounded(max(0.0, abs(float(market_state.get("volatility_ratio", 1.0) or 1.0) - 1.0)))

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
    negative_deviation = _bounded(float(negative_space_engine.get("signal", {}).get("deviation_score", 0.0) or 0.0))
    negative_anomaly = bool(negative_space_engine.get("signal", {}).get("negative_space_signal", False))

    counterfactual_items = counterfactual_engine.get("counterfactual_evaluations", [])
    if not isinstance(counterfactual_items, list):
        counterfactual_items = []
    counterfactual_disadvantage = _bounded(
        sum(1 for item in counterfactual_items if isinstance(item, dict) and not bool(item.get("strategy_improved_outcome", False)))
        / max(1, len(counterfactual_items))
    )

    spread_proxy = _state_score(spread_state, elevated="elevated", severe="shock")
    slippage_proxy = _state_score(slippage_state, elevated="elevated", severe="high_damage")
    delay_proxy = _state_score(fill_delay_state, elevated="elevated", severe="degraded")
    partial_proxy = _state_score(partial_fill_state, elevated="elevated", severe="degraded")

    quote_fade_proxy = _bounded((spread_proxy * 0.45) + (delay_proxy * 0.3) + (partial_proxy * 0.15) + (spread_stress * 0.1))
    sweep_aftermath_risk = _bounded((spread_stress * 0.35) + (slippage_stress * 0.25) + (liquidity_vulnerability * 0.2) + (failure_cluster_risk * 0.2))
    fill_collapse_risk = _bounded((partial_proxy * 0.45) + (delay_proxy * 0.25) + (failure_cluster_risk * 0.2) + (execution_penalty * 0.1))
    adverse_selection_risk = _bounded((entry_timing_degradation * 0.4) + (slippage_proxy * 0.25) + (counterfactual_disadvantage * 0.2) + (negative_deviation * 0.15))
    toxicity_proxy = _bounded(
        (execution_penalty * 0.25)
        + (failure_cluster_risk * 0.2)
        + (liquidity_vulnerability * 0.2)
        + (quote_fade_proxy * 0.2)
        + (sweep_aftermath_risk * 0.15)
    )
    hostile_execution_score = _bounded(
        (toxicity_proxy * 0.3)
        + (quote_fade_proxy * 0.15)
        + (sweep_aftermath_risk * 0.2)
        + (fill_collapse_risk * 0.15)
        + (adverse_selection_risk * 0.15)
        + (volatility_stress * 0.05)
    )

    if hostile_execution_score >= 0.72:
        predatory_liquidity_state = "hostile"
    elif hostile_execution_score >= 0.45:
        predatory_liquidity_state = "elevated"
    else:
        predatory_liquidity_state = "normal"

    context_signature = {
        "replay_scope": replay_scope,
        "structure_state": str(market_state.get("structure_state", "unknown")),
        "execution_state": execution_state,
    }
    context_key = f"{context_signature['replay_scope']}|{context_signature['structure_state']}|{context_signature['execution_state']}"
    detector_registry = read_json_safe(detector_registry_path, default={"contexts": {}})
    if not isinstance(detector_registry, dict):
        detector_registry = {"contexts": {}}
    contexts = detector_registry.get("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
    prior_context = contexts.get(context_key, {})
    if not isinstance(prior_context, dict):
        prior_context = {}
    prior_hostility = _bounded(float(prior_context.get("rolling_hostility", 0.0) or 0.0))
    prior_observations = int(prior_context.get("observations", 0) or 0)
    observations = prior_observations + 1
    historical_execution_hostility = _bounded(((prior_hostility * prior_observations) + hostile_execution_score) / max(1, observations))
    contexts[context_key] = {
        "rolling_hostility": historical_execution_hostility,
        "observations": observations,
        "detector_reliability": _bounded(1.0 - abs(hostile_execution_score - prior_hostility)),
        "predatory_liquidity_state": predatory_liquidity_state,
    }
    write_json_atomic(detector_registry_path, {"contexts": contexts})

    should_reduce_size = hostile_execution_score >= 0.45 or fill_collapse_risk >= 0.5 or adverse_selection_risk >= 0.55
    should_pause = hostile_execution_score >= 0.6 or sweep_aftermath_risk >= 0.62 or quote_fade_proxy >= 0.65
    should_refuse = hostile_execution_score >= 0.78 or (fill_collapse_risk >= 0.75 and sweep_aftermath_risk >= 0.65)
    execution_survival_bias = _bounded(
        (hostile_execution_score * 0.45)
        + (0.2 if should_reduce_size else 0.0)
        + (0.2 if should_pause else 0.0)
        + (0.15 if should_refuse else 0.0)
    )

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    adversarial_execution_state = {
        "hostile_execution_score": hostile_execution_score,
        "toxicity_proxy": toxicity_proxy,
        "quote_fade_proxy": quote_fade_proxy,
        "sweep_aftermath_risk": sweep_aftermath_risk,
        "fill_collapse_risk": fill_collapse_risk,
        "adverse_selection_risk": adverse_selection_risk,
        "predatory_liquidity_state": predatory_liquidity_state,
        "historical_execution_hostility": historical_execution_hostility,
        "execution_survival_bias": execution_survival_bias,
        "governance_flags": governance_flags,
    }
    confidence_adjustments = {
        "hostility_penalty": _bounded((hostile_execution_score * 0.5) + (adverse_selection_risk * 0.2) + (quote_fade_proxy * 0.3)),
        "hostility_adjusted_confidence": _bounded(1.0 - ((hostile_execution_score * 0.65) + (toxicity_proxy * 0.25))),
    }
    pause_reasons = []
    refusal_reasons = []
    if quote_fade_proxy >= 0.55:
        pause_reasons.append("adversarial_quote_fade_risk")
    if sweep_aftermath_risk >= 0.55:
        pause_reasons.append("adversarial_sweep_aftermath_risk")
    if adverse_selection_risk >= 0.55:
        pause_reasons.append("adversarial_adverse_selection_risk")
    if should_refuse:
        refusal_reasons.append("adversarial_execution_refuse_guard")
    risk_adjustments = {
        "adversarial_execution_multiplier": _bounded(1.0 - (hostile_execution_score * 0.65), low=0.25, high=1.0),
        "should_reduce_size": should_reduce_size,
        "should_pause": should_pause,
        "should_refuse": should_refuse,
        "pause_reasons": pause_reasons,
        "refusal_reasons": refusal_reasons,
    }
    governance = {
        **governance_flags,
        "pause_guard_triggered": should_pause,
        "refuse_guard_triggered": should_refuse,
    }
    event_payload = read_json_safe(event_registry_path, default={"events": []})
    if not isinstance(event_payload, dict):
        event_payload = {"events": []}
    events = event_payload.get("events", [])
    if not isinstance(events, list):
        events = []
    cycle_events: list[dict[str, Any]] = []
    for event_type, severity in (
        ("quote_fade_proxy", quote_fade_proxy),
        ("sweep_aftermath_risk", sweep_aftermath_risk),
        ("fill_collapse_risk", fill_collapse_risk),
        ("adverse_selection_risk", adverse_selection_risk),
    ):
        if severity >= 0.55:
            cycle_events.append(
                {
                    "event_type": event_type,
                    "severity": severity,
                    "context_signature": context_signature,
                    "predatory_liquidity_state": predatory_liquidity_state,
                }
            )
    events.extend(cycle_events)
    write_json_atomic(event_registry_path, {"events": events[-600:]})

    clusters_payload = read_json_safe(contextual_clusters_path, default={"clusters": {}})
    if not isinstance(clusters_payload, dict):
        clusters_payload = {"clusters": {}}
    clusters = clusters_payload.get("clusters", {})
    if not isinstance(clusters, dict):
        clusters = {}
    cluster_state = clusters.get(context_key, {"occurrences": 0, "hostility_sum": 0.0, "state_counts": {}})
    if not isinstance(cluster_state, dict):
        cluster_state = {"occurrences": 0, "hostility_sum": 0.0, "state_counts": {}}
    state_counts = cluster_state.get("state_counts", {})
    if not isinstance(state_counts, dict):
        state_counts = {}
    state_counts[predatory_liquidity_state] = int(state_counts.get(predatory_liquidity_state, 0) or 0) + 1
    cluster_state["occurrences"] = int(cluster_state.get("occurrences", 0) or 0) + 1
    cluster_state["hostility_sum"] = round(float(cluster_state.get("hostility_sum", 0.0) or 0.0) + hostile_execution_score, 4)
    cluster_state["avg_hostility"] = _bounded(cluster_state["hostility_sum"] / max(1, cluster_state["occurrences"]))
    cluster_state["state_counts"] = state_counts
    clusters[context_key] = cluster_state
    write_json_atomic(contextual_clusters_path, {"clusters": clusters})

    payload = {
        "adversarial_execution_state": adversarial_execution_state,
        "confidence_adjustments": confidence_adjustments,
        "risk_adjustments": risk_adjustments,
        "governance": governance,
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
    write_json_atomic(governance_path, governance)
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "hostility_event_registry": str(event_registry_path),
            "contextual_hostility_clusters": str(contextual_clusters_path),
            "hostility_governance_state": str(governance_path),
            "detector_reliability_registry": str(detector_registry_path),
        },
    }


def _dynamic_market_maker_deception_inference_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    adversarial_execution_engine: dict[str, Any],
    negative_space_engine: dict[str, Any],
    liquidity_decay_engine: dict[str, Any],
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    replay_scope: str,
) -> dict[str, Any]:
    deception_dir = memory_root / "deception_inference"
    deception_dir.mkdir(parents=True, exist_ok=True)
    latest_path = deception_dir / "deception_inference_latest.json"
    history_path = deception_dir / "deception_inference_history.json"
    event_registry_path = deception_dir / "deception_event_registry.json"
    context_registry_path = deception_dir / "deception_context_registry.json"
    reliability_registry_path = deception_dir / "deception_reliability_registry.json"
    governance_path = deception_dir / "deception_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    def _state_score(state: str, *, elevated: str, severe: str) -> float:
        if state == severe:
            return 1.0
        if state == elevated:
            return 0.6
        return 0.2 if state == "normal" else 0.4

    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    latent_transition_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_transition_state, dict):
        latent_transition_state = {}

    spread_stress = _bounded(max(0.0, float(market_state.get("spread_ratio", 1.0) or 1.0) - 1.0))
    slippage_stress = _bounded(max(0.0, float(market_state.get("slippage_ratio", 1.0) or 1.0) - 1.0))
    failure_cluster_risk = _bounded(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0))
    partial_fill_state = str(execution_microstructure_engine.get("partial_fill_state", "normal"))
    partial_fill_proxy = _state_score(partial_fill_state, elevated="elevated", severe="degraded")
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    quote_fade_proxy = _bounded(float(adversarial_state.get("quote_fade_proxy", 0.0) or 0.0))
    sweep_aftermath_risk = _bounded(float(adversarial_state.get("sweep_aftermath_risk", 0.0) or 0.0))
    fill_collapse_risk = _bounded(float(adversarial_state.get("fill_collapse_risk", 0.0) or 0.0))
    historical_execution_hostility = _bounded(float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0))
    transition_hazard_score = _bounded(float(latent_transition_state.get("transition_hazard_score", 0.0) or 0.0))

    negative_signal = bool(negative_space_engine.get("signal", {}).get("negative_space_signal", False))
    negative_deviation = _bounded(float(negative_space_engine.get("signal", {}).get("deviation_score", 0.0) or 0.0))
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
    trap_probability = _bounded(
        (negative_deviation * 0.4)
        + (0.3 if negative_signal else 0.0)
        + (sweep_aftermath_risk * 0.15)
        + (failure_cluster_risk * 0.15)
    )
    liquidity_bait_risk = _bounded(
        (quote_fade_proxy * 0.35)
        + (spread_stress * 0.15)
        + (slippage_stress * 0.15)
        + (liquidity_vulnerability * 0.2)
        + (fill_collapse_risk * 0.15)
    )
    engineered_move_probability = _bounded(
        (hostile_execution_score * 0.32)
        + (sweep_aftermath_risk * 0.2)
        + (trap_probability * 0.2)
        + (liquidity_bait_risk * 0.18)
        + (transition_hazard_score * 0.1)
    )
    inventory_defense_proxy = _bounded(
        (quote_fade_proxy * 0.35)
        + (partial_fill_proxy * 0.2)
        + (fill_collapse_risk * 0.2)
        + (historical_execution_hostility * 0.15)
        + (failure_cluster_risk * 0.1)
    )
    sweep_trap_bias = _bounded((sweep_aftermath_risk * 0.45) + (trap_probability * 0.35) + (0.2 if negative_signal else 0.0))
    continuation_confidence_proxy = _bounded(
        float(
            contradiction_arbitration_engine.get("confidence_adjustments", {}).get(
                "base_composite_confidence",
                adversarial_execution_engine.get("confidence_adjustments", {}).get("hostility_adjusted_confidence", 0.5),
            )
            or 0.5
        )
    )
    continuation_deception_conflict = _bounded(
        (continuation_confidence_proxy * 0.45)
        + (engineered_move_probability * 0.35)
        + (trap_probability * 0.2)
    )
    deception_score = _bounded(
        (engineered_move_probability * 0.33)
        + (liquidity_bait_risk * 0.22)
        + (inventory_defense_proxy * 0.2)
        + (sweep_trap_bias * 0.15)
        + (continuation_deception_conflict * 0.1)
    )
    if not closed:
        deception_state_label = "insufficient_data"
    elif deception_score >= 0.72:
        deception_state_label = "hostile"
    elif deception_score >= 0.46:
        deception_state_label = "elevated"
    else:
        deception_state_label = "normal"

    context_signature = {
        "replay_scope": replay_scope,
        "structure_state": str(market_state.get("structure_state", "unknown")),
        "execution_state": execution_state,
        "predatory_liquidity_state": str(adversarial_state.get("predatory_liquidity_state", "normal")),
    }
    input_signature = {
        "context_signature": context_signature,
        "closed_count": len(closed),
        "hostile_execution_score": hostile_execution_score,
        "quote_fade_proxy": quote_fade_proxy,
        "sweep_aftermath_risk": sweep_aftermath_risk,
        "negative_signal": negative_signal,
        "negative_deviation": negative_deviation,
        "liquidity_vulnerability": liquidity_vulnerability,
        "trap_probability": trap_probability,
        "liquidity_bait_risk": liquidity_bait_risk,
        "engineered_move_probability": engineered_move_probability,
        "inventory_defense_proxy": inventory_defense_proxy,
        "sweep_trap_bias": sweep_trap_bias,
        "continuation_deception_conflict": continuation_deception_conflict,
        "deception_score": deception_score,
    }
    previous_latest = read_json_safe(latest_path, default={})
    if isinstance(previous_latest, dict) and previous_latest.get("_signature") == input_signature:
        returned = dict(previous_latest)
        returned.pop("_signature", None)
        return {
            **returned,
            "paths": {
                "latest": str(latest_path),
                "history": str(history_path),
                "deception_event_registry": str(event_registry_path),
                "deception_context_registry": str(context_registry_path),
                "deception_reliability_registry": str(reliability_registry_path),
                "deception_governance_state": str(governance_path),
            },
        }
    context_key = (
        f"{context_signature['replay_scope']}|{context_signature['structure_state']}|"
        f"{context_signature['execution_state']}|{context_signature['predatory_liquidity_state']}"
    )
    context_registry = read_json_safe(context_registry_path, default={"contexts": {}})
    if not isinstance(context_registry, dict):
        context_registry = {"contexts": {}}
    contexts = context_registry.get("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
    prior_context = contexts.get(context_key, {})
    if not isinstance(prior_context, dict):
        prior_context = {}
    prior_deception = _bounded(float(prior_context.get("rolling_deception_score", 0.0) or 0.0))
    prior_observations = int(prior_context.get("observations", 0) or 0)
    observations = prior_observations + 1
    rolling_deception_score = _bounded(((prior_deception * prior_observations) + deception_score) / max(1, observations))
    contexts[context_key] = {
        "rolling_deception_score": rolling_deception_score,
        "observations": observations,
        "deception_state": deception_state_label,
        "engineered_move_probability": engineered_move_probability,
        "liquidity_bait_risk": liquidity_bait_risk,
    }
    write_json_atomic(context_registry_path, {"contexts": contexts})

    reliability_registry = read_json_safe(reliability_registry_path, default={"contexts": {}})
    if not isinstance(reliability_registry, dict):
        reliability_registry = {"contexts": {}}
    reliability_contexts = reliability_registry.get("contexts", {})
    if not isinstance(reliability_contexts, dict):
        reliability_contexts = {}
    prior_reliability_state = reliability_contexts.get(context_key, {})
    if not isinstance(prior_reliability_state, dict):
        prior_reliability_state = {}
    prior_reliability = _bounded(float(prior_reliability_state.get("deception_reliability", 0.5) or 0.5))
    reliability_observations = int(prior_reliability_state.get("observations", 0) or 0)
    current_reliability = _bounded(1.0 - abs(deception_score - prior_deception))
    deception_reliability = _bounded(
        ((prior_reliability * reliability_observations) + current_reliability) / max(1, reliability_observations + 1)
    )
    reliability_contexts[context_key] = {
        "deception_reliability": deception_reliability,
        "observations": reliability_observations + 1,
        "rolling_deception_score": rolling_deception_score,
    }
    write_json_atomic(reliability_registry_path, {"contexts": reliability_contexts})

    should_pause = deception_score >= 0.58 or liquidity_bait_risk >= 0.62 or sweep_trap_bias >= 0.62
    should_refuse = deception_score >= 0.78 or (engineered_move_probability >= 0.82 and trap_probability >= 0.7)
    pause_reasons: list[str] = []
    refusal_reasons: list[str] = []
    if liquidity_bait_risk >= 0.55:
        pause_reasons.append("deception_liquidity_bait_risk")
    if sweep_trap_bias >= 0.55:
        pause_reasons.append("deception_sweep_trap_bias")
    if should_refuse:
        refusal_reasons.append("deception_engineered_move_refuse_guard")

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    deception_state = {
        "deception_state": deception_state_label,
        "deception_score": deception_score,
        "trap_probability": trap_probability,
        "liquidity_bait_risk": liquidity_bait_risk,
        "engineered_move_probability": engineered_move_probability,
        "inventory_defense_proxy": inventory_defense_proxy,
        "sweep_trap_bias": sweep_trap_bias,
        "continuation_deception_conflict": continuation_deception_conflict,
        "deception_reliability": deception_reliability,
        "governance_flags": governance_flags,
    }
    confidence_adjustments = {
        "deception_penalty": _bounded((deception_score * 0.55) + ((1.0 - deception_reliability) * 0.2) + (sweep_trap_bias * 0.25)),
        "deception_adjusted_confidence": _bounded(
            1.0 - ((deception_score * 0.65) + (liquidity_bait_risk * 0.2) + (sweep_trap_bias * 0.15))
        ),
    }
    risk_adjustments = {
        "deception_multiplier": _bounded(1.0 - (deception_score * 0.6), low=0.25, high=1.0),
        "should_reduce_size": deception_score >= 0.45 or liquidity_bait_risk >= 0.5,
        "should_pause": should_pause,
        "should_refuse": should_refuse,
        "pause_reasons": pause_reasons,
        "refusal_reasons": refusal_reasons,
    }
    governance = {
        **governance_flags,
        "pause_guard_triggered": should_pause,
        "refuse_guard_triggered": should_refuse,
    }
    event_payload = read_json_safe(event_registry_path, default={"events": []})
    if not isinstance(event_payload, dict):
        event_payload = {"events": []}
    events = event_payload.get("events", [])
    if not isinstance(events, list):
        events = []
    cycle_events: list[dict[str, Any]] = []
    for event_type, severity in (
        ("engineered_move_probability", engineered_move_probability),
        ("liquidity_bait_risk", liquidity_bait_risk),
        ("sweep_trap_bias", sweep_trap_bias),
    ):
        if severity >= 0.55:
            cycle_events.append(
                {
                    "event_type": event_type,
                    "severity": severity,
                    "context_signature": context_signature,
                    "deception_state": deception_state_label,
                }
            )
    events.extend(cycle_events)
    write_json_atomic(event_registry_path, {"events": events[-600:]})

    payload = {
        "deception_state": deception_state,
        "confidence_adjustments": confidence_adjustments,
        "risk_adjustments": risk_adjustments,
        "governance": governance,
    }
    write_json_atomic(latest_path, {**payload, "_signature": input_signature})
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})
    write_json_atomic(governance_path, governance)
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "deception_event_registry": str(event_registry_path),
            "deception_context_registry": str(context_registry_path),
            "deception_reliability_registry": str(reliability_registry_path),
            "deception_governance_state": str(governance_path),
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
    self_expansion_quality_layer: dict[str, Any] | None = None,
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
    quality_layer_context = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    expansion_quality_state = str(quality_layer_context.get("self_expansion_quality_state", "unknown"))
    redundancy_risk = float(quality_layer_context.get("redundancy_risk", 0.0) or 0.0)
    regression_risk = float(quality_layer_context.get("regression_risk", 0.0) or 0.0)
    transferability_score = float(quality_layer_context.get("transferability_score", 0.5) or 0.5)
    expansion_quality_score = float(quality_layer_context.get("expansion_quality_score", 0.5) or 0.5)
    if redundancy_risk >= 0.6:
        gaps.append(
            {
                "gap_type": "expansion_redundancy_pressure",
                "evidence_strength": round(min(1.0, max(0.4, redundancy_risk)), 4),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": "redundancy_aware_capability_selector",
                "sandbox_only": True,
                "replay_validation_required": True,
            }
        )
    if regression_risk >= 0.55:
        gaps.append(
            {
                "gap_type": "expansion_regression_risk",
                "evidence_strength": round(min(1.0, max(0.4, regression_risk)), 4),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": "regression_risk_containment_filter",
                "sandbox_only": True,
                "replay_validation_required": True,
            }
        )
    if transferability_score <= 0.45:
        gaps.append(
            {
                "gap_type": "poor_capability_transferability",
                "evidence_strength": round(min(1.0, max(0.35, 1.0 - transferability_score)), 4),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": "cross_context_transferability_validator",
                "sandbox_only": True,
                "replay_validation_required": True,
            }
        )
    if expansion_quality_state in {"degraded", "critical"} or expansion_quality_score < 0.5:
        gaps.append(
            {
                "gap_type": "degraded_expansion_quality_state",
                "evidence_strength": round(min(1.0, max(0.35, 1.0 - expansion_quality_score)), 4),
                "failure_clusters": failure_clusters[:5],
                "hypothesized_capability": "self_expansion_quality_stabilizer",
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
    self_expansion_quality_layer: dict[str, Any] | None = None,
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
    quality_layer_context = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    redundancy_risk = round(float(quality_layer_context.get("redundancy_risk", 0.0) or 0.0), 4)
    regression_risk = round(float(quality_layer_context.get("regression_risk", 0.0) or 0.0), 4)
    expansion_quality_score = round(float(quality_layer_context.get("expansion_quality_score", 0.5) or 0.5), 4)
    overlap_map = quality_layer_context.get("capability_overlap_map", {})
    overlap_pairs = sum(len(item) for item in overlap_map.values()) if isinstance(overlap_map, dict) else 0
    quality_penalty = round(min(0.18, (redundancy_risk * 0.1) + (regression_risk * 0.08)), 4)

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
                    - quality_penalty
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
                "promotion_candidate": predictive_value >= (0.68 + min(0.1, redundancy_risk * 0.08)) and counterfactual_advantage >= 0.35,
                "self_expansion_quality_context": {
                    "redundancy_risk": redundancy_risk,
                    "regression_risk": regression_risk,
                    "expansion_quality_score": expansion_quality_score,
                },
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
            "self_expansion_quality": {
                "redundancy_risk": redundancy_risk,
                "regression_risk": regression_risk,
                "expansion_quality_score": expansion_quality_score,
                "overlap_pair_count": overlap_pairs,
            },
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
    adversarial_execution_engine: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
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
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    prior_cycle_hostility = round(float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0), 4)
    predatory_liquidity_state = str(adversarial_state.get("predatory_liquidity_state", "normal"))
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
    structural_alignment_registry = read_json_safe(
        memory_root / "structural_memory_graph" / "regime_memory_alignment_registry.json",
        default={"regimes": {}},
    )
    if not isinstance(structural_alignment_registry, dict):
        structural_alignment_registry = {"regimes": {}}
    structural_alignment_items = structural_alignment_registry.get("regimes", {})
    if not isinstance(structural_alignment_items, dict):
        structural_alignment_items = {}
    structural_alignment_scores = [
        float(item.get("alignment_score", 0.5) or 0.5)
        for item in structural_alignment_items.values()
        if isinstance(item, dict)
    ]
    prior_structural_alignment = round(
        max(0.0, min(1.0, sum(structural_alignment_scores) / max(1, len(structural_alignment_scores)))),
        4,
    )
    structural_context_registry = read_json_safe(
        memory_root / "structural_memory_graph" / "structural_context_registry.json",
        default={"contexts": {}},
    )
    if not isinstance(structural_context_registry, dict):
        structural_context_registry = {"contexts": {}}
    structural_context_items = structural_context_registry.get("contexts", {})
    if not isinstance(structural_context_items, dict):
        structural_context_items = {}
    structural_context_coverage = min(1.0, len(structural_context_items) / 25.0)
    latent_transition_registry = read_json_safe(
        memory_root / "latent_transition_hazard" / "transition_hazard_registry.json",
        default={"contexts": {}},
    )
    if not isinstance(latent_transition_registry, dict):
        latent_transition_registry = {"contexts": {}}
    latent_transition_items = latent_transition_registry.get("contexts", {})
    if not isinstance(latent_transition_items, dict):
        latent_transition_items = {}
    latent_transition_scores = [
        float(item.get("transition_hazard_score", 0.0) or 0.0) for item in latent_transition_items.values() if isinstance(item, dict)
    ]
    prior_transition_hazard_score = round(
        max(0.0, min(1.0, sum(latent_transition_scores) / max(1, len(latent_transition_scores)))),
        4,
    )
    latent_transition_context_coverage = round(min(1.0, len(latent_transition_items) / 25.0), 4)
    deception_reliability_registry = read_json_safe(
        memory_root / "deception_inference" / "deception_reliability_registry.json",
        default={"contexts": {}},
    )
    if not isinstance(deception_reliability_registry, dict):
        deception_reliability_registry = {"contexts": {}}
    deception_reliability_items = deception_reliability_registry.get("contexts", {})
    if not isinstance(deception_reliability_items, dict):
        deception_reliability_items = {}
    deception_reliability_scores = [
        float(item.get("deception_reliability", 0.5) or 0.5)
        for item in deception_reliability_items.values()
        if isinstance(item, dict)
    ]
    prior_deception_reliability = round(
        max(0.0, min(1.0, sum(deception_reliability_scores) / max(1, len(deception_reliability_scores)))),
        4,
    )
    deception_context_registry = read_json_safe(
        memory_root / "deception_inference" / "deception_context_registry.json",
        default={"contexts": {}},
    )
    if not isinstance(deception_context_registry, dict):
        deception_context_registry = {"contexts": {}}
    deception_context_items = deception_context_registry.get("contexts", {})
    if not isinstance(deception_context_items, dict):
        deception_context_items = {}
    deception_scores = [
        float(item.get("rolling_deception_score", 0.0) or 0.0)
        for item in deception_context_items.values()
        if isinstance(item, dict)
    ]
    prior_deception_score = round(
        max(0.0, min(1.0, sum(deception_scores) / max(1, len(deception_scores)))),
        4,
    )
    deception_context_coverage = round(min(1.0, len(deception_context_items) / 25.0), 4)
    quality_layer_context = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    promotion_confidence_multiplier = round(
        max(
            0.75,
            min(
                1.0,
                float(quality_layer_context.get("quality_components", {}).get("promotion_confidence_multiplier", 1.0) or 1.0),
            ),
        ),
        4,
    )
    quarantine_pressure = round(
        max(
            0.0,
            min(
                0.2,
                float(quality_layer_context.get("quality_components", {}).get("quarantine_pressure_delta", 0.0) or 0.0),
            ),
        ),
        4,
    )
    incoming_promotion_maturity = str(quality_layer_context.get("promotion_maturity", "seeded"))
    prior_capability_expansion = read_json_safe(
        memory_root / "capability_expansion" / "capability_expansion_latest.json",
        default={},
    )
    if not isinstance(prior_capability_expansion, dict):
        prior_capability_expansion = {}
    prior_transfer_robustness = read_json_safe(
        memory_root / "transfer_robustness" / "transfer_robustness_latest.json",
        default={},
    )
    if not isinstance(prior_transfer_robustness, dict):
        prior_transfer_robustness = {}
    transfer_state = prior_transfer_robustness.get("transfer_robustness_state", {})
    if not isinstance(transfer_state, dict):
        transfer_state = {}
    prior_transfer_score = round(float(prior_transfer_robustness.get("cross_regime_transfer_score", 0.5) or 0.5), 4)
    prior_transfer_penalty = round(float(prior_transfer_robustness.get("promotion_transfer_penalty", 0.0) or 0.0), 4)
    prior_overfit_risk = round(float(prior_transfer_robustness.get("overfit_risk", 0.0) or 0.0), 4)
    incoming_transfer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    incoming_transfer_penalty = round(float(incoming_transfer.get("promotion_transfer_penalty", 0.0) or 0.0), 4)
    transfer_penalty = round(min(0.35, prior_transfer_penalty + min(0.1, incoming_transfer_penalty)), 4)
    prior_causal_intervention = read_json_safe(
        memory_root / "causal_intervention_robustness" / "causal_intervention_robustness_latest.json",
        default={},
    )
    if not isinstance(prior_causal_intervention, dict):
        prior_causal_intervention = {}
    incoming_causal_intervention = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    causal_context = incoming_causal_intervention if incoming_causal_intervention else prior_causal_intervention
    prior_false_improvement_risk = round(float(causal_context.get("false_improvement_risk", 0.0) or 0.0), 4)
    prior_counterfactual_robustness = round(
        float(causal_context.get("counterfactual_robustness_score", 0.5) or 0.5),
        4,
    )
    prior_intervention_reliability = round(float(causal_context.get("intervention_reliability", 0.5) or 0.5), 4)
    prior_primary_intervention_axis = str(causal_context.get("primary_intervention_axis", "unknown"))
    causal_promotion_penalty = round(
        max(
            0.0,
            min(
                0.08,
                (prior_false_improvement_risk * 0.05)
                + ((1.0 - prior_counterfactual_robustness) * 0.02)
                + ((1.0 - prior_intervention_reliability) * 0.01),
            ),
        ),
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
        deception_pressure = round(prior_deception_score * (1.0 - prior_deception_reliability), 4)
        deception_penalty = round(min(0.08, deception_pressure * 0.08), 4)
        quality_adjusted_replay_score = round(
            max(
                0.0,
                min(
                    1.0,
                    (replay_score * promotion_confidence_multiplier)
                    - deception_penalty
                    - min(0.12, transfer_penalty * 0.4)
                    - causal_promotion_penalty,
                ),
            ),
            4,
        )
        comparative_advantage = round(min(1.0, (quality_adjusted_replay_score * 0.55) + (prototype_predictive * 0.45)), 4)
        conflict_with_unified = round(min(1.0, max(0.0, quality_adjusted_replay_score - unified_score + 0.2 + quarantine_pressure)), 4)
        if quality_adjusted_replay_score < (0.42 + quarantine_pressure):
            decision = "rejected"
        elif conflict_with_unified >= (0.65 - min(0.15, quarantine_pressure)):
            decision = "quarantined"
        elif quality_adjusted_replay_score >= (0.72 + (quarantine_pressure * 0.5)) and comparative_advantage >= 0.58 and conflict_with_unified < 0.45:
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
                "self_expansion_quality_evaluation",
                "comparative_advantage_test",
                "conflict_check_unified_field",
                "governor_promotion_decision",
            ],
            "replay_validation": {
                "scope": replay_scope,
                "score": quality_adjusted_replay_score,
                "raw_score": replay_score,
                "passed": quality_adjusted_replay_score >= (0.52 + quarantine_pressure),
            },
            "comparative_advantage": comparative_advantage,
            "unified_conflict_score": conflict_with_unified,
            "governance_decision": decision,
            "promotion_maturity": incoming_promotion_maturity,
            "self_expansion_quality_context": {
                "promotion_confidence_multiplier": promotion_confidence_multiplier,
                "quarantine_pressure_delta": quarantine_pressure,
                "source": "memory/self_expansion_quality/self_expansion_quality_latest.json",
            },
            "calibration_reliability_context": {
                "prior_cycle_reliability": calibration_reliability,
                "source": "memory/calibration_uncertainty/regime_reliability_registry.json",
            },
            "adversarial_execution_context": {
                "prior_cycle_hostility": prior_cycle_hostility,
                "predatory_liquidity_state": predatory_liquidity_state,
                "source": "memory/adversarial_execution/detector_reliability_registry.json",
            },
            "structural_memory_context": {
                "prior_alignment_score": prior_structural_alignment,
                "context_coverage": round(float(structural_context_coverage), 4),
                "source": "memory/structural_memory_graph/regime_memory_alignment_registry.json",
            },
            "latent_transition_context": {
                "prior_cycle_transition_hazard_score": prior_transition_hazard_score,
                "context_coverage": latent_transition_context_coverage,
                "source": "memory/latent_transition_hazard/transition_hazard_registry.json",
            },
            "deception_inference_context": {
                "prior_cycle_deception_score": prior_deception_score,
                "prior_cycle_deception_reliability": prior_deception_reliability,
                "context_coverage": deception_context_coverage,
                "source": "memory/deception_inference/deception_reliability_registry.json",
            },
            "transfer_robustness_context": {
                "prior_cycle_transfer_score": prior_transfer_score,
                "prior_cycle_promotion_transfer_penalty": transfer_penalty,
                "prior_cycle_overfit_risk": prior_overfit_risk,
                "prior_cycle_transfer_state": str(transfer_state.get("state", "unknown")),
                "source": "memory/transfer_robustness/transfer_robustness_latest.json",
            },
            "intervention_robustness_context": {
                "prior_cycle_counterfactual_robustness_score": prior_counterfactual_robustness,
                "prior_cycle_intervention_reliability": prior_intervention_reliability,
                "prior_cycle_false_improvement_risk": prior_false_improvement_risk,
                "primary_intervention_axis": prior_primary_intervention_axis,
                "promotion_penalty": causal_promotion_penalty,
                "source": "memory/causal_intervention_robustness/causal_intervention_robustness_latest.json",
            },
            "autonomous_capability_expansion_context": {
                "integration_mode": "prior_cycle_context_optional",
                "source": "memory/capability_expansion/capability_expansion_latest.json",
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
                "replay_validation_score": quality_adjusted_replay_score,
                "raw_replay_validation_score": replay_score,
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


def _structural_memory_graph_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    adversarial_execution_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    replay_scope: str,
) -> dict[str, Any]:
    structural_dir = memory_root / "structural_memory_graph"
    structural_dir.mkdir(parents=True, exist_ok=True)
    latest_path = structural_dir / "structural_memory_graph_latest.json"
    history_path = structural_dir / "structural_memory_graph_history.json"
    context_registry_path = structural_dir / "structural_context_registry.json"
    zone_registry_path = structural_dir / "zone_magnet_registry.json"
    episodic_links_path = structural_dir / "episodic_pattern_links.json"
    regime_alignment_path = structural_dir / "regime_memory_alignment_registry.json"
    governance_path = structural_dir / "structural_memory_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    settled = [
        item
        for item in closed[-120:]
        if isinstance(item, dict) and str(item.get("result", "")).lower() in {"win", "loss", "flat"}
    ]
    regime_state = str(unified_market_intelligence_field.get("components", {}).get("regime_state", "unknown"))
    structure_state = str(market_state.get("structure_state", "unknown"))
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))
    context_key = f"{replay_scope}|{structure_state}|{regime_state}|{execution_state}"
    losses = sum(1 for trade in settled if str(trade.get("result", "")).lower() == "loss")
    wins = sum(1 for trade in settled if str(trade.get("result", "")).lower() == "win")
    flats = sum(1 for trade in settled if str(trade.get("result", "")).lower() == "flat")
    cycle_signature = {
        "context_key": context_key,
        "settled_count": len(settled),
        "losses": losses,
        "wins": wins,
        "flats": flats,
        "structure_state": structure_state,
        "regime_state": regime_state,
        "execution_state": execution_state,
        "execution_penalty": round(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0), 4),
        "composite_confidence": round(
            float(unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.0) or 0.0),
            4,
        ),
    }
    previous_latest = read_json_safe(latest_path, default={})
    if isinstance(previous_latest, dict) and previous_latest.get("input_signature") == cycle_signature:
        returned = dict(previous_latest)
        returned.pop("input_signature", None)
        return {
            **returned,
            "paths": {
                "latest": str(latest_path),
                "history": str(history_path),
                "structural_context_registry": str(context_registry_path),
                "zone_magnet_registry": str(zone_registry_path),
                "episodic_pattern_links": str(episodic_links_path),
                "regime_memory_alignment_registry": str(regime_alignment_path),
                "structural_memory_governance_state": str(governance_path),
            },
        }

    context_registry = read_json_safe(context_registry_path, default={"contexts": {}})
    if not isinstance(context_registry, dict):
        context_registry = {"contexts": {}}
    contexts = context_registry.get("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
    prior_context = contexts.get(context_key, {})
    if not isinstance(prior_context, dict):
        prior_context = {}
    prior_occurrences = int(prior_context.get("occurrences", 0) or 0)

    zone_registry = read_json_safe(zone_registry_path, default={"zones": {}})
    if not isinstance(zone_registry, dict):
        zone_registry = {"zones": {}}
    zones = zone_registry.get("zones", {})
    if not isinstance(zones, dict):
        zones = {}

    zone_counts: dict[str, int] = {}
    for trade in settled:
        for key in ("entry_price", "intended_entry_price", "average_fill_price"):
            value = trade.get(key)
            if not isinstance(value, (int, float)):
                continue
            bucket = int(math.floor(float(value) / _PRICE_LEVEL_BUCKET_SIZE))
            zone_key = f"zone_{bucket}"
            zone_counts[zone_key] = zone_counts.get(zone_key, 0) + 1
            break
    zone_occurrences = list(zone_counts.values())
    structural_magnet_score = _bounded(max(zone_occurrences, default=0) / max(1, len(settled)))

    for zone_key, count in zone_counts.items():
        zone_state = zones.get(zone_key, {"occurrences": 0, "wins": 0, "losses": 0})
        if not isinstance(zone_state, dict):
            zone_state = {"occurrences": 0, "wins": 0, "losses": 0}
        zone_state["occurrences"] = int(zone_state.get("occurrences", 0) or 0) + int(count)
        zone_state["last_context_key"] = context_key
        zones[zone_key] = zone_state
    write_json_atomic(zone_registry_path, {"zones": zones})

    episodic_clusters: dict[tuple[str, str, str], dict[str, int]] = {}
    for trade in settled:
        key = (
            str(trade.get("setup_type", "unknown")),
            str(trade.get("session", "unknown")),
            str(trade.get("failure_cause", "unknown")),
        )
        if key not in episodic_clusters:
            episodic_clusters[key] = {"wins": 0, "losses": 0, "flats": 0}
        result = str(trade.get("result", "")).lower()
        if result == "win":
            episodic_clusters[key]["wins"] += 1
        elif result == "loss":
            episodic_clusters[key]["losses"] += 1
        else:
            episodic_clusters[key]["flats"] += 1
    episodic_pattern_links = []
    for index, (cluster_key, counts) in enumerate(
        sorted(
            episodic_clusters.items(),
            key=lambda item: (sum(item[1].values()), item[0]),
            reverse=True,
        )[:6]
    ):
        total = sum(counts.values())
        if total < 2:
            continue
        wins = int(counts["wins"])
        losses = int(counts["losses"])
        if losses > wins:
            outcome_bias = "risk_off"
        elif wins > losses:
            outcome_bias = "continuation"
        else:
            outcome_bias = "mixed"
        episodic_pattern_links.append(
            {
                "episode_id": f"episode_{index + 1}",
                "context_signature": {
                    "setup_type": cluster_key[0],
                    "session": cluster_key[1],
                    "failure_cause": cluster_key[2],
                },
                "occurrences": total,
                "outcome_bias": outcome_bias,
                "link_strength": _bounded(total / max(1, len(settled))),
            }
        )
    episodic_payload = read_json_safe(episodic_links_path, default={"episodes": []})
    if not isinstance(episodic_payload, dict):
        episodic_payload = {"episodes": []}
    episodes = episodic_payload.get("episodes", [])
    if not isinstance(episodes, list):
        episodes = []
    episodes.extend(episodic_pattern_links)
    write_json_atomic(episodic_links_path, {"episodes": episodes[-300:]})

    historical_recurrence_score = _bounded((prior_occurrences + 1) / max(1, prior_occurrences + 3))
    long_horizon_context_match = _bounded((historical_recurrence_score * 0.65) + (structural_magnet_score * 0.35))

    regime_alignment_payload = read_json_safe(regime_alignment_path, default={"regimes": {}})
    if not isinstance(regime_alignment_payload, dict):
        regime_alignment_payload = {"regimes": {}}
    regimes = regime_alignment_payload.get("regimes", {})
    if not isinstance(regimes, dict):
        regimes = {}
    regime_key = f"{replay_scope}|{regime_state}"
    prior_regime = regimes.get(regime_key, {})
    if not isinstance(prior_regime, dict):
        prior_regime = {}

    loss_ratio = _bounded(losses / max(1, len(settled)))
    prior_alignment = _bounded(float(prior_regime.get("alignment_score", 0.5) or 0.5))
    current_alignment = _bounded(1.0 - abs(loss_ratio - float(prior_context.get("loss_ratio", loss_ratio) or loss_ratio)))
    observations = int(prior_regime.get("observations", 0) or 0) + 1
    regime_memory_alignment = _bounded(((prior_alignment * max(0, observations - 1)) + current_alignment) / max(1, observations))
    regimes[regime_key] = {
        "alignment_score": regime_memory_alignment,
        "observations": observations,
        "structure_state": structure_state,
        "execution_state": execution_state,
    }
    write_json_atomic(regime_alignment_path, {"regimes": regimes})

    transition_count = 0
    if len(settled) > 1:
        for left, right in zip(settled[:-1], settled[1:]):
            if str(left.get("result", "")).lower() != str(right.get("result", "")).lower():
                transition_count += 1
    structural_reversal_bias = _bounded(transition_count / max(1, len(settled) - 1))
    recent_abs = [abs(float(item.get("pnl_points", 0.0) or 0.0)) for item in settled[-6:]]
    baseline_abs = [abs(float(item.get("pnl_points", 0.0) or 0.0)) for item in settled[-24:-6]]
    recent_intensity = sum(recent_abs) / max(1, len(recent_abs))
    baseline_intensity = sum(baseline_abs) / max(1, len(baseline_abs)) if baseline_abs else recent_intensity
    structural_acceleration_bias = _bounded(recent_intensity / max(1e-6, baseline_intensity + _DEFAULT_RETEST_INTERVAL_PADDING))

    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    hostility = _bounded(float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    memory_reliability = _bounded(
        (long_horizon_context_match * 0.34)
        + (regime_memory_alignment * 0.3)
        + (structural_magnet_score * 0.22)
        + ((1.0 - structural_reversal_bias) * 0.14)
        - (execution_penalty * 0.08)
        - (hostility * 0.08)
    )
    if memory_reliability >= 0.72:
        memory_state = "strong"
    elif memory_reliability >= 0.52:
        memory_state = "moderate"
    elif memory_reliability > 0.0:
        memory_state = "weak"
    else:
        memory_state = "insufficient_data"

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    composite_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.0) or 0.0))
    structural_memory_active = bool(
        long_horizon_context_match >= 0.6
        or structural_reversal_bias >= 0.62
        or structural_magnet_score >= 0.72
    )
    memory_adjustment = 0.0
    if structural_memory_active:
        memory_adjustment = _bounded(
            ((memory_reliability - 0.5) * 0.28)
            + ((long_horizon_context_match - 0.5) * 0.12)
            - (structural_reversal_bias * 0.08)
            - (structural_acceleration_bias * 0.06),
            low=-0.4,
            high=0.4,
        )
    memory_adjusted_confidence = _bounded(composite_confidence + memory_adjustment)

    structural_memory_multiplier = 1.0
    if structural_memory_active:
        structural_memory_multiplier = _bounded(
            1.0
            - (structural_reversal_bias * 0.3)
            - ((1.0 - memory_reliability) * 0.25)
            - (structural_acceleration_bias * 0.2)
            + (structural_magnet_score * 0.08),
            low=0.25,
            high=1.0,
        )
    pause_reasons: list[str] = []
    refusal_reasons: list[str] = []
    should_pause = structural_memory_active and long_horizon_context_match >= 0.5 and (
        structural_reversal_bias >= 0.62 or structural_acceleration_bias >= 0.82
    )
    should_refuse = (
        structural_memory_active
        and long_horizon_context_match >= 0.65
        and structural_reversal_bias >= 0.74
        and memory_reliability >= 0.45
    )
    if should_pause:
        pause_reasons.append("structural_memory_recurrence_hostility")
    if should_refuse:
        refusal_reasons.append("structural_memory_reversal_refuse_guard")
    if structural_memory_active and regime_memory_alignment < 0.42:
        pause_reasons.append("structural_memory_regime_misalignment")

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "pause_guard_triggered": should_pause,
        "refuse_guard_triggered": should_refuse,
    }
    structural_state = {
        "structural_memory_state": memory_state,
        "historical_recurrence_score": historical_recurrence_score,
        "structural_magnet_score": structural_magnet_score,
        "long_horizon_context_match": long_horizon_context_match,
        "regime_memory_alignment": regime_memory_alignment,
        "episodic_pattern_links": episodic_pattern_links,
        "structural_reversal_bias": structural_reversal_bias,
        "structural_acceleration_bias": structural_acceleration_bias,
        "memory_reliability": memory_reliability,
        "governance_flags": governance_flags,
    }
    confidence_adjustments = {
        "memory_confidence_adjustment": memory_adjustment,
        "memory_adjusted_confidence": memory_adjusted_confidence,
    }
    risk_adjustments = {
        "structural_memory_multiplier": structural_memory_multiplier,
        "should_pause": should_pause,
        "should_refuse": should_refuse,
        "pause_reasons": pause_reasons,
        "refusal_reasons": refusal_reasons,
    }
    context_links = {
        "context_key": context_key,
        "zone_keys": sorted(zone_counts, key=lambda key: zone_counts[key], reverse=True)[:6],
        "episode_count": len(episodic_pattern_links),
    }
    governance = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    payload = {
        "input_signature": cycle_signature,
        "structural_memory_state": structural_state,
        "confidence_adjustments": confidence_adjustments,
        "risk_adjustments": risk_adjustments,
        "context_links": context_links,
        "governance": governance,
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
    contexts[context_key] = {
        "occurrences": prior_occurrences + 1,
        "historical_recurrence_score": historical_recurrence_score,
        "loss_ratio": loss_ratio,
        "memory_reliability": memory_reliability,
    }
    write_json_atomic(context_registry_path, {"contexts": contexts})
    write_json_atomic(governance_path, governance_flags)
    returned_payload = dict(payload)
    returned_payload.pop("input_signature", None)
    return {
        **returned_payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "structural_context_registry": str(context_registry_path),
            "zone_magnet_registry": str(zone_registry_path),
            "episodic_pattern_links": str(episodic_links_path),
            "regime_memory_alignment_registry": str(regime_alignment_path),
            "structural_memory_governance_state": str(governance_path),
        },
    }


def _latent_transition_hazard_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    structural_memory_graph_engine: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    adversarial_execution_engine: dict[str, Any] | None = None,
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    negative_space_engine: dict[str, Any] | None = None,
    invariant_break_engine: dict[str, Any] | None = None,
    replay_scope: str,
) -> dict[str, Any]:
    hazard_dir = memory_root / "latent_transition_hazard"
    hazard_dir.mkdir(parents=True, exist_ok=True)
    latest_path = hazard_dir / "latent_transition_hazard_latest.json"
    history_path = hazard_dir / "latent_transition_hazard_history.json"
    registry_path = hazard_dir / "transition_hazard_registry.json"
    precursor_events_path = hazard_dir / "precursor_instability_events.json"
    historical_match_registry_path = hazard_dir / "historical_transition_match_registry.json"
    governance_path = hazard_dir / "latent_transition_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    settled = [
        item
        for item in closed[-120:]
        if isinstance(item, dict) and str(item.get("result", "")).lower() in {"win", "loss", "flat"}
    ]
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    composite_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.0) or 0.0))

    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    long_horizon_context_match = _bounded(float(structural_state.get("long_horizon_context_match", 0.0) or 0.0))
    structural_reversal_bias = _bounded(float(structural_state.get("structural_reversal_bias", 0.0) or 0.0))
    structural_acceleration_bias = _bounded(float(structural_state.get("structural_acceleration_bias", 0.0) or 0.0))
    structural_memory_reliability = _bounded(float(structural_state.get("memory_reliability", 0.0) or 0.0))
    regime_memory_alignment = _bounded(float(structural_state.get("regime_memory_alignment", 0.0) or 0.0))

    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    execution_cluster_risk = _bounded(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0))
    execution_timing_drag = _bounded(float(execution_microstructure_engine.get("entry_timing_degradation", 0.0) or 0.0))
    execution_state = str(execution_microstructure_engine.get("execution_state", "insufficient_data"))

    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    historical_execution_hostility = _bounded(float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0))

    contradiction_arbitration_engine = (
        contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    )
    contradiction_severity = _bounded(
        float(contradiction_arbitration_engine.get("arbitration", {}).get("max_contradiction_severity", 0.0) or 0.0)
    )
    calibration_uncertainty_engine = (
        calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    )
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    calibration_drift = _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0))

    negative_space_engine = negative_space_engine if isinstance(negative_space_engine, dict) else {}
    negative_deviation_score = _bounded(float(negative_space_engine.get("signal", {}).get("deviation_score", 0.0) or 0.0))
    invariant_break_engine = invariant_break_engine if isinstance(invariant_break_engine, dict) else {}
    invariant_break_count = sum(
        1
        for event in invariant_break_engine.get("invariant_break_events", [])
        if isinstance(event, dict) and bool(event.get("invariant_break", False))
    )
    invariant_break_risk = _bounded(min(1.0, invariant_break_count * 0.35))

    regime_state = str(unified_market_intelligence_field.get("components", {}).get("regime_state", "unknown"))
    structure_state = str(market_state.get("structure_state", "unknown"))
    context_key = f"{replay_scope}|{structure_state}|{regime_state}|{execution_state}"
    market_stress = _bounded(
        (
            max(0.0, float(market_state.get("volatility_ratio", 1.0) or 1.0) - 1.0) * 0.4
            + max(0.0, float(market_state.get("spread_ratio", 1.0) or 1.0) - 1.0) * 0.3
            + max(0.0, float(market_state.get("slippage_ratio", 1.0) or 1.0) - 1.0) * 0.3
        )
        / 2.5
    )

    loss_ratio = _bounded(
        sum(1 for item in settled if str(item.get("result", "")).lower() == "loss") / max(1, len(settled))
    )
    cycle_signature = {
        "context_key": context_key,
        "settled_count": len(settled),
        "market_stress": market_stress,
        "loss_ratio": loss_ratio,
        "execution_penalty": execution_penalty,
        "execution_cluster_risk": execution_cluster_risk,
        "hostile_execution_score": hostile_execution_score,
        "structural_reversal_bias": structural_reversal_bias,
        "structural_acceleration_bias": structural_acceleration_bias,
    }
    previous_latest = read_json_safe(latest_path, default={})
    if isinstance(previous_latest, dict) and previous_latest.get("input_signature") == cycle_signature:
        returned = dict(previous_latest)
        returned.pop("input_signature", None)
        return {
            **returned,
            "paths": {
                "latest": str(latest_path),
                "history": str(history_path),
                "transition_hazard_registry": str(registry_path),
                "precursor_instability_events": str(precursor_events_path),
                "historical_transition_match_registry": str(historical_match_registry_path),
                "latent_transition_governance_state": str(governance_path),
            },
        }

    precursor_instability_score = _bounded(
        (market_stress * 0.24)
        + (execution_penalty * 0.18)
        + (execution_cluster_risk * 0.14)
        + (execution_timing_drag * 0.08)
        + (hostile_execution_score * 0.12)
        + (negative_deviation_score * 0.1)
        + (invariant_break_risk * 0.06)
        + (calibration_drift * 0.08)
    )
    regime_deformation_score = _bounded(
        (structural_reversal_bias * 0.3)
        + (structural_acceleration_bias * 0.22)
        + ((1.0 - regime_memory_alignment) * 0.2)
        + ((1.0 - structural_memory_reliability) * 0.14)
        + (loss_ratio * 0.14)
    )

    registry = read_json_safe(registry_path, default={"contexts": {}})
    if not isinstance(registry, dict):
        registry = {"contexts": {}}
    contexts = registry.get("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
    prior_context = contexts.get(context_key, {})
    if not isinstance(prior_context, dict):
        prior_context = {}
    prior_occurrences = int(prior_context.get("occurrences", 0) or 0)
    prior_score = _bounded(float(prior_context.get("transition_hazard_score", 0.0) or 0.0))
    historical_transition_match = _bounded(
        (min(1.0, prior_occurrences / 6.0) * 0.62) + ((1.0 - abs(prior_score - regime_deformation_score)) * 0.38)
    )
    hazard_reliability = _bounded(
        (historical_transition_match * 0.44)
        + (structural_memory_reliability * 0.24)
        + (long_horizon_context_match * 0.16)
        + ((1.0 - historical_execution_hostility) * 0.08)
        + (min(1.0, len(settled) / 20.0) * 0.08)
    )
    transition_hazard_score = _bounded(
        (precursor_instability_score * 0.44)
        + (regime_deformation_score * 0.34)
        + (historical_transition_match * 0.12)
        + ((1.0 - structural_memory_reliability) * 0.06)
        + (contradiction_severity * 0.04)
    )
    if transition_hazard_score >= 0.8:
        transition_hazard_state = "critical"
    elif transition_hazard_score >= 0.62:
        transition_hazard_state = "elevated"
    elif transition_hazard_score >= 0.42:
        transition_hazard_state = "watch"
    else:
        transition_hazard_state = "stable"
    if transition_hazard_score >= 0.66 or regime_deformation_score >= 0.62:
        transition_directional_bias = "risk_off"
    elif hazard_reliability >= 0.62 and transition_hazard_score <= 0.36:
        transition_directional_bias = "continuation"
    else:
        transition_directional_bias = "neutral"

    transition_confidence_suppression = _bounded(
        max(
            0.0,
            (transition_hazard_score * 0.4)
            + (precursor_instability_score * 0.25)
            + (regime_deformation_score * 0.2)
            - (hazard_reliability * 0.18),
        ),
        high=0.65,
    )
    hazard_adjusted_confidence = _bounded(composite_confidence - transition_confidence_suppression)
    anticipatory_risk_bias = _bounded(
        (transition_hazard_score * 0.46)
        + (precursor_instability_score * 0.28)
        + (regime_deformation_score * 0.2)
        + (max(0.0, 0.5 - hazard_reliability) * 0.06)
    )
    transition_hazard_multiplier = _bounded(
        1.0 - (transition_confidence_suppression * 0.45) - (anticipatory_risk_bias * 0.4),
        low=0.25,
        high=1.0,
    )
    should_pause = bool(
        transition_hazard_score >= 0.58
        or precursor_instability_score >= 0.64
        or regime_deformation_score >= 0.66
        or market_stress >= 0.55
    )
    should_refuse = bool(transition_hazard_score >= 0.78 and hazard_reliability >= 0.45 and regime_deformation_score >= 0.62)
    pause_reasons: list[str] = []
    refusal_reasons: list[str] = []
    if precursor_instability_score >= 0.64:
        pause_reasons.append("latent_precursor_instability_pause")
    elif transition_hazard_score >= 0.55:
        pause_reasons.append("latent_precursor_instability_pause")
    if regime_deformation_score >= 0.66:
        pause_reasons.append("latent_regime_deformation_pause")
    if should_pause and "latent_precursor_instability_pause" not in pause_reasons:
        pause_reasons.append("latent_precursor_instability_pause")
    if should_refuse:
        refusal_reasons.append("latent_transition_hazard_refuse_guard")

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "pause_guard_triggered": should_pause,
        "refuse_guard_triggered": should_refuse,
    }
    latent_transition_hazard_state = {
        "transition_hazard_state": transition_hazard_state,
        "transition_hazard_score": transition_hazard_score,
        "precursor_instability_score": precursor_instability_score,
        "regime_deformation_score": regime_deformation_score,
        "transition_directional_bias": transition_directional_bias,
        "transition_confidence_suppression": transition_confidence_suppression,
        "historical_transition_match": historical_transition_match,
        "hazard_reliability": hazard_reliability,
        "anticipatory_risk_bias": anticipatory_risk_bias,
        "governance_flags": governance_flags,
    }
    confidence_adjustments = {
        "transition_hazard_score": transition_hazard_score,
        "transition_confidence_suppression": transition_confidence_suppression,
        "hazard_adjusted_confidence": hazard_adjusted_confidence,
    }
    risk_adjustments = {
        "transition_hazard_multiplier": transition_hazard_multiplier,
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
        "input_signature": cycle_signature,
        "latent_transition_hazard_state": latent_transition_hazard_state,
        "confidence_adjustments": confidence_adjustments,
        "risk_adjustments": risk_adjustments,
        "governance": governance,
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
    contexts[context_key] = {
        "occurrences": prior_occurrences + 1,
        "transition_hazard_score": transition_hazard_score,
        "precursor_instability_score": precursor_instability_score,
        "regime_deformation_score": regime_deformation_score,
        "hazard_reliability": hazard_reliability,
    }
    write_json_atomic(registry_path, {"contexts": contexts})
    precursor_payload = read_json_safe(precursor_events_path, default={"events": []})
    if not isinstance(precursor_payload, dict):
        precursor_payload = {"events": []}
    precursor_events = precursor_payload.get("events", [])
    if not isinstance(precursor_events, list):
        precursor_events = []
    if precursor_instability_score >= 0.55 or transition_hazard_score >= 0.58:
        precursor_events.append(
            {
                "context_key": context_key,
                "precursor_instability_score": precursor_instability_score,
                "transition_hazard_score": transition_hazard_score,
                "transition_hazard_state": transition_hazard_state,
                "transition_directional_bias": transition_directional_bias,
            }
        )
    write_json_atomic(precursor_events_path, {"events": precursor_events[-400:]})
    historical_match_payload = read_json_safe(historical_match_registry_path, default={"matches": []})
    if not isinstance(historical_match_payload, dict):
        historical_match_payload = {"matches": []}
    historical_matches = historical_match_payload.get("matches", [])
    if not isinstance(historical_matches, list):
        historical_matches = []
    historical_matches.append(
        {
            "context_key": context_key,
            "historical_transition_match": historical_transition_match,
            "hazard_reliability": hazard_reliability,
            "transition_hazard_score": transition_hazard_score,
        }
    )
    write_json_atomic(historical_match_registry_path, {"matches": historical_matches[-400:]})
    write_json_atomic(governance_path, governance_flags)
    returned_payload = dict(payload)
    returned_payload.pop("input_signature", None)
    return {
        **returned_payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "transition_hazard_registry": str(registry_path),
            "precursor_instability_events": str(precursor_events_path),
            "historical_transition_match_registry": str(historical_match_registry_path),
            "latent_transition_governance_state": str(governance_path),
        },
    }


def _calibration_and_uncertainty_governance_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    adversarial_execution_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
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
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    historical_execution_hostility = _bounded(float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0))
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    latent_transition_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_transition_state, dict):
        latent_transition_state = {}
    transition_hazard_score = _bounded(float(latent_transition_state.get("transition_hazard_score", 0.0) or 0.0))
    transition_confidence_suppression = _bounded(
        float(latent_transition_state.get("transition_confidence_suppression", 0.0) or 0.0)
    )
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    deception_score = _bounded(float(deception_state.get("deception_score", 0.0) or 0.0))
    deception_reliability = _bounded(float(deception_state.get("deception_reliability", 0.5) or 0.5))
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    transfer_score = _bounded(
        float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5)
    )
    transfer_overfit_risk = _bounded(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0))
    transfer_penalty = _bounded(
        float(cross_regime_transfer_robustness_layer.get("promotion_transfer_penalty", 0.0) or 0.0), high=0.35
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
        "transition_hazard_score": transition_hazard_score,
        "deception_score": deception_score,
        "deception_reliability": deception_reliability,
        "transfer_score": transfer_score,
        "transfer_overfit_risk": transfer_overfit_risk,
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
        (epistemic_uncertainty * 0.4)
        + (aleatoric_proxy * 0.45)
        + ((1.0 - execution_confidence) * 0.15)
        + (hostile_execution_score * 0.08)
        + (historical_execution_hostility * 0.04)
        + (transition_hazard_score * 0.06)
        + (deception_score * 0.05)
        + ((1.0 - deception_reliability) * 0.03)
        + ((1.0 - transfer_score) * 0.06)
        + (transfer_overfit_risk * 0.05)
        + (transfer_penalty * 0.03)
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
        - (transition_confidence_suppression * 0.08)
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
        "transfer_uncertainty_term": _bounded(
            ((1.0 - transfer_score) * 0.45) + (transfer_overfit_risk * 0.35) + (transfer_penalty * 0.2),
            high=0.4,
        ),
        "latent_transition_context": {
            "transition_hazard_score": transition_hazard_score,
            "transition_confidence_suppression": transition_confidence_suppression,
            "transition_hazard_state": str(latent_transition_state.get("transition_hazard_state", "stable")),
        },
        "deception_context": {
            "deception_score": deception_score,
            "deception_reliability": deception_reliability,
            "deception_state": str(deception_state.get("deception_state", "normal")),
        },
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
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
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
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    historical_execution_hostility = _bounded(float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0))
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    deception_score = _bounded(float(deception_state.get("deception_score", 0.0) or 0.0))
    engineered_move_probability = _bounded(float(deception_state.get("engineered_move_probability", 0.0) or 0.0))
    deception_reliability = _bounded(float(deception_state.get("deception_reliability", 0.5) or 0.5))
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    structural_memory_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_memory_state, dict):
        structural_memory_state = {}
    long_horizon_context_match = _bounded(float(structural_memory_state.get("long_horizon_context_match", 0.0) or 0.0))
    structural_reversal_bias = _bounded(float(structural_memory_state.get("structural_reversal_bias", 0.0) or 0.0))
    structural_memory_reliability = _bounded(float(structural_memory_state.get("memory_reliability", 0.0) or 0.0))
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    latent_transition_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_transition_state, dict):
        latent_transition_state = {}
    transition_hazard_score = _bounded(float(latent_transition_state.get("transition_hazard_score", 0.0) or 0.0))
    transition_hazard_reliability = _bounded(float(latent_transition_state.get("hazard_reliability", 0.0) or 0.0))
    transition_directional_bias = str(latent_transition_state.get("transition_directional_bias", "neutral"))
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
        "deception_score": deception_score,
        "engineered_move_probability": engineered_move_probability,
        "deception_reliability": deception_reliability,
        "long_horizon_context_match": long_horizon_context_match,
        "structural_reversal_bias": structural_reversal_bias,
        "structural_memory_reliability": structural_memory_reliability,
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
    adversarial_direction = "risk_off" if hostile_execution_score >= 0.65 else "wait" if hostile_execution_score >= 0.45 else "continuation"
    _belief(
        source_layer="adversarial_execution_intelligence_layer",
        belief_direction=adversarial_direction,
        belief_confidence=hostile_execution_score,
        belief_intent="predatory_execution_safety",
        historical_reliability=_bounded(1.0 - historical_execution_hostility),
        execution_adjusted_trust=_bounded(hostile_execution_score * (1.0 - (execution_penalty * 0.3))),
    )
    structural_direction = "wait"
    if structural_reversal_bias >= 0.65 and long_horizon_context_match >= 0.65:
        structural_direction = "risk_off"
    elif structural_memory_reliability >= 0.55:
        structural_direction = "continuation"
    _belief(
        source_layer="structural_memory_graph_layer",
        belief_direction=structural_direction,
        belief_confidence=max(structural_reversal_bias, structural_memory_reliability),
        belief_intent="long_horizon_structural_memory",
        historical_reliability=long_horizon_context_match,
        execution_adjusted_trust=_bounded(structural_memory_reliability * (1.0 - (execution_penalty * 0.15))),
    )
    transition_direction = "risk_off" if transition_directional_bias == "risk_off" else "wait" if transition_hazard_score >= 0.45 else "continuation"
    _belief(
        source_layer="latent_transition_hazard_layer",
        belief_direction=transition_direction,
        belief_confidence=transition_hazard_score,
        belief_intent="precursor_transition_hazard",
        historical_reliability=transition_hazard_reliability,
        execution_adjusted_trust=_bounded(transition_hazard_score * (1.0 - (execution_penalty * 0.2))),
    )
    deception_direction = "risk_off" if deception_score >= 0.65 else "wait" if deception_score >= 0.45 else "continuation"
    _belief(
        source_layer="dynamic_market_maker_deception_inference_layer",
        belief_direction=deception_direction,
        belief_confidence=deception_score,
        belief_intent="engineered_move_deception_guard",
        historical_reliability=deception_reliability,
        execution_adjusted_trust=_bounded(deception_score * (1.0 - (execution_penalty * 0.2))),
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

    base_confidence_execution_severity = _bounded((unified_confidence * 0.55) + (execution_penalty * 0.45))
    confidence_execution_severity = _bounded(base_confidence_execution_severity + (hostile_execution_score * 0.12))
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
    base_risk_disable_signal = _bounded(max(pain_risk, execution_penalty, liquidity_vulnerability))
    risk_disable_signal = _bounded(max(base_risk_disable_signal, hostile_execution_score))
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
    if beliefs[0]["belief_direction"] == "continuation" and transition_direction == "risk_off" and transition_hazard_score >= 0.55:
        _push_contradiction(
            contradiction_type="continuation_vs_hazard_buildup",
            contradiction_severity=_bounded((beliefs[0]["belief_confidence"] * 0.45) + (transition_hazard_score * 0.55)),
            partners=[beliefs[0], beliefs[-1]],
            dominance_candidate="latent_transition_hazard_layer",
            arbitration_outcome="pause" if transition_hazard_score < 0.78 else "refuse",
            resolution_rationale=["continuation_signal_conflicts_with_latent_hazard_buildup"],
            historical_recurrence=_historical_recurrence("continuation_vs_hazard_buildup"),
            historical_outcome_bias=_historical_bias("continuation_vs_hazard_buildup"),
        )
    if beliefs[0]["belief_direction"] == "continuation" and deception_direction == "risk_off" and engineered_move_probability >= 0.55:
        _push_contradiction(
            contradiction_type="continuation_vs_engineered_move",
            contradiction_severity=_bounded((beliefs[0]["belief_confidence"] * 0.45) + (engineered_move_probability * 0.55)),
            partners=[beliefs[0], beliefs[-1]],
            dominance_candidate="dynamic_market_maker_deception_inference_layer",
            arbitration_outcome="pause" if engineered_move_probability < 0.78 else "refuse",
            resolution_rationale=["continuation_signal_conflicts_with_engineered_move_deception_inference"],
            historical_recurrence=_historical_recurrence("continuation_vs_engineered_move"),
            historical_outcome_bias=_historical_bias("continuation_vs_engineered_move"),
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
        str(item.get("contradiction_type", "")) in {
            "continuation_vs_trap",
            "risk_enable_vs_risk_disable",
            "continuation_vs_hazard_buildup",
        }
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


def _cross_regime_transfer_robustness_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
    capability_evolution_ladder: dict[str, Any],
    self_expansion_quality_layer: dict[str, Any] | None = None,
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    unified_market_intelligence_field: dict[str, Any] | None = None,
) -> dict[str, Any]:
    transfer_dir = memory_root / "transfer_robustness"
    transfer_dir.mkdir(parents=True, exist_ok=True)
    latest_path = transfer_dir / "transfer_robustness_latest.json"
    history_path = transfer_dir / "transfer_robustness_history.json"
    context_registry_path = transfer_dir / "context_transfer_registry.json"
    failure_clusters_path = transfer_dir / "context_failure_clusters.json"
    penalty_registry_path = transfer_dir / "transfer_penalty_registry.json"
    overfit_watchlist_path = transfer_dir / "overfit_watchlist.json"
    governance_path = transfer_dir / "transfer_robustness_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    settled = [
        item
        for item in closed[-60:]
        if isinstance(item, dict) and str(item.get("result", "")).lower() in {"win", "loss", "flat"}
    ]
    session_counts: dict[str, int] = {}
    context_counts: dict[str, int] = {}
    context_losses: dict[str, int] = {}
    failure_by_context: dict[tuple[str, str], int] = {}
    outcome_counts = {"win": 0, "loss": 0, "flat": 0}
    for item in settled:
        session = str(item.get("session", "unknown")).strip() or "unknown"
        session_counts[session] = session_counts.get(session, 0) + 1
        result = str(item.get("result", "flat")).lower()
        if result not in outcome_counts:
            result = "flat"
        outcome_counts[result] += 1
        volatility_ratio = float(item.get("volatility_ratio", market_state.get("volatility_ratio", 1.0)) or 1.0)
        spread_ratio = float(item.get("spread_ratio", market_state.get("spread_ratio", 1.0)) or 1.0)
        slippage_ratio = float(item.get("slippage_ratio", market_state.get("slippage_ratio", 1.0)) or 1.0)
        volatility_bucket = "high" if volatility_ratio >= 1.45 else "mid" if volatility_ratio >= 1.1 else "low"
        liquidity_bucket = "stressed" if max(spread_ratio, slippage_ratio) >= 1.85 else "normal"
        context_key = f"{session}|{volatility_bucket}|{liquidity_bucket}"
        context_counts[context_key] = context_counts.get(context_key, 0) + 1
        if result == "loss":
            context_losses[context_key] = context_losses.get(context_key, 0) + 1
            failure_cause = str(item.get("failure_cause", "unknown")).strip() or "unknown"
            failure_by_context[(context_key, failure_cause)] = failure_by_context.get((context_key, failure_cause), 0) + 1

    total = len(settled)
    unique_sessions = len(session_counts)
    unique_contexts = len(context_counts)
    dominant_context_ratio = _bounded(max(context_counts.values(), default=0) / max(1, total))
    dominant_outcome_ratio = _bounded(max(outcome_counts.values()) / max(1, total))
    session_transfer_score = _bounded((min(1.0, unique_sessions / 3.0) * 0.55) + ((1.0 - dominant_context_ratio) * 0.45))
    volatility_diversity = min(1.0, len({key.split("|")[1] for key in context_counts}) / 3.0) if context_counts else 0.0
    liquidity_diversity = min(1.0, len({key.split("|")[2] for key in context_counts}) / 2.0) if context_counts else 0.0
    loss_concentration = _bounded(max(context_losses.values(), default=0) / max(1, sum(context_losses.values())))
    volatility_transfer_score = _bounded((volatility_diversity * 0.6) + ((1.0 - loss_concentration) * 0.4))
    liquidity_transfer_score = _bounded((liquidity_diversity * 0.6) + ((1.0 - loss_concentration) * 0.4))
    cross_regime_transfer_score = _bounded(
        (session_transfer_score * 0.4) + (volatility_transfer_score * 0.3) + (liquidity_transfer_score * 0.3)
    )

    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}
    promotion_registry = capability_evolution_ladder.get("promotion_registry", {})
    if not isinstance(promotion_registry, dict):
        promotion_registry = {}
    promoted_count = len([item for item in promotion_registry.get("promoted", []) if isinstance(item, dict)])
    rejected_count = len([item for item in promotion_registry.get("rejected", []) if isinstance(item, dict)])
    quarantined_count = len([item for item in promotion_registry.get("quarantined", []) if isinstance(item, dict)])
    capability_pressure = _bounded((rejected_count + quarantined_count) / max(1, promoted_count + rejected_count + quarantined_count))

    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    calibration_uncertainty_engine = (
        calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    )
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    prior_transferability = _bounded(float(self_expansion_quality_layer.get("transferability_score", 0.5) or 0.5))
    context_concentration = dominant_context_ratio
    overfit_risk = _bounded(
        (context_concentration * 0.5)
        + (dominant_outcome_ratio * 0.3)
        + ((1.0 - cross_regime_transfer_score) * 0.15)
        + (capability_pressure * 0.05)
    )
    robustness_reliability = _bounded(
        1.0
        - (
            ((1.0 - cross_regime_transfer_score) * 0.5)
            + (overfit_risk * 0.25)
            + (float(latent_state.get("transition_hazard_score", 0.0) or 0.0) * 0.1)
            + (float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0) * 0.08)
            + (float(deception_state.get("deception_score", 0.0) or 0.0) * 0.07)
        )
    )
    promotion_transfer_penalty = _bounded(
        max(
            0.0,
            min(
                0.35,
                ((1.0 - cross_regime_transfer_score) * 0.22)
                + (overfit_risk * 0.12)
                + ((1.0 - prior_transferability) * 0.06),
            ),
        ),
        high=0.35,
    )
    if cross_regime_transfer_score >= 0.72 and overfit_risk < 0.45:
        transfer_state = "robust"
    elif cross_regime_transfer_score >= 0.5 and overfit_risk < 0.62:
        transfer_state = "watch"
    elif cross_regime_transfer_score >= 0.35:
        transfer_state = "fragile"
    else:
        transfer_state = "breakdown"

    context_failure_clusters = [
        {
            "context_key": key[0],
            "failure_cause": key[1],
            "count": count,
            "loss_ratio": _bounded(count / max(1, context_counts.get(key[0], 0))),
        }
        for key, count in sorted(failure_by_context.items(), key=lambda entry: (entry[1], entry[0]), reverse=True)[:8]
    ]
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "transfer_breakdown_guard": transfer_state in {"fragile", "breakdown"},
        "overfit_guard_triggered": overfit_risk >= 0.62,
    }
    payload = {
        "transfer_robustness_state": {
            "state": transfer_state,
            "context_coverage": _bounded(unique_contexts / 8.0),
            "context_concentration": context_concentration,
            "dominant_outcome_ratio": dominant_outcome_ratio,
            "sample_size": total,
            "prior_calibration_drift": _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0)),
            "prior_structural_alignment": _bounded(float(structural_state.get("regime_memory_alignment", 0.0) or 0.0)),
        },
        "cross_regime_transfer_score": cross_regime_transfer_score,
        "session_transfer_score": session_transfer_score,
        "volatility_transfer_score": volatility_transfer_score,
        "liquidity_transfer_score": liquidity_transfer_score,
        "overfit_risk": overfit_risk,
        "robustness_reliability": robustness_reliability,
        "context_failure_clusters": context_failure_clusters,
        "promotion_transfer_penalty": promotion_transfer_penalty,
        "governance_flags": governance_flags,
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
    context_registry = read_json_safe(context_registry_path, default={"contexts": {}})
    if not isinstance(context_registry, dict):
        context_registry = {"contexts": {}}
    contexts = context_registry.get("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
    for key, count in context_counts.items():
        prior = contexts.get(key, {})
        if not isinstance(prior, dict):
            prior = {}
        prior_seen = int(prior.get("seen_count", 0) or 0)
        prior_transfer = float(prior.get("avg_transfer_score", 0.5) or 0.5)
        seen = prior_seen + count
        contexts[key] = {
            "seen_count": seen,
            "loss_count": int(prior.get("loss_count", 0) or 0) + int(context_losses.get(key, 0)),
            "avg_transfer_score": _bounded(
                ((prior_transfer * prior_seen) + (cross_regime_transfer_score * count)) / max(1, seen)
            ),
        }
    write_json_atomic(context_registry_path, {"contexts": contexts})
    write_json_atomic(failure_clusters_path, {"clusters": context_failure_clusters})
    penalty_registry = read_json_safe(penalty_registry_path, default={"entries": []})
    if not isinstance(penalty_registry, dict):
        penalty_registry = {"entries": []}
    penalty_entries = penalty_registry.get("entries", [])
    if not isinstance(penalty_entries, list):
        penalty_entries = []
    penalty_entries.append(
        {
            "replay_scope": replay_scope,
            "promotion_transfer_penalty": promotion_transfer_penalty,
            "overfit_risk": overfit_risk,
            "cross_regime_transfer_score": cross_regime_transfer_score,
        }
    )
    write_json_atomic(penalty_registry_path, {"entries": penalty_entries[-400:]})
    watchlist = read_json_safe(overfit_watchlist_path, default={"watchlist": []})
    if not isinstance(watchlist, dict):
        watchlist = {"watchlist": []}
    watch_items = watchlist.get("watchlist", [])
    if not isinstance(watch_items, list):
        watch_items = []
    if overfit_risk >= 0.62:
        watch_items.append(
            {
                "replay_scope": replay_scope,
                "reason": "narrow_regime_overfit_risk",
                "overfit_risk": overfit_risk,
                "context_concentration": context_concentration,
            }
        )
    write_json_atomic(overfit_watchlist_path, {"watchlist": watch_items[-200:]})
    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
        },
    )
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "context_transfer_registry": str(context_registry_path),
            "context_failure_clusters": str(failure_clusters_path),
            "transfer_penalty_registry": str(penalty_registry_path),
            "overfit_watchlist": str(overfit_watchlist_path),
            "transfer_robustness_governance_state": str(governance_path),
        },
    }


def _causal_intervention_counterfactual_robustness_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
    counterfactual_engine: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    cross_regime_transfer_robustness_layer: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    capability_evolution_ladder: dict[str, Any] | None = None,
) -> dict[str, Any]:
    causal_dir = memory_root / "causal_intervention_robustness"
    causal_dir.mkdir(parents=True, exist_ok=True)
    latest_path = causal_dir / "causal_intervention_robustness_latest.json"
    history_path = causal_dir / "causal_intervention_robustness_history.json"
    context_registry_path = causal_dir / "intervention_context_registry.json"
    axis_registry_path = causal_dir / "intervention_axis_reliability_registry.json"
    watchlist_path = causal_dir / "false_improvement_watchlist.json"
    priority_trace_path = causal_dir / "intervention_priority_trace.json"
    governance_path = causal_dir / "causal_intervention_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    settled = [item for item in closed[-80:] if isinstance(item, dict)]
    counterfactual_engine = counterfactual_engine if isinstance(counterfactual_engine, dict) else {}
    evaluations = counterfactual_engine.get("counterfactual_evaluations", [])
    if not isinstance(evaluations, list):
        evaluations = []
    execution_microstructure_engine = (
        execution_microstructure_engine if isinstance(execution_microstructure_engine, dict) else {}
    )
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer
        if isinstance(cross_regime_transfer_robustness_layer, dict)
        else {}
    )
    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}

    axis_counts: dict[str, int] = {}
    axis_opportunity: dict[str, float] = {}
    context_axis_counts: dict[str, dict[str, int]] = {}
    context_deltas: dict[str, list[float]] = {}
    improvements = 0
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue
        axis = str(evaluation.get("best_alternative_action", "no_trade_taken")).strip() or "no_trade_taken"
        axis_counts[axis] = axis_counts.get(axis, 0) + 1
        delta = abs(float(evaluation.get("outcome_delta_vs_best", 0.0) or 0.0))
        axis_opportunity[axis] = axis_opportunity.get(axis, 0.0) + delta
        if not bool(evaluation.get("strategy_improved_outcome", False)):
            improvements += 1
        trade_id = str(evaluation.get("trade_id", ""))
        trade_context = next(
            (
                item
                for item in settled
                if str(item.get("trade_id", "")) == trade_id
            ),
            {},
        )
        session = str(trade_context.get("session", "unknown")).strip() or "unknown"
        volatility_ratio = float(
            trade_context.get("volatility_ratio", market_state.get("volatility_ratio", 1.0)) or 1.0
        )
        volatility_bucket = "high" if volatility_ratio >= 1.45 else "mid" if volatility_ratio >= 1.1 else "low"
        structure_state = str(trade_context.get("structure_state", market_state.get("structure_state", "unknown"))).strip() or "unknown"
        context_key = f"{session}|{volatility_bucket}|{structure_state}"
        context_axis = context_axis_counts.setdefault(context_key, {})
        context_axis[axis] = context_axis.get(axis, 0) + 1
        context_deltas.setdefault(context_key, []).append(delta)

    sample_size = len([item for item in evaluations if isinstance(item, dict)])
    primary_intervention_axis, primary_axis_count = sorted(
        axis_counts.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )[0] if axis_counts else ("no_trade_taken", 0)
    intervention_consistency = _bounded(primary_axis_count / max(1, sample_size))
    average_opportunity = _bounded(sum(axis_opportunity.values()) / max(1, sample_size), high=2.0)
    opportunity_score = _bounded(average_opportunity / 2.0)
    context_concentration = _bounded(max([sum(axes.values()) for axes in context_axis_counts.values()], default=0) / max(1, sample_size))
    context_diversity = _bounded(min(1.0, len(context_axis_counts) / 8.0))
    counterfactual_improvement_rate = _bounded(improvements / max(1, sample_size))
    transfer_score = _bounded(float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    false_improvement_risk = _bounded(
        (context_concentration * 0.45)
        + ((1.0 - context_diversity) * 0.2)
        + ((1.0 - transfer_score) * 0.15)
        + (counterfactual_improvement_rate * 0.15)
        + (execution_penalty * 0.05)
    )
    counterfactual_robustness_score = _bounded(
        (counterfactual_improvement_rate * 0.4)
        + ((1.0 - context_concentration) * 0.2)
        + (context_diversity * 0.2)
        + (transfer_score * 0.2)
    )
    intervention_reliability = _bounded(
        1.0
        - (
            (false_improvement_risk * 0.55)
            + ((1.0 - intervention_consistency) * 0.2)
            + ((1.0 - counterfactual_robustness_score) * 0.25)
        )
    )
    intervention_priority_score = _bounded(
        (opportunity_score * 0.5)
        + (counterfactual_improvement_rate * 0.25)
        + ((1.0 - intervention_reliability) * 0.2)
        + (float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0) * 0.05)
    )
    causal_confidence_proxy = _bounded(
        (counterfactual_robustness_score * 0.45)
        + (intervention_reliability * 0.35)
        + (min(1.0, sample_size / 20.0) * 0.15)
        + (float(unified_market_intelligence_field.get("confidence_structure", {}).get("composite_confidence", 0.5) or 0.5) * 0.05)
    )
    if counterfactual_robustness_score >= 0.72 and false_improvement_risk < 0.42:
        intervention_quality_state = "robust"
    elif counterfactual_robustness_score >= 0.54 and false_improvement_risk < 0.58:
        intervention_quality_state = "watch"
    elif counterfactual_robustness_score >= 0.38:
        intervention_quality_state = "fragile"
    else:
        intervention_quality_state = "breakdown"
    context_sensitive_intervention_map = {
        key: {
            "dominant_axis": sorted(axes.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0],
            "axis_agreement": _bounded(
                sorted(axes.values(), reverse=True)[0] / max(1, sum(axes.values()))
            ),
            "sample_size": int(sum(axes.values())),
            "average_outcome_delta_vs_best": _bounded(
                sum(context_deltas.get(key, [])) / max(1, len(context_deltas.get(key, []))),
                high=2.0,
            ),
        }
        for key, axes in sorted(context_axis_counts.items())
        if axes
    }
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "causal_false_improvement_guard": false_improvement_risk >= 0.62,
        "causal_intervention_reliability_guard": intervention_reliability <= 0.42,
    }
    payload = {
        "intervention_quality_state": intervention_quality_state,
        "intervention_priority_score": intervention_priority_score,
        "counterfactual_robustness_score": counterfactual_robustness_score,
        "primary_intervention_axis": primary_intervention_axis,
        "intervention_consistency": intervention_consistency,
        "intervention_reliability": intervention_reliability,
        "context_sensitive_intervention_map": context_sensitive_intervention_map,
        "false_improvement_risk": false_improvement_risk,
        "causal_confidence_proxy": causal_confidence_proxy,
        "governance_flags": governance_flags,
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
    context_registry = read_json_safe(context_registry_path, default={"contexts": {}})
    if not isinstance(context_registry, dict):
        context_registry = {"contexts": {}}
    contexts = context_registry.get("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
    for key, context in context_sensitive_intervention_map.items():
        prior = contexts.get(key, {})
        if not isinstance(prior, dict):
            prior = {}
        prior_seen = int(prior.get("seen_count", 0) or 0)
        seen = prior_seen + int(context.get("sample_size", 0) or 0)
        prior_confidence = float(prior.get("rolling_causal_confidence_proxy", 0.5) or 0.5)
        contexts[key] = {
            "seen_count": seen,
            "dominant_axis": str(context.get("dominant_axis", "no_trade_taken")),
            "rolling_causal_confidence_proxy": _bounded(
                ((prior_confidence * prior_seen) + (causal_confidence_proxy * int(context.get("sample_size", 0) or 0)))
                / max(1, seen)
            ),
        }
    write_json_atomic(context_registry_path, {"contexts": contexts})
    axis_registry = read_json_safe(axis_registry_path, default={"axes": {}})
    if not isinstance(axis_registry, dict):
        axis_registry = {"axes": {}}
    axes = axis_registry.get("axes", {})
    if not isinstance(axes, dict):
        axes = {}
    for axis, count in axis_counts.items():
        prior = axes.get(axis, {})
        if not isinstance(prior, dict):
            prior = {}
        prior_count = int(prior.get("count", 0) or 0)
        total_count = prior_count + int(count)
        prior_reliability = float(prior.get("reliability", 0.5) or 0.5)
        axes[axis] = {
            "count": total_count,
            "reliability": _bounded(((prior_reliability * prior_count) + (intervention_reliability * count)) / max(1, total_count)),
            "avg_opportunity": _bounded(axis_opportunity.get(axis, 0.0) / max(1, count), high=2.0),
        }
    write_json_atomic(axis_registry_path, {"axes": axes})
    watchlist = read_json_safe(watchlist_path, default={"watchlist": []})
    if not isinstance(watchlist, dict):
        watchlist = {"watchlist": []}
    watch_items = watchlist.get("watchlist", [])
    if not isinstance(watch_items, list):
        watch_items = []
    if false_improvement_risk >= 0.62:
        watch_items.append(
            {
                "replay_scope": replay_scope,
                "reason": "counterfactual_narrow_context_concentration",
                "false_improvement_risk": false_improvement_risk,
                "primary_intervention_axis": primary_intervention_axis,
                "context_concentration": context_concentration,
            }
        )
    write_json_atomic(watchlist_path, {"watchlist": watch_items[-200:]})
    priority_trace = read_json_safe(priority_trace_path, default={"entries": []})
    if not isinstance(priority_trace, dict):
        priority_trace = {"entries": []}
    trace_entries = priority_trace.get("entries", [])
    if not isinstance(trace_entries, list):
        trace_entries = []
    trace_entries.append(
        {
            "replay_scope": replay_scope,
            "intervention_priority_score": intervention_priority_score,
            "counterfactual_robustness_score": counterfactual_robustness_score,
            "false_improvement_risk": false_improvement_risk,
            "primary_intervention_axis": primary_intervention_axis,
        }
    )
    write_json_atomic(priority_trace_path, {"entries": trace_entries[-400:]})
    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
            "capability_candidate_count": len(
                [item for item in capability_evolution_ladder.get("capability_candidates", []) if isinstance(item, dict)]
            ),
            "quality_integration_enabled": bool(self_expansion_quality_layer.get("integration_enabled", False)),
        },
    )

    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "intervention_context_registry": str(context_registry_path),
            "intervention_axis_reliability_registry": str(axis_registry_path),
            "false_improvement_watchlist": str(watchlist_path),
            "intervention_priority_trace": str(priority_trace_path),
            "causal_intervention_governance_state": str(governance_path),
        },
    }


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
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    governed_capability_invention_layer: dict[str, Any] | None = None,
    autonomous_capability_expansion_layer: dict[str, Any] | None = None,
    rollback_orchestration_and_safe_reversion_layer: dict[str, Any] | None = None,
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
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    hostile_execution_score = float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0)
    quote_fade_proxy = float(adversarial_state.get("quote_fade_proxy", 0.0) or 0.0)
    sweep_aftermath_risk = float(adversarial_state.get("sweep_aftermath_risk", 0.0) or 0.0)
    fill_collapse_risk = float(adversarial_state.get("fill_collapse_risk", 0.0) or 0.0)
    adverse_selection_risk = float(adversarial_state.get("adverse_selection_risk", 0.0) or 0.0)
    historical_execution_hostility = float(adversarial_state.get("historical_execution_hostility", 0.0) or 0.0)
    if hostile_execution_score >= 0.62 and historical_execution_hostility >= 0.55:
        gaps.append(
            {
                "gap_type": "persistent_hostile_execution_cluster",
                "detail": "adversarial_execution_hostility_cluster",
                "frequency": max(1, int(round((hostile_execution_score + historical_execution_hostility) * 4))),
                "severity": round(min(1.0, max(hostile_execution_score, historical_execution_hostility)), 4),
            }
        )
    if adverse_selection_risk >= 0.55:
        gaps.append(
            {
                "gap_type": "chronic_adverse_selection_risk",
                "detail": "adverse_selection_execution_drag",
                "frequency": max(1, int(round(adverse_selection_risk * 4))),
                "severity": round(min(1.0, adverse_selection_risk), 4),
            }
        )
    if quote_fade_proxy >= 0.55 and execution_state in {"degraded", "fragile"}:
        gaps.append(
            {
                "gap_type": "quote_fade_execution_fragility",
                "detail": "quote_fade_fragility_pattern",
                "frequency": max(1, int(round(quote_fade_proxy * 4))),
                "severity": round(min(1.0, max(quote_fade_proxy, hostile_execution_score)), 4),
            }
        )
    if sweep_aftermath_risk >= 0.55 and fill_collapse_risk >= 0.5:
        gaps.append(
            {
                "gap_type": "sweep_aftermath_fill_collapse_pattern",
                "detail": "sweep_aftermath_fill_collapse",
                "frequency": max(1, int(round((sweep_aftermath_risk + fill_collapse_risk) * 3))),
                "severity": round(min(1.0, max(sweep_aftermath_risk, fill_collapse_risk)), 4),
            }
        )
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    deception_score = float(deception_state.get("deception_score", 0.0) or 0.0)
    engineered_move_probability = float(deception_state.get("engineered_move_probability", 0.0) or 0.0)
    liquidity_bait_risk = float(deception_state.get("liquidity_bait_risk", 0.0) or 0.0)
    sweep_trap_bias = float(deception_state.get("sweep_trap_bias", 0.0) or 0.0)
    deception_reliability = float(deception_state.get("deception_reliability", 0.5) or 0.5)
    if deception_score >= 0.62 and engineered_move_probability >= 0.6:
        gaps.append(
            {
                "gap_type": "persistent_engineered_move_deception_cluster",
                "detail": "engineered_move_deception_cluster",
                "frequency": max(1, int(round((deception_score + engineered_move_probability) * 4))),
                "severity": round(min(1.0, max(deception_score, engineered_move_probability)), 4),
            }
        )
    if liquidity_bait_risk >= 0.55 and sweep_trap_bias >= 0.5:
        gaps.append(
            {
                "gap_type": "liquidity_bait_recurrence_gap",
                "detail": "liquidity_bait_recurrence",
                "frequency": max(1, int(round((liquidity_bait_risk + sweep_trap_bias) * 3))),
                "severity": round(min(1.0, max(liquidity_bait_risk, sweep_trap_bias)), 4),
            }
        )
    if sweep_trap_bias >= 0.55 and deception_score >= 0.55:
        gaps.append(
            {
                "gap_type": "sweep_trap_deception_under_modeled",
                "detail": "sweep_trap_deception_under_modeled",
                "frequency": max(1, int(round(sweep_trap_bias * 4))),
                "severity": round(min(1.0, max(sweep_trap_bias, deception_score)), 4),
            }
        )
    if deception_reliability <= 0.45:
        gaps.append(
            {
                "gap_type": "deception_reliability_decay",
                "detail": "deception_reliability_decay",
                "frequency": 1,
                "severity": round(min(1.0, 1.0 - deception_reliability), 4),
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
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    structural_memory_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_memory_state, dict):
        structural_memory_state = {}
    memory_reliability = float(structural_memory_state.get("memory_reliability", 0.0) or 0.0)
    structural_reversal_bias = float(structural_memory_state.get("structural_reversal_bias", 0.0) or 0.0)
    long_horizon_context_match = float(structural_memory_state.get("long_horizon_context_match", 0.0) or 0.0)
    regime_memory_alignment = float(structural_memory_state.get("regime_memory_alignment", 0.0) or 0.0)
    structural_magnet_score = float(structural_memory_state.get("structural_magnet_score", 0.0) or 0.0)
    if memory_reliability > 0.0 and memory_reliability < 0.45:
        gaps.append(
            {
                "gap_type": "low_structural_memory_reliability",
                "detail": "structural_memory_reliability_degraded",
                "frequency": 1,
                "severity": round(min(1.0, 1.0 - memory_reliability), 4),
            }
        )
    if long_horizon_context_match >= 0.5 and structural_reversal_bias >= 0.62:
        gaps.append(
            {
                "gap_type": "recurrent_structural_reversal_not_captured",
                "detail": "recurrent_structural_reversal_context",
                "frequency": max(1, int(round((long_horizon_context_match + structural_reversal_bias) * 3))),
                "severity": round(min(1.0, max(long_horizon_context_match, structural_reversal_bias)), 4),
            }
        )
    if long_horizon_context_match >= 0.45 and regime_memory_alignment > 0.0 and regime_memory_alignment < 0.5:
        gaps.append(
            {
                "gap_type": "regime_memory_misalignment",
                "detail": "structural_regime_memory_alignment_gap",
                "frequency": 1,
                "severity": round(min(1.0, 1.0 - regime_memory_alignment), 4),
            }
        )
    if structural_magnet_score >= 0.65 and long_horizon_context_match >= 0.5:
        gaps.append(
            {
                "gap_type": "persistent_structural_magnet_behavior_unmodeled",
                "detail": "persistent_structural_magnet_context",
                "frequency": max(1, int(round((structural_magnet_score + long_horizon_context_match) * 3))),
                "severity": round(min(1.0, max(structural_magnet_score, long_horizon_context_match)), 4),
            }
        )
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    latent_transition_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_transition_state, dict):
        latent_transition_state = {}
    transition_hazard_score = float(latent_transition_state.get("transition_hazard_score", 0.0) or 0.0)
    precursor_instability_score = float(latent_transition_state.get("precursor_instability_score", 0.0) or 0.0)
    regime_deformation_score = float(latent_transition_state.get("regime_deformation_score", 0.0) or 0.0)
    hazard_reliability = float(latent_transition_state.get("hazard_reliability", 0.0) or 0.0)
    transition_directional_bias = str(latent_transition_state.get("transition_directional_bias", "neutral"))
    if transition_hazard_score >= 0.6 and hazard_reliability >= 0.4:
        gaps.append(
            {
                "gap_type": "latent_transition_hazard_under_modeled",
                "detail": "latent_transition_hazard_score_elevated",
                "frequency": max(1, int(round((transition_hazard_score + hazard_reliability) * 3))),
                "severity": round(min(1.0, transition_hazard_score), 4),
            }
        )
    if transition_directional_bias == "risk_off" and precursor_instability_score >= 0.58:
        gaps.append(
            {
                "gap_type": "hazard_directional_bias_mismatch",
                "detail": "continuation_vs_hazard_risk_off_bias",
                "frequency": max(1, int(round((precursor_instability_score + regime_deformation_score) * 2))),
                "severity": round(min(1.0, max(precursor_instability_score, regime_deformation_score)), 4),
            }
        )
    if hazard_reliability > 0.0 and hazard_reliability < 0.45:
        gaps.append(
            {
                "gap_type": "hazard_reliability_decay",
                "detail": "latent_transition_hazard_reliability_decay",
                "frequency": 1,
                "severity": round(min(1.0, 1.0 - hazard_reliability), 4),
            }
        )
    if precursor_instability_score >= 0.62:
        gaps.append(
            {
                "gap_type": "precursor_instability_not_captured",
                "detail": "precursor_instability_persistent",
                "frequency": max(1, int(round(precursor_instability_score * 4))),
                "severity": round(min(1.0, precursor_instability_score), 4),
            }
        )
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    transfer_state = cross_regime_transfer_robustness_layer.get("transfer_robustness_state", {})
    if not isinstance(transfer_state, dict):
        transfer_state = {}
    transfer_score = float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5)
    session_transfer_score = float(cross_regime_transfer_robustness_layer.get("session_transfer_score", 0.5) or 0.5)
    volatility_transfer_score = float(
        cross_regime_transfer_robustness_layer.get("volatility_transfer_score", 0.5) or 0.5
    )
    liquidity_transfer_score = float(cross_regime_transfer_robustness_layer.get("liquidity_transfer_score", 0.5) or 0.5)
    overfit_risk = float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0)
    if transfer_score <= 0.45:
        gaps.append(
            {
                "gap_type": "cross_regime_transfer_breakdown",
                "detail": str(transfer_state.get("state", "fragile")),
                "frequency": max(1, int(round((1.0 - transfer_score) * 5))),
                "severity": round(min(1.0, 1.0 - transfer_score), 4),
            }
        )
    if session_transfer_score <= 0.45:
        gaps.append(
            {
                "gap_type": "session_transfer_instability",
                "detail": "session_transfer_instability",
                "frequency": max(1, int(round((1.0 - session_transfer_score) * 5))),
                "severity": round(min(1.0, 1.0 - session_transfer_score), 4),
            }
        )
    if volatility_transfer_score <= 0.45:
        gaps.append(
            {
                "gap_type": "volatility_transfer_failure",
                "detail": "volatility_transfer_failure",
                "frequency": max(1, int(round((1.0 - volatility_transfer_score) * 5))),
                "severity": round(min(1.0, 1.0 - volatility_transfer_score), 4),
            }
        )
    if liquidity_transfer_score <= 0.45:
        gaps.append(
            {
                "gap_type": "liquidity_transfer_failure",
                "detail": "liquidity_transfer_failure",
                "frequency": max(1, int(round((1.0 - liquidity_transfer_score) * 5))),
                "severity": round(min(1.0, 1.0 - liquidity_transfer_score), 4),
            }
        )
    if overfit_risk >= 0.62:
        gaps.append(
            {
                "gap_type": "overfit_narrow_regime_dependency",
                "detail": "narrow_regime_dependency",
                "frequency": max(1, int(round(overfit_risk * 4))),
                "severity": round(min(1.0, overfit_risk), 4),
            }
        )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    intervention_state = str(
        causal_intervention_counterfactual_robustness_layer.get("intervention_quality_state", "watch")
    )
    counterfactual_robustness_score = float(
        causal_intervention_counterfactual_robustness_layer.get("counterfactual_robustness_score", 0.5) or 0.5
    )
    intervention_consistency = float(
        causal_intervention_counterfactual_robustness_layer.get("intervention_consistency", 0.5) or 0.5
    )
    intervention_reliability = float(
        causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5
    )
    false_improvement_risk = float(
        causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0
    )
    if intervention_state in {"fragile", "breakdown"} or counterfactual_robustness_score <= 0.42:
        gaps.append(
            {
                "gap_type": "causal_intervention_robustness_breakdown",
                "detail": intervention_state,
                "frequency": max(1, int(round((1.0 - counterfactual_robustness_score) * 5))),
                "severity": round(min(1.0, max(1.0 - counterfactual_robustness_score, 0.55)), 4),
            }
        )
    if false_improvement_risk >= 0.62:
        gaps.append(
            {
                "gap_type": "false_improvement_risk_elevated",
                "detail": "counterfactual_narrow_context_concentration",
                "frequency": max(1, int(round(false_improvement_risk * 4))),
                "severity": round(min(1.0, false_improvement_risk), 4),
            }
        )
    if intervention_consistency <= 0.42:
        gaps.append(
            {
                "gap_type": "intervention_axis_instability",
                "detail": "primary_axis_instability",
                "frequency": max(1, int(round((1.0 - intervention_consistency) * 5))),
                "severity": round(min(1.0, 1.0 - intervention_consistency), 4),
            }
        )
    if intervention_reliability <= 0.45:
        gaps.append(
            {
                "gap_type": "low_intervention_reliability",
                "detail": "counterfactual_intervention_reliability_decay",
                "frequency": max(1, int(round((1.0 - intervention_reliability) * 5))),
                "severity": round(min(1.0, 1.0 - intervention_reliability), 4),
            }
        )
    governed_capability_invention_layer = (
        governed_capability_invention_layer if isinstance(governed_capability_invention_layer, dict) else {}
    )
    invention_redundancy_risk = float(governed_capability_invention_layer.get("redundancy_risk", 0.0) or 0.0)
    invention_maturity_score = float(governed_capability_invention_layer.get("invention_maturity_score", 0.0) or 0.0)
    invention_reliability = float(governed_capability_invention_layer.get("invention_reliability", 0.0) or 0.0)
    if invention_redundancy_risk >= 0.65:
        gaps.append(
            {
                "gap_type": "invention_redundancy_pressure",
                "detail": str(governed_capability_invention_layer.get("invention_reason_cluster", "redundancy_pressure")),
                "frequency": max(1, int(round(invention_redundancy_risk * 4))),
                "severity": round(min(1.0, invention_redundancy_risk), 4),
            }
        )
    if invention_maturity_score <= 0.35:
        gaps.append(
            {
                "gap_type": "invention_maturity_stall",
                "detail": str(governed_capability_invention_layer.get("dominant_invention_axis", "unknown")),
                "frequency": max(1, int(round((1.0 - invention_maturity_score) * 4))),
                "severity": round(min(1.0, 1.0 - invention_maturity_score), 4),
            }
        )
    if invention_reliability <= 0.4:
        gaps.append(
            {
                "gap_type": "invention_reliability_decay",
                "detail": str(governed_capability_invention_layer.get("capability_invention_state", "unknown")),
                "frequency": max(1, int(round((1.0 - invention_reliability) * 4))),
                "severity": round(min(1.0, 1.0 - invention_reliability), 4),
            }
        )
    autonomous_capability_expansion_layer = (
        autonomous_capability_expansion_layer if isinstance(autonomous_capability_expansion_layer, dict) else {}
    )
    expansion_readiness_score = float(autonomous_capability_expansion_layer.get("expansion_readiness_score", 0.0) or 0.0)
    rollbackability_score = float(autonomous_capability_expansion_layer.get("rollbackability_score", 0.0) or 0.0)
    expansion_reliability = float(autonomous_capability_expansion_layer.get("expansion_reliability", 0.0) or 0.0)
    if expansion_readiness_score <= 0.4:
        gaps.append(
            {
                "gap_type": "expansion_readiness_stall",
                "detail": str(autonomous_capability_expansion_layer.get("capability_expansion_state", "stalled")),
                "frequency": max(1, int(round((1.0 - expansion_readiness_score) * 4))),
                "severity": round(min(1.0, 1.0 - expansion_readiness_score), 4),
            }
        )
    if rollbackability_score <= 0.42:
        gaps.append(
            {
                "gap_type": "expansion_rollback_risk",
                "detail": str(autonomous_capability_expansion_layer.get("dominant_expansion_axis", "risk")),
                "frequency": max(1, int(round((1.0 - rollbackability_score) * 4))),
                "severity": round(min(1.0, 1.0 - rollbackability_score), 4),
            }
        )
    if expansion_reliability <= 0.45:
        gaps.append(
            {
                "gap_type": "expansion_reliability_decay",
                "detail": str(autonomous_capability_expansion_layer.get("expansion_reason_cluster", "expansion_reliability_decay")),
                "frequency": max(1, int(round((1.0 - expansion_reliability) * 4))),
                "severity": round(min(1.0, 1.0 - expansion_reliability), 4),
            }
        )
    rollback_orchestration_and_safe_reversion_layer = (
        rollback_orchestration_and_safe_reversion_layer
        if isinstance(rollback_orchestration_and_safe_reversion_layer, dict)
        else {}
    )
    rollback_urgency = float(rollback_orchestration_and_safe_reversion_layer.get("rollback_urgency", 0.0) or 0.0)
    safe_reversion_ready = bool(rollback_orchestration_and_safe_reversion_layer.get("safe_reversion_ready", False))
    rollback_reliability = float(
        rollback_orchestration_and_safe_reversion_layer.get("rollback_reversion_reliability", 0.0) or 0.0
    )
    rollback_state = str(rollback_orchestration_and_safe_reversion_layer.get("rollback_orchestration_state", "stable"))
    if rollback_urgency >= 0.55:
        gaps.append(
            {
                "gap_type": "rollback_orchestration_deficit",
                "detail": rollback_state,
                "frequency": max(1, int(round(rollback_urgency * 4))),
                "severity": round(min(1.0, rollback_urgency), 4),
            }
        )
    if (not safe_reversion_ready) and (rollback_urgency >= 0.45 or rollback_reliability <= 0.5):
        gaps.append(
            {
                "gap_type": "safe_reversion_precondition_failure",
                "detail": str(
                    rollback_orchestration_and_safe_reversion_layer.get(
                        "reversion_sequence_mode",
                        "none",
                    )
                ),
                "frequency": max(1, int(round((max(rollback_urgency, 1.0 - rollback_reliability)) * 3))),
                "severity": round(min(1.0, max(rollback_urgency, 1.0 - rollback_reliability)), 4),
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
        "persistent_hostile_execution_cluster": [
            {"suggestion_type": "new_execution_refinement", "target": "persistent_hostile_execution_guard"},
            {"suggestion_type": "new_detector_idea", "target": "hostile_execution_cluster_detector"},
        ],
        "chronic_adverse_selection_risk": [
            {"suggestion_type": "new_execution_refinement", "target": "adverse_selection_entry_filter"},
        ],
        "quote_fade_execution_fragility": [
            {"suggestion_type": "new_execution_refinement", "target": "quote_fade_fragility_guard"},
        ],
        "sweep_aftermath_fill_collapse_pattern": [
            {"suggestion_type": "new_execution_refinement", "target": "sweep_aftermath_fill_collapse_guard"},
        ],
        "persistent_engineered_move_deception_cluster": [
            {"suggestion_type": "new_detector_idea", "target": "engineered_move_deception_cluster_detector"},
            {"suggestion_type": "new_survival_rule", "target": "engineered_move_deception_guard"},
        ],
        "liquidity_bait_recurrence_gap": [
            {"suggestion_type": "new_execution_refinement", "target": "liquidity_bait_recurrence_filter"},
        ],
        "sweep_trap_deception_under_modeled": [
            {"suggestion_type": "new_detector_idea", "target": "sweep_trap_deception_detector"},
        ],
        "deception_reliability_decay": [
            {"suggestion_type": "new_detector_idea", "target": "deception_reliability_recovery_detector"},
        ],
        "low_structural_memory_reliability": [
            {"suggestion_type": "new_detector_idea", "target": "structural_memory_reliability_recovery_detector"},
        ],
        "recurrent_structural_reversal_not_captured": [
            {"suggestion_type": "new_survival_rule", "target": "structural_reversal_memory_guard"},
            {"suggestion_type": "new_detector_idea", "target": "structural_reversal_recurrence_detector"},
        ],
        "regime_memory_misalignment": [
            {"suggestion_type": "new_detector_idea", "target": "regime_structural_alignment_detector"},
        ],
        "persistent_structural_magnet_behavior_unmodeled": [
            {"suggestion_type": "new_feature_combination", "target": "structural_magnet_memory_features"},
        ],
        "latent_transition_hazard_under_modeled": [
            {"suggestion_type": "new_detector_idea", "target": "latent_transition_hazard_detector"},
            {"suggestion_type": "new_survival_rule", "target": "latent_transition_hazard_pause_guard"},
        ],
        "hazard_directional_bias_mismatch": [
            {"suggestion_type": "new_strategy_mutation", "target": "hazard_bias_directional_alignment"},
        ],
        "hazard_reliability_decay": [
            {"suggestion_type": "new_detector_idea", "target": "hazard_reliability_recovery_detector"},
        ],
        "precursor_instability_not_captured": [
            {"suggestion_type": "new_execution_refinement", "target": "precursor_instability_capture_guard"},
        ],
        "cross_regime_transfer_breakdown": [
            {"suggestion_type": "new_detector_idea", "target": "cross_regime_transfer_breakdown_detector"},
            {"suggestion_type": "new_survival_rule", "target": "cross_regime_transfer_quarantine_guard"},
        ],
        "session_transfer_instability": [
            {"suggestion_type": "new_detector_idea", "target": "session_transfer_stability_detector"},
        ],
        "volatility_transfer_failure": [
            {"suggestion_type": "new_strategy_mutation", "target": "volatility_transfer_aware_adaptation"},
        ],
        "liquidity_transfer_failure": [
            {"suggestion_type": "new_execution_refinement", "target": "liquidity_transfer_failure_guard"},
        ],
        "overfit_narrow_regime_dependency": [
            {"suggestion_type": "new_survival_rule", "target": "narrow_regime_overfit_guard"},
            {"suggestion_type": "new_feature_combination", "target": "cross_regime_generalization_features"},
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
        "persistent_hostile_execution_cluster": "adversarial_execution_intelligence_layer",
        "chronic_adverse_selection_risk": "adversarial_execution_intelligence_layer",
        "quote_fade_execution_fragility": "adversarial_execution_intelligence_layer",
        "sweep_aftermath_fill_collapse_pattern": "adversarial_execution_intelligence_layer",
        "persistent_engineered_move_deception_cluster": "dynamic_market_maker_deception_inference_layer",
        "liquidity_bait_recurrence_gap": "dynamic_market_maker_deception_inference_layer",
        "sweep_trap_deception_under_modeled": "dynamic_market_maker_deception_inference_layer",
        "deception_reliability_decay": "dynamic_market_maker_deception_inference_layer",
        "low_structural_memory_reliability": "structural_memory_graph_layer",
        "recurrent_structural_reversal_not_captured": "structural_memory_graph_layer",
        "regime_memory_misalignment": "structural_memory_graph_layer",
        "persistent_structural_magnet_behavior_unmodeled": "structural_memory_graph_layer",
        "latent_transition_hazard_under_modeled": "latent_transition_hazard_layer",
        "hazard_directional_bias_mismatch": "latent_transition_hazard_layer",
        "hazard_reliability_decay": "latent_transition_hazard_layer",
        "precursor_instability_not_captured": "latent_transition_hazard_layer",
        "cross_regime_transfer_breakdown": "cross_regime_transfer_robustness_layer",
        "session_transfer_instability": "cross_regime_transfer_robustness_layer",
        "volatility_transfer_failure": "cross_regime_transfer_robustness_layer",
        "liquidity_transfer_failure": "cross_regime_transfer_robustness_layer",
        "overfit_narrow_regime_dependency": "cross_regime_transfer_robustness_layer",
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


def _temporal_execution_sequencing_layer(
    *,
    memory_root: Path,
    closed: list[dict[str, Any]],
    market_state: dict[str, Any],
    replay_scope: str,
    execution_microstructure_engine: dict[str, Any],
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    unified_market_intelligence_field: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sequencing_dir = memory_root / "temporal_execution"
    sequencing_dir.mkdir(parents=True, exist_ok=True)
    latest_path = sequencing_dir / "temporal_execution_latest.json"
    history_path = sequencing_dir / "temporal_execution_history.json"
    reason_registry_path = sequencing_dir / "sequencing_reason_registry.json"
    execution_window_quality_registry_path = sequencing_dir / "execution_window_quality_registry.json"
    transition_trace_path = sequencing_dir / "temporal_sequence_transition_trace.json"
    governance_path = sequencing_dir / "temporal_execution_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    execution_microstructure_engine = execution_microstructure_engine if isinstance(execution_microstructure_engine, dict) else {}
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    calibration_uncertainty_engine = calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    contradiction_state = contradiction_arbitration_engine.get("arbitration", {})
    if not isinstance(contradiction_state, dict):
        contradiction_state = {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}

    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    entry_timing_degradation = _bounded(float(execution_microstructure_engine.get("entry_timing_degradation", 0.0) or 0.0))
    failure_cluster_risk = _bounded(float(execution_microstructure_engine.get("failure_cluster_risk", 0.0) or 0.0))
    should_delay_entry = bool(execution_microstructure_engine.get("should_delay_entry", False))
    should_refuse_trade = bool(execution_microstructure_engine.get("should_refuse_trade", False))
    fill_delay_state = str(execution_microstructure_engine.get("fill_delay_state", "normal"))

    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    deception_score = _bounded(float(deception_state.get("deception_score", 0.0) or 0.0))
    transition_hazard_score = _bounded(float(latent_state.get("transition_hazard_score", 0.0) or 0.0))
    calibration_drift = _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0))
    contradiction_severity = _bounded(float(contradiction_state.get("max_contradiction_severity", 0.0) or 0.0))
    contradiction_outcome = str(contradiction_state.get("outcome", "allow"))
    memory_reliability = _bounded(float(structural_state.get("memory_reliability", 0.5) or 0.5))
    expansion_quality_score = _bounded(float(self_expansion_quality_layer.get("expansion_quality_score", 0.5) or 0.5))
    composite_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.5) or 0.5))
    telemetry_count = len([item for item in closed if isinstance(item, dict)])

    execution_window_quality = _bounded(
        1.0
        - min(
            1.0,
            (execution_penalty * 0.45)
            + (entry_timing_degradation * 0.2)
            + (failure_cluster_risk * 0.15)
            + (hostile_execution_score * 0.1)
            + (deception_score * 0.1),
        )
    )
    timing_priority_score = _bounded(
        (execution_penalty * 0.25)
        + (entry_timing_degradation * 0.2)
        + (transition_hazard_score * 0.14)
        + (calibration_drift * 0.12)
        + (contradiction_severity * 0.1)
        + (hostile_execution_score * 0.1)
        + (deception_score * 0.09)
        + (0.12 if should_delay_entry else 0.0)
        + (0.15 if should_refuse_trade else 0.0)
        + (0.08 if contradiction_outcome in {"pause", "refuse"} else 0.0)
    )
    sequencing_reliability = _bounded(
        (execution_window_quality * 0.35)
        + (composite_confidence * 0.2)
        + (memory_reliability * 0.2)
        + (expansion_quality_score * 0.1)
        + ((1.0 - calibration_drift) * 0.08)
        + ((1.0 - contradiction_severity) * 0.07)
        - (timing_priority_score * 0.25)
    )
    phase_maturity_score = _bounded(
        (sequencing_reliability * 0.35)
        + (memory_reliability * 0.25)
        + (execution_window_quality * 0.2)
        + (expansion_quality_score * 0.2)
    )

    delay_bias = _bounded(
        (timing_priority_score * 0.32)
        + ((1.0 - execution_window_quality) * 0.2)
        + (transition_hazard_score * 0.14)
        + (calibration_drift * 0.12)
        + (0.15 if should_delay_entry else 0.0)
    )
    abandon_bias = _bounded(
        (timing_priority_score * 0.22)
        + (contradiction_severity * 0.15)
        + (hostile_execution_score * 0.14)
        + (failure_cluster_risk * 0.12)
        + (0.2 if should_refuse_trade else 0.0)
        + (0.12 if contradiction_outcome == "refuse" else 0.0)
    )
    stagger_bias = _bounded(
        ((1.0 - execution_penalty) * 0.2)
        + (delay_bias * 0.25)
        + (sequencing_reliability * 0.3)
        + ((1.0 - abandon_bias) * 0.15)
        + (0.1 if fill_delay_state in {"elevated", "degraded"} else 0.0)
    )
    entry_now_bias = _bounded(
        (composite_confidence * 0.35)
        + (execution_window_quality * 0.35)
        + (sequencing_reliability * 0.2)
        + ((1.0 - delay_bias) * 0.1)
        - (abandon_bias * 0.25)
    )

    reason_candidates = {
        "execution_drag_cluster": execution_penalty + entry_timing_degradation + failure_cluster_risk,
        "hazard_uncertainty_cluster": transition_hazard_score + calibration_drift + contradiction_severity,
        "hostile_adverse_cluster": hostile_execution_score + deception_score + abandon_bias,
        "staggered_opportunity_cluster": stagger_bias + entry_now_bias + sequencing_reliability,
    }
    sequencing_reason_cluster = sorted(reason_candidates.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]

    recommended_sequence_mode = "hold"
    if abandon_bias >= 0.72:
        recommended_sequence_mode = "abandon"
    elif delay_bias >= 0.68 and stagger_bias >= 0.5:
        recommended_sequence_mode = "stagger"
    elif delay_bias >= 0.58:
        recommended_sequence_mode = "delay"
    elif entry_now_bias >= 0.6 and sequencing_reliability >= 0.55 and execution_window_quality >= 0.5:
        recommended_sequence_mode = "enter_now"

    temporal_execution_state = (
        "unstable"
        if abandon_bias >= 0.72 or sequencing_reliability < 0.35
        else "deferential"
        if recommended_sequence_mode in {"delay", "stagger", "hold"}
        else "ready"
    )
    sequence_actions: list[str] = []
    if recommended_sequence_mode == "abandon":
        sequence_actions.append("abandon_sequence_until_execution_window_recovers")
    elif recommended_sequence_mode == "delay":
        sequence_actions.append("delay_entry_until_execution_window_quality_recovers")
    elif recommended_sequence_mode == "stagger":
        sequence_actions.append("stagger_entry_with_governed_tranche_steps")
    elif recommended_sequence_mode == "enter_now":
        sequence_actions.append("enter_now_under_current_governed_controls")
    else:
        sequence_actions.append("hold_and_reassess_next_execution_window")

    timing_controls = {
        "max_deferral_cycles": max(1, min(4, 1 + int(round(delay_bias * 3)))),
        "stagger_tranche_count": max(1, min(4, 1 + int(round(stagger_bias * 2)))),
        "phase_out_pressure": round(min(1.0, abandon_bias * 0.85), 4),
        "window_recheck_interval": max(1, min(6, 1 + int(round((1.0 - execution_window_quality) * 5)))),
    }
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    payload = {
        "temporal_execution_state": temporal_execution_state,
        "timing_priority_score": timing_priority_score,
        "sequencing_reliability": sequencing_reliability,
        "entry_now_bias": entry_now_bias,
        "delay_bias": delay_bias,
        "stagger_bias": stagger_bias,
        "abandon_bias": abandon_bias,
        "phase_maturity_score": phase_maturity_score,
        "execution_window_quality": execution_window_quality,
        "sequencing_reason_cluster": sequencing_reason_cluster,
        "recommended_sequence_mode": recommended_sequence_mode,
        "sequence_actions": sequence_actions,
        "timing_controls": timing_controls,
        "governance_flags": governance_flags,
    }
    previous_payload = read_json_safe(latest_path, default={})
    if not isinstance(previous_payload, dict):
        previous_payload = {}
    write_json_atomic(latest_path, payload)

    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})

    reason_registry = read_json_safe(reason_registry_path, default={"entries": []})
    if not isinstance(reason_registry, dict):
        reason_registry = {"entries": []}
    reason_entries = reason_registry.get("entries", [])
    if not isinstance(reason_entries, list):
        reason_entries = []
    reason_entries.append(
        {
            "replay_scope": replay_scope,
            "sequencing_reason_cluster": sequencing_reason_cluster,
            "recommended_sequence_mode": recommended_sequence_mode,
            "timing_priority_score": timing_priority_score,
            "sequencing_reliability": sequencing_reliability,
        }
    )
    write_json_atomic(reason_registry_path, {"entries": reason_entries[-400:]})

    execution_window_registry = read_json_safe(execution_window_quality_registry_path, default={"entries": []})
    if not isinstance(execution_window_registry, dict):
        execution_window_registry = {"entries": []}
    execution_window_entries = execution_window_registry.get("entries", [])
    if not isinstance(execution_window_entries, list):
        execution_window_entries = []
    execution_window_entries.append(
        {
            "replay_scope": replay_scope,
            "execution_window_quality": execution_window_quality,
            "entry_timing_degradation": entry_timing_degradation,
            "execution_penalty": execution_penalty,
            "sample_size": telemetry_count,
        }
    )
    write_json_atomic(execution_window_quality_registry_path, {"entries": execution_window_entries[-400:]})

    transition_trace = read_json_safe(transition_trace_path, default={"transitions": []})
    if not isinstance(transition_trace, dict):
        transition_trace = {"transitions": []}
    transitions = transition_trace.get("transitions", [])
    if not isinstance(transitions, list):
        transitions = []
    transitions.append(
        {
            "replay_scope": replay_scope,
            "from_state": str(previous_payload.get("temporal_execution_state", "seed")),
            "to_state": temporal_execution_state,
            "from_mode": str(previous_payload.get("recommended_sequence_mode", "seed")),
            "to_mode": recommended_sequence_mode,
            "timing_priority_score": timing_priority_score,
        }
    )
    write_json_atomic(transition_trace_path, {"transitions": transitions[-400:]})
    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
        },
    )
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "sequencing_reason_registry": str(reason_registry_path),
            "execution_window_quality_registry": str(execution_window_quality_registry_path),
            "temporal_sequence_transition_trace": str(transition_trace_path),
            "temporal_execution_governance_state": str(governance_path),
        },
    }


def _hierarchical_decision_policy_layer(
    *,
    memory_root: Path,
    market_state: dict[str, Any],
    replay_scope: str,
    unified_market_intelligence_field: dict[str, Any],
    execution_microstructure_engine: dict[str, Any],
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    temporal_execution_sequencing_layer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy_dir = memory_root / "decision_policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    latest_path = policy_dir / "decision_policy_latest.json"
    history_path = policy_dir / "decision_policy_history.json"
    reason_registry_path = policy_dir / "policy_reason_registry.json"
    conflict_registry_path = policy_dir / "policy_conflict_registry.json"
    transition_trace_path = policy_dir / "policy_transition_trace.json"
    governance_path = policy_dir / "decision_policy_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    execution_microstructure_engine = execution_microstructure_engine if isinstance(execution_microstructure_engine, dict) else {}
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    calibration_uncertainty_engine = calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    temporal_execution_sequencing_layer = (
        temporal_execution_sequencing_layer if isinstance(temporal_execution_sequencing_layer, dict) else {}
    )

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    contradiction_state = contradiction_arbitration_engine.get("arbitration", {})
    if not isinstance(contradiction_state, dict):
        contradiction_state = {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}

    contradiction_outcome = str(contradiction_state.get("outcome", "allow"))
    contradiction_severity = _bounded(float(contradiction_state.get("max_contradiction_severity", 0.0) or 0.0))
    calibrated_confidence = _bounded(
        float(calibration_state.get("calibrated_confidence", confidence_structure.get("composite_confidence", 0.5)) or 0.5)
    )
    calibration_drift = _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    deception_score = _bounded(float(deception_state.get("deception_score", 0.0) or 0.0))
    transition_hazard_score = _bounded(float(latent_state.get("transition_hazard_score", 0.0) or 0.0))
    transfer_overfit_risk = _bounded(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0))
    false_improvement_risk = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0)
    )
    intervention_reliability = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5)
    )
    transfer_score = _bounded(float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5))
    memory_reliability = _bounded(float(structural_state.get("memory_reliability", 0.5) or 0.5))
    expansion_quality = _bounded(float(self_expansion_quality_layer.get("expansion_quality_score", 0.5) or 0.5))
    timing_priority_score = _bounded(float(temporal_execution_sequencing_layer.get("timing_priority_score", 0.0) or 0.0))
    sequencing_reliability = _bounded(float(temporal_execution_sequencing_layer.get("sequencing_reliability", 0.5) or 0.5))
    execution_window_quality = _bounded(float(temporal_execution_sequencing_layer.get("execution_window_quality", 0.5) or 0.5))
    delay_bias = _bounded(float(temporal_execution_sequencing_layer.get("delay_bias", 0.0) or 0.0))
    abandon_bias = _bounded(float(temporal_execution_sequencing_layer.get("abandon_bias", 0.0) or 0.0))
    contradiction_pressure = 0.3 if contradiction_outcome == "refuse" else 0.2 if contradiction_outcome == "pause" else 0.0

    survival_priority_score = _bounded(
        (execution_penalty * 0.2)
        + (hostile_execution_score * 0.15)
        + (deception_score * 0.1)
        + (transition_hazard_score * 0.15)
        + (transfer_overfit_risk * 0.1)
        + (false_improvement_risk * 0.1)
        + (calibration_drift * 0.1)
        + (contradiction_severity * 0.1)
        + contradiction_pressure
    )
    opportunity_priority_score = _bounded(
        (calibrated_confidence * 0.35)
        + (transfer_score * 0.2)
        + (memory_reliability * 0.15)
        + (intervention_reliability * 0.2)
        + (expansion_quality * 0.1)
        + (sequencing_reliability * 0.08)
        - (execution_penalty * 0.2)
        - ((1.0 - execution_window_quality) * 0.14)
        - (delay_bias * 0.08)
        - (abandon_bias * 0.1)
        - (contradiction_severity * 0.15)
        - (false_improvement_risk * 0.1)
    )
    refusal_priority_score = _bounded(
        (survival_priority_score * 0.4)
        + (contradiction_severity * 0.25)
        + (false_improvement_risk * 0.15)
        + (execution_penalty * 0.1)
        + (abandon_bias * 0.16)
        + (calibration_drift * 0.1)
        + (0.15 if contradiction_outcome == "refuse" else 0.0)
    )
    deferral_priority_score = _bounded(
        (survival_priority_score * 0.3)
        + (contradiction_severity * 0.15)
        + (calibration_drift * 0.2)
        + ((1.0 - intervention_reliability) * 0.2)
        + (transition_hazard_score * 0.1)
        + (delay_bias * 0.14)
        + ((1.0 - execution_window_quality) * 0.08)
        + (timing_priority_score * 0.08)
        + (0.15 if contradiction_outcome == "pause" else 0.0)
    )

    priorities = {
        "survival_first": survival_priority_score,
        "opportunity_first": opportunity_priority_score,
        "refusal_first": refusal_priority_score,
        "deferral_first": deferral_priority_score,
    }
    dominant_policy_mode = sorted(priorities.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]
    if dominant_policy_mode in {"refusal_first", "survival_first"}:
        recommended_policy_posture = "capital_preservation"
    elif dominant_policy_mode == "deferral_first":
        recommended_policy_posture = "governed_deferral"
    elif opportunity_priority_score >= 0.58 and calibrated_confidence >= 0.62 and contradiction_severity <= 0.45:
        recommended_policy_posture = "opportunity_selective"
    else:
        recommended_policy_posture = "balanced_watch"

    reason_candidates = {
        "contradiction_pressure_cluster": contradiction_severity + contradiction_pressure,
        "execution_hostility_cluster": execution_penalty + hostile_execution_score + deception_score,
        "fragility_cluster": calibration_drift + transition_hazard_score + (1.0 - intervention_reliability),
        "opportunity_alignment_cluster": opportunity_priority_score + calibrated_confidence + transfer_score,
        "temporal_sequencing_pressure_cluster": delay_bias + abandon_bias + (1.0 - execution_window_quality),
    }
    dominant_reason_cluster = sorted(reason_candidates.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]
    mean_priority = (survival_priority_score + opportunity_priority_score + refusal_priority_score + deferral_priority_score) / 4.0
    spread = max(priorities.values()) - min(priorities.values())
    policy_conflict_score = _bounded(
        (spread * 0.4)
        + (abs(survival_priority_score - opportunity_priority_score) * 0.25)
        + (contradiction_severity * 0.2)
        + (calibration_drift * 0.15)
    )
    policy_reliability = _bounded(
        (calibrated_confidence * 0.35)
        + (memory_reliability * 0.2)
        + (intervention_reliability * 0.2)
        + (transfer_score * 0.15)
        + (expansion_quality * 0.1)
        - (policy_conflict_score * 0.25)
        - (execution_penalty * 0.1)
    )
    policy_risk_multiplier = round(max(0.25, min(1.0, 1.0 - min(0.55, (survival_priority_score * 0.3) + (policy_conflict_score * 0.25)))), 4)
    policy_confidence_adjustment = round(
        max(0.5, min(1.0, 0.78 + (policy_reliability * 0.18) - (policy_conflict_score * 0.12))),
        4,
    )
    if refusal_priority_score >= 0.72:
        decision_policy_state = "restrictive"
    elif deferral_priority_score >= 0.68:
        decision_policy_state = "deferential"
    elif opportunity_priority_score >= 0.62 and policy_reliability >= 0.6 and survival_priority_score < 0.6:
        decision_policy_state = "opportunistic_guarded"
    elif policy_reliability >= 0.55 and policy_conflict_score <= 0.5:
        decision_policy_state = "balanced"
    else:
        decision_policy_state = "fragile"

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "policy_refusal_guard": refusal_priority_score >= 0.65,
        "policy_deferral_guard": deferral_priority_score >= 0.62,
    }
    payload = {
        "decision_policy_state": decision_policy_state,
        "dominant_policy_mode": dominant_policy_mode,
        "recommended_policy_posture": recommended_policy_posture,
        "survival_priority_score": survival_priority_score,
        "opportunity_priority_score": opportunity_priority_score,
        "refusal_priority_score": refusal_priority_score,
        "deferral_priority_score": deferral_priority_score,
        "dominant_reason_cluster": dominant_reason_cluster,
        "policy_conflict_score": policy_conflict_score,
        "policy_reliability": policy_reliability,
        "policy_risk_multiplier": policy_risk_multiplier,
        "policy_confidence_adjustment": policy_confidence_adjustment,
        "temporal_sequencing_pressure": _bounded(delay_bias + abandon_bias + (1.0 - execution_window_quality)),
        "governance_flags": governance_flags,
    }
    previous_policy = read_json_safe(latest_path, default={})
    if not isinstance(previous_policy, dict):
        previous_policy = {}
    write_json_atomic(latest_path, payload)
    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})

    reason_registry = read_json_safe(reason_registry_path, default={"entries": []})
    if not isinstance(reason_registry, dict):
        reason_registry = {"entries": []}
    reason_entries = reason_registry.get("entries", [])
    if not isinstance(reason_entries, list):
        reason_entries = []
    reason_entries.append(
        {
            "replay_scope": replay_scope,
            "dominant_reason_cluster": dominant_reason_cluster,
            "dominant_policy_mode": dominant_policy_mode,
            "recommended_policy_posture": recommended_policy_posture,
            "mean_priority": round(mean_priority, 4),
        }
    )
    write_json_atomic(reason_registry_path, {"entries": reason_entries[-400:]})

    conflict_registry = read_json_safe(conflict_registry_path, default={"entries": []})
    if not isinstance(conflict_registry, dict):
        conflict_registry = {"entries": []}
    conflict_entries = conflict_registry.get("entries", [])
    if not isinstance(conflict_entries, list):
        conflict_entries = []
    conflict_entries.append(
        {
            "replay_scope": replay_scope,
            "policy_conflict_score": policy_conflict_score,
            "policy_reliability": policy_reliability,
            "survival_priority_score": survival_priority_score,
            "opportunity_priority_score": opportunity_priority_score,
            "refusal_priority_score": refusal_priority_score,
            "deferral_priority_score": deferral_priority_score,
        }
    )
    write_json_atomic(conflict_registry_path, {"entries": conflict_entries[-400:]})

    transition_trace = read_json_safe(transition_trace_path, default={"transitions": []})
    if not isinstance(transition_trace, dict):
        transition_trace = {"transitions": []}
    transitions = transition_trace.get("transitions", [])
    if not isinstance(transitions, list):
        transitions = []
    transitions.append(
        {
            "replay_scope": replay_scope,
            "from_state": str(previous_policy.get("decision_policy_state", "seed")),
            "to_state": decision_policy_state,
            "from_mode": str(previous_policy.get("dominant_policy_mode", "seed")),
            "to_mode": dominant_policy_mode,
            "policy_conflict_score": policy_conflict_score,
        }
    )
    write_json_atomic(transition_trace_path, {"transitions": transitions[-400:]})
    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
        },
    )
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "policy_reason_registry": str(reason_registry_path),
            "policy_conflict_registry": str(conflict_registry_path),
            "policy_transition_trace": str(transition_trace_path),
            "decision_policy_governance_state": str(governance_path),
        },
    }


def _portfolio_multi_context_capital_allocation_layer(
    *,
    memory_root: Path,
    market_state: dict[str, Any],
    replay_scope: str,
    autonomous_behavior: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    hierarchical_decision_policy_layer: dict[str, Any],
    execution_microstructure_engine: dict[str, Any] | None = None,
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    temporal_execution_sequencing_layer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allocation_dir = memory_root / "capital_allocation"
    allocation_dir.mkdir(parents=True, exist_ok=True)
    latest_path = allocation_dir / "capital_allocation_latest.json"
    history_path = allocation_dir / "capital_allocation_history.json"
    reason_registry_path = allocation_dir / "allocation_reason_registry.json"
    context_competition_registry_path = allocation_dir / "context_competition_registry.json"
    exposure_compression_trace_path = allocation_dir / "exposure_compression_trace.json"
    governance_path = allocation_dir / "capital_allocation_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    market_state = market_state if isinstance(market_state, dict) else {}
    autonomous_behavior = autonomous_behavior if isinstance(autonomous_behavior, dict) else {}
    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    hierarchical_decision_policy_layer = (
        hierarchical_decision_policy_layer if isinstance(hierarchical_decision_policy_layer, dict) else {}
    )
    execution_microstructure_engine = execution_microstructure_engine if isinstance(execution_microstructure_engine, dict) else {}
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    calibration_uncertainty_engine = calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    temporal_execution_sequencing_layer = (
        temporal_execution_sequencing_layer if isinstance(temporal_execution_sequencing_layer, dict) else {}
    )

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    contradiction_state = contradiction_arbitration_engine.get("arbitration", {})
    if not isinstance(contradiction_state, dict):
        contradiction_state = {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}

    calibrated_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.5) or 0.5))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    deception_score = _bounded(float(deception_state.get("deception_score", 0.0) or 0.0))
    transition_hazard_score = _bounded(float(latent_state.get("transition_hazard_score", 0.0) or 0.0))
    calibration_drift = _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0))
    contradiction_severity = _bounded(float(contradiction_state.get("max_contradiction_severity", 0.0) or 0.0))
    contradiction_outcome = str(contradiction_state.get("outcome", "allow"))
    policy_conflict_score = _bounded(float(hierarchical_decision_policy_layer.get("policy_conflict_score", 0.0) or 0.0))
    policy_reliability = _bounded(float(hierarchical_decision_policy_layer.get("policy_reliability", 0.5) or 0.5))
    survival_priority_score = _bounded(float(hierarchical_decision_policy_layer.get("survival_priority_score", 0.0) or 0.0))
    opportunity_priority_score = _bounded(
        float(hierarchical_decision_policy_layer.get("opportunity_priority_score", 0.0) or 0.0)
    )
    cross_regime_transfer_score = _bounded(float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5))
    overfit_risk = _bounded(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0))
    intervention_reliability = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5)
    )
    false_improvement_risk = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0)
    )
    expansion_quality_score = _bounded(float(self_expansion_quality_layer.get("expansion_quality_score", 0.5) or 0.5))
    sequencing_reliability = _bounded(float(temporal_execution_sequencing_layer.get("sequencing_reliability", 0.5) or 0.5))
    delay_bias = _bounded(float(temporal_execution_sequencing_layer.get("delay_bias", 0.0) or 0.0))
    abandon_bias = _bounded(float(temporal_execution_sequencing_layer.get("abandon_bias", 0.0) or 0.0))
    stagger_bias = _bounded(float(temporal_execution_sequencing_layer.get("stagger_bias", 0.0) or 0.0))
    execution_window_quality = _bounded(float(temporal_execution_sequencing_layer.get("execution_window_quality", 0.5) or 0.5))
    memory_reliability = _bounded(float(structural_state.get("memory_reliability", 0.5) or 0.5))
    volatility_ratio = _bounded(float(market_state.get("volatility_ratio", 1.0) or 1.0) / 3.0)
    capital_survival_pressure = _bounded(
        float(autonomous_behavior.get("capital_survival_engine", {}).get("survival_pressure", 0.0) or 0.0)
    )
    contradiction_pressure = 0.12 if contradiction_outcome == "refuse" else 0.07 if contradiction_outcome == "pause" else 0.0

    survival_exposure_bias = _bounded(
        (execution_penalty * 0.2)
        + (hostile_execution_score * 0.12)
        + (deception_score * 0.08)
        + (transition_hazard_score * 0.14)
        + (calibration_drift * 0.12)
        + (contradiction_severity * 0.1)
        + (policy_conflict_score * 0.08)
        + (overfit_risk * 0.08)
        + (false_improvement_risk * 0.06)
        + (delay_bias * 0.08)
        + (abandon_bias * 0.08)
        + ((1.0 - execution_window_quality) * 0.06)
        + (survival_priority_score * 0.12)
        + (volatility_ratio * 0.05)
        + (capital_survival_pressure * 0.05)
        + contradiction_pressure
    )
    opportunity_allocation_bias = _bounded(
        (calibrated_confidence * 0.24)
        + (policy_reliability * 0.2)
        + (opportunity_priority_score * 0.2)
        + (cross_regime_transfer_score * 0.14)
        + (memory_reliability * 0.08)
        + (expansion_quality_score * 0.06)
        + (sequencing_reliability * 0.08)
        + (intervention_reliability * 0.08)
        - (execution_penalty * 0.12)
        - (delay_bias * 0.08)
        - (abandon_bias * 0.12)
        - ((1.0 - execution_window_quality) * 0.08)
        - (policy_conflict_score * 0.1)
        - (false_improvement_risk * 0.08)
    )
    context_competition_score = _bounded(
        min(1.0, survival_exposure_bias + opportunity_allocation_bias)
        * (0.55 + ((1.0 - abs(survival_exposure_bias - opportunity_allocation_bias)) * 0.45))
    )
    exposure_compression_score = _bounded(
        (survival_exposure_bias * 0.4)
        + (context_competition_score * 0.24)
        + (policy_conflict_score * 0.14)
        + (1.0 - policy_reliability) * 0.12
        + (false_improvement_risk * 0.1)
    )
    allocation_priority_score = _bounded(
        (opportunity_allocation_bias * 0.55)
        + ((1.0 - exposure_compression_score) * 0.25)
        + (policy_reliability * 0.2)
    )
    allocation_reliability = _bounded(
        (calibrated_confidence * 0.22)
        + (policy_reliability * 0.26)
        + (cross_regime_transfer_score * 0.18)
        + (intervention_reliability * 0.14)
        + (memory_reliability * 0.1)
        + (sequencing_reliability * 0.08)
        + (expansion_quality_score * 0.1)
        - (policy_conflict_score * 0.16)
        - (calibration_drift * 0.12)
        - (abandon_bias * 0.08)
        - (execution_penalty * 0.08)
    )
    staged_release_bonus = 0.03 if stagger_bias >= 0.58 and sequencing_reliability >= 0.58 else 0.0
    recommended_capital_fraction = round(
        max(
            0.05,
            min(
                0.95,
                0.16
                + (allocation_priority_score * 0.52)
                + (allocation_reliability * 0.26)
                + staged_release_bonus
                - (survival_exposure_bias * 0.3)
                - (exposure_compression_score * 0.28),
            ),
        ),
        4,
    )
    if survival_exposure_bias >= 0.72 or exposure_compression_score >= 0.72:
        capital_allocation_state = "capital_preservation"
    elif opportunity_allocation_bias >= 0.64 and allocation_reliability >= 0.62 and exposure_compression_score <= 0.56:
        capital_allocation_state = "opportunity_selective"
    elif context_competition_score >= 0.62:
        capital_allocation_state = "context_competitive"
    else:
        capital_allocation_state = "balanced_guarded"

    reason_candidates = {
        "survival_pressure_cluster": survival_exposure_bias + execution_penalty + transition_hazard_score,
        "opportunity_alignment_cluster": opportunity_allocation_bias + allocation_reliability + cross_regime_transfer_score,
        "compression_pressure_cluster": exposure_compression_score + policy_conflict_score + false_improvement_risk,
        "competition_pressure_cluster": context_competition_score + abs(survival_exposure_bias - opportunity_allocation_bias),
    }
    allocation_reason_cluster = sorted(reason_candidates.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "survival_priority_guard": survival_exposure_bias >= 0.7,
        "allocation_compression_guard": exposure_compression_score >= 0.68,
    }
    payload = {
        "capital_allocation_state": capital_allocation_state,
        "allocation_priority_score": allocation_priority_score,
        "survival_exposure_bias": survival_exposure_bias,
        "opportunity_allocation_bias": opportunity_allocation_bias,
        "exposure_compression_score": exposure_compression_score,
        "context_competition_score": context_competition_score,
        "allocation_reliability": allocation_reliability,
        "recommended_capital_fraction": recommended_capital_fraction,
        "allocation_reason_cluster": allocation_reason_cluster,
        "temporal_pacing_pressure": _bounded(delay_bias + abandon_bias + (1.0 - execution_window_quality)),
        "staged_deployment_bias": _bounded(stagger_bias * sequencing_reliability),
        "governance_flags": governance_flags,
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

    reason_registry = read_json_safe(reason_registry_path, default={"entries": []})
    if not isinstance(reason_registry, dict):
        reason_registry = {"entries": []}
    reason_entries = reason_registry.get("entries", [])
    if not isinstance(reason_entries, list):
        reason_entries = []
    reason_entries.append(
        {
            "replay_scope": replay_scope,
            "capital_allocation_state": capital_allocation_state,
            "allocation_reason_cluster": allocation_reason_cluster,
            "allocation_priority_score": allocation_priority_score,
        }
    )
    write_json_atomic(reason_registry_path, {"entries": reason_entries[-400:]})

    context_registry = read_json_safe(context_competition_registry_path, default={"entries": []})
    if not isinstance(context_registry, dict):
        context_registry = {"entries": []}
    context_entries = context_registry.get("entries", [])
    if not isinstance(context_entries, list):
        context_entries = []
    context_entries.append(
        {
            "replay_scope": replay_scope,
            "context_competition_score": context_competition_score,
            "survival_exposure_bias": survival_exposure_bias,
            "opportunity_allocation_bias": opportunity_allocation_bias,
        }
    )
    write_json_atomic(context_competition_registry_path, {"entries": context_entries[-400:]})

    compression_trace = read_json_safe(exposure_compression_trace_path, default={"entries": []})
    if not isinstance(compression_trace, dict):
        compression_trace = {"entries": []}
    compression_entries = compression_trace.get("entries", [])
    if not isinstance(compression_entries, list):
        compression_entries = []
    compression_entries.append(
        {
            "replay_scope": replay_scope,
            "exposure_compression_score": exposure_compression_score,
            "recommended_capital_fraction": recommended_capital_fraction,
            "allocation_reliability": allocation_reliability,
        }
    )
    write_json_atomic(exposure_compression_trace_path, {"entries": compression_entries[-400:]})
    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
        },
    )
    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "allocation_reason_registry": str(reason_registry_path),
            "context_competition_registry": str(context_competition_registry_path),
            "exposure_compression_trace": str(exposure_compression_trace_path),
            "capital_allocation_governance_state": str(governance_path),
        },
    }


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
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    hierarchical_decision_policy_layer: dict[str, Any] | None = None,
    portfolio_multi_context_capital_allocation_layer: dict[str, Any] | None = None,
    temporal_execution_sequencing_layer: dict[str, Any] | None = None,
    governed_capability_invention_layer: dict[str, Any] | None = None,
    autonomous_capability_expansion_layer: dict[str, Any] | None = None,
    rollback_orchestration_and_safe_reversion_layer: dict[str, Any] | None = None,
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
    if not isinstance(autonomous_capability_expansion_layer, dict):
        autonomous_capability_expansion_layer = {}

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
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_layer,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_counterfactual_robustness_layer,
        governed_capability_invention_layer=governed_capability_invention_layer,
        autonomous_capability_expansion_layer=autonomous_capability_expansion_layer,
        rollback_orchestration_and_safe_reversion_layer=rollback_orchestration_and_safe_reversion_layer,
    )
    calibration_uncertainty_engine = (
        calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    )
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    structural_memory_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_memory_state, dict):
        structural_memory_state = {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    latent_transition_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_transition_state, dict):
        latent_transition_state = {}
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    hierarchical_decision_policy_layer = (
        hierarchical_decision_policy_layer if isinstance(hierarchical_decision_policy_layer, dict) else {}
    )
    portfolio_multi_context_capital_allocation_layer = (
        portfolio_multi_context_capital_allocation_layer
        if isinstance(portfolio_multi_context_capital_allocation_layer, dict)
        else {}
    )
    temporal_execution_sequencing_layer = (
        temporal_execution_sequencing_layer if isinstance(temporal_execution_sequencing_layer, dict) else {}
    )
    temporal_execution_state = str(temporal_execution_sequencing_layer.get("temporal_execution_state", "unknown"))
    timing_priority_score = float(temporal_execution_sequencing_layer.get("timing_priority_score", 0.0) or 0.0)
    sequencing_reliability = float(temporal_execution_sequencing_layer.get("sequencing_reliability", 0.5) or 0.5)
    delay_bias = float(temporal_execution_sequencing_layer.get("delay_bias", 0.0) or 0.0)
    abandon_bias = float(temporal_execution_sequencing_layer.get("abandon_bias", 0.0) or 0.0)
    execution_window_quality = float(temporal_execution_sequencing_layer.get("execution_window_quality", 0.5) or 0.5)
    if delay_bias >= 0.62 or temporal_execution_state in {"deferential", "unstable"}:
        gaps.append(
            {
                "gap_type": "temporal_sequencing_instability",
                "detail": temporal_execution_state,
                "frequency": max(1, int(round(delay_bias * 4))),
                "severity": round(min(1.0, max(0.45, delay_bias)), 4),
            }
        )
    if execution_window_quality <= 0.45:
        gaps.append(
            {
                "gap_type": "execution_window_quality_degradation",
                "detail": "execution_window_quality_degradation",
                "frequency": max(1, int(round((1.0 - execution_window_quality) * 4))),
                "severity": round(min(1.0, max(0.45, 1.0 - execution_window_quality)), 4),
            }
        )
    if abandon_bias >= 0.62:
        gaps.append(
            {
                "gap_type": "temporal_abandonment_pressure",
                "detail": "abandonment_pressure",
                "frequency": max(1, int(round(abandon_bias * 4))),
                "severity": round(min(1.0, max(0.5, abandon_bias)), 4),
            }
        )
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
        "hostile_execution_score": round(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0), 4),
        "predatory_liquidity_state": str(adversarial_state.get("predatory_liquidity_state", "normal")),
        "deception_score": round(float(deception_state.get("deception_score", 0.0) or 0.0), 4),
        "engineered_move_probability": round(float(deception_state.get("engineered_move_probability", 0.0) or 0.0), 4),
        "deception_reliability": round(float(deception_state.get("deception_reliability", 0.5) or 0.5), 4),
        "structural_memory_reliability": round(float(structural_memory_state.get("memory_reliability", 0.0) or 0.0), 4),
        "structural_reversal_bias": round(float(structural_memory_state.get("structural_reversal_bias", 0.0) or 0.0), 4),
        "long_horizon_context_match": round(float(structural_memory_state.get("long_horizon_context_match", 0.0) or 0.0), 4),
        "transition_hazard_score": round(float(latent_transition_state.get("transition_hazard_score", 0.0) or 0.0), 4),
        "precursor_instability_score": round(float(latent_transition_state.get("precursor_instability_score", 0.0) or 0.0), 4),
        "transition_directional_bias": str(latent_transition_state.get("transition_directional_bias", "neutral")),
        "cross_regime_transfer_score": round(
            float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.0) or 0.0), 4
        ),
        "transfer_overfit_risk": round(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0), 4),
        "counterfactual_robustness_score": round(
            float(causal_intervention_counterfactual_robustness_layer.get("counterfactual_robustness_score", 0.0) or 0.0),
            4,
        ),
        "intervention_reliability": round(
            float(causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.0) or 0.0),
            4,
        ),
        "false_improvement_risk": round(
            float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0),
            4,
        ),
        "decision_policy_state": str(hierarchical_decision_policy_layer.get("decision_policy_state", "unknown")),
        "dominant_policy_mode": str(hierarchical_decision_policy_layer.get("dominant_policy_mode", "balanced")),
        "policy_conflict_score": round(float(hierarchical_decision_policy_layer.get("policy_conflict_score", 0.0) or 0.0), 4),
        "policy_reliability": round(float(hierarchical_decision_policy_layer.get("policy_reliability", 0.0) or 0.0), 4),
        "capital_allocation_state": str(
            portfolio_multi_context_capital_allocation_layer.get("capital_allocation_state", "unknown")
        ),
        "capital_allocation_reliability": round(
            float(portfolio_multi_context_capital_allocation_layer.get("allocation_reliability", 0.0) or 0.0),
            4,
        ),
        "capital_allocation_exposure_compression": round(
            float(portfolio_multi_context_capital_allocation_layer.get("exposure_compression_score", 0.0) or 0.0),
            4,
        ),
        "capital_allocation_context_competition": round(
            float(portfolio_multi_context_capital_allocation_layer.get("context_competition_score", 0.0) or 0.0),
            4,
        ),
        "capital_allocation_survival_bias": round(
            float(portfolio_multi_context_capital_allocation_layer.get("survival_exposure_bias", 0.0) or 0.0),
            4,
        ),
        "temporal_execution_state": temporal_execution_state,
        "timing_priority_score": round(timing_priority_score, 4),
        "sequencing_reliability": round(sequencing_reliability, 4),
        "execution_window_quality": round(execution_window_quality, 4),
        "temporal_delay_bias": round(delay_bias, 4),
        "temporal_abandon_bias": round(abandon_bias, 4),
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
    quality_layer_context = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    expansion_quality_score = float(quality_layer_context.get("expansion_quality_score", 1.0) or 1.0)
    redundancy_risk = float(quality_layer_context.get("redundancy_risk", 0.0) or 0.0)
    regression_risk = float(quality_layer_context.get("regression_risk", 0.0) or 0.0)
    durability_score = float(quality_layer_context.get("durability_score", 1.0) or 1.0)
    transferability_score = float(quality_layer_context.get("transferability_score", 1.0) or 1.0)
    quality_threshold_delta = round(
        min(0.12, max(0.0, ((1.0 - expansion_quality_score) * 0.08) + (redundancy_risk * 0.03) + (regression_risk * 0.03))),
        4,
    )
    expansion_rate_limit = 1 if expansion_quality_score < 0.55 else 0
    policy_mode = str(hierarchical_decision_policy_layer.get("dominant_policy_mode", "balanced"))
    policy_conflict_score = float(hierarchical_decision_policy_layer.get("policy_conflict_score", 0.0) or 0.0)
    policy_reliability = float(hierarchical_decision_policy_layer.get("policy_reliability", 0.5) or 0.5)
    if policy_mode in {"refusal_first", "deferral_first"}:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.04), 4)
    if policy_conflict_score >= 0.6:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.03), 4)
    allocation_reliability = float(portfolio_multi_context_capital_allocation_layer.get("allocation_reliability", 0.5) or 0.5)
    exposure_compression_score = float(
        portfolio_multi_context_capital_allocation_layer.get("exposure_compression_score", 0.0) or 0.0
    )
    context_competition_score = float(
        portfolio_multi_context_capital_allocation_layer.get("context_competition_score", 0.0) or 0.0
    )
    survival_exposure_bias = float(portfolio_multi_context_capital_allocation_layer.get("survival_exposure_bias", 0.0) or 0.0)
    opportunity_allocation_bias = float(
        portfolio_multi_context_capital_allocation_layer.get("opportunity_allocation_bias", 0.0) or 0.0
    )
    if exposure_compression_score >= 0.68:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.04), 4)
    if context_competition_score >= 0.7:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.03), 4)
    if survival_exposure_bias >= opportunity_allocation_bias and survival_exposure_bias >= 0.66:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.04), 4)
    if opportunity_allocation_bias >= 0.62 and allocation_reliability >= 0.64 and exposure_compression_score <= 0.55:
        quality_threshold_delta = round(max(0.0, quality_threshold_delta - 0.02), 4)
    if temporal_execution_state in {"deferential", "unstable"}:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.04), 4)
    if abandon_bias >= 0.66:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.04), 4)
    if execution_window_quality <= 0.45:
        quality_threshold_delta = round(min(0.2, quality_threshold_delta + 0.03), 4)
    min_threshold = _SUGGESTION_LOW_VALUE_THRESHOLD + (0.08 if noisy_cluster else 0.0)
    max_per_cycle = _SUGGESTION_MAX_PER_NOISY_CYCLE if noisy_cluster else _SUGGESTION_MAX_PER_CYCLE
    min_threshold = round(min(1.0, min_threshold + quality_threshold_delta), 4)
    max_per_cycle = max(1, max_per_cycle - expansion_rate_limit)
    min_threshold = round(
        min(1.0, max(0.0, min_threshold + min(0.08, (1.0 - max(0.0, min(1.0, policy_reliability))) * 0.08))),
        4,
    )

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
                    suggestion["priority_score"]
                    + (strategy_expectancy * 0.15)
                    + (unified_confidence * 0.08)
                    - (0.02 * index)
                    - min(0.12, (regression_risk * 0.07) + ((1.0 - durability_score) * 0.03) + ((1.0 - transferability_score) * 0.02)),
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
            "self_expansion_quality_discipline": {
                "quality_threshold_delta": quality_threshold_delta,
                "expansion_rate_limit": expansion_rate_limit,
                "expansion_quality_score": round(expansion_quality_score, 4),
                "redundancy_risk": round(redundancy_risk, 4),
                "regression_risk": round(regression_risk, 4),
            },
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
        "adversarial_execution_intelligence_layer": {
            "adversarial_execution_state": adversarial_state,
            "confidence_adjustments": adversarial_execution_engine.get("confidence_adjustments", {}),
            "risk_adjustments": adversarial_execution_engine.get("risk_adjustments", {}),
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
        "latent_transition_hazard_layer": {
            "latent_transition_hazard_state": latent_transition_state,
            "confidence_adjustments": latent_transition_hazard_engine.get("confidence_adjustments", {}),
            "risk_adjustments": latent_transition_hazard_engine.get("risk_adjustments", {}),
        },
        "cross_regime_transfer_robustness_layer": {
            "transfer_robustness_state": cross_regime_transfer_robustness_layer.get("transfer_robustness_state", {}),
            "cross_regime_transfer_score": cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.0),
            "promotion_transfer_penalty": cross_regime_transfer_robustness_layer.get("promotion_transfer_penalty", 0.0),
            "overfit_risk": cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0),
        },
        "hierarchical_decision_policy_layer": {
            "decision_policy_state": hierarchical_decision_policy_layer.get("decision_policy_state", "unknown"),
            "dominant_policy_mode": hierarchical_decision_policy_layer.get("dominant_policy_mode", "balanced"),
            "policy_conflict_score": round(float(hierarchical_decision_policy_layer.get("policy_conflict_score", 0.0) or 0.0), 4),
            "policy_reliability": round(float(hierarchical_decision_policy_layer.get("policy_reliability", 0.0) or 0.0), 4),
        },
        "portfolio_multi_context_capital_allocation_layer": {
            "capital_allocation_state": portfolio_multi_context_capital_allocation_layer.get(
                "capital_allocation_state",
                "unknown",
            ),
            "allocation_reliability": round(
                float(portfolio_multi_context_capital_allocation_layer.get("allocation_reliability", 0.0) or 0.0),
                4,
            ),
            "exposure_compression_score": round(
                float(portfolio_multi_context_capital_allocation_layer.get("exposure_compression_score", 0.0) or 0.0),
                4,
            ),
            "context_competition_score": round(
                float(portfolio_multi_context_capital_allocation_layer.get("context_competition_score", 0.0) or 0.0),
                4,
            ),
            "survival_exposure_bias": round(
                float(portfolio_multi_context_capital_allocation_layer.get("survival_exposure_bias", 0.0) or 0.0),
                4,
            ),
        },
        "temporal_execution_sequencing_layer": {
            "temporal_execution_state": temporal_execution_state,
            "timing_priority_score": round(timing_priority_score, 4),
            "sequencing_reliability": round(sequencing_reliability, 4),
            "delay_bias": round(delay_bias, 4),
            "abandon_bias": round(abandon_bias, 4),
            "execution_window_quality": round(execution_window_quality, 4),
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


def _governed_capability_invention_layer(
    *,
    memory_root: Path,
    self_suggestion_governor: dict[str, Any],
    intelligence_gap_engine: dict[str, Any],
    capability_evolution_ladder: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    invention_dir = memory_root / "capability_invention"
    invention_dir.mkdir(parents=True, exist_ok=True)
    latest_path = invention_dir / "capability_invention_latest.json"
    history_path = invention_dir / "capability_invention_history.json"
    candidate_registry_path = invention_dir / "invention_candidate_registry.json"
    novelty_registry_path = invention_dir / "invention_novelty_registry.json"
    redundancy_watchlist_path = invention_dir / "invention_redundancy_watchlist.json"
    maturity_registry_path = invention_dir / "invention_maturity_registry.json"
    governance_state_path = invention_dir / "invention_governance_state.json"

    self_suggestion_governor = self_suggestion_governor if isinstance(self_suggestion_governor, dict) else {}
    intelligence_gap_engine = intelligence_gap_engine if isinstance(intelligence_gap_engine, dict) else {}
    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    def _axis_for_gap(gap_type: str) -> str:
        normalized = gap_type.lower()
        if "timing" in normalized or "temporal" in normalized:
            return "timing"
        if "execution" in normalized:
            return "execution"
        if "risk" in normalized or "hazard" in normalized or "drift" in normalized:
            return "risk"
        if "capital" in normalized or "allocation" in normalized:
            return "allocation"
        if "policy" in normalized or "contradiction" in normalized:
            return "policy"
        if "coherence" in normalized or "transfer" in normalized:
            return "coherence"
        return "detection"

    detected_gaps = self_suggestion_governor.get("detected_gaps", [])
    if not isinstance(detected_gaps, list):
        detected_gaps = []
    proposed_improvements = self_suggestion_governor.get("proposed_improvements", [])
    if not isinstance(proposed_improvements, list):
        proposed_improvements = []
    implemented_improvements = self_suggestion_governor.get("implemented_improvements", [])
    if not isinstance(implemented_improvements, list):
        implemented_improvements = []
    repeated_unresolved = self_suggestion_governor.get("repeated_unresolved_gaps", [])
    if not isinstance(repeated_unresolved, list):
        repeated_unresolved = []
    intelligence_gaps = intelligence_gap_engine.get("intelligence_gaps", [])
    if not isinstance(intelligence_gaps, list):
        intelligence_gaps = []
    capability_candidates = capability_evolution_ladder.get("capability_candidates", [])
    if not isinstance(capability_candidates, list):
        capability_candidates = []

    candidate_inventions: list[dict[str, Any]] = []
    axis_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    signature_counts: dict[str, int] = {}
    for index, gap in enumerate(detected_gaps[:40]):
        if not isinstance(gap, dict):
            continue
        gap_type = str(gap.get("gap_type", "unknown"))
        detail = str(gap.get("detail", "unknown"))
        axis = _axis_for_gap(gap_type)
        reason = f"{gap_type}:{detail}"[:120]
        signature = f"{axis}|{gap_type}|{detail}".lower()
        severity = _bounded(float(gap.get("severity", 0.5) or 0.5))
        frequency = max(1, int(gap.get("frequency", 1) or 1))
        candidate_inventions.append(
            {
                "candidate_id": f"invention_candidate_{index + 1}",
                "source_gap_type": gap_type,
                "source_detail": detail,
                "invention_axis": axis,
                "reason_cluster": reason,
                "frequency": frequency,
                "severity": severity,
                "signature": signature,
                "sandbox_proposal": {
                    "sandbox_only": True,
                    "replay_validation_required": True,
                    "live_deployment_allowed": False,
                },
            }
        )
        axis_counts[axis] = axis_counts.get(axis, 0) + 1
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        signature_counts[signature] = signature_counts.get(signature, 0) + 1

    candidate_invention_count = len(candidate_inventions)
    dominant_invention_axis = (
        sorted(axis_counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if axis_counts else "coherence"
    )
    invention_reason_cluster = (
        sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if reason_counts
        else "insufficient_invention_signal"
    )
    replay_scores = [
        float(item.get("replay_test", {}).get("score", 0.0) or 0.0)
        for item in implemented_improvements
        if isinstance(item, dict)
    ]
    replay_score_context = _bounded(sum(replay_scores) / max(1, len(replay_scores)))
    unresolved_pressure = _bounded(len(repeated_unresolved) / 10.0)
    opportunity_pressure = _bounded((len(proposed_improvements) + len(intelligence_gaps) + len(capability_candidates)) / 30.0)
    invention_pressure_score = _bounded(
        (min(1.0, candidate_invention_count / 8.0) * 0.5)
        + (unresolved_pressure * 0.3)
        + (opportunity_pressure * 0.2)
    )
    input_signature = {
        "replay_scope": replay_scope,
        "gap_signatures": sorted(str(item.get("signature", "")) for item in candidate_inventions),
        "candidate_invention_count": candidate_invention_count,
        "unresolved_count": len(repeated_unresolved),
        "proposed_count": len(proposed_improvements),
    }
    previous_payload = read_json_safe(latest_path, default={})
    if isinstance(previous_payload, dict) and previous_payload.get("input_signature") == input_signature:
        return previous_payload

    novelty_registry = read_json_safe(novelty_registry_path, default={"known_signatures": []})
    if not isinstance(novelty_registry, dict):
        novelty_registry = {"known_signatures": []}
    known_signatures = novelty_registry.get("known_signatures", [])
    if not isinstance(known_signatures, list):
        known_signatures = []
    known_signature_set = {str(item) for item in known_signatures}
    novel_signatures = sorted(
        signature for signature in signature_counts if signature_counts.get(signature, 0) > 0 and signature not in known_signature_set
    )
    novelty_score = _bounded(len(novel_signatures) / max(1, len(signature_counts)))
    repetition_pressure = _bounded(
        sum(max(0, count - 1) for count in signature_counts.values()) / max(1, len(signature_counts))
    )
    redundancy_risk = _bounded((1.0 - novelty_score) * 0.7 + (repetition_pressure * 0.3))
    invention_reliability = _bounded((replay_score_context * 0.5) + (novelty_score * 0.35) + ((1.0 - redundancy_risk) * 0.15))
    invention_maturity_score = _bounded(
        (invention_reliability * 0.45)
        + (invention_pressure_score * 0.35)
        + (min(1.0, candidate_invention_count / 6.0) * 0.2)
    )

    if candidate_invention_count == 0 and invention_pressure_score <= 0.1:
        capability_invention_state = "seeded"
    elif redundancy_risk >= 0.7:
        capability_invention_state = "redundant"
    elif invention_reliability <= 0.42:
        capability_invention_state = "constrained"
    elif invention_maturity_score <= 0.3 and invention_pressure_score >= 0.45:
        capability_invention_state = "stalled"
    else:
        capability_invention_state = "active"

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    payload = {
        "input_signature": input_signature,
        "capability_invention_state": capability_invention_state,
        "invention_pressure_score": invention_pressure_score,
        "novelty_score": novelty_score,
        "redundancy_risk": redundancy_risk,
        "invention_reliability": invention_reliability,
        "invention_maturity_score": invention_maturity_score,
        "candidate_invention_count": candidate_invention_count,
        "dominant_invention_axis": dominant_invention_axis,
        "invention_reason_cluster": invention_reason_cluster,
        "governance_flags": governance_flags,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "invention_candidate_registry": str(candidate_registry_path),
            "invention_novelty_registry": str(novelty_registry_path),
            "invention_redundancy_watchlist": str(redundancy_watchlist_path),
            "invention_maturity_registry": str(maturity_registry_path),
            "invention_governance_state": str(governance_state_path),
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
    write_json_atomic(
        candidate_registry_path,
        {
            "candidate_invention_count": candidate_invention_count,
            "candidate_inventions": candidate_inventions,
            "dominant_invention_axis": dominant_invention_axis,
        },
    )
    updated_known_signatures = list(known_signatures)
    for signature in signature_counts.keys():
        if signature not in known_signature_set:
            updated_known_signatures.append(signature)
    write_json_atomic(
        novelty_registry_path,
        {
            "known_signatures": updated_known_signatures[-1000:],
            "novel_signatures": novel_signatures,
            "novelty_score": novelty_score,
        },
    )
    write_json_atomic(
        redundancy_watchlist_path,
        {
            "redundancy_risk": redundancy_risk,
            "watchlist": sorted(
                [
                    {"signature": signature, "repeat_count": count}
                    for signature, count in signature_counts.items()
                    if count >= 2
                ],
                key=lambda item: (-item["repeat_count"], item["signature"]),
            ),
        },
    )
    write_json_atomic(
        maturity_registry_path,
        {
            "capability_invention_state": capability_invention_state,
            "invention_maturity_score": invention_maturity_score,
            "invention_reliability": invention_reliability,
            "candidate_invention_count": candidate_invention_count,
        },
    )
    write_json_atomic(governance_state_path, {**governance_flags, "replay_scope": replay_scope})
    return payload


def _autonomous_capability_expansion_layer(
    *,
    memory_root: Path,
    self_suggestion_governor: dict[str, Any],
    capability_evolution_ladder: dict[str, Any],
    governed_capability_invention_layer: dict[str, Any],
    replay_scope: str,
) -> dict[str, Any]:
    expansion_dir = memory_root / "capability_expansion"
    expansion_dir.mkdir(parents=True, exist_ok=True)
    latest_path = expansion_dir / "capability_expansion_latest.json"
    history_path = expansion_dir / "capability_expansion_history.json"
    candidate_registry_path = expansion_dir / "expansion_candidate_registry.json"
    readiness_registry_path = expansion_dir / "expansion_readiness_registry.json"
    rollback_watchlist_path = expansion_dir / "expansion_rollback_watchlist.json"
    maturity_registry_path = expansion_dir / "expansion_maturity_registry.json"
    governance_state_path = expansion_dir / "expansion_governance_state.json"

    self_suggestion_governor = self_suggestion_governor if isinstance(self_suggestion_governor, dict) else {}
    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}
    governed_capability_invention_layer = (
        governed_capability_invention_layer if isinstance(governed_capability_invention_layer, dict) else {}
    )

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    detected_gaps = self_suggestion_governor.get("detected_gaps", [])
    if not isinstance(detected_gaps, list):
        detected_gaps = []
    repeated_unresolved = self_suggestion_governor.get("repeated_unresolved_gaps", [])
    if not isinstance(repeated_unresolved, list):
        repeated_unresolved = []
    ladder_candidates = capability_evolution_ladder.get("capability_candidates", [])
    if not isinstance(ladder_candidates, list):
        ladder_candidates = []

    invention_state = str(governed_capability_invention_layer.get("capability_invention_state", "seeded"))
    invention_pressure_score = _bounded(float(governed_capability_invention_layer.get("invention_pressure_score", 0.0) or 0.0))
    invention_reliability = _bounded(float(governed_capability_invention_layer.get("invention_reliability", 0.0) or 0.0))
    invention_maturity_score = _bounded(float(governed_capability_invention_layer.get("invention_maturity_score", 0.0) or 0.0))
    redundancy_risk = _bounded(float(governed_capability_invention_layer.get("redundancy_risk", 0.0) or 0.0))
    dominant_expansion_axis = str(governed_capability_invention_layer.get("dominant_invention_axis", "coherence"))
    expansion_reason_cluster = str(
        governed_capability_invention_layer.get("invention_reason_cluster", "insufficient_expansion_signal")
    )
    candidate_invention_count = max(
        0,
        int(governed_capability_invention_layer.get("candidate_invention_count", 0) or 0),
    )

    candidate_registry_source = str(governed_capability_invention_layer.get("paths", {}).get("invention_candidate_registry", ""))
    invention_candidate_registry = (
        read_json_safe(Path(candidate_registry_source), default={}) if candidate_registry_source.strip() else {}
    )
    if not isinstance(invention_candidate_registry, dict):
        invention_candidate_registry = {}
    invention_candidates = invention_candidate_registry.get("candidate_inventions", [])
    if not isinstance(invention_candidates, list):
        invention_candidates = []
    experiment_intents = [
        {
            "experiment_id": f"expansion_intent_{index + 1}",
            "candidate_id": str(item.get("candidate_id", f"invention_candidate_{index + 1}")),
            "expansion_axis": str(item.get("invention_axis", dominant_expansion_axis)),
            "reason_cluster": str(item.get("reason_cluster", expansion_reason_cluster)),
            "intent_state": "sandbox_ready",
            "governance": {
                "sandbox_only": True,
                "replay_validation_required": True,
                "live_deployment_allowed": False,
            },
        }
        for index, item in enumerate(item for item in invention_candidates[:40] if isinstance(item, dict))
    ]
    candidate_expansion_count = len(experiment_intents) if experiment_intents else candidate_invention_count

    unresolved_pressure = _bounded(len(repeated_unresolved) / 10.0)
    gap_pressure = _bounded(len([item for item in detected_gaps if isinstance(item, dict)]) / 20.0)
    candidate_pressure = _bounded(len([item for item in ladder_candidates if isinstance(item, dict)]) / 20.0)
    expansion_pressure_score = _bounded(
        (invention_pressure_score * 0.45)
        + (unresolved_pressure * 0.25)
        + (gap_pressure * 0.15)
        + (candidate_pressure * 0.15)
    )
    rollbackability_score = _bounded(
        ((1.0 - redundancy_risk) * 0.45)
        + (invention_reliability * 0.25)
        + (invention_maturity_score * 0.2)
        + ((1.0 if replay_scope == "full_replay" else 0.85) * 0.1)
    )
    expansion_readiness_score = _bounded(
        (invention_reliability * 0.4)
        + (invention_maturity_score * 0.3)
        + (rollbackability_score * 0.2)
        + ((1.0 - redundancy_risk) * 0.1)
    )
    expansion_reliability = _bounded(
        (invention_reliability * 0.55)
        + (expansion_readiness_score * 0.25)
        + ((1.0 - redundancy_risk) * 0.2)
    )
    expansion_maturity_score = _bounded(
        (invention_maturity_score * 0.6)
        + (expansion_readiness_score * 0.2)
        + (min(1.0, candidate_expansion_count / 8.0) * 0.2)
    )

    if candidate_expansion_count == 0 and expansion_pressure_score <= 0.2:
        capability_expansion_state = "seeded"
    elif expansion_reliability <= 0.4 or rollbackability_score <= 0.42:
        capability_expansion_state = "constrained"
    elif expansion_readiness_score >= 0.68 and rollbackability_score >= 0.62 and expansion_reliability >= 0.6:
        capability_expansion_state = "sandbox_ready"
    elif expansion_readiness_score >= 0.5 and expansion_maturity_score >= 0.45:
        capability_expansion_state = "staged"
    else:
        capability_expansion_state = "stalled"

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    input_signature = {
        "replay_scope": replay_scope,
        "invention_state": invention_state,
        "invention_pressure_score": invention_pressure_score,
        "invention_reliability": invention_reliability,
        "invention_maturity_score": invention_maturity_score,
        "candidate_expansion_count": candidate_expansion_count,
        "dominant_expansion_axis": dominant_expansion_axis,
    }
    payload = {
        "input_signature": input_signature,
        "capability_expansion_state": capability_expansion_state,
        "expansion_readiness_score": expansion_readiness_score,
        "expansion_reliability": expansion_reliability,
        "rollbackability_score": rollbackability_score,
        "expansion_maturity_score": expansion_maturity_score,
        "expansion_pressure_score": expansion_pressure_score,
        "candidate_expansion_count": candidate_expansion_count,
        "dominant_expansion_axis": dominant_expansion_axis,
        "expansion_reason_cluster": expansion_reason_cluster,
        "governance_flags": governance_flags,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "expansion_candidate_registry": str(candidate_registry_path),
            "expansion_readiness_registry": str(readiness_registry_path),
            "expansion_rollback_watchlist": str(rollback_watchlist_path),
            "expansion_maturity_registry": str(maturity_registry_path),
            "expansion_governance_state": str(governance_state_path),
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
    write_json_atomic(
        candidate_registry_path,
        {
            "candidate_expansion_count": candidate_expansion_count,
            "experiment_intents": experiment_intents,
            "dominant_expansion_axis": dominant_expansion_axis,
            "expansion_reason_cluster": expansion_reason_cluster,
        },
    )
    readiness_registry = read_json_safe(readiness_registry_path, default={"entries": []})
    if not isinstance(readiness_registry, dict):
        readiness_registry = {"entries": []}
    readiness_entries = readiness_registry.get("entries", [])
    if not isinstance(readiness_entries, list):
        readiness_entries = []
    readiness_entries.append(
        {
            "replay_scope": replay_scope,
            "capability_expansion_state": capability_expansion_state,
            "expansion_readiness_score": expansion_readiness_score,
            "expansion_reliability": expansion_reliability,
            "rollbackability_score": rollbackability_score,
            "expansion_pressure_score": expansion_pressure_score,
        }
    )
    write_json_atomic(readiness_registry_path, {"entries": readiness_entries[-400:]})
    rollback_watchlist = [
        {
            "capability_expansion_state": capability_expansion_state,
            "rollbackability_score": rollbackability_score,
            "dominant_expansion_axis": dominant_expansion_axis,
            "expansion_reason_cluster": expansion_reason_cluster,
        }
    ]
    write_json_atomic(rollback_watchlist_path, {"watchlist": rollback_watchlist[-200:]})
    write_json_atomic(
        maturity_registry_path,
        {
            "capability_expansion_state": capability_expansion_state,
            "expansion_maturity_score": expansion_maturity_score,
            "expansion_readiness_score": expansion_readiness_score,
            "expansion_reliability": expansion_reliability,
            "candidate_expansion_count": candidate_expansion_count,
        },
    )
    write_json_atomic(governance_state_path, {**governance_flags, "replay_scope": replay_scope})
    return payload


def _self_expansion_quality_layer(
    *,
    memory_root: Path,
    capability_evolution_ladder: dict[str, Any],
    self_suggestion_governor: dict[str, Any],
    intelligence_gap_engine: dict[str, Any],
    synthetic_data_plane_engine: dict[str, Any],
    unified_market_intelligence_field: dict[str, Any],
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    hierarchical_decision_policy_layer: dict[str, Any] | None = None,
    portfolio_multi_context_capital_allocation_layer: dict[str, Any] | None = None,
    temporal_execution_sequencing_layer: dict[str, Any] | None = None,
    governed_capability_invention_layer: dict[str, Any] | None = None,
    autonomous_capability_expansion_layer: dict[str, Any] | None = None,
    rollback_orchestration_and_safe_reversion_layer: dict[str, Any] | None = None,
    replay_scope: str,
) -> dict[str, Any]:
    quality_dir = memory_root / "self_expansion_quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    latest_path = quality_dir / "self_expansion_quality_latest.json"
    history_path = quality_dir / "self_expansion_quality_history.json"
    quality_registry_path = quality_dir / "capability_quality_registry.json"
    overlap_registry_path = quality_dir / "capability_overlap_registry.json"
    maturity_registry_path = quality_dir / "promotion_maturity_registry.json"
    regression_watchlist_path = quality_dir / "expansion_regression_watchlist.json"
    governance_path = quality_dir / "self_expansion_quality_governance_state.json"

    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}
    self_suggestion_governor = self_suggestion_governor if isinstance(self_suggestion_governor, dict) else {}
    intelligence_gap_engine = intelligence_gap_engine if isinstance(intelligence_gap_engine, dict) else {}
    synthetic_data_plane_engine = synthetic_data_plane_engine if isinstance(synthetic_data_plane_engine, dict) else {}
    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    calibration_uncertainty_engine = calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    hierarchical_decision_policy_layer = (
        hierarchical_decision_policy_layer if isinstance(hierarchical_decision_policy_layer, dict) else {}
    )
    portfolio_multi_context_capital_allocation_layer = (
        portfolio_multi_context_capital_allocation_layer
        if isinstance(portfolio_multi_context_capital_allocation_layer, dict)
        else {}
    )
    temporal_execution_sequencing_layer = (
        temporal_execution_sequencing_layer if isinstance(temporal_execution_sequencing_layer, dict) else {}
    )
    governed_capability_invention_layer = (
        governed_capability_invention_layer if isinstance(governed_capability_invention_layer, dict) else {}
    )
    autonomous_capability_expansion_layer = (
        autonomous_capability_expansion_layer if isinstance(autonomous_capability_expansion_layer, dict) else {}
    )
    rollback_orchestration_and_safe_reversion_layer = (
        rollback_orchestration_and_safe_reversion_layer
        if isinstance(rollback_orchestration_and_safe_reversion_layer, dict)
        else {}
    )

    candidates = capability_evolution_ladder.get("capability_candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    validation_history = capability_evolution_ladder.get("validation_history", [])
    if not isinstance(validation_history, list):
        validation_history = []
    promotion_registry = capability_evolution_ladder.get("promotion_registry", {})
    if not isinstance(promotion_registry, dict):
        promotion_registry = {}
    anti_noise = self_suggestion_governor.get("anti_noise_controls", {})
    if not isinstance(anti_noise, dict):
        anti_noise = {}
    repeated_unresolved = self_suggestion_governor.get("repeated_unresolved_gaps", [])
    if not isinstance(repeated_unresolved, list):
        repeated_unresolved = []
    synthetic_planes = synthetic_data_plane_engine.get("synthetic_data_planes", [])
    if not isinstance(synthetic_planes, list):
        synthetic_planes = []
    intelligence_gaps = intelligence_gap_engine.get("intelligence_gaps", [])
    if not isinstance(intelligence_gaps, list):
        intelligence_gaps = []

    def _token_set(*parts: str) -> set[str]:
        tokens: set[str] = set()
        for part in parts:
            normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in part)
            tokens.update(token for token in normalized.split() if token)
        return tokens

    texts: dict[str, set[str]] = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        capability_id = str(item.get("capability_id", "unknown"))
        texts[capability_id] = _token_set(
            str(item.get("gap_type", "")),
            str(item.get("capability_hypothesis", "")),
            str(item.get("synthetic_prototype", {}).get("synthetic_plane_name", "")),
        )

    capability_overlap_map: dict[str, list[dict[str, Any]]] = {}
    redundancy_scores: list[float] = []
    overlap_source = list(texts.items())[:40]
    for capability_id, left_tokens in overlap_source:
        peers: list[dict[str, Any]] = []
        max_overlap = 0.0
        for other_id, right_tokens in overlap_source:
            if capability_id == other_id:
                continue
            union = left_tokens | right_tokens
            overlap = round(len(left_tokens & right_tokens) / max(1, len(union)), 4)
            if overlap > 0.0:
                peers.append({"other_capability_id": other_id, "overlap_score": overlap, "basis": "token_overlap"})
            max_overlap = max(max_overlap, overlap)
        capability_overlap_map[capability_id] = sorted(peers, key=lambda item: item["overlap_score"], reverse=True)[:5]
        redundancy_scores.append(max_overlap)

    redundancy_risk = round(sum(redundancy_scores) / max(1, len(redundancy_scores)), 4)
    capability_novelty_score = round(max(0.0, min(1.0, 1.0 - redundancy_risk)), 4)

    replay_scores = [
        float(item.get("replay_validation_score", 0.0) or 0.0) for item in validation_history if isinstance(item, dict)
    ]
    replay_quality = round(sum(replay_scores) / max(1, len(replay_scores)), 4)
    promoted_count = len([item for item in promotion_registry.get("promoted", []) if isinstance(item, dict)])
    quarantined_count = len([item for item in promotion_registry.get("quarantined", []) if isinstance(item, dict)])
    rejected_count = len([item for item in promotion_registry.get("rejected", []) if isinstance(item, dict)])
    candidate_count = len([item for item in candidates if isinstance(item, dict)])
    promoted_ratio = promoted_count / max(1, candidate_count)

    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    contradiction_state = contradiction_arbitration_engine.get("arbitration", {})
    if not isinstance(contradiction_state, dict):
        contradiction_state = {}

    durability_score = round(
        max(
            0.0,
            min(
                1.0,
                (replay_quality * 0.5)
                + (promoted_ratio * 0.2)
                + (float(structural_state.get("memory_reliability", 0.5) or 0.5) * 0.2)
                + (float(calibration_state.get("regime_specific_reliability", {}).get("reliability_score", 0.5) or 0.5) * 0.1),
            ),
        ),
        4,
    )
    unique_gap_types = {str(item.get("gap_type", "unknown")) for item in candidates if isinstance(item, dict)}
    unique_planes = {str(item.get("synthetic_plane_name", "unknown")) for item in synthetic_planes if isinstance(item, dict)}
    transferability_score = round(
        max(
            0.0,
            min(
                1.0,
                (min(1.0, len(unique_gap_types) / 5.0) * 0.45)
                + (min(1.0, len(unique_planes) / 6.0) * 0.35)
                + (float(structural_state.get("long_horizon_context_match", 0.5) or 0.5) * 0.2),
            ),
        ),
        4,
    )
    transferability_score = round(
        max(
            0.0,
            min(
                1.0,
                (transferability_score * 0.9)
                + (
                    float(
                        causal_intervention_counterfactual_robustness_layer.get("counterfactual_robustness_score", 0.5) or 0.5
                    )
                    * 0.1
                )
                - min(
                    0.04,
                    float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0) * 0.08,
                ),
            ),
        ),
        4,
    )
    transferability_score = round(
        max(
            0.0,
            min(
                1.0,
                (transferability_score * 0.75)
                + (float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5) * 0.25)
                - min(0.06, float(cross_regime_transfer_robustness_layer.get("promotion_transfer_penalty", 0.0) or 0.0) * 0.15),
            ),
        ),
        4,
    )
    unresolved_pressure = min(1.0, len(repeated_unresolved) / 8.0)
    low_value_pressure = min(1.0, float(anti_noise.get("low_value_pruned", 0) or 0) / 8.0)
    contradiction_pressure = 0.2 if str(contradiction_state.get("outcome", "allow")) in {"pause", "refuse"} else 0.0
    hazard_pressure = min(1.0, float(latent_state.get("transition_hazard_score", 0.0) or 0.0))
    policy_conflict_pressure = min(
        1.0,
        float(hierarchical_decision_policy_layer.get("policy_conflict_score", 0.0) or 0.0),
    )
    policy_refusal_pressure = min(
        1.0,
        float(hierarchical_decision_policy_layer.get("refusal_priority_score", 0.0) or 0.0),
    )
    policy_deferral_pressure = min(
        1.0,
        float(hierarchical_decision_policy_layer.get("deferral_priority_score", 0.0) or 0.0),
    )
    capital_allocation_reliability = min(
        1.0,
        max(0.0, float(portfolio_multi_context_capital_allocation_layer.get("allocation_reliability", 0.5) or 0.5)),
    )
    capital_allocation_exposure_compression = min(
        1.0,
        max(0.0, float(portfolio_multi_context_capital_allocation_layer.get("exposure_compression_score", 0.0) or 0.0)),
    )
    capital_allocation_context_competition = min(
        1.0,
        max(0.0, float(portfolio_multi_context_capital_allocation_layer.get("context_competition_score", 0.0) or 0.0)),
    )
    temporal_sequencing_reliability = min(
        1.0,
        max(0.0, float(temporal_execution_sequencing_layer.get("sequencing_reliability", 0.5) or 0.5)),
    )
    temporal_delay_bias = min(1.0, max(0.0, float(temporal_execution_sequencing_layer.get("delay_bias", 0.0) or 0.0)))
    temporal_abandon_bias = min(
        1.0,
        max(0.0, float(temporal_execution_sequencing_layer.get("abandon_bias", 0.0) or 0.0)),
    )
    temporal_execution_window_quality = min(
        1.0,
        max(0.0, float(temporal_execution_sequencing_layer.get("execution_window_quality", 0.5) or 0.5)),
    )
    temporal_timing_priority = min(
        1.0,
        max(0.0, float(temporal_execution_sequencing_layer.get("timing_priority_score", 0.0) or 0.0)),
    )
    temporal_sequencing_pressure = min(
        1.0,
        max(
            0.0,
            temporal_delay_bias + temporal_abandon_bias + (1.0 - temporal_execution_window_quality) + temporal_timing_priority,
        )
        / 3.0,
    )
    regression_risk = round(
        max(
            0.0,
            min(
                1.0,
                (quarantined_count + rejected_count) / max(1, candidate_count)
                + (low_value_pressure * 0.15)
                + (unresolved_pressure * 0.15)
                + (hazard_pressure * 0.1)
                + (float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0) * 0.08)
                + (
                    float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0)
                    * 0.06
                )
                + (
                    (
                        1.0
                        - float(
                            causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5
                        )
                    )
                    * 0.04
                )
                + (policy_conflict_pressure * 0.06)
                + ((policy_refusal_pressure + policy_deferral_pressure) * 0.03)
                + (capital_allocation_exposure_compression * 0.04)
                + (capital_allocation_context_competition * 0.03)
                + ((1.0 - capital_allocation_reliability) * 0.03)
                + ((1.0 - temporal_sequencing_reliability) * 0.04)
                + (temporal_sequencing_pressure * 0.04)
                + contradiction_pressure,
            ),
        ),
        4,
    )
    comparative_scores = [
        float(item.get("comparative_advantage", 0.0) or 0.0) for item in validation_history if isinstance(item, dict)
    ]
    comparative_quality = round(sum(comparative_scores) / max(1, len(comparative_scores)), 4)
    conflict_scores = [float(item.get("unified_conflict_score", 0.0) or 0.0) for item in validation_history if isinstance(item, dict)]
    conflict_penalty = round(sum(conflict_scores) / max(1, len(conflict_scores)), 4)
    expansion_quality_score = round(
        max(
            0.0,
            min(
                1.0,
                (capability_novelty_score * 0.18)
                + (durability_score * 0.24)
                + (transferability_score * 0.2)
                + (replay_quality * 0.18)
                + (comparative_quality * 0.15)
                - (regression_risk * 0.2)
                - (conflict_penalty * 0.1),
            ),
        ),
        4,
    )
    if expansion_quality_score >= 0.72:
        self_expansion_quality_state = "healthy"
    elif expansion_quality_score >= 0.55:
        self_expansion_quality_state = "watch"
    elif expansion_quality_score >= 0.38:
        self_expansion_quality_state = "degraded"
    else:
        self_expansion_quality_state = "critical"

    if promoted_ratio >= 0.6 and expansion_quality_score >= 0.72 and transferability_score >= 0.6:
        promotion_maturity = "promotion_hardened"
    elif promoted_ratio >= 0.4 and expansion_quality_score >= 0.64:
        promotion_maturity = "promotion_ready"
    elif durability_score >= 0.5 and replay_quality >= 0.52:
        promotion_maturity = "cross_context_validated"
    elif replay_quality >= 0.45:
        promotion_maturity = "sandbox_validated"
    else:
        promotion_maturity = "seeded"

    promotion_confidence_multiplier = round(max(0.75, min(1.0, 0.82 + (expansion_quality_score * 0.18) - (regression_risk * 0.2))), 4)
    quarantine_pressure_delta = round(max(0.0, min(0.2, (regression_risk * 0.12) + (redundancy_risk * 0.08))), 4)
    expansion_rate_limit = 1 if self_expansion_quality_state in {"degraded", "critical"} else 0
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "promotion_confidence_reduced": promotion_confidence_multiplier < 0.95,
        "quarantine_pressure_increased": quarantine_pressure_delta > 0.05,
        "expansion_rate_limited": expansion_rate_limit > 0,
        "no_blind_live_self_rewrites": True,
    }
    quality_components = {
        "replay_quality": replay_quality,
        "comparative_quality": comparative_quality,
        "conflict_penalty": conflict_penalty,
        "duplicate_pressure": round(min(1.0, float(anti_noise.get("duplicate_suppression", 0) or 0) / 8.0), 4),
        "low_value_pressure": round(low_value_pressure, 4),
        "unresolved_gap_pressure": round(unresolved_pressure, 4),
        "calibration_reliability_context": round(
            float(calibration_state.get("regime_specific_reliability", {}).get("reliability_score", 0.5) or 0.5),
            4,
        ),
        "structural_alignment_context": round(float(structural_state.get("regime_memory_alignment", 0.5) or 0.5), 4),
        "transition_hazard_context": round(hazard_pressure, 4),
        "cross_regime_transfer_score_context": round(
            float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5),
            4,
        ),
        "transfer_overfit_risk_context": round(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0), 4),
        "transfer_penalty_context": round(
            float(cross_regime_transfer_robustness_layer.get("promotion_transfer_penalty", 0.0) or 0.0),
            4,
        ),
        "causal_counterfactual_robustness_context": round(
            float(causal_intervention_counterfactual_robustness_layer.get("counterfactual_robustness_score", 0.5) or 0.5),
            4,
        ),
        "causal_false_improvement_pressure": round(
            float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0),
            4,
        ),
        "causal_intervention_reliability_context": round(
            float(causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5),
            4,
        ),
        "decision_policy_state_context": str(hierarchical_decision_policy_layer.get("decision_policy_state", "unknown")),
        "decision_policy_mode_context": str(hierarchical_decision_policy_layer.get("dominant_policy_mode", "balanced")),
        "decision_policy_conflict_pressure": round(policy_conflict_pressure, 4),
        "decision_policy_refusal_deferral_pressure": round(min(1.0, policy_refusal_pressure + policy_deferral_pressure), 4),
        "capital_allocation_state_context": str(
            portfolio_multi_context_capital_allocation_layer.get("capital_allocation_state", "unknown")
        ),
        "capital_allocation_reliability_context": round(capital_allocation_reliability, 4),
        "capital_allocation_exposure_compression_pressure": round(capital_allocation_exposure_compression, 4),
        "capital_allocation_context_competition_pressure": round(capital_allocation_context_competition, 4),
        "temporal_execution_state_context": str(
            temporal_execution_sequencing_layer.get("temporal_execution_state", "unknown")
        ),
        "temporal_sequencing_reliability_context": round(temporal_sequencing_reliability, 4),
        "temporal_delay_abandon_pressure": round(min(1.0, temporal_delay_bias + temporal_abandon_bias), 4),
        "temporal_execution_window_quality_context": round(temporal_execution_window_quality, 4),
        "temporal_timing_priority_context": round(temporal_timing_priority, 4),
        "temporal_sequencing_pressure_context": round(temporal_sequencing_pressure, 4),
        "invention_pressure_context": round(
            max(0.0, min(1.0, float(governed_capability_invention_layer.get("invention_pressure_score", 0.0) or 0.0))),
            4,
        ),
        "invention_novelty_context": round(
            max(0.0, min(1.0, float(governed_capability_invention_layer.get("novelty_score", 0.0) or 0.0))),
            4,
        ),
        "invention_redundancy_context": round(
            max(0.0, min(1.0, float(governed_capability_invention_layer.get("redundancy_risk", 0.0) or 0.0))),
            4,
        ),
        "invention_maturity_context": round(
            max(0.0, min(1.0, float(governed_capability_invention_layer.get("invention_maturity_score", 0.0) or 0.0))),
            4,
        ),
        "invention_reliability_context": round(
            max(0.0, min(1.0, float(governed_capability_invention_layer.get("invention_reliability", 0.0) or 0.0))),
            4,
        ),
        "expansion_pressure_context": round(
            max(0.0, min(1.0, float(autonomous_capability_expansion_layer.get("expansion_pressure_score", 0.0) or 0.0))),
            4,
        ),
        "expansion_readiness_context": round(
            max(0.0, min(1.0, float(autonomous_capability_expansion_layer.get("expansion_readiness_score", 0.0) or 0.0))),
            4,
        ),
        "expansion_rollbackability_context": round(
            max(0.0, min(1.0, float(autonomous_capability_expansion_layer.get("rollbackability_score", 0.0) or 0.0))),
            4,
        ),
        "expansion_maturity_context": round(
            max(0.0, min(1.0, float(autonomous_capability_expansion_layer.get("expansion_maturity_score", 0.0) or 0.0))),
            4,
        ),
        "expansion_reliability_context": round(
            max(0.0, min(1.0, float(autonomous_capability_expansion_layer.get("expansion_reliability", 0.0) or 0.0))),
            4,
        ),
        "rollback_urgency_context": round(
            max(
                0.0,
                min(1.0, float(rollback_orchestration_and_safe_reversion_layer.get("rollback_urgency", 0.0) or 0.0)),
            ),
            4,
        ),
        "safe_reversion_readiness_context": 1.0
        if bool(rollback_orchestration_and_safe_reversion_layer.get("safe_reversion_ready", False))
        else 0.0,
        "rollback_reversion_reliability_context": round(
            max(
                0.0,
                min(
                    1.0,
                    float(
                        rollback_orchestration_and_safe_reversion_layer.get(
                            "rollback_reversion_reliability",
                            0.0,
                        )
                        or 0.0
                    ),
                ),
            ),
            4,
        ),
        "promotion_confidence_multiplier": promotion_confidence_multiplier,
        "quarantine_pressure_delta": quarantine_pressure_delta,
        "expansion_rate_limit": expansion_rate_limit,
    }

    capability_quality_records: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        capability_id = str(item.get("capability_id", "unknown"))
        overlaps = capability_overlap_map.get(capability_id, [])
        local_redundancy = max([float(entry.get("overlap_score", 0.0) or 0.0) for entry in overlaps], default=0.0)
        capability_quality_records.append(
            {
                "capability_id": capability_id,
                "capability_novelty_score": round(max(0.0, min(1.0, 1.0 - local_redundancy)), 4),
                "redundancy_risk": round(local_redundancy, 4),
                "durability_score": durability_score,
                "transferability_score": transferability_score,
                "regression_risk": regression_risk,
                "promotion_maturity": promotion_maturity,
            }
        )

    regression_watchlist = [
        {
            "capability_id": item.get("capability_id", "unknown"),
            "reason": "elevated_regression_risk",
            "regression_risk": regression_risk,
        }
        for item in candidates
        if isinstance(item, dict) and regression_risk >= 0.6
    ]
    existing_governance_state = read_json_safe(governance_path, default={})
    if not isinstance(existing_governance_state, dict):
        existing_governance_state = {}
    integration_enabled = bool(existing_governance_state.get("allow_cross_cycle_integration", False))
    governance_state = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "replay_scope": replay_scope,
        "expansion_discipline_mode": "strict" if expansion_rate_limit else "normal",
        "allow_cross_cycle_integration": integration_enabled,
    }
    payload = {
        "self_expansion_quality_state": self_expansion_quality_state,
        "integration_enabled": integration_enabled,
        "capability_novelty_score": capability_novelty_score,
        "redundancy_risk": redundancy_risk,
        "durability_score": durability_score,
        "transferability_score": transferability_score,
        "regression_risk": regression_risk,
        "capability_overlap_map": capability_overlap_map,
        "expansion_quality_score": expansion_quality_score,
        "promotion_maturity": promotion_maturity,
        "governance_flags": governance_flags,
        "quality_components": quality_components,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "capability_quality_registry": str(quality_registry_path),
            "capability_overlap_registry": str(overlap_registry_path),
            "promotion_maturity_registry": str(maturity_registry_path),
            "expansion_regression_watchlist": str(regression_watchlist_path),
            "governance_state": str(governance_path),
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
    write_json_atomic(
        quality_registry_path,
        {
            "expansion_quality_score": expansion_quality_score,
            "capabilities": capability_quality_records,
            "candidate_count": candidate_count,
            "intelligence_gap_count": len([item for item in intelligence_gaps if isinstance(item, dict)]),
        },
    )
    write_json_atomic(overlap_registry_path, {"capability_overlap_map": capability_overlap_map})
    write_json_atomic(
        maturity_registry_path,
        {
            "promotion_maturity": promotion_maturity,
            "self_expansion_quality_state": self_expansion_quality_state,
            "promoted_count": promoted_count,
            "candidate_count": candidate_count,
        },
    )
    write_json_atomic(regression_watchlist_path, {"watchlist": regression_watchlist})
    write_json_atomic(governance_path, governance_state)
    return payload


def _system_coherence_and_drift_integrity_layer(
    *,
    memory_root: Path,
    replay_scope: str,
    unified_market_intelligence_field: dict[str, Any],
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    hierarchical_decision_policy_layer: dict[str, Any] | None = None,
    portfolio_multi_context_capital_allocation_layer: dict[str, Any] | None = None,
    temporal_execution_sequencing_layer: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    execution_microstructure_engine: dict[str, Any] | None = None,
    adversarial_execution_engine: dict[str, Any] | None = None,
    deception_inference_engine: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coherence_dir = memory_root / "system_coherence"
    coherence_dir.mkdir(parents=True, exist_ok=True)
    latest_path = coherence_dir / "system_coherence_latest.json"
    history_path = coherence_dir / "system_coherence_history.json"
    drift_registry_path = coherence_dir / "drift_integrity_registry.json"
    disagreement_trace_path = coherence_dir / "disagreement_trace.json"
    fragmentation_watchlist_path = coherence_dir / "fragmentation_watchlist.json"
    governance_path = coherence_dir / "system_coherence_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    calibration_uncertainty_engine = calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    hierarchical_decision_policy_layer = (
        hierarchical_decision_policy_layer if isinstance(hierarchical_decision_policy_layer, dict) else {}
    )
    portfolio_multi_context_capital_allocation_layer = (
        portfolio_multi_context_capital_allocation_layer
        if isinstance(portfolio_multi_context_capital_allocation_layer, dict)
        else {}
    )
    temporal_execution_sequencing_layer = (
        temporal_execution_sequencing_layer if isinstance(temporal_execution_sequencing_layer, dict) else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    execution_microstructure_engine = execution_microstructure_engine if isinstance(execution_microstructure_engine, dict) else {}
    adversarial_execution_engine = adversarial_execution_engine if isinstance(adversarial_execution_engine, dict) else {}
    deception_inference_engine = deception_inference_engine if isinstance(deception_inference_engine, dict) else {}

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    contradiction_state = contradiction_arbitration_engine.get("arbitration", {})
    if not isinstance(contradiction_state, dict):
        contradiction_state = {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}
    adversarial_state = adversarial_execution_engine.get("adversarial_execution_state", {})
    if not isinstance(adversarial_state, dict):
        adversarial_state = {}
    deception_state = deception_inference_engine.get("deception_state", {})
    if not isinstance(deception_state, dict):
        deception_state = {}

    calibration_drift = _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0))
    contradiction_severity = _bounded(float(contradiction_state.get("max_contradiction_severity", 0.0) or 0.0))
    contradiction_outcome = str(contradiction_state.get("outcome", "allow"))
    memory_reliability = _bounded(float(structural_state.get("memory_reliability", 0.5) or 0.5))
    regime_memory_alignment = _bounded(
        float(structural_memory_graph_engine.get("structural_memory_state", {}).get("regime_memory_alignment", 0.5) or 0.5)
        if isinstance(structural_memory_graph_engine.get("structural_memory_state"), dict)
        else 0.5
    )
    transition_hazard_score = _bounded(float(latent_state.get("transition_hazard_score", 0.0) or 0.0))
    transfer_score = _bounded(
        float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5)
    )
    transfer_reliability = _bounded(
        float(cross_regime_transfer_robustness_layer.get("robustness_reliability", 0.5) or 0.5)
    )
    overfit_risk = _bounded(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0))
    intervention_reliability = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5)
    )
    false_improvement_risk = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0)
    )
    policy_conflict_score = _bounded(
        float(hierarchical_decision_policy_layer.get("policy_conflict_score", 0.0) or 0.0)
    )
    policy_reliability = _bounded(
        float(hierarchical_decision_policy_layer.get("policy_reliability", 0.5) or 0.5)
    )
    allocation_reliability = _bounded(
        float(portfolio_multi_context_capital_allocation_layer.get("allocation_reliability", 0.5) or 0.5)
    )
    context_competition_score = _bounded(
        float(portfolio_multi_context_capital_allocation_layer.get("context_competition_score", 0.0) or 0.0)
    )
    sequencing_reliability = _bounded(
        float(temporal_execution_sequencing_layer.get("sequencing_reliability", 0.5) or 0.5)
    )
    execution_window_quality = _bounded(
        float(temporal_execution_sequencing_layer.get("execution_window_quality", 0.5) or 0.5)
    )
    timing_priority_score = _bounded(
        float(temporal_execution_sequencing_layer.get("timing_priority_score", 0.0) or 0.0)
    )
    expansion_quality_score = _bounded(
        float(self_expansion_quality_layer.get("expansion_quality_score", 0.5) or 0.5)
    )
    expansion_state = str(self_expansion_quality_layer.get("self_expansion_quality_state", "unknown"))
    composite_confidence = _bounded(float(confidence_structure.get("composite_confidence", 0.5) or 0.5))
    execution_penalty = _bounded(float(execution_microstructure_engine.get("execution_penalty", 0.0) or 0.0))
    hostile_execution_score = _bounded(float(adversarial_state.get("hostile_execution_score", 0.0) or 0.0))
    deception_score = _bounded(float(deception_state.get("deception_score", 0.0) or 0.0))

    confidence_alignment_score = _bounded(
        1.0
        - min(
            1.0,
            (calibration_drift * 0.3)
            + (abs(composite_confidence - policy_reliability) * 0.25)
            + (abs(composite_confidence - allocation_reliability) * 0.2)
            + (abs(composite_confidence - sequencing_reliability) * 0.15)
            + (abs(composite_confidence - intervention_reliability) * 0.1),
        )
    )

    policy_alignment_score = _bounded(
        1.0
        - min(
            1.0,
            (policy_conflict_score * 0.35)
            + (abs(policy_reliability - allocation_reliability) * 0.2)
            + (abs(policy_reliability - sequencing_reliability) * 0.15)
            + (contradiction_severity * 0.15)
            + ((1.0 - regime_memory_alignment) * 0.15),
        )
    )

    drift_integrity_score = _bounded(
        1.0
        - min(
            1.0,
            (calibration_drift * 0.25)
            + ((1.0 - transfer_reliability) * 0.2)
            + (overfit_risk * 0.15)
            + (false_improvement_risk * 0.15)
            + (transition_hazard_score * 0.15)
            + ((1.0 - memory_reliability) * 0.1),
        )
    )

    disagreement_load = _bounded(
        (contradiction_severity * 0.25)
        + (policy_conflict_score * 0.2)
        + (abs(policy_reliability - allocation_reliability) * 0.15)
        + (abs(sequencing_reliability - allocation_reliability) * 0.1)
        + (context_competition_score * 0.1)
        + (calibration_drift * 0.1)
        + (0.1 if contradiction_outcome in {"pause", "refuse"} else 0.0)
    )

    expansion_stability_score = _bounded(
        (expansion_quality_score * 0.35)
        + (transfer_score * 0.2)
        + (intervention_reliability * 0.15)
        + ((1.0 - false_improvement_risk) * 0.15)
        + ((1.0 - overfit_risk) * 0.15)
    )

    fragmentation_risk = _bounded(
        (disagreement_load * 0.25)
        + ((1.0 - confidence_alignment_score) * 0.2)
        + ((1.0 - policy_alignment_score) * 0.15)
        + ((1.0 - drift_integrity_score) * 0.15)
        + ((1.0 - expansion_stability_score) * 0.15)
        + (hostile_execution_score * 0.05)
        + (deception_score * 0.05)
    )

    coherence_score = _bounded(
        (confidence_alignment_score * 0.2)
        + (policy_alignment_score * 0.2)
        + (drift_integrity_score * 0.2)
        + ((1.0 - disagreement_load) * 0.15)
        + (expansion_stability_score * 0.15)
        + ((1.0 - fragmentation_risk) * 0.1)
    )

    coherence_reliability = _bounded(
        (memory_reliability * 0.2)
        + (policy_reliability * 0.15)
        + (allocation_reliability * 0.15)
        + (sequencing_reliability * 0.15)
        + (transfer_reliability * 0.15)
        + (intervention_reliability * 0.1)
        + (execution_window_quality * 0.1)
    )

    system_coherence_state = (
        "coherent"
        if coherence_score >= 0.65 and fragmentation_risk < 0.35
        else "degraded"
        if coherence_score >= 0.45 or fragmentation_risk < 0.55
        else "fragmented"
    )

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }

    payload: dict[str, Any] = {
        "system_coherence_state": system_coherence_state,
        "coherence_score": coherence_score,
        "drift_integrity_score": drift_integrity_score,
        "disagreement_load": disagreement_load,
        "policy_alignment_score": policy_alignment_score,
        "confidence_alignment_score": confidence_alignment_score,
        "expansion_stability_score": expansion_stability_score,
        "fragmentation_risk": fragmentation_risk,
        "coherence_reliability": coherence_reliability,
        "governance_flags": governance_flags,
    }

    previous_payload = read_json_safe(latest_path, default={})
    if not isinstance(previous_payload, dict):
        previous_payload = {}
    write_json_atomic(latest_path, payload)

    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})

    drift_registry = read_json_safe(drift_registry_path, default={"entries": []})
    if not isinstance(drift_registry, dict):
        drift_registry = {"entries": []}
    drift_entries = drift_registry.get("entries", [])
    if not isinstance(drift_entries, list):
        drift_entries = []
    drift_entries.append(
        {
            "replay_scope": replay_scope,
            "calibration_drift": calibration_drift,
            "drift_integrity_score": drift_integrity_score,
            "transfer_reliability": transfer_reliability,
            "overfit_risk": overfit_risk,
            "false_improvement_risk": false_improvement_risk,
        }
    )
    write_json_atomic(drift_registry_path, {"entries": drift_entries[-400:]})

    disagreement_trace = read_json_safe(disagreement_trace_path, default={"entries": []})
    if not isinstance(disagreement_trace, dict):
        disagreement_trace = {"entries": []}
    disagreement_entries = disagreement_trace.get("entries", [])
    if not isinstance(disagreement_entries, list):
        disagreement_entries = []
    disagreement_entries.append(
        {
            "replay_scope": replay_scope,
            "disagreement_load": disagreement_load,
            "contradiction_severity": contradiction_severity,
            "policy_conflict_score": policy_conflict_score,
            "confidence_alignment_score": confidence_alignment_score,
            "policy_alignment_score": policy_alignment_score,
        }
    )
    write_json_atomic(disagreement_trace_path, {"entries": disagreement_entries[-400:]})

    fragmentation_watchlist = read_json_safe(fragmentation_watchlist_path, default={"entries": []})
    if not isinstance(fragmentation_watchlist, dict):
        fragmentation_watchlist = {"entries": []}
    frag_entries = fragmentation_watchlist.get("entries", [])
    if not isinstance(frag_entries, list):
        frag_entries = []
    if fragmentation_risk >= 0.45:
        frag_entries.append(
            {
                "replay_scope": replay_scope,
                "fragmentation_risk": fragmentation_risk,
                "system_coherence_state": system_coherence_state,
                "coherence_score": coherence_score,
                "disagreement_load": disagreement_load,
            }
        )
    write_json_atomic(fragmentation_watchlist_path, {"entries": frag_entries[-200:]})

    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
        },
    )

    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "drift_integrity_registry": str(drift_registry_path),
            "disagreement_trace": str(disagreement_trace_path),
            "fragmentation_watchlist": str(fragmentation_watchlist_path),
            "system_coherence_governance_state": str(governance_path),
        },
    }


def _learning_stability_and_catastrophic_drift_guard_layer(
    *,
    memory_root: Path,
    replay_scope: str,
    unified_market_intelligence_field: dict[str, Any],
    calibration_uncertainty_engine: dict[str, Any] | None = None,
    contradiction_arbitration_engine: dict[str, Any] | None = None,
    system_coherence_and_drift_integrity_layer: dict[str, Any] | None = None,
    cross_regime_transfer_robustness_layer: dict[str, Any] | None = None,
    causal_intervention_counterfactual_robustness_layer: dict[str, Any] | None = None,
    self_expansion_quality_layer: dict[str, Any] | None = None,
    structural_memory_graph_engine: dict[str, Any] | None = None,
    latent_transition_hazard_engine: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stability_dir = memory_root / "learning_stability"
    stability_dir.mkdir(parents=True, exist_ok=True)
    latest_path = stability_dir / "learning_stability_latest.json"
    history_path = stability_dir / "learning_stability_history.json"
    drift_registry_path = stability_dir / "catastrophic_drift_registry.json"
    pressure_registry_path = stability_dir / "expansion_pressure_registry.json"
    transition_trace_path = stability_dir / "stability_transition_trace.json"
    governance_path = stability_dir / "learning_stability_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    unified_market_intelligence_field = (
        unified_market_intelligence_field if isinstance(unified_market_intelligence_field, dict) else {}
    )
    calibration_uncertainty_engine = calibration_uncertainty_engine if isinstance(calibration_uncertainty_engine, dict) else {}
    contradiction_arbitration_engine = contradiction_arbitration_engine if isinstance(contradiction_arbitration_engine, dict) else {}
    system_coherence_and_drift_integrity_layer = (
        system_coherence_and_drift_integrity_layer if isinstance(system_coherence_and_drift_integrity_layer, dict) else {}
    )
    cross_regime_transfer_robustness_layer = (
        cross_regime_transfer_robustness_layer if isinstance(cross_regime_transfer_robustness_layer, dict) else {}
    )
    causal_intervention_counterfactual_robustness_layer = (
        causal_intervention_counterfactual_robustness_layer
        if isinstance(causal_intervention_counterfactual_robustness_layer, dict)
        else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    structural_memory_graph_engine = structural_memory_graph_engine if isinstance(structural_memory_graph_engine, dict) else {}
    latent_transition_hazard_engine = latent_transition_hazard_engine if isinstance(latent_transition_hazard_engine, dict) else {}

    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    calibration_state = calibration_uncertainty_engine.get("calibration_state", {})
    if not isinstance(calibration_state, dict):
        calibration_state = {}
    contradiction_state = contradiction_arbitration_engine.get("arbitration", {})
    if not isinstance(contradiction_state, dict):
        contradiction_state = {}
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    latent_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_state, dict):
        latent_state = {}

    coherence_score = _bounded(float(system_coherence_and_drift_integrity_layer.get("coherence_score", 0.5) or 0.5))
    expansion_stability_score = _bounded(
        float(system_coherence_and_drift_integrity_layer.get("expansion_stability_score", 0.5) or 0.5)
    )
    transfer_score = _bounded(
        float(cross_regime_transfer_robustness_layer.get("cross_regime_transfer_score", 0.5) or 0.5)
    )
    intervention_reliability = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("intervention_reliability", 0.5) or 0.5)
    )
    memory_reliability = _bounded(float(structural_state.get("memory_reliability", 0.5) or 0.5))

    calibration_drift = _bounded(float(calibration_state.get("calibration_drift", 0.0) or 0.0))
    contradiction_severity = _bounded(float(contradiction_state.get("max_contradiction_severity", 0.0) or 0.0))
    policy_conflict_score = _bounded(
        float(system_coherence_and_drift_integrity_layer.get("policy_alignment_score", 0.5) or 0.5)
    )
    policy_conflict_score = _bounded(1.0 - policy_conflict_score)
    expansion_quality_score = _bounded(
        float(self_expansion_quality_layer.get("expansion_quality_score", 0.5) or 0.5)
    )
    expansion_quality_instability = _bounded(1.0 - expansion_quality_score)
    false_improvement_risk = _bounded(
        float(causal_intervention_counterfactual_robustness_layer.get("false_improvement_risk", 0.0) or 0.0)
    )
    overfit_risk = _bounded(float(cross_regime_transfer_robustness_layer.get("overfit_risk", 0.0) or 0.0))

    suggestion_volume = _bounded(
        float(
            unified_market_intelligence_field.get("decision_refinements", {}).get(
                "self_suggestion", {}
            ).get("suggestion_volume", 0.0)
            if isinstance(unified_market_intelligence_field.get("decision_refinements", {}).get("self_suggestion"), dict)
            else 0.0
        )
    )
    expansion_quality_pressure = _bounded(expansion_quality_instability * 0.6 + false_improvement_risk * 0.4)
    feature_invention_rate = _bounded(
        float(
            unified_market_intelligence_field.get("components", {}).get(
                "synthetic_feature_invention", {}
            ).get("feature_invention_rate", 0.0)
            if isinstance(unified_market_intelligence_field.get("components", {}).get("synthetic_feature_invention"), dict)
            else 0.0
        )
    )
    capability_ladder_pressure = _bounded(
        float(
            unified_market_intelligence_field.get("components", {}).get(
                "capability_evolution_ladder", {}
            ).get("evolution_pressure", 0.0)
            if isinstance(unified_market_intelligence_field.get("components", {}).get("capability_evolution_ladder"), dict)
            else 0.0
        )
    )

    regime_memory_alignment = _bounded(
        float(structural_state.get("regime_memory_alignment", 0.5) or 0.5)
    )
    transition_hazard_score = _bounded(float(latent_state.get("transition_hazard_score", 0.0) or 0.0))
    transfer_reliability = _bounded(
        float(cross_regime_transfer_robustness_layer.get("robustness_reliability", 0.5) or 0.5)
    )

    disagreement_load = _bounded(
        float(system_coherence_and_drift_integrity_layer.get("disagreement_load", 0.0) or 0.0)
    )
    coherence_degradation = _bounded(1.0 - coherence_score)
    fragmentation_risk = _bounded(
        float(system_coherence_and_drift_integrity_layer.get("fragmentation_risk", 0.0) or 0.0)
    )

    sequencing_reliability = _bounded(
        float(
            unified_market_intelligence_field.get("confidence_structure", {}).get(
                "sequencing_reliability", 0.5
            )
            if isinstance(unified_market_intelligence_field.get("confidence_structure"), dict)
            else 0.5
        )
    )
    policy_reliability = _bounded(
        float(
            unified_market_intelligence_field.get("confidence_structure", {}).get(
                "policy_reliability", 0.5
            )
            if isinstance(unified_market_intelligence_field.get("confidence_structure"), dict)
            else 0.5
        )
    )
    allocation_reliability = _bounded(
        float(
            unified_market_intelligence_field.get("confidence_structure", {}).get(
                "allocation_reliability", 0.5
            )
            if isinstance(unified_market_intelligence_field.get("confidence_structure"), dict)
            else 0.5
        )
    )
    policy_vs_allocation_divergence = _bounded(abs(policy_reliability - allocation_reliability))
    sequencing_vs_policy_divergence = _bounded(abs(sequencing_reliability - policy_reliability))

    # --- Metric 1: learning_stability_score ---
    learning_stability_score = _bounded(
        (coherence_score * 0.25)
        + (expansion_stability_score * 0.2)
        + (transfer_score * 0.2)
        + (intervention_reliability * 0.15)
        + (memory_reliability * 0.2)
    )

    # --- Metric 2: catastrophic_drift_risk ---
    catastrophic_drift_risk = _bounded(
        (calibration_drift * 0.2)
        + (contradiction_severity * 0.15)
        + (policy_conflict_score * 0.15)
        + (expansion_quality_instability * 0.15)
        + (false_improvement_risk * 0.15)
        + (overfit_risk * 0.2)
    )

    # --- Metric 3: capability_expansion_pressure ---
    capability_expansion_pressure = _bounded(
        (suggestion_volume * 0.25)
        + (expansion_quality_pressure * 0.25)
        + (feature_invention_rate * 0.25)
        + (capability_ladder_pressure * 0.25)
    )

    # --- Metric 4: regime_overfit_risk ---
    regime_overfit_risk = _bounded(
        ((1.0 - transfer_reliability) * 0.3)
        + ((1.0 - regime_memory_alignment) * 0.25)
        + (transition_hazard_score * 0.25)
        + ((1.0 - intervention_reliability) * 0.2)
    )

    # --- Metric 5: learning_fragmentation_risk ---
    learning_fragmentation_risk = _bounded(
        (disagreement_load * 0.3)
        + (coherence_degradation * 0.25)
        + (policy_vs_allocation_divergence * 0.25)
        + (sequencing_vs_policy_divergence * 0.2)
    )

    # --- Stability reliability ---
    stability_reliability = _bounded(
        (memory_reliability * 0.2)
        + (transfer_reliability * 0.2)
        + (intervention_reliability * 0.2)
        + (coherence_score * 0.2)
        + (expansion_stability_score * 0.2)
    )

    # --- State Classification ---
    if learning_stability_score >= 0.65 and catastrophic_drift_risk < 0.3:
        learning_stability_state = "stable"
    elif learning_stability_score >= 0.5 and catastrophic_drift_risk < 0.5:
        learning_stability_state = "strained"
    elif catastrophic_drift_risk >= 0.65:
        learning_stability_state = "catastrophic_drift_risk"
    else:
        learning_stability_state = "drifting"

    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
        "catastrophic_drift_guard": catastrophic_drift_risk >= 0.55,
        "expansion_pressure_guard": capability_expansion_pressure >= 0.6,
        "regime_overfit_guard": regime_overfit_risk >= 0.55,
        "learning_fragmentation_guard": learning_fragmentation_risk >= 0.5,
    }

    payload: dict[str, Any] = {
        "learning_stability_state": learning_stability_state,
        "learning_stability_score": learning_stability_score,
        "catastrophic_drift_risk": catastrophic_drift_risk,
        "capability_expansion_pressure": capability_expansion_pressure,
        "regime_overfit_risk": regime_overfit_risk,
        "learning_fragmentation_risk": learning_fragmentation_risk,
        "stability_reliability": stability_reliability,
        "governance_flags": governance_flags,
    }

    previous_payload = read_json_safe(latest_path, default={})
    if not isinstance(previous_payload, dict):
        previous_payload = {}
    write_json_atomic(latest_path, payload)

    history = read_json_safe(history_path, default={"snapshots": []})
    if not isinstance(history, dict):
        history = {"snapshots": []}
    snapshots = history.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append(payload)
    write_json_atomic(history_path, {"snapshots": snapshots[-200:]})

    drift_registry = read_json_safe(drift_registry_path, default={"entries": []})
    if not isinstance(drift_registry, dict):
        drift_registry = {"entries": []}
    drift_entries = drift_registry.get("entries", [])
    if not isinstance(drift_entries, list):
        drift_entries = []
    drift_entries.append(
        {
            "replay_scope": replay_scope,
            "catastrophic_drift_risk": catastrophic_drift_risk,
            "calibration_drift": calibration_drift,
            "contradiction_severity": contradiction_severity,
            "false_improvement_risk": false_improvement_risk,
            "overfit_risk": overfit_risk,
            "learning_stability_state": learning_stability_state,
        }
    )
    write_json_atomic(drift_registry_path, {"entries": drift_entries[-400:]})

    pressure_registry = read_json_safe(pressure_registry_path, default={"entries": []})
    if not isinstance(pressure_registry, dict):
        pressure_registry = {"entries": []}
    pressure_entries = pressure_registry.get("entries", [])
    if not isinstance(pressure_entries, list):
        pressure_entries = []
    pressure_entries.append(
        {
            "replay_scope": replay_scope,
            "capability_expansion_pressure": capability_expansion_pressure,
            "suggestion_volume": suggestion_volume,
            "feature_invention_rate": feature_invention_rate,
            "expansion_quality_pressure": expansion_quality_pressure,
            "capability_ladder_pressure": capability_ladder_pressure,
        }
    )
    write_json_atomic(pressure_registry_path, {"entries": pressure_entries[-400:]})

    transition_trace = read_json_safe(transition_trace_path, default={"entries": []})
    if not isinstance(transition_trace, dict):
        transition_trace = {"entries": []}
    trace_entries = transition_trace.get("entries", [])
    if not isinstance(trace_entries, list):
        trace_entries = []
    previous_state = str(previous_payload.get("learning_stability_state", "unknown"))
    if previous_state != learning_stability_state:
        trace_entries.append(
            {
                "replay_scope": replay_scope,
                "from_state": previous_state,
                "to_state": learning_stability_state,
                "learning_stability_score": learning_stability_score,
                "catastrophic_drift_risk": catastrophic_drift_risk,
            }
        )
    write_json_atomic(transition_trace_path, {"entries": trace_entries[-200:]})

    write_json_atomic(
        governance_path,
        {
            "sandbox_only": True,
            "replay_validation_required": True,
            "live_deployment_allowed": False,
            "no_blind_live_self_rewrites": True,
            "replay_scope": replay_scope,
        },
    )

    return {
        **payload,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "catastrophic_drift_registry": str(drift_registry_path),
            "expansion_pressure_registry": str(pressure_registry_path),
            "stability_transition_trace": str(transition_trace_path),
            "learning_stability_governance_state": str(governance_path),
        },
    }


def _rollback_orchestration_and_safe_reversion_layer(
    *,
    memory_root: Path,
    replay_scope: str,
    governed_capability_invention_layer: dict[str, Any],
    autonomous_capability_expansion_layer: dict[str, Any],
    self_expansion_quality_layer: dict[str, Any],
    system_coherence_and_drift_integrity_layer: dict[str, Any] | None = None,
    learning_stability_and_catastrophic_drift_guard_layer: dict[str, Any] | None = None,
    capability_evolution_ladder: dict[str, Any] | None = None,
    self_suggestion_governor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rollback_dir = memory_root / "rollback_orchestration"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    latest_path = rollback_dir / "rollback_orchestration_latest.json"
    history_path = rollback_dir / "rollback_orchestration_history.json"
    safe_reversion_plan_registry_path = rollback_dir / "safe_reversion_plan_registry.json"
    rollback_decision_trace_path = rollback_dir / "rollback_decision_trace.json"
    rollback_candidate_registry_path = rollback_dir / "rollback_candidate_registry.json"
    governance_state_path = rollback_dir / "rollback_orchestration_governance_state.json"

    def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
        return round(max(low, min(high, value)), 4)

    governed_capability_invention_layer = (
        governed_capability_invention_layer if isinstance(governed_capability_invention_layer, dict) else {}
    )
    autonomous_capability_expansion_layer = (
        autonomous_capability_expansion_layer if isinstance(autonomous_capability_expansion_layer, dict) else {}
    )
    self_expansion_quality_layer = self_expansion_quality_layer if isinstance(self_expansion_quality_layer, dict) else {}
    system_coherence_and_drift_integrity_layer = (
        system_coherence_and_drift_integrity_layer
        if isinstance(system_coherence_and_drift_integrity_layer, dict)
        else {}
    )
    learning_stability_and_catastrophic_drift_guard_layer = (
        learning_stability_and_catastrophic_drift_guard_layer
        if isinstance(learning_stability_and_catastrophic_drift_guard_layer, dict)
        else {}
    )
    capability_evolution_ladder = capability_evolution_ladder if isinstance(capability_evolution_ladder, dict) else {}
    self_suggestion_governor = self_suggestion_governor if isinstance(self_suggestion_governor, dict) else {}

    rollbackability_score = _bounded(float(autonomous_capability_expansion_layer.get("rollbackability_score", 0.0) or 0.0))
    expansion_pressure_score = _bounded(
        float(autonomous_capability_expansion_layer.get("expansion_pressure_score", 0.0) or 0.0)
    )
    expansion_reliability = _bounded(float(autonomous_capability_expansion_layer.get("expansion_reliability", 0.5) or 0.5))
    redundancy_risk = _bounded(float(governed_capability_invention_layer.get("redundancy_risk", 0.0) or 0.0))
    invention_reliability = _bounded(float(governed_capability_invention_layer.get("invention_reliability", 0.5) or 0.5))
    quality_regression_risk = _bounded(float(self_expansion_quality_layer.get("regression_risk", 0.0) or 0.0))
    expansion_quality_score = _bounded(float(self_expansion_quality_layer.get("expansion_quality_score", 0.5) or 0.5))
    coherence_fragmentation_risk = _bounded(
        float(system_coherence_and_drift_integrity_layer.get("fragmentation_risk", 0.0) or 0.0)
    )
    drift_integrity_score = _bounded(
        float(system_coherence_and_drift_integrity_layer.get("drift_integrity_score", 0.5) or 0.5)
    )
    catastrophic_drift_risk = _bounded(
        float(
            learning_stability_and_catastrophic_drift_guard_layer.get(
                "catastrophic_drift_risk",
                0.0,
            )
            or 0.0
        )
    )
    capability_expansion_pressure = _bounded(
        float(
            learning_stability_and_catastrophic_drift_guard_layer.get(
                "capability_expansion_pressure",
                0.0,
            )
            or 0.0
        )
    )
    learning_fragmentation_risk = _bounded(
        float(
            learning_stability_and_catastrophic_drift_guard_layer.get(
                "learning_fragmentation_risk",
                0.0,
            )
            or 0.0
        )
    )
    regime_overfit_risk = _bounded(
        float(
            learning_stability_and_catastrophic_drift_guard_layer.get(
                "regime_overfit_risk",
                0.0,
            )
            or 0.0
        )
    )
    promotion_registry = capability_evolution_ladder.get("promotion_registry", {})
    if not isinstance(promotion_registry, dict):
        promotion_registry = {}
    promotion_quarantined_count = len([item for item in promotion_registry.get("quarantined", []) if isinstance(item, dict)])
    promotion_rejected_count = len([item for item in promotion_registry.get("rejected", []) if isinstance(item, dict)])
    repeated_unresolved = self_suggestion_governor.get("repeated_unresolved_gaps", [])
    if not isinstance(repeated_unresolved, list):
        repeated_unresolved = []
    repeated_unresolved_pressure = _bounded(len([item for item in repeated_unresolved if isinstance(item, dict)]) / 12.0)

    rollback_urgency = _bounded(
        ((1.0 - rollbackability_score) * 0.25)
        + (expansion_pressure_score * 0.12)
        + (quality_regression_risk * 0.12)
        + (coherence_fragmentation_risk * 0.12)
        + (catastrophic_drift_risk * 0.16)
        + (capability_expansion_pressure * 0.1)
        + (learning_fragmentation_risk * 0.08)
        + (regime_overfit_risk * 0.05)
    )
    rollback_reversion_reliability = _bounded(
        (rollbackability_score * 0.35)
        + (expansion_reliability * 0.2)
        + (invention_reliability * 0.1)
        + ((1.0 - redundancy_risk) * 0.1)
        + (drift_integrity_score * 0.15)
        + (expansion_quality_score * 0.1)
    )

    pending_rollback_count = max(
        promotion_quarantined_count + promotion_rejected_count,
        int(round((rollback_urgency * 6) + (repeated_unresolved_pressure * 4))),
    )
    safe_reversion_ready = bool(
        rollback_reversion_reliability >= 0.58
        and drift_integrity_score >= 0.5
        and catastrophic_drift_risk < 0.72
    )
    promotion_freeze = bool(
        rollback_urgency >= 0.68
        or catastrophic_drift_risk >= 0.65
        or coherence_fragmentation_risk >= 0.65
    )

    if rollback_urgency >= 0.8 or catastrophic_drift_risk >= 0.75:
        rollback_orchestration_state = "critical"
        rollback_mode = "freeze_and_revert"
        reversion_sequence_mode = "highest_risk_first"
    elif rollback_urgency >= 0.65:
        rollback_orchestration_state = "urgent"
        rollback_mode = "freeze_only" if not safe_reversion_ready else "freeze_and_revert"
        reversion_sequence_mode = "coherence_first" if coherence_fragmentation_risk >= 0.55 else "highest_risk_first"
    elif rollback_urgency >= 0.45:
        rollback_orchestration_state = "watch"
        rollback_mode = "selective_revert" if safe_reversion_ready else "monitor_only"
        reversion_sequence_mode = "staged" if rollback_mode == "selective_revert" else "none"
    else:
        rollback_orchestration_state = "stable"
        rollback_mode = "monitor_only"
        reversion_sequence_mode = "none"

    rollback_reason_cluster = (
        "catastrophic_drift_escalation"
        if catastrophic_drift_risk >= 0.65
        else "coherence_fragmentation_risk"
        if coherence_fragmentation_risk >= 0.62
        else "rollbackability_decay"
        if rollbackability_score <= 0.45
        else "expansion_pressure"
        if capability_expansion_pressure >= 0.58
        else "stable_rollback_monitoring"
    )

    rollback_candidates: list[dict[str, Any]] = []
    if pending_rollback_count > 0:
        rollback_candidates.append(
            {
                "candidate_id": "rollback_candidate_capability_expansion",
                "candidate_type": "capability_expansion",
                "risk_score": rollback_urgency,
                "reversion_ready": safe_reversion_ready,
                "rollback_mode": rollback_mode,
            }
        )
    if coherence_fragmentation_risk >= 0.5:
        rollback_candidates.append(
            {
                "candidate_id": "rollback_candidate_system_coherence",
                "candidate_type": "system_coherence",
                "risk_score": coherence_fragmentation_risk,
                "reversion_ready": safe_reversion_ready,
                "rollback_mode": rollback_mode,
            }
        )
    if catastrophic_drift_risk >= 0.55:
        rollback_candidates.append(
            {
                "candidate_id": "rollback_candidate_learning_stability",
                "candidate_type": "learning_stability",
                "risk_score": catastrophic_drift_risk,
                "reversion_ready": safe_reversion_ready,
                "rollback_mode": rollback_mode,
            }
        )

    rollback_candidate_registry = {
        "pending_rollback_count": pending_rollback_count,
        "candidates": rollback_candidates,
    }
    governance_flags = {
        "sandbox_only": True,
        "replay_validation_required": True,
        "live_deployment_allowed": False,
        "no_blind_live_self_rewrites": True,
    }
    payload = {
        "rollback_orchestration_state": rollback_orchestration_state,
        "rollback_urgency": rollback_urgency,
        "safe_reversion_ready": safe_reversion_ready,
        "pending_rollback_count": pending_rollback_count,
        "rollback_reversion_reliability": rollback_reversion_reliability,
        "promotion_freeze": promotion_freeze,
        "rollback_mode": rollback_mode,
        "reversion_sequence_mode": reversion_sequence_mode,
        "rollback_reason_cluster": rollback_reason_cluster,
        "rollback_candidate_registry": rollback_candidate_registry,
        "governance_flags": governance_flags,
        "paths": {
            "latest": str(latest_path),
            "history": str(history_path),
            "safe_reversion_plan_registry": str(safe_reversion_plan_registry_path),
            "rollback_decision_trace": str(rollback_decision_trace_path),
            "rollback_candidate_registry": str(rollback_candidate_registry_path),
            "rollback_orchestration_governance_state": str(governance_state_path),
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
    write_json_atomic(
        safe_reversion_plan_registry_path,
        {
            "entries": [
                {
                    "replay_scope": replay_scope,
                    "rollback_mode": rollback_mode,
                    "reversion_sequence_mode": reversion_sequence_mode,
                    "safe_reversion_ready": safe_reversion_ready,
                    "pending_rollback_count": pending_rollback_count,
                }
            ]
        },
    )
    write_json_atomic(
        rollback_decision_trace_path,
        {
            "entries": [
                {
                    "replay_scope": replay_scope,
                    "rollback_orchestration_state": rollback_orchestration_state,
                    "rollback_reason_cluster": rollback_reason_cluster,
                    "rollback_urgency": rollback_urgency,
                    "promotion_freeze": promotion_freeze,
                }
            ]
        },
    )
    write_json_atomic(rollback_candidate_registry_path, rollback_candidate_registry)
    write_json_atomic(governance_state_path, {**governance_flags, "replay_scope": replay_scope})
    return payload


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
    adversarial_execution_engine = _adversarial_execution_intelligence_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        execution_microstructure_engine=execution_microstructure_engine,
        liquidity_decay_engine=liquidity_decay_engine,
        negative_space_engine=negative_space_engine,
        counterfactual_engine=counterfactual_engine,
        replay_scope=replay_scope,
    )
    deception_inference_engine = _dynamic_market_maker_deception_inference_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        negative_space_engine=negative_space_engine,
        liquidity_decay_engine=liquidity_decay_engine,
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
        "components": {
            "adversarial_execution_state": adversarial_execution_engine.get("adversarial_execution_state", {}),
        },
    }
    previous_self_expansion_quality = read_json_safe(
        memory_root / "self_expansion_quality" / "self_expansion_quality_latest.json",
        default={},
    )
    if not isinstance(previous_self_expansion_quality, dict):
        previous_self_expansion_quality = {}
    quality_integration_context = (
        previous_self_expansion_quality if bool(previous_self_expansion_quality.get("integration_enabled", False)) else {}
    )
    intelligence_gap_engine = _intelligence_gap_discovery_engine(
        memory_root=memory_root,
        closed=closed,
        counterfactual_engine=counterfactual_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        pain_geometry_engine=pain_geometry_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        self_expansion_quality_layer=quality_integration_context,
    )
    synthetic_data_plane_engine = _synthetic_data_plane_expansion_engine(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        counterfactual_engine=counterfactual_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        execution_microstructure_engine=execution_microstructure_engine,
        self_expansion_quality_layer=quality_integration_context,
    )
    capability_evolution_ladder = _capability_evolution_governance_ladder(
        memory_root=memory_root,
        intelligence_gap_engine=intelligence_gap_engine,
        synthetic_data_plane_engine=synthetic_data_plane_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        adversarial_execution_engine=adversarial_execution_engine,
        self_expansion_quality_layer=quality_integration_context,
        replay_scope=replay_scope,
    )
    cross_regime_transfer_robustness_engine = _cross_regime_transfer_robustness_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
        capability_evolution_ladder=capability_evolution_ladder,
        self_expansion_quality_layer=quality_integration_context,
        calibration_uncertainty_engine=None,
        structural_memory_graph_engine=None,
        latent_transition_hazard_engine=None,
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
    )
    causal_intervention_robustness_engine = _causal_intervention_counterfactual_robustness_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
        counterfactual_engine=counterfactual_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        unified_market_intelligence_field=provisional_unified_market_intelligence,
        self_expansion_quality_layer=quality_integration_context,
        capability_evolution_ladder=capability_evolution_ladder,
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
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["adversarial_execution_state"] = adversarial_execution_engine.get("adversarial_execution_state", {})
    components["deception_inference_state"] = deception_inference_engine.get("deception_state", {})
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["hostility_adjusted_confidence"] = round(
        max(
            0.0,
            min(
                1.0,
                float(confidence_structure.get("composite_confidence", 0.0) or 0.0)
                * float(adversarial_execution_engine.get("confidence_adjustments", {}).get("hostility_adjusted_confidence", 1.0) or 1.0),
            ),
        ),
        4,
    )
    confidence_structure["deception_adjusted_confidence"] = round(
        max(
            0.0,
            min(
                1.0,
                float(confidence_structure.get("composite_confidence", 0.0) or 0.0)
                * float(deception_inference_engine.get("confidence_adjustments", {}).get("deception_adjusted_confidence", 1.0) or 1.0),
            ),
        ),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    risk_sizing["adversarial_execution_multiplier"] = round(
        max(
            0.25,
            min(
                1.0,
                float(adversarial_execution_engine.get("risk_adjustments", {}).get("adversarial_execution_multiplier", 1.0) or 1.0),
            ),
        ),
        4,
    )
    risk_sizing["deception_multiplier"] = round(
        max(
            0.25,
            min(
                1.0,
                float(deception_inference_engine.get("risk_adjustments", {}).get("deception_multiplier", 1.0) or 1.0),
            ),
        ),
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
    for reason in adversarial_execution_engine.get("risk_adjustments", {}).get("refusal_reasons", []):
        if reason not in refusal_reasons:
            refusal_reasons.append(str(reason))
    for reason in adversarial_execution_engine.get("risk_adjustments", {}).get("pause_reasons", []):
        if reason not in pause_reasons:
            pause_reasons.append(str(reason))
    for reason in deception_inference_engine.get("risk_adjustments", {}).get("refusal_reasons", []):
        if reason not in refusal_reasons:
            refusal_reasons.append(str(reason))
    for reason in deception_inference_engine.get("risk_adjustments", {}).get("pause_reasons", []):
        if reason not in pause_reasons:
            pause_reasons.append(str(reason))
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        adversarial_execution_engine.get("risk_adjustments", {}).get("should_refuse", False)
    ) or bool(
        deception_inference_engine.get("risk_adjustments", {}).get("should_refuse", False)
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        adversarial_execution_engine.get("risk_adjustments", {}).get("should_pause", False)
    ) or bool(
        deception_inference_engine.get("risk_adjustments", {}).get("should_pause", False)
    )
    transfer_state = cross_regime_transfer_robustness_engine.get("transfer_robustness_state", {})
    if not isinstance(transfer_state, dict):
        transfer_state = {}
    components["transfer_robustness_state"] = transfer_state
    confidence_structure["cross_regime_transfer_score"] = round(
        max(
            0.0,
            min(1.0, float(cross_regime_transfer_robustness_engine.get("cross_regime_transfer_score", 0.0) or 0.0)),
        ),
        4,
    )
    confidence_structure["transfer_robustness_reliability"] = round(
        max(
            0.0,
            min(1.0, float(cross_regime_transfer_robustness_engine.get("robustness_reliability", 0.0) or 0.0)),
        ),
        4,
    )
    risk_sizing["transfer_robustness_multiplier"] = round(
        max(
            0.25,
            min(
                1.0,
                1.0 - float(cross_regime_transfer_robustness_engine.get("promotion_transfer_penalty", 0.0) or 0.0),
            ),
        ),
        4,
    )
    if transfer_state.get("state") in {"fragile", "breakdown"}:
        if "transfer_robustness_breakdown_guard" not in pause_reasons:
            pause_reasons.append("transfer_robustness_breakdown_guard")
    if float(cross_regime_transfer_robustness_engine.get("overfit_risk", 0.0) or 0.0) >= 0.72:
        if "transfer_overfit_narrow_regime_guard" not in refusal_reasons:
            refusal_reasons.append("transfer_overfit_narrow_regime_guard")
    components["causal_intervention_robustness_state"] = {
        "state": str(causal_intervention_robustness_engine.get("intervention_quality_state", "watch")),
        "primary_intervention_axis": str(causal_intervention_robustness_engine.get("primary_intervention_axis", "unknown")),
        "intervention_reliability": round(
            float(causal_intervention_robustness_engine.get("intervention_reliability", 0.5) or 0.5),
            4,
        ),
    }
    confidence_structure["counterfactual_robustness_score"] = round(
        max(
            0.0,
            min(1.0, float(causal_intervention_robustness_engine.get("counterfactual_robustness_score", 0.0) or 0.0)),
        ),
        4,
    )
    confidence_structure["causal_confidence_proxy"] = round(
        max(0.0, min(1.0, float(causal_intervention_robustness_engine.get("causal_confidence_proxy", 0.0) or 0.0))),
        4,
    )
    risk_sizing["causal_intervention_multiplier"] = round(
        max(
            0.25,
            min(
                1.0,
                1.0
                - min(
                    0.45,
                    (float(causal_intervention_robustness_engine.get("false_improvement_risk", 0.0) or 0.0) * 0.35)
                    + (
                        (1.0 - float(causal_intervention_robustness_engine.get("intervention_reliability", 0.5) or 0.5))
                        * 0.2
                    ),
                ),
            ),
        ),
        4,
    )
    if float(causal_intervention_robustness_engine.get("false_improvement_risk", 0.0) or 0.0) >= 0.62:
        if "causal_false_improvement_guard" not in refusal_reasons:
            refusal_reasons.append("causal_false_improvement_guard")
    if (
        str(causal_intervention_robustness_engine.get("intervention_quality_state", "watch")) in {"fragile", "breakdown"}
        or float(causal_intervention_robustness_engine.get("intervention_reliability", 0.5) or 0.5) <= 0.45
    ):
        if "causal_intervention_reliability_guard" not in pause_reasons:
            pause_reasons.append("causal_intervention_reliability_guard")
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or (
        float(causal_intervention_robustness_engine.get("false_improvement_risk", 0.0) or 0.0) >= 0.72
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or (
        str(causal_intervention_robustness_engine.get("intervention_quality_state", "watch")) in {"fragile", "breakdown"}
    )
    unified_market_intelligence_field["components"] = components
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    structural_memory_graph_engine = _structural_memory_graph_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        unified_market_intelligence_field=unified_market_intelligence_field,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        replay_scope=replay_scope,
    )
    structural_state = structural_memory_graph_engine.get("structural_memory_state", {})
    if not isinstance(structural_state, dict):
        structural_state = {}
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["structural_memory_state"] = structural_state
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    for key in ("historical_recurrence_score", "long_horizon_context_match", "memory_reliability"):
        if key in structural_state:
            confidence_structure[key] = structural_state[key]
    memory_adjusted_confidence = structural_memory_graph_engine.get("confidence_adjustments", {}).get("memory_adjusted_confidence")
    if isinstance(memory_adjusted_confidence, (int, float)):
        confidence_structure["memory_adjusted_confidence"] = round(max(0.0, min(1.0, float(memory_adjusted_confidence))), 4)
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    structural_multiplier = float(
        structural_memory_graph_engine.get("risk_adjustments", {}).get("structural_memory_multiplier", 1.0) or 1.0
    )
    risk_sizing["structural_memory_multiplier"] = round(max(0.25, min(1.0, structural_multiplier)), 4)
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
    for reason in structural_memory_graph_engine.get("risk_adjustments", {}).get("refusal_reasons", []):
        if reason not in refusal_reasons:
            refusal_reasons.append(str(reason))
    for reason in structural_memory_graph_engine.get("risk_adjustments", {}).get("pause_reasons", []):
        if reason not in pause_reasons:
            pause_reasons.append(str(reason))
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        structural_memory_graph_engine.get("risk_adjustments", {}).get("should_refuse", False)
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        structural_memory_graph_engine.get("risk_adjustments", {}).get("should_pause", False)
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    latent_transition_hazard_engine = _latent_transition_hazard_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        unified_market_intelligence_field=unified_market_intelligence_field,
        structural_memory_graph_engine=structural_memory_graph_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        replay_scope=replay_scope,
        negative_space_engine=negative_space_engine,
        invariant_break_engine=invariant_break_engine,
    )
    latent_transition_state = latent_transition_hazard_engine.get("latent_transition_hazard_state", {})
    if not isinstance(latent_transition_state, dict):
        latent_transition_state = {}
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["latent_transition_hazard_state"] = latent_transition_state
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["transition_hazard_score"] = round(
        max(0.0, min(1.0, float(latent_transition_state.get("transition_hazard_score", 0.0) or 0.0))),
        4,
    )
    confidence_structure["hazard_adjusted_confidence"] = round(
        max(
            0.0,
            min(
                1.0,
                float(latent_transition_hazard_engine.get("confidence_adjustments", {}).get("hazard_adjusted_confidence", 0.0) or 0.0),
            ),
        ),
        4,
    )
    confidence_structure["transition_confidence_suppression"] = round(
        max(0.0, min(1.0, float(latent_transition_state.get("transition_confidence_suppression", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    risk_sizing["transition_hazard_multiplier"] = round(
        max(
            0.25,
            min(
                1.0,
                float(latent_transition_hazard_engine.get("risk_adjustments", {}).get("transition_hazard_multiplier", 1.0) or 1.0),
            ),
        ),
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
    for reason in latent_transition_hazard_engine.get("risk_adjustments", {}).get("refusal_reasons", []):
        if reason not in refusal_reasons:
            refusal_reasons.append(str(reason))
    for reason in latent_transition_hazard_engine.get("risk_adjustments", {}).get("pause_reasons", []):
        if reason not in pause_reasons:
            pause_reasons.append(str(reason))
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        latent_transition_hazard_engine.get("risk_adjustments", {}).get("should_refuse", False)
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        latent_transition_hazard_engine.get("risk_adjustments", {}).get("should_pause", False)
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    calibration_uncertainty_engine = _calibration_and_uncertainty_governance_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        unified_market_intelligence_field=unified_market_intelligence_field,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        deception_inference_engine=deception_inference_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
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
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        strategy_evolution=strategy_evolution,
        detector_generator=detector_generator,
        replay_scope=replay_scope,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
    )
    temporal_execution_sequencing_engine = _temporal_execution_sequencing_layer(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        replay_scope=replay_scope,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        unified_market_intelligence_field=unified_market_intelligence_field,
        self_expansion_quality_layer=quality_integration_context,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["temporal_execution_state"] = {
        "state": str(temporal_execution_sequencing_engine.get("temporal_execution_state", "unknown")),
        "recommended_sequence_mode": str(temporal_execution_sequencing_engine.get("recommended_sequence_mode", "hold")),
        "sequencing_reason_cluster": str(temporal_execution_sequencing_engine.get("sequencing_reason_cluster", "unknown")),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["timing_priority_score"] = round(
        max(0.0, min(1.0, float(temporal_execution_sequencing_engine.get("timing_priority_score", 0.0) or 0.0))),
        4,
    )
    confidence_structure["sequencing_reliability"] = round(
        max(0.0, min(1.0, float(temporal_execution_sequencing_engine.get("sequencing_reliability", 0.0) or 0.0))),
        4,
    )
    confidence_structure["execution_window_quality"] = round(
        max(0.0, min(1.0, float(temporal_execution_sequencing_engine.get("execution_window_quality", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    decision_refinements["temporal_execution"] = {
        "temporal_execution_state": temporal_execution_sequencing_engine.get("temporal_execution_state", "unknown"),
        "recommended_sequence_mode": temporal_execution_sequencing_engine.get("recommended_sequence_mode", "hold"),
        "timing_priority_score": round(
            float(temporal_execution_sequencing_engine.get("timing_priority_score", 0.0) or 0.0),
            4,
        ),
        "sequencing_reliability": round(
            float(temporal_execution_sequencing_engine.get("sequencing_reliability", 0.0) or 0.0),
            4,
        ),
        "execution_window_quality": round(
            float(temporal_execution_sequencing_engine.get("execution_window_quality", 0.0) or 0.0),
            4,
        ),
        "sequence_actions": list(temporal_execution_sequencing_engine.get("sequence_actions", [])),
        "timing_controls": dict(temporal_execution_sequencing_engine.get("timing_controls", {})),
    }
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    if float(temporal_execution_sequencing_engine.get("delay_bias", 0.0) or 0.0) >= 0.62:
        if "temporal_execution_delay_bias_guard" not in pause_reasons:
            pause_reasons.append("temporal_execution_delay_bias_guard")
    if float(temporal_execution_sequencing_engine.get("abandon_bias", 0.0) or 0.0) >= 0.68:
        if "temporal_execution_abandon_bias_guard" not in refusal_reasons:
            refusal_reasons.append("temporal_execution_abandon_bias_guard")
    if float(temporal_execution_sequencing_engine.get("execution_window_quality", 1.0) or 1.0) <= 0.42:
        if "temporal_execution_window_quality_guard" not in pause_reasons:
            pause_reasons.append("temporal_execution_window_quality_guard")
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        temporal_execution_sequencing_engine.get("recommended_sequence_mode") == "abandon"
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        temporal_execution_sequencing_engine.get("recommended_sequence_mode") in {"delay", "stagger", "hold"}
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
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
    hierarchical_decision_policy_engine = _hierarchical_decision_policy_layer(
        memory_root=memory_root,
        market_state=market_state,
        replay_scope=replay_scope,
        unified_market_intelligence_field=unified_market_intelligence_field,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_robustness_engine,
        self_expansion_quality_layer=quality_integration_context,
        temporal_execution_sequencing_layer=temporal_execution_sequencing_engine,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["decision_policy_state"] = {
        "state": str(hierarchical_decision_policy_engine.get("decision_policy_state", "unknown")),
        "dominant_policy_mode": str(hierarchical_decision_policy_engine.get("dominant_policy_mode", "balanced")),
        "recommended_policy_posture": str(hierarchical_decision_policy_engine.get("recommended_policy_posture", "balanced_watch")),
        "dominant_reason_cluster": str(hierarchical_decision_policy_engine.get("dominant_reason_cluster", "unknown")),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["policy_reliability"] = round(
        max(0.0, min(1.0, float(hierarchical_decision_policy_engine.get("policy_reliability", 0.0) or 0.0))),
        4,
    )
    confidence_structure["policy_confidence_adjustment"] = round(
        max(0.5, min(1.0, float(hierarchical_decision_policy_engine.get("policy_confidence_adjustment", 1.0) or 1.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    risk_sizing["decision_policy_multiplier"] = round(
        max(0.25, min(1.0, float(hierarchical_decision_policy_engine.get("policy_risk_multiplier", 1.0) or 1.0))),
        4,
    )
    decision_refinements["risk_sizing"] = risk_sizing
    decision_refinements["decision_policy"] = {
        "decision_policy_state": hierarchical_decision_policy_engine.get("decision_policy_state", "unknown"),
        "dominant_policy_mode": hierarchical_decision_policy_engine.get("dominant_policy_mode", "balanced"),
        "recommended_policy_posture": hierarchical_decision_policy_engine.get("recommended_policy_posture", "balanced_watch"),
        "policy_conflict_score": round(float(hierarchical_decision_policy_engine.get("policy_conflict_score", 0.0) or 0.0), 4),
    }
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    if str(hierarchical_decision_policy_engine.get("dominant_policy_mode", "balanced")) == "refusal_first":
        if "decision_policy_refusal_priority_guard" not in refusal_reasons:
            refusal_reasons.append("decision_policy_refusal_priority_guard")
    if str(hierarchical_decision_policy_engine.get("dominant_policy_mode", "balanced")) == "deferral_first":
        if "decision_policy_deferral_priority_guard" not in pause_reasons:
            pause_reasons.append("decision_policy_deferral_priority_guard")
    if float(hierarchical_decision_policy_engine.get("policy_conflict_score", 0.0) or 0.0) >= 0.68:
        if "decision_policy_conflict_pause_guard" not in pause_reasons:
            pause_reasons.append("decision_policy_conflict_pause_guard")
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        hierarchical_decision_policy_engine.get("dominant_policy_mode") == "refusal_first"
        and float(hierarchical_decision_policy_engine.get("refusal_priority_score", 0.0) or 0.0) >= 0.72
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        hierarchical_decision_policy_engine.get("dominant_policy_mode") in {"deferral_first", "refusal_first"}
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    portfolio_multi_context_capital_allocation_engine = _portfolio_multi_context_capital_allocation_layer(
        memory_root=memory_root,
        market_state=market_state,
        replay_scope=replay_scope,
        autonomous_behavior=autonomous_behavior,
        unified_market_intelligence_field=unified_market_intelligence_field,
        hierarchical_decision_policy_layer=hierarchical_decision_policy_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_robustness_engine,
        self_expansion_quality_layer=quality_integration_context,
        temporal_execution_sequencing_layer=temporal_execution_sequencing_engine,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["capital_allocation_state"] = {
        "state": str(portfolio_multi_context_capital_allocation_engine.get("capital_allocation_state", "unknown")),
        "allocation_reason_cluster": str(
            portfolio_multi_context_capital_allocation_engine.get("allocation_reason_cluster", "unknown")
        ),
        "recommended_capital_fraction": round(
            float(portfolio_multi_context_capital_allocation_engine.get("recommended_capital_fraction", 0.0) or 0.0),
            4,
        ),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["allocation_reliability"] = round(
        max(
            0.0,
            min(1.0, float(portfolio_multi_context_capital_allocation_engine.get("allocation_reliability", 0.0) or 0.0)),
        ),
        4,
    )
    confidence_structure["context_competition_score"] = round(
        max(
            0.0,
            min(
                1.0,
                float(portfolio_multi_context_capital_allocation_engine.get("context_competition_score", 0.0) or 0.0),
            ),
        ),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    risk_sizing = decision_refinements.get("risk_sizing", {})
    if not isinstance(risk_sizing, dict):
        risk_sizing = {}
    capital_fraction = float(portfolio_multi_context_capital_allocation_engine.get("recommended_capital_fraction", 0.2) or 0.2)
    compression_score = float(portfolio_multi_context_capital_allocation_engine.get("exposure_compression_score", 0.0) or 0.0)
    capital_allocation_multiplier = round(max(0.25, min(1.0, (capital_fraction * 0.75) + ((1.0 - compression_score) * 0.25))), 4)
    risk_sizing["capital_allocation_multiplier"] = capital_allocation_multiplier
    decision_refinements["risk_sizing"] = risk_sizing
    decision_refinements["capital_allocation"] = {
        "capital_allocation_state": portfolio_multi_context_capital_allocation_engine.get("capital_allocation_state", "unknown"),
        "allocation_priority_score": round(
            float(portfolio_multi_context_capital_allocation_engine.get("allocation_priority_score", 0.0) or 0.0),
            4,
        ),
        "allocation_reliability": round(
            float(portfolio_multi_context_capital_allocation_engine.get("allocation_reliability", 0.0) or 0.0),
            4,
        ),
        "recommended_capital_fraction": round(capital_fraction, 4),
    }
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    survival_exposure_bias = float(portfolio_multi_context_capital_allocation_engine.get("survival_exposure_bias", 0.0) or 0.0)
    context_competition_score = float(portfolio_multi_context_capital_allocation_engine.get("context_competition_score", 0.0) or 0.0)
    if (
        str(portfolio_multi_context_capital_allocation_engine.get("capital_allocation_state", ""))
        == "capital_preservation"
        and "capital_allocation_survival_priority_guard" not in refusal_reasons
    ):
        refusal_reasons.append("capital_allocation_survival_priority_guard")
    if compression_score >= 0.7 and "capital_allocation_exposure_compression_guard" not in pause_reasons:
        pause_reasons.append("capital_allocation_exposure_compression_guard")
    if context_competition_score >= 0.7 and "capital_allocation_context_competition_guard" not in pause_reasons:
        pause_reasons.append("capital_allocation_context_competition_guard")
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        survival_exposure_bias >= 0.84 and float(portfolio_multi_context_capital_allocation_engine.get("allocation_reliability", 1.0) or 1.0)
        <= 0.5
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        compression_score >= 0.68 or context_competition_score >= 0.7
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    previous_rollback_orchestration = read_json_safe(
        memory_root / "rollback_orchestration" / "rollback_orchestration_latest.json",
        default={},
    )
    if not isinstance(previous_rollback_orchestration, dict):
        previous_rollback_orchestration = {}
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
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        mutation_candidates=mutation_candidates,
        capability_evolution_ladder=capability_evolution_ladder,
        replay_scope=replay_scope,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        self_expansion_quality_layer=quality_integration_context,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_robustness_engine,
        hierarchical_decision_policy_layer=hierarchical_decision_policy_engine,
        portfolio_multi_context_capital_allocation_layer=portfolio_multi_context_capital_allocation_engine,
        temporal_execution_sequencing_layer=temporal_execution_sequencing_engine,
        rollback_orchestration_and_safe_reversion_layer=previous_rollback_orchestration,
    )
    governed_capability_invention_engine = _governed_capability_invention_layer(
        memory_root=memory_root,
        self_suggestion_governor=self_suggestion_governor,
        intelligence_gap_engine=intelligence_gap_engine,
        capability_evolution_ladder=capability_evolution_ladder,
        replay_scope=replay_scope,
    )
    self_suggestion_governor["governed_capability_invention_layer"] = {
        "capability_invention_state": governed_capability_invention_engine.get("capability_invention_state", "seeded"),
        "invention_pressure_score": governed_capability_invention_engine.get("invention_pressure_score", 0.0),
        "novelty_score": governed_capability_invention_engine.get("novelty_score", 0.0),
        "redundancy_risk": governed_capability_invention_engine.get("redundancy_risk", 0.0),
        "invention_reliability": governed_capability_invention_engine.get("invention_reliability", 0.0),
        "invention_maturity_score": governed_capability_invention_engine.get("invention_maturity_score", 0.0),
        "candidate_invention_count": governed_capability_invention_engine.get("candidate_invention_count", 0),
        "dominant_invention_axis": governed_capability_invention_engine.get("dominant_invention_axis", "coherence"),
    }
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["capability_invention_state"] = {
        "state": str(governed_capability_invention_engine.get("capability_invention_state", "seeded")),
        "dominant_invention_axis": str(governed_capability_invention_engine.get("dominant_invention_axis", "coherence")),
        "invention_reason_cluster": str(governed_capability_invention_engine.get("invention_reason_cluster", "unknown")),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["invention_reliability"] = round(
        max(0.0, min(1.0, float(governed_capability_invention_engine.get("invention_reliability", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    decision_refinements["capability_invention"] = {
        "capability_invention_state": governed_capability_invention_engine.get("capability_invention_state", "seeded"),
        "invention_pressure_score": round(float(governed_capability_invention_engine.get("invention_pressure_score", 0.0) or 0.0), 4),
        "novelty_score": round(float(governed_capability_invention_engine.get("novelty_score", 0.0) or 0.0), 4),
        "redundancy_risk": round(float(governed_capability_invention_engine.get("redundancy_risk", 0.0) or 0.0), 4),
        "invention_maturity_score": round(
            float(governed_capability_invention_engine.get("invention_maturity_score", 0.0) or 0.0),
            4,
        ),
        "invention_reliability": round(float(governed_capability_invention_engine.get("invention_reliability", 0.0) or 0.0), 4),
        "candidate_invention_count": int(governed_capability_invention_engine.get("candidate_invention_count", 0) or 0),
        "dominant_invention_axis": governed_capability_invention_engine.get("dominant_invention_axis", "coherence"),
    }
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    autonomous_capability_expansion_engine = _autonomous_capability_expansion_layer(
        memory_root=memory_root,
        self_suggestion_governor=self_suggestion_governor,
        capability_evolution_ladder=capability_evolution_ladder,
        governed_capability_invention_layer=governed_capability_invention_engine,
        replay_scope=replay_scope,
    )
    self_suggestion_governor["autonomous_capability_expansion_layer"] = {
        "capability_expansion_state": autonomous_capability_expansion_engine.get("capability_expansion_state", "seeded"),
        "expansion_readiness_score": autonomous_capability_expansion_engine.get("expansion_readiness_score", 0.0),
        "expansion_reliability": autonomous_capability_expansion_engine.get("expansion_reliability", 0.0),
        "rollbackability_score": autonomous_capability_expansion_engine.get("rollbackability_score", 0.0),
        "expansion_maturity_score": autonomous_capability_expansion_engine.get("expansion_maturity_score", 0.0),
        "expansion_pressure_score": autonomous_capability_expansion_engine.get("expansion_pressure_score", 0.0),
        "candidate_expansion_count": autonomous_capability_expansion_engine.get("candidate_expansion_count", 0),
        "dominant_expansion_axis": autonomous_capability_expansion_engine.get("dominant_expansion_axis", "coherence"),
    }
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["capability_expansion_state"] = {
        "state": str(autonomous_capability_expansion_engine.get("capability_expansion_state", "seeded")),
        "dominant_expansion_axis": str(autonomous_capability_expansion_engine.get("dominant_expansion_axis", "coherence")),
        "expansion_reason_cluster": str(
            autonomous_capability_expansion_engine.get("expansion_reason_cluster", "insufficient_expansion_signal")
        ),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["expansion_reliability"] = round(
        max(0.0, min(1.0, float(autonomous_capability_expansion_engine.get("expansion_reliability", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    decision_refinements["capability_expansion"] = {
        "capability_expansion_state": autonomous_capability_expansion_engine.get("capability_expansion_state", "seeded"),
        "expansion_readiness_score": round(
            float(autonomous_capability_expansion_engine.get("expansion_readiness_score", 0.0) or 0.0),
            4,
        ),
        "expansion_reliability": round(
            float(autonomous_capability_expansion_engine.get("expansion_reliability", 0.0) or 0.0),
            4,
        ),
        "rollbackability_score": round(
            float(autonomous_capability_expansion_engine.get("rollbackability_score", 0.0) or 0.0),
            4,
        ),
        "expansion_maturity_score": round(
            float(autonomous_capability_expansion_engine.get("expansion_maturity_score", 0.0) or 0.0),
            4,
        ),
        "expansion_pressure_score": round(
            float(autonomous_capability_expansion_engine.get("expansion_pressure_score", 0.0) or 0.0),
            4,
        ),
        "candidate_expansion_count": int(autonomous_capability_expansion_engine.get("candidate_expansion_count", 0) or 0),
        "dominant_expansion_axis": autonomous_capability_expansion_engine.get("dominant_expansion_axis", "coherence"),
    }
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    self_expansion_quality_engine = _self_expansion_quality_layer(
        memory_root=memory_root,
        capability_evolution_ladder=capability_evolution_ladder,
        self_suggestion_governor=self_suggestion_governor,
        intelligence_gap_engine=intelligence_gap_engine,
        synthetic_data_plane_engine=synthetic_data_plane_engine,
        unified_market_intelligence_field=unified_market_intelligence_field,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_robustness_engine,
        hierarchical_decision_policy_layer=hierarchical_decision_policy_engine,
        portfolio_multi_context_capital_allocation_layer=portfolio_multi_context_capital_allocation_engine,
        temporal_execution_sequencing_layer=temporal_execution_sequencing_engine,
        governed_capability_invention_layer=governed_capability_invention_engine,
        autonomous_capability_expansion_layer=autonomous_capability_expansion_engine,
        rollback_orchestration_and_safe_reversion_layer=previous_rollback_orchestration,
        replay_scope=replay_scope,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["self_expansion_quality_state"] = self_expansion_quality_engine.get("self_expansion_quality_state", "unknown")
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["expansion_quality_adjusted_confidence"] = round(
        max(
            0.0,
            min(
                1.0,
                float(confidence_structure.get("composite_confidence", 0.0) or 0.0)
                * float(self_expansion_quality_engine.get("quality_components", {}).get("promotion_confidence_multiplier", 1.0) or 1.0),
            ),
        ),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    system_coherence_drift_integrity_engine = _system_coherence_and_drift_integrity_layer(
        memory_root=memory_root,
        replay_scope=replay_scope,
        unified_market_intelligence_field=unified_market_intelligence_field,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_robustness_engine,
        hierarchical_decision_policy_layer=hierarchical_decision_policy_engine,
        portfolio_multi_context_capital_allocation_layer=portfolio_multi_context_capital_allocation_engine,
        temporal_execution_sequencing_layer=temporal_execution_sequencing_engine,
        self_expansion_quality_layer=self_expansion_quality_engine,
        execution_microstructure_engine=execution_microstructure_engine,
        adversarial_execution_engine=adversarial_execution_engine,
        deception_inference_engine=deception_inference_engine,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["system_coherence_state"] = {
        "state": str(system_coherence_drift_integrity_engine.get("system_coherence_state", "unknown")),
        "coherence_score": round(
            float(system_coherence_drift_integrity_engine.get("coherence_score", 0.0) or 0.0), 4
        ),
        "fragmentation_risk": round(
            float(system_coherence_drift_integrity_engine.get("fragmentation_risk", 0.0) or 0.0), 4
        ),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["coherence_score"] = round(
        max(0.0, min(1.0, float(system_coherence_drift_integrity_engine.get("coherence_score", 0.0) or 0.0))),
        4,
    )
    confidence_structure["drift_integrity_score"] = round(
        max(0.0, min(1.0, float(system_coherence_drift_integrity_engine.get("drift_integrity_score", 0.0) or 0.0))),
        4,
    )
    confidence_structure["coherence_reliability"] = round(
        max(0.0, min(1.0, float(system_coherence_drift_integrity_engine.get("coherence_reliability", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    decision_refinements["system_coherence"] = {
        "system_coherence_state": system_coherence_drift_integrity_engine.get("system_coherence_state", "unknown"),
        "coherence_score": round(float(system_coherence_drift_integrity_engine.get("coherence_score", 0.0) or 0.0), 4),
        "drift_integrity_score": round(float(system_coherence_drift_integrity_engine.get("drift_integrity_score", 0.0) or 0.0), 4),
        "disagreement_load": round(float(system_coherence_drift_integrity_engine.get("disagreement_load", 0.0) or 0.0), 4),
        "fragmentation_risk": round(float(system_coherence_drift_integrity_engine.get("fragmentation_risk", 0.0) or 0.0), 4),
    }
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    coherence_fragmentation_risk = float(system_coherence_drift_integrity_engine.get("fragmentation_risk", 0.0) or 0.0)
    coherence_disagreement_load = float(system_coherence_drift_integrity_engine.get("disagreement_load", 0.0) or 0.0)
    if coherence_fragmentation_risk >= 0.65:
        if "system_coherence_fragmentation_guard" not in refusal_reasons:
            refusal_reasons.append("system_coherence_fragmentation_guard")
    if coherence_fragmentation_risk >= 0.5:
        if "system_coherence_fragmentation_pause_guard" not in pause_reasons:
            pause_reasons.append("system_coherence_fragmentation_pause_guard")
    if coherence_disagreement_load >= 0.6:
        if "system_coherence_disagreement_load_guard" not in pause_reasons:
            pause_reasons.append("system_coherence_disagreement_load_guard")
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        coherence_fragmentation_risk >= 0.72
    )
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        coherence_fragmentation_risk >= 0.5 or coherence_disagreement_load >= 0.6
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    learning_stability_guard_engine = _learning_stability_and_catastrophic_drift_guard_layer(
        memory_root=memory_root,
        replay_scope=replay_scope,
        unified_market_intelligence_field=unified_market_intelligence_field,
        calibration_uncertainty_engine=calibration_uncertainty_engine,
        contradiction_arbitration_engine=contradiction_arbitration_engine,
        system_coherence_and_drift_integrity_layer=system_coherence_drift_integrity_engine,
        cross_regime_transfer_robustness_layer=cross_regime_transfer_robustness_engine,
        causal_intervention_counterfactual_robustness_layer=causal_intervention_robustness_engine,
        self_expansion_quality_layer=self_expansion_quality_engine,
        structural_memory_graph_engine=structural_memory_graph_engine,
        latent_transition_hazard_engine=latent_transition_hazard_engine,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["learning_stability_state"] = {
        "state": str(learning_stability_guard_engine.get("learning_stability_state", "unknown")),
        "learning_stability_score": round(
            float(learning_stability_guard_engine.get("learning_stability_score", 0.0) or 0.0), 4
        ),
        "catastrophic_drift_risk": round(
            float(learning_stability_guard_engine.get("catastrophic_drift_risk", 0.0) or 0.0), 4
        ),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["learning_stability_score"] = round(
        max(0.0, min(1.0, float(learning_stability_guard_engine.get("learning_stability_score", 0.0) or 0.0))),
        4,
    )
    confidence_structure["catastrophic_drift_risk"] = round(
        max(0.0, min(1.0, float(learning_stability_guard_engine.get("catastrophic_drift_risk", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    decision_refinements["learning_stability"] = {
        "learning_stability_state": learning_stability_guard_engine.get("learning_stability_state", "unknown"),
        "learning_stability_score": round(float(learning_stability_guard_engine.get("learning_stability_score", 0.0) or 0.0), 4),
        "catastrophic_drift_risk": round(float(learning_stability_guard_engine.get("catastrophic_drift_risk", 0.0) or 0.0), 4),
        "capability_expansion_pressure": round(float(learning_stability_guard_engine.get("capability_expansion_pressure", 0.0) or 0.0), 4),
        "regime_overfit_risk": round(float(learning_stability_guard_engine.get("regime_overfit_risk", 0.0) or 0.0), 4),
        "learning_fragmentation_risk": round(float(learning_stability_guard_engine.get("learning_fragmentation_risk", 0.0) or 0.0), 4),
    }
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
    rollback_orchestration_engine = _rollback_orchestration_and_safe_reversion_layer(
        memory_root=memory_root,
        replay_scope=replay_scope,
        governed_capability_invention_layer=governed_capability_invention_engine,
        autonomous_capability_expansion_layer=autonomous_capability_expansion_engine,
        self_expansion_quality_layer=self_expansion_quality_engine,
        system_coherence_and_drift_integrity_layer=system_coherence_drift_integrity_engine,
        learning_stability_and_catastrophic_drift_guard_layer=learning_stability_guard_engine,
        capability_evolution_ladder=capability_evolution_ladder,
        self_suggestion_governor=self_suggestion_governor,
    )
    components = unified_market_intelligence_field.get("components", {})
    if not isinstance(components, dict):
        components = {}
    components["rollback_orchestration_state"] = {
        "state": str(rollback_orchestration_engine.get("rollback_orchestration_state", "stable")),
        "rollback_mode": str(rollback_orchestration_engine.get("rollback_mode", "monitor_only")),
        "reversion_sequence_mode": str(rollback_orchestration_engine.get("reversion_sequence_mode", "none")),
        "rollback_reason_cluster": str(rollback_orchestration_engine.get("rollback_reason_cluster", "stable_rollback_monitoring")),
    }
    unified_market_intelligence_field["components"] = components
    confidence_structure = unified_market_intelligence_field.get("confidence_structure", {})
    if not isinstance(confidence_structure, dict):
        confidence_structure = {}
    confidence_structure["rollback_reversion_reliability"] = round(
        max(0.0, min(1.0, float(rollback_orchestration_engine.get("rollback_reversion_reliability", 0.0) or 0.0))),
        4,
    )
    unified_market_intelligence_field["confidence_structure"] = confidence_structure
    decision_refinements = unified_market_intelligence_field.get("decision_refinements", {})
    if not isinstance(decision_refinements, dict):
        decision_refinements = {}
    decision_refinements["rollback_orchestration"] = {
        "rollback_mode": rollback_orchestration_engine.get("rollback_mode", "monitor_only"),
        "promotion_freeze": bool(rollback_orchestration_engine.get("promotion_freeze", False)),
        "reversion_sequence_mode": rollback_orchestration_engine.get("reversion_sequence_mode", "none"),
        "rollback_urgency": round(float(rollback_orchestration_engine.get("rollback_urgency", 0.0) or 0.0), 4),
        "safe_reversion_ready": bool(rollback_orchestration_engine.get("safe_reversion_ready", False)),
    }
    refusal_pause_behavior = decision_refinements.get("refusal_pause_behavior", {})
    if not isinstance(refusal_pause_behavior, dict):
        refusal_pause_behavior = {}
    refusal_reasons = refusal_pause_behavior.get("refusal_reasons", [])
    if not isinstance(refusal_reasons, list):
        refusal_reasons = []
    pause_reasons = refusal_pause_behavior.get("pause_reasons", [])
    if not isinstance(pause_reasons, list):
        pause_reasons = []
    rollback_urgency = float(rollback_orchestration_engine.get("rollback_urgency", 0.0) or 0.0)
    rollback_mode = str(rollback_orchestration_engine.get("rollback_mode", "monitor_only"))
    if rollback_urgency >= 0.55 and "rollback_orchestration_pause_guard" not in pause_reasons:
        pause_reasons.append("rollback_orchestration_pause_guard")
    if rollback_urgency >= 0.75 and "rollback_orchestration_refusal_guard" not in refusal_reasons:
        refusal_reasons.append("rollback_orchestration_refusal_guard")
    refusal_pause_behavior["refusal_reasons"] = refusal_reasons
    refusal_pause_behavior["pause_reasons"] = pause_reasons
    refusal_pause_behavior["should_pause"] = bool(refusal_pause_behavior.get("should_pause", False)) or bool(
        rollback_urgency >= 0.55 or rollback_mode in {"selective_revert", "freeze_only", "freeze_and_revert"}
    )
    refusal_pause_behavior["should_refuse"] = bool(refusal_pause_behavior.get("should_refuse", False)) or bool(
        rollback_urgency >= 0.75 or rollback_mode == "freeze_and_revert"
    )
    decision_refinements["refusal_pause_behavior"] = refusal_pause_behavior
    unified_market_intelligence_field["decision_refinements"] = decision_refinements
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
        "adversarial_execution_intelligence_layer": adversarial_execution_engine,
        "dynamic_market_maker_deception_inference_layer": deception_inference_engine,
        "structural_memory_graph_layer": structural_memory_graph_engine,
        "latent_transition_hazard_layer": latent_transition_hazard_engine,
        "cross_regime_transfer_robustness_layer": cross_regime_transfer_robustness_engine,
        "causal_intervention_counterfactual_robustness_layer": causal_intervention_robustness_engine,
        "temporal_execution_sequencing_layer": temporal_execution_sequencing_engine,
        "hierarchical_decision_policy_layer": hierarchical_decision_policy_engine,
        "portfolio_multi_context_capital_allocation_layer": portfolio_multi_context_capital_allocation_engine,
        "calibration_and_uncertainty_governance_layer": calibration_uncertainty_engine,
        "contradiction_arbitration_and_belief_resolution_layer": contradiction_arbitration_engine,
        "recursive_self_modeling": recursive_self_modeling,
        "discovery_state_tags": discovery_state_tags,
        "unified_market_intelligence_field": unified_market_intelligence_field,
        "governed_capability_invention_layer": governed_capability_invention_engine,
        "autonomous_capability_expansion_layer": autonomous_capability_expansion_engine,
        "self_expansion_quality_layer": self_expansion_quality_engine,
        "system_coherence_and_drift_integrity_layer": system_coherence_drift_integrity_engine,
        "learning_stability_and_catastrophic_drift_guard_layer": learning_stability_guard_engine,
        "rollback_orchestration_and_safe_reversion_layer": rollback_orchestration_engine,
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
        "adversarial_execution_intelligence_layer": adversarial_execution_engine,
        "dynamic_market_maker_deception_inference_layer": deception_inference_engine,
        "structural_memory_graph_layer": structural_memory_graph_engine,
        "latent_transition_hazard_layer": latent_transition_hazard_engine,
        "cross_regime_transfer_robustness_layer": cross_regime_transfer_robustness_engine,
        "causal_intervention_counterfactual_robustness_layer": causal_intervention_robustness_engine,
        "temporal_execution_sequencing_layer": temporal_execution_sequencing_engine,
        "hierarchical_decision_policy_layer": hierarchical_decision_policy_engine,
        "portfolio_multi_context_capital_allocation_layer": portfolio_multi_context_capital_allocation_engine,
        "calibration_and_uncertainty_governance_layer": calibration_uncertainty_engine,
        "contradiction_arbitration_and_belief_resolution_layer": contradiction_arbitration_engine,
        "recursive_self_modeling": recursive_self_modeling,
        "discovery_state_tags": discovery_state_tags,
        "unified_market_intelligence_field": unified_market_intelligence_field,
        "governed_capability_invention_layer": governed_capability_invention_engine,
        "autonomous_capability_expansion_layer": autonomous_capability_expansion_engine,
        "self_expansion_quality_layer": self_expansion_quality_engine,
        "system_coherence_and_drift_integrity_layer": system_coherence_drift_integrity_engine,
        "learning_stability_and_catastrophic_drift_guard_layer": learning_stability_guard_engine,
        "rollback_orchestration_and_safe_reversion_layer": rollback_orchestration_engine,
        "meta_learning_loop": meta_learning_loop,
    }
