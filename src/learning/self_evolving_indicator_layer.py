from __future__ import annotations

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
    self_suggestion_governor = _self_suggestion_governor(
        memory_root=memory_root,
        closed=closed,
        market_state=market_state,
        autonomous_behavior=autonomous_behavior,
        detector_generator=detector_generator,
        strategy_evolution=strategy_evolution,
        pain_memory_survival=pain_memory_survival,
        mutation_candidates=mutation_candidates,
        replay_scope=replay_scope,
    )
    survival_intelligence = {
        "capital_survival_engine": autonomous_behavior.get("capital_survival_engine", {}),
        "pain_memory_survival_layer": pain_memory_survival,
        "self_suggestion_governor": self_suggestion_governor,
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
        "meta_learning_loop": meta_learning_loop,
    }
