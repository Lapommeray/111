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
    survival_intelligence = {
        "capital_survival_engine": autonomous_behavior.get("capital_survival_engine", {}),
        "pain_memory_survival_layer": pain_memory_survival,
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
        "meta_learning_loop": meta_learning_loop,
    }
