from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.features.displacement import compute_displacement
from src.module_factory import ModuleFactory
from src.features.fvg import detect_fvg_state
from src.features.human_lag_exploit import measure_human_lag_signal
from src.features.invisible_data_miner import mine_internal_patterns
from src.features.liquidity import detect_liquidity_sweep_state
from src.features.market_structure import classify_market_regime
from src.features.quantum_tremor_scanner import scan_tremor_state
from src.features.sessions import compute_session_state, track_session_behavior
from src.features.spread_state import compute_spread_state, track_execution_quality
from src.features.volatility import compute_volatility_state, detect_compression_expansion_state
from src.filters.conflict_filter import apply_conflict_filter
from src.filters.memory_filter import apply_memory_filter
from src.filters.self_destruct_protocol import apply_self_destruct_protocol
from src.filters.session_filter import apply_session_filter
from src.filters.spread_filter import apply_spread_filter
from src.memory.meta_adaptive_ai import MetaAdaptiveAI
from src.scoring.meta_conscious_routing import compute_meta_conscious_routing
from src.scoring.regime_score import compute_regime_score
from src.scoring.setup_score import compute_setup_score
from src.scoring.spectral_signal_fusion import fuse_spectral_signals
from src.state import ConnectorHook, ModuleHealth, ModuleResult, PipelineState
from src.utils import aggregate_confidence, aggregate_direction, module_ready


class OversoulDirector:
    """Visible module map/director for advanced module wiring and traceability."""

    def __init__(self) -> None:
        self.module_factory = ModuleFactory()
        self.discovered_modules = self.module_factory.list_all_modules()

        self.module_map: dict[str, dict[str, str]] = {
            "displacement": {"role": "momentum_displacement", "group": "features"},
            "fvg": {"role": "fair_value_gap_detection", "group": "features"},
            "volatility": {"role": "volatility_regime", "group": "features"},
            "sessions": {"role": "session_classifier", "group": "features"},
            "spread_state": {"role": "spread_proxy_estimator", "group": "features"},
            "liquidity_sweep": {"role": "liquidity_sweep_stop_run_detector", "group": "features"},
            "compression_expansion": {"role": "compression_expansion_detector", "group": "features"},
            "session_behavior": {"role": "session_behavior_tracker", "group": "features"},
            "market_regime": {"role": "market_regime_classifier", "group": "features"},
            "execution_quality": {"role": "execution_quality_tracker", "group": "features"},
            "invisible_data_miner": {"role": "internal_pattern_miner", "group": "features"},
            "human_lag_exploit": {"role": "public_behavior_lag_model", "group": "features"},
            "quantum_tremor_scanner": {"role": "micro_volatility_tremor_model", "group": "features"},
            "session_filter": {"role": "session_block_gate", "group": "filters"},
            "spread_filter": {"role": "spread_block_gate", "group": "filters"},
            "conflict_filter": {"role": "vote_conflict_gate", "group": "filters"},
            "memory_filter": {"role": "outcome_memory_gate", "group": "filters"},
            "self_destruct_protocol": {"role": "failing_logic_downrank_gate", "group": "filters"},
            "setup_score": {"role": "setup_quality_scoring", "group": "scoring"},
            "regime_score": {"role": "regime_quality_scoring", "group": "scoring"},
            "spectral_signal_fusion": {"role": "multi_signal_fusion", "group": "scoring"},
            "meta_conscious_routing": {"role": "entropy_liquidity_regime_router", "group": "scoring"},
            "meta_adaptive_ai": {"role": "internal_memory_adaptive_profile", "group": "memory"},
            "evolution_kernel": {"role": "evolution_kernel_reporter", "group": "evolution"},
        }
        self.connector_hooks: dict[str, dict[str, str]] = {
            "hook_displacement": {
                "source_module": "displacement",
                "target_interface": "direction_vote_bus",
                "description": "Expose displacement vote to external AI/ensemble consumers.",
            },
            "hook_spectral_fusion": {
                "source_module": "spectral_signal_fusion",
                "target_interface": "confidence_bus",
                "description": "Expose spectral fusion confidence contribution.",
            },
            "hook_meta_routing": {
                "source_module": "meta_conscious_routing",
                "target_interface": "routing_bus",
                "description": "Expose entropy/liquidity/regime routing output.",
            },
            "hook_self_destruct": {
                "source_module": "self_destruct_protocol",
                "target_interface": "risk_gate_bus",
                "description": "Expose measurable down-rank/disable risk gate state.",
            },
            "hook_meta_adaptive": {
                "source_module": "meta_adaptive_ai",
                "target_interface": "adaptive_profile_bus",
                "description": "Expose internal-memory adaptive profile output.",
            },
            "hook_evolution_kernel": {
                "source_module": "evolution_kernel",
                "target_interface": "evolution_control_bus",
                "description": "Expose evolution inspection/proposal lifecycle summary.",
            },
        }

    def as_dict(self) -> dict[str, dict[str, str]]:
        return self.module_map

    def hooks_as_dict(self) -> dict[str, dict[str, str]]:
        return self.connector_hooks

    def discovered_as_dict(self) -> dict[str, list[str]]:
        return self.discovered_modules


def _module_result(name: str, role: str, output: dict[str, Any]) -> ModuleResult:
    return ModuleResult(
        name=name,
        role=role,
        direction_vote=str(output.get("direction_vote", "neutral")),
        confidence_delta=float(output.get("confidence_delta", 0.0)),
        blocked=bool(output.get("blocked", False)),
        reasons=list(output.get("reasons", [])),
        payload=output,
    )


def _register_health(state: PipelineState, module_name: str, output: dict[str, Any]) -> None:
    ready, status, details = module_ready(output)
    state.module_health[module_name] = ModuleHealth(
        name=module_name,
        ready=ready,
        status=status,
        details=details,
    )


def _register_connector_hooks(state: PipelineState, director: OversoulDirector) -> None:
    for name, hook in director.hooks_as_dict().items():
        state.connector_hooks[name] = ConnectorHook(
            name=name,
            source_module=hook["source_module"],
            target_interface=hook["target_interface"],
            enabled=hook["source_module"] in state.module_results,
            description=hook["description"],
        )


def run_advanced_modules(
    director: OversoulDirector,
    bars: list[dict[str, Any]],
    base_direction: str,
    structure: dict[str, Any],
    liquidity: dict[str, Any],
    base_confidence: float,
    blocked_setups: list[dict[str, Any]],
    trade_outcomes: list[dict[str, Any]],
    symbol: str = "XAUUSD",
    mode: str = "live",
) -> PipelineState:
    state = PipelineState(
        symbol=symbol,
        mode=mode,
        bars=bars,
        structure=structure,
        liquidity=liquidity,
        base_confidence=base_confidence,
        base_direction=base_direction,
    )

    volatility_output = compute_volatility_state(bars)
    feature_outputs: dict[str, dict[str, Any]] = {
        "displacement": compute_displacement(bars),
        "fvg": detect_fvg_state(bars),
        "volatility": volatility_output,
        "sessions": compute_session_state(bars),
        "spread_state": compute_spread_state(bars),
        "liquidity_sweep": detect_liquidity_sweep_state(bars),
        "compression_expansion": detect_compression_expansion_state(bars),
        "session_behavior": track_session_behavior(bars, trade_outcomes),
        "market_regime": classify_market_regime(structure, volatility_output),
        "execution_quality": track_execution_quality(bars),
        "invisible_data_miner": mine_internal_patterns(bars, structure, liquidity),
        "human_lag_exploit": measure_human_lag_signal(bars),
        "quantum_tremor_scanner": scan_tremor_state(bars),
    }

    for name, output in feature_outputs.items():
        state.module_results[name] = _module_result(name, director.module_map[name]["role"], output)
        _register_health(state, name, output)

    votes = [state.base_direction.lower()] + [o.get("direction_vote", "neutral") for o in feature_outputs.values()]

    filter_outputs: dict[str, dict[str, Any]] = {
        "session_filter": apply_session_filter(feature_outputs["sessions"]),
        "spread_filter": apply_spread_filter(feature_outputs["spread_state"]),
        "conflict_filter": apply_conflict_filter(votes, base_direction),
        "memory_filter": apply_memory_filter(base_direction, blocked_setups, trade_outcomes),
        "self_destruct_protocol": apply_self_destruct_protocol(trade_outcomes, feature_outputs),
    }

    for name, output in filter_outputs.items():
        state.module_results[name] = _module_result(name, director.module_map[name]["role"], output)
        _register_health(state, name, output)

    regime_score_output = compute_regime_score(structure, feature_outputs["volatility"])
    scoring_outputs: dict[str, dict[str, Any]] = {
        "setup_score": compute_setup_score({**feature_outputs, **filter_outputs}),
        "regime_score": regime_score_output,
        "spectral_signal_fusion": fuse_spectral_signals({**feature_outputs, **filter_outputs}),
        "meta_conscious_routing": compute_meta_conscious_routing(
            regime_score=regime_score_output,
            liquidity=liquidity,
            volatility=feature_outputs["volatility"],
        ),
    }

    for name, output in scoring_outputs.items():
        state.module_results[name] = _module_result(name, director.module_map[name]["role"], output)
        _register_health(state, name, output)

    meta_ai = MetaAdaptiveAI()
    profile = meta_ai.update_from_internal_memory(trade_outcomes)
    meta_ai_output = meta_ai.profile_as_module_output(profile, base_direction)
    state.module_results["meta_adaptive_ai"] = _module_result(
        "meta_adaptive_ai",
        director.module_map["meta_adaptive_ai"]["role"],
        meta_ai_output,
    )
    _register_health(state, "meta_adaptive_ai", meta_ai_output)

    all_votes = [m.direction_vote for m in state.module_results.values()]
    all_deltas = [m.confidence_delta for m in state.module_results.values()]

    state.final_direction = aggregate_direction(base_direction, all_votes)
    state.final_confidence = aggregate_confidence(base_confidence, all_deltas)

    blocked_modules = [m for m in state.module_results.values() if m.blocked]
    state.blocked = len(blocked_modules) > 0
    state.blocked_reasons = [f"{m.name}:{','.join(m.reasons)}" for m in blocked_modules]

    _register_connector_hooks(state, director)
    return state


def state_to_dict(state: PipelineState) -> dict[str, Any]:
    payload = asdict(state)
    payload["module_results"] = state.as_module_payload()
    payload["module_health"] = state.as_health_payload()
    payload["connector_hooks"] = state.as_connector_payload()
    return payload
