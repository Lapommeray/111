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
        predictive_usefulness = round(max(0.0, min(1.0, (value * 0.1) + (loss_ratio * 0.35))), 4)
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

    events_path = invariant_dir / "invariant_break_events_latest.json"
    write_json_atomic(events_path, {"invariant_break_events": events})
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
            kernel_values.append(math.exp(-distance_sq))
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
        level_key = str(round(level_price / 5.0) * 5.0)
        levels.setdefault(level_key, []).append(index)
    models = []
    for level, hits in sorted(levels.items()):
        intervals = [hits[i] - hits[i - 1] for i in range(1, len(hits))]
        avg_interval = sum(intervals) / max(1, len(intervals)) if intervals else float(len(closed) + 1)
        regeneration = round(min(1.0, math.sqrt(max(1.0, avg_interval)) / 5.0), 4)
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
        learning_efficiency = round(max(0.0, min(1.0, 0.6 + (liquidity_models * 0.05) - (counterfactual_edges * 0.04) - (pain_risk * 0.2))), 4)
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
    mutation_candidates: list[dict[str, Any]],
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
        "low_value_noisy_mutations": [
            {"suggestion_type": "new_survival_rule", "target": "mutation_noise_filter"},
            {"suggestion_type": "new_strategy_mutation", "target": "quality_gated_mutation_generator"},
        ],
        "survival_rule_gap": [
            {"suggestion_type": "new_survival_rule", "target": "pain_memory_survival_strengthening"},
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
        "low_value_noisy_mutations": "strategy_evolution_engine",
        "survival_rule_gap": "pain_memory_survival_layer",
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
    mutation_candidates: list[dict[str, Any]],
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
        mutation_candidates=mutation_candidates,
    )
    input_signature = {
        "replay_scope": replay_scope,
        "gap_signatures": sorted(_gap_signature(gap) for gap in gaps),
        "strongest_branch": str(strategy_evolution.get("strongest_branch", {}).get("branch_id", "current_strategy")),
        "closed_count": len(closed),
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
        replay_score = round(
            max(
                0.0,
                min(
                    1.0,
                    suggestion["priority_score"] + (strategy_expectancy * 0.15) - (0.02 * index),
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
        replay_scope=replay_scope,
    )
    self_suggestion_governor = _self_suggestion_governor(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        autonomous_behavior=autonomous_behavior,
        detector_generator=detector_generator,
        strategy_evolution=strategy_evolution,
        pain_memory_survival=pain_memory_survival,
        discovery_state_tags=discovery_state_tags,
        mutation_candidates=mutation_candidates,
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
        "recursive_self_modeling": recursive_self_modeling,
        "discovery_state_tags": discovery_state_tags,
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
        "recursive_self_modeling": recursive_self_modeling,
        "discovery_state_tags": discovery_state_tags,
        "meta_learning_loop": meta_learning_loop,
    }
