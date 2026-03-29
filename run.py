from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.evaluation.decision_completeness import run_decision_completeness_gate
from src.evaluation.decision_quality import run_decision_quality_gate
from src.evaluation.drawdown_comparison import compare_drawdown_files
from src.evaluation.replay_outcome import run_replay_outcome_gate, ReplayOutcomeError
from src.evaluation.threshold_calibration import run_threshold_calibration
from src.evaluation.replay_evaluator import evaluate_replay
from src.evolution.architecture_guard import ArchitectureGuard
from src.evolution.code_generator import CodeGenerator
from src.evolution.duplication_audit import DuplicationAudit
from src.evolution.evolution_registry import EvolutionRegistry
from src.evolution.gap_discovery import GapDiscovery
from src.evolution.promotion_policy import PromotionThresholds, evaluate_module_promotion_policy
from src.evolution.promoter import Promoter
from src.evolution.self_inspector import SelfInspector
from src.evolution.verifier import Verifier
from src.evolution.experimental_module_spec_flow import run_continuous_governed_improvement_cycle
from src.evolution.knowledge_expansion_orchestrator import run_knowledge_expansion_phase_a
from src.features.liquidity import assess_liquidity_state
from src.features.market_structure import classify_market_structure
from src.filters.loss_blocker import LossBlocker
from src.indicator.chart_objects import build_chart_objects
from src.indicator.indicator_output import build_indicator_output, build_status_panel
from src.indicator.signal_model import build_signal_output
from src.memory.pattern_store import PatternStore, PatternStoreConfig
from src.memory.self_coder import SelfCoder
from src.memory.tracker import OutcomeTracker
from src.monitoring.system_state import update_system_monitor_state
from src.mt5.adapter import MT5Adapter, MT5Config
from src.mt5.execution_state import ExecutionState
from src.mt5.symbol_guard import SymbolGuard
from src.pipeline import OversoulDirector, run_advanced_modules, state_to_dict
from src.learning.live_feedback import process_live_trade_feedback
from src.macro.gold_macro import MacroFeedConfig, collect_xauusd_macro_state
from src.risk.capital_guard import evaluate_capital_protection
from src.scoring.confidence_score import compute_confidence
from src.strategy.intelligence import score_signal_intelligence
from src.utils import normalize_reasons, register_generated_artifact, write_json_atomic


SUPPORTED_TIMEFRAMES = {"M1", "M5", "M15", "H1", "H4"}
SUPPORTED_MODES = {"live", "replay"}
SUPPORTED_REPLAY_SOURCES = {"csv", "memory"}
MIN_TRADE_VOLUME = 0.01
BOUNDED_DELAYED_BROKER_RECHECK_SECONDS = 0.5
BOUNDED_SINGLE_RETRY_DELAY_SECONDS = 0.5
TRANSIENT_RETRY_ELIGIBLE_STATUSES = frozenset(
    {
        "requote",
        "price_changed",
        "price_off",
        "too_many_requests",
    }
)
BOUNDED_SINGLE_RETRY_EXECUTION_STATUSES = frozenset(
    {
        "requote",
        "price_changed",
        "price_off",
    }
)


@dataclass(frozen=True)
class RuntimeConfig:
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    bars: int = 220
    sample_path: str = "data/samples/xauusd.csv"
    memory_root: str = "memory"
    mode: str = "live"
    replay_source: str = "csv"
    replay_csv_path: str = "data/samples/xauusd.csv"
    generated_registry_path: str = "memory/generated_code_registry.json"
    meta_adaptive_profile_path: str = "memory/meta_adaptive_profile.json"
    evolution_enabled: bool = True
    evolution_registry_path: str = "memory/evolution_registry.json"
    evolution_artifact_root: str = "memory/evolution_artifacts"
    evolution_max_proposals: int = 3
    compact_output: bool = False
    evaluation_steps: int = 30
    evaluation_stride: int = 5
    evaluation_output_path: str = "memory/replay_evaluation_report.json"
    walk_forward_enabled: bool = False
    walk_forward_context_bars: int = 220
    walk_forward_test_bars: int = 60
    walk_forward_step_bars: int = 60
    execution_spread_cost_points: float = 0.0
    execution_commission_cost_points: float = 0.0
    execution_slippage_cost_points: float = 0.0
    execution_realism_v2_enabled: bool = False
    execution_latency_penalty_points: float = 0.0
    execution_slippage_multiplier: float = 1.0
    execution_no_fill_spread_threshold: float = 0.0
    execution_min_fill_confidence: float = 0.0
    knowledge_expansion_enabled: bool = False
    knowledge_expansion_root: str = "memory/knowledge_expansion"
    knowledge_candidate_limit: int = 6
    live_execution_enabled: bool = True
    live_authorization_enabled: bool = False
    live_order_volume: float = 0.01
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    treasury_yields_endpoint: str = "https://moneymatter.me/api/treasury/interest-rates"
    economic_calendar_endpoint: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    comex_open_interest_endpoint: str = ""
    gold_etf_flows_endpoint: str = ""
    option_magnet_levels_endpoint: str = ""
    physical_premium_discount_endpoint: str = ""
    central_bank_reserve_endpoint: str = ""
    macro_feed_enabled: bool = True
    macro_feed_allow_replay_fetch: bool = False
    max_daily_loss_points: float = 3.0
    max_total_drawdown_points: float = 12.0
    max_consecutive_loss_streak: int = 3
    max_anomaly_clusters: int = 2
    promotion_minimum_replay_sample_size: int = 30
    promotion_minimum_expectancy_points: float = 0.05
    promotion_maximum_drawdown_points: float = 4.0
    promotion_minimum_stability_score: float = 0.55
    signal_lifecycle_enabled: bool = False
    signal_max_age_seconds: int = 900
    quarantined_modules: list[str] = field(default_factory=list)


REQUIRED_RUNTIME_CONFIG_KEYS = (
    "symbol",
    "timeframe",
    "bars",
    "sample_path",
    "memory_root",
    "mode",
)

RUNTIME_CONFIG_TYPES: dict[str, str] = {
    "symbol": "str",
    "timeframe": "str",
    "bars": "int",
    "sample_path": "str",
    "memory_root": "str",
    "mode": "str",
    "replay_source": "str",
    "replay_csv_path": "str",
    "generated_registry_path": "str",
    "meta_adaptive_profile_path": "str",
    "evolution_enabled": "bool",
    "evolution_registry_path": "str",
    "evolution_artifact_root": "str",
    "evolution_max_proposals": "int",
    "compact_output": "bool",
    "evaluation_steps": "int",
    "evaluation_stride": "int",
    "evaluation_output_path": "str",
    "walk_forward_enabled": "bool",
    "walk_forward_context_bars": "int",
    "walk_forward_test_bars": "int",
    "walk_forward_step_bars": "int",
    "execution_spread_cost_points": "float",
    "execution_commission_cost_points": "float",
    "execution_slippage_cost_points": "float",
    "execution_realism_v2_enabled": "bool",
    "execution_latency_penalty_points": "float",
    "execution_slippage_multiplier": "float",
    "execution_no_fill_spread_threshold": "float",
    "execution_min_fill_confidence": "float",
    "knowledge_expansion_enabled": "bool",
    "knowledge_expansion_root": "str",
    "knowledge_candidate_limit": "int",
    "live_execution_enabled": "bool",
    "live_authorization_enabled": "bool",
    "live_order_volume": "float",
    "alpha_vantage_api_key": "str",
    "fred_api_key": "str",
    "treasury_yields_endpoint": "str",
    "economic_calendar_endpoint": "str",
    "comex_open_interest_endpoint": "str",
    "gold_etf_flows_endpoint": "str",
    "option_magnet_levels_endpoint": "str",
    "physical_premium_discount_endpoint": "str",
    "central_bank_reserve_endpoint": "str",
    "macro_feed_enabled": "bool",
    "macro_feed_allow_replay_fetch": "bool",
    "max_daily_loss_points": "float",
    "max_total_drawdown_points": "float",
    "max_consecutive_loss_streak": "int",
    "max_anomaly_clusters": "int",
    "promotion_minimum_replay_sample_size": "int",
    "promotion_minimum_expectancy_points": "float",
    "promotion_maximum_drawdown_points": "float",
    "promotion_minimum_stability_score": "float",
    "signal_lifecycle_enabled": "bool",
    "signal_max_age_seconds": "int",
    "quarantined_modules": "list_of_str",
}

NON_EMPTY_STRING_CONFIG_KEYS = {
    "symbol",
    "timeframe",
    "sample_path",
    "memory_root",
    "mode",
    "replay_source",
    "replay_csv_path",
    "generated_registry_path",
    "meta_adaptive_profile_path",
    "evolution_registry_path",
    "evolution_artifact_root",
    "evaluation_output_path",
    "knowledge_expansion_root",
}


def ensure_sample_data(path: Path) -> None:
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    base = 2030.0
    for i in range(1, 321):
        if i < 120:
            drift = i * 0.12
        elif i < 220:
            drift = (120 * 0.12) - ((i - 120) * 0.07)
        else:
            drift = (120 * 0.12) - (100 * 0.07) + ((i - 220) * 0.1)

        close = base + drift
        rows.append(
            {
                "time": 1700000000 + i * 60,
                "open": round(close - 0.25, 2),
                "high": round(close + 0.5, 2),
                "low": round(close - 0.55, 2),
                "close": round(close, 2),
                "tick_volume": 120 + (i % 40),
            }
        )

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _expect_runtime_config_type(key: str, value: Any, expected: str) -> Any:
    def _is_plain_int(candidate: Any) -> bool:
        return isinstance(candidate, int) and not isinstance(candidate, bool)

    def _is_plain_number(candidate: Any) -> bool:
        return isinstance(candidate, (int, float)) and not isinstance(candidate, bool)

    if expected == "bool":
        if isinstance(value, bool):
            return value
        raise ValueError(
            f"Invalid type for config key '{key}': expected bool, got {type(value).__name__}"
        )
    if expected == "int":
        if not _is_plain_int(value):
            raise ValueError(
                f"Invalid type for config key '{key}': expected int, got {type(value).__name__}"
            )
        return value
    if expected == "float":
        if not _is_plain_number(value):
            raise ValueError(
                f"Invalid type for config key '{key}': expected float, got {type(value).__name__}"
            )
        return float(value)
    if expected == "str":
        if not isinstance(value, str):
            raise ValueError(
                f"Invalid type for config key '{key}': expected str, got {type(value).__name__}"
            )
        return value
    if expected == "list_of_str":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(
                f"Invalid type for config key '{key}': expected list of strings, got {type(value).__name__}"
            )
        return list(value)
    raise ValueError(f"Unsupported runtime config schema type for key '{key}': {expected}")


def _should_apply_replay_wait_structure_override(
    *,
    decision: str,
    structure_bias: str,
    advanced_confidence: float,
    hard_liquidity_conflict: bool,
    memory_root: str,
    combined_reasons: list[str],
    effective_signal_confidence: float,
) -> tuple[bool, str]:
    """Return whether replay WAIT→structure-bias override should apply.

    Additive mitigation: when a soft structure/liquidity conflict is present and
    effective signal confidence is weak, skip the replay-only override so the
    pipeline remains in WAIT during known drawdown-prone disagreement segments.
    """
    if decision != "WAIT":
        return False, ""
    if structure_bias not in {"buy", "sell"}:
        return False, ""
    if advanced_confidence < 0.58:
        return False, ""
    if hard_liquidity_conflict:
        return False, ""
    if "__replay_isolation" not in str(memory_root):
        return False, ""

    soft_conflict = "structure_liquidity_conflict_soft" in {
        str(reason).strip() for reason in combined_reasons
    }
    if soft_conflict and effective_signal_confidence < 0.5:
        return False, "replay_drawdown_soft_conflict_override_guard"
    return True, ""


def load_runtime_config(path: Path) -> RuntimeConfig:
    if not path.exists():
        return RuntimeConfig()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in runtime config '{path}': {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid runtime config root in '{path}': expected JSON object, got {type(data).__name__}"
        )

    missing_keys = [key for key in REQUIRED_RUNTIME_CONFIG_KEYS if key not in data]
    if missing_keys:
        raise ValueError(
            f"Missing required config key(s) in '{path}': {', '.join(sorted(missing_keys))}"
        )

    unknown_keys = sorted(set(data) - set(RUNTIME_CONFIG_TYPES))
    if unknown_keys:
        raise ValueError(f"Unsupported config key(s) in '{path}': {', '.join(unknown_keys)}")

    defaults = RuntimeConfig(
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
        fred_api_key=os.getenv("FRED_API_KEY", ""),
    )
    payload: dict[str, Any] = dict(defaults.__dict__)

    for key, value in data.items():
        payload[key] = _expect_runtime_config_type(key, value, RUNTIME_CONFIG_TYPES[key])
        if (
            key in NON_EMPTY_STRING_CONFIG_KEYS
            and isinstance(payload[key], str)
            and not payload[key].strip()
        ):
            raise ValueError(f"Config key '{key}' must be a non-empty string")

    return RuntimeConfig(**payload)


def validate_runtime_config(config: RuntimeConfig) -> None:
    if config.mode not in SUPPORTED_MODES:
        supported_modes = ", ".join(sorted(SUPPORTED_MODES))
        raise ValueError(f"Unsupported mode: {config.mode}. Supported modes: {supported_modes}")

    if config.replay_source not in SUPPORTED_REPLAY_SOURCES:
        supported_sources = ", ".join(sorted(SUPPORTED_REPLAY_SOURCES))
        raise ValueError(
            f"Unsupported replay_source: {config.replay_source}. Supported sources: {supported_sources}"
        )

    guard_result = SymbolGuard().validate(config.symbol)
    if not guard_result["ready"]:
        raise ValueError("Only XAUUSD is supported in this project stage.")

    if config.timeframe.upper() not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {config.timeframe}")
    if config.bars <= 20:
        raise ValueError("bars must be > 20 for feature calculations")

    Path(config.sample_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.memory_root).mkdir(parents=True, exist_ok=True)
    Path(config.generated_registry_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.meta_adaptive_profile_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.evolution_registry_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.evolution_artifact_root).mkdir(parents=True, exist_ok=True)
    Path(config.evaluation_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.knowledge_expansion_root).mkdir(parents=True, exist_ok=True)

    if config.evaluation_steps <= 0:
        raise ValueError("evaluation_steps must be > 0")
    if config.evaluation_stride <= 0:
        raise ValueError("evaluation_stride must be > 0")
    if config.walk_forward_context_bars <= 0:
        raise ValueError("walk_forward_context_bars must be > 0")
    if config.walk_forward_test_bars <= 0:
        raise ValueError("walk_forward_test_bars must be > 0")
    if config.walk_forward_step_bars <= 0:
        raise ValueError("walk_forward_step_bars must be > 0")
    if config.walk_forward_enabled and config.walk_forward_context_bars < config.bars:
        raise ValueError("walk_forward_context_bars must be >= bars")
    if config.walk_forward_enabled and config.walk_forward_test_bars < config.evaluation_stride:
        raise ValueError("walk_forward_test_bars must be >= evaluation_stride")
    if config.live_order_volume <= 0:
        raise ValueError("live_order_volume must be > 0")
    if config.execution_spread_cost_points < 0:
        raise ValueError("execution_spread_cost_points must be >= 0")
    if config.execution_commission_cost_points < 0:
        raise ValueError("execution_commission_cost_points must be >= 0")
    if config.execution_slippage_cost_points < 0:
        raise ValueError("execution_slippage_cost_points must be >= 0")
    if config.execution_latency_penalty_points < 0:
        raise ValueError("execution_latency_penalty_points must be >= 0")
    if config.execution_slippage_multiplier < 1:
        raise ValueError("execution_slippage_multiplier must be >= 1")
    if config.execution_no_fill_spread_threshold < 0:
        raise ValueError("execution_no_fill_spread_threshold must be >= 0")
    if config.execution_min_fill_confidence < 0 or config.execution_min_fill_confidence > 1:
        raise ValueError("execution_min_fill_confidence must be within [0, 1]")
    if config.max_daily_loss_points <= 0:
        raise ValueError("max_daily_loss_points must be > 0")
    if config.max_total_drawdown_points <= 0:
        raise ValueError("max_total_drawdown_points must be > 0")
    if config.max_consecutive_loss_streak <= 0:
        raise ValueError("max_consecutive_loss_streak must be > 0")
    if config.max_anomaly_clusters <= 0:
        raise ValueError("max_anomaly_clusters must be > 0")
    if config.signal_max_age_seconds <= 0:
        raise ValueError("signal_max_age_seconds must be > 0")

    _QUARANTINABLE_MODULES = {
        "invisible_data_miner",
        "human_lag_exploit",
        "quantum_tremor_scanner",
        "spectral_signal_fusion",
        "meta_conscious_routing",
    }
    for module_name in config.quarantined_modules:
        if module_name not in _QUARANTINABLE_MODULES:
            raise ValueError(
                f"quarantined_modules contains unknown module '{module_name}'. "
                f"Allowed: {', '.join(sorted(_QUARANTINABLE_MODULES))}"
            )


def load_bars_from_csv(csv_path: Path, bars: int) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Replay CSV not found: {csv_path}")
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                {
                    "time": int(row["time"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "tick_volume": float(row.get("tick_volume", 0.0)),
                }
            )
    if not rows:
        raise ValueError(f"Replay CSV is empty: {csv_path}")
    return rows[-bars:]


def load_bars_from_memory(store: PatternStore, bars: int) -> list[dict[str, Any]]:
    payload = store.load("pattern_memory")
    patterns = payload.get("patterns", [])
    if not patterns:
        raise ValueError("No pattern snapshots available for memory replay.")
    snapshot_bars = patterns[-1].get("bars")
    if not snapshot_bars:
        raise ValueError("Latest snapshot has no stored bars for replay.")
    return snapshot_bars[-bars:]


def _assess_data_freshness(bars: list[dict[str, Any]], *, max_age_seconds: int) -> tuple[bool, int | None]:
    if not bars:
        return False, None
    latest_time = int(bars[-1].get("time", 0))
    if latest_time <= 0:
        return False, None
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    data_age_seconds = max(0, now_ts - latest_time)
    return data_age_seconds <= int(max_age_seconds), data_age_seconds


def _coerce_unix_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        candidate = int(value)
        return candidate if candidate > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            if stripped.isdigit():
                candidate = int(stripped)
                return candidate if candidate > 0 else None
            normalized = (
                f"{stripped.removesuffix('Z')}+00:00"
                if stripped.endswith("Z")
                else stripped
            )
            parsed = datetime.fromisoformat(normalized)
            candidate = int(parsed.timestamp())
            return candidate if candidate > 0 else None
        except Exception:
            return None
    return None


def _build_signal_lifecycle_context(
    *,
    enabled: bool,
    max_age_seconds: int,
    bars: list[dict[str, Any]],
) -> dict[str, Any]:
    source_bar_time = _coerce_unix_timestamp(bars[-1].get("time")) if bars else None
    return {
        "signal_lifecycle_enabled": bool(enabled),
        "signal_max_age_seconds": int(max_age_seconds),
        "decision_created_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_bar_time": source_bar_time,
        "signal_age_basis": "source_bar_time" if source_bar_time is not None else "decision_created_at",
    }


def _evaluate_signal_lifecycle(
    *,
    signal_lifecycle: dict[str, Any] | None,
) -> dict[str, Any]:
    lifecycle = dict(signal_lifecycle or {})
    execution_checked_at = datetime.now(tz=timezone.utc)
    enabled = bool(lifecycle.get("signal_lifecycle_enabled", False))
    max_age_seconds = int(lifecycle.get("signal_max_age_seconds", 900))
    execution_ts = int(execution_checked_at.timestamp())
    source_bar_time = _coerce_unix_timestamp(lifecycle.get("source_bar_time"))
    decision_created_at_ts = _coerce_unix_timestamp(lifecycle.get("decision_created_at"))
    if source_bar_time is not None:
        source_ts = source_bar_time
        age_basis = "source_bar_time"
    elif decision_created_at_ts is not None:
        source_ts = decision_created_at_ts
        age_basis = "decision_created_at"
    else:
        source_ts = None
        age_basis = "none"
    future_timestamp = source_ts is not None and source_ts > execution_ts
    if future_timestamp:
        # Cannot compute age for signals with timestamps in the future.
        signal_age_seconds = None
    else:
        signal_age_seconds = (execution_ts - source_ts) if source_ts is not None else None
    if not enabled:
        signal_fresh = True
        lifecycle_reason = "signal_lifecycle_disabled"
        refusal_reasons: list[str] = []
    elif future_timestamp:
        signal_fresh = False
        lifecycle_reason = "signal_timestamp_in_future"
        refusal_reasons = ["signal_stale", "signal_timestamp_in_future"]
    elif signal_age_seconds is None:
        signal_fresh = False
        lifecycle_reason = "signal_timestamp_missing"
        refusal_reasons = ["signal_stale", "signal_timestamp_missing"]
    elif signal_age_seconds <= max_age_seconds:
        signal_fresh = True
        lifecycle_reason = "signal_fresh"
        refusal_reasons = []
    else:
        signal_fresh = False
        lifecycle_reason = "signal_age_exceeded"
        refusal_reasons = ["signal_stale", "signal_age_exceeded"]
    return {
        "signal_lifecycle_enabled": enabled,
        "signal_max_age_seconds": max_age_seconds,
        "signal_age_basis": age_basis,
        "source_bar_time": source_bar_time,
        "decision_created_at": lifecycle.get("decision_created_at"),
        "execution_checked_at": execution_checked_at.isoformat(),
        "signal_age_seconds": signal_age_seconds,
        "signal_fresh": signal_fresh,
        "signal_lifecycle_reason": lifecycle_reason,
        "signal_lifecycle_refusal_reasons": refusal_reasons,
    }


def _build_non_live_mt5_readiness(
    *,
    symbol: str,
    bars: list[dict[str, Any]],
    data_source: str,
) -> dict[str, Any]:
    symbol_validation = SymbolGuard().validate_for_mt5(symbol)
    data_freshness, data_age_seconds = _assess_data_freshness(bars, max_age_seconds=900)
    reasons = list(symbol_validation["symbol_reasons"])
    reasons.extend(["non_live_mode", "live_execution_blocked_by_default"])
    if not data_freshness:
        reasons.append("data_stale_or_missing")
    fail_safe_reasons = [
        "terminal_connection_unstable",
        "account_not_ready",
    ]
    if not bool(symbol_validation.get("symbol_subscription_ready", False)):
        fail_safe_reasons.append("symbol_not_subscribed")
    if not data_freshness:
        fail_safe_reasons.append("tick_data_stale")
    fail_safe_reasons = sorted(set(fail_safe_reasons))
    reasons.extend(fail_safe_reasons)
    return {
        "readiness_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "data_source": data_source,
        "terminal_connection_attempts": 0,
        "terminal_connection_successes": 0,
        "terminal_connectivity": False,
        "terminal_connection_stable": False,
        "symbol_validity": bool(symbol_validation["symbol_validity"]),
        "symbol_subscription_ready": bool(symbol_validation.get("symbol_subscription_ready", False)),
        "account_trading_permission": False,
        "account_readiness": False,
        "data_freshness": data_freshness,
        "data_age_seconds": data_age_seconds,
        "tick_freshness_window_seconds": 900,
        "tick_data_freshness": data_freshness,
        "tick_age_seconds": data_age_seconds,
        "fail_safe_blocked_state": True,
        "fail_safe_blocked_reasons": fail_safe_reasons,
        "live_execution_blocked": True,
        "order_execution_enabled": False,
        "execution_gate": "non_live_enforced",
        "execution_refused": True,
        "ready_for_controlled_usage": False,
        "reason_codes": sorted({str(reason) for reason in reasons if str(reason).strip()}),
    }


def _persist_controlled_mt5_readiness(memory_root: str, payload: dict[str, Any]) -> str:
    readiness_path = Path(memory_root) / "mt5_controlled_readiness_state.json"
    write_json_atomic(readiness_path, payload)
    return str(readiness_path)


def _verify_mt5_readiness_chain(*, readiness: dict[str, Any], mode: str) -> dict[str, Any]:
    checks = [
        {
            "name": "terminal_connection_stable",
            "required": mode == "live",
            "passed": bool(readiness.get("terminal_connection_stable", False)),
        },
        {
            "name": "symbol_subscription_ready",
            "required": True,
            "passed": bool(readiness.get("symbol_subscription_ready", False)),
        },
        {
            "name": "account_readiness",
            "required": mode == "live",
            "passed": bool(readiness.get("account_readiness", False)),
        },
        {
            "name": "tick_data_freshness",
            "required": True,
            "passed": bool(readiness.get("tick_data_freshness", False)),
        },
        {
            "name": "fail_safe_blocked_state",
            "required": True,
            "passed": bool(readiness.get("fail_safe_blocked_state", False)),
        },
        {
            "name": "live_execution_blocked",
            "required": True,
            "passed": bool(readiness.get("live_execution_blocked", False)),
        },
        {
            "name": "order_execution_disabled",
            "required": True,
            "passed": not bool(readiness.get("order_execution_enabled", True)),
        },
    ]
    failed_required_checks = sorted(
        check["name"] for check in checks if bool(check["required"]) and not bool(check["passed"])
    )
    return {
        "mode": mode,
        "checks": checks,
        "required_check_count": sum(1 for check in checks if bool(check["required"])),
        "failed_required_checks": failed_required_checks,
        "all_checks_passed": not failed_required_checks,
    }


def _build_mt5_quarantine_state(
    *,
    readiness: dict[str, Any],
    mode: str,
    readiness_chain: dict[str, Any],
) -> dict[str, Any]:
    invalid_state_reasons: list[str] = []
    if bool(readiness.get("order_execution_enabled", False)):
        invalid_state_reasons.append("order_execution_must_remain_disabled")
    if not bool(readiness.get("live_execution_blocked", False)):
        invalid_state_reasons.append("live_execution_must_remain_blocked_by_default")
    if bool(readiness.get("execution_refused", True)) and (
        bool(readiness.get("ready_for_controlled_usage", False))
        or str(readiness.get("execution_gate", "")).strip().lower() == "controlled_non_live"
    ):
        invalid_state_reasons.append("inconsistent_ready_or_controlled_gate_refused_state")
    failed_required_checks = list(readiness_chain.get("failed_required_checks", []))
    quarantine_reasons = sorted(set(invalid_state_reasons + failed_required_checks))
    quarantine_required = bool(invalid_state_reasons) or (mode == "live" and bool(failed_required_checks))
    return {
        "quarantine_required": quarantine_required,
        "quarantine_reasons": quarantine_reasons,
        "invalid_state_reasons": sorted(set(invalid_state_reasons)),
        "failed_required_checks": failed_required_checks,
    }


def _load_mt5_resume_state(memory_root: str) -> dict[str, Any]:
    resume_path = Path(memory_root) / "mt5_runtime_resume_state.json"
    if not resume_path.exists():
        return {"status": "unknown", "interruption_detected": False, "safe_resume_applied": False}
    try:
        payload = json.loads(resume_path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unknown", "interruption_detected": False, "safe_resume_applied": False}
    if not isinstance(payload, dict):
        return {"status": "unknown", "interruption_detected": False, "safe_resume_applied": False}
    return payload


def _build_mt5_resume_state(
    *,
    previous_resume_state: dict[str, Any],
    readiness_chain: dict[str, Any],
    quarantine_state: dict[str, Any],
) -> dict[str, Any]:
    interruption_detected = bool(quarantine_state.get("quarantine_required", False)) or not bool(
        readiness_chain.get("all_checks_passed", False)
    )
    prior_interruption = bool(previous_resume_state.get("interruption_detected", False))
    safe_resume_applied = prior_interruption and not interruption_detected
    status = "interrupted" if interruption_detected else "stable"
    if safe_resume_applied:
        status = "resumed_safe"
    return {
        "previous_status": str(previous_resume_state.get("status", "unknown")),
        "status": status,
        "interruption_detected": interruption_detected,
        "safe_resume_applied": safe_resume_applied,
    }


def _build_mt5_self_audit_report(
    *,
    readiness: dict[str, Any],
    mode: str,
    readiness_chain: dict[str, Any],
    quarantine_state: dict[str, Any],
    resume_state: dict[str, Any],
) -> dict[str, Any]:
    failed_checks = list(readiness_chain.get("failed_required_checks", []))
    quarantine_reasons = list(quarantine_state.get("quarantine_reasons", []))
    deterministic_fingerprint = "|".join(
        [
            str(readiness.get("symbol_validity", False)),
            str(readiness.get("symbol_subscription_ready", False)),
            str(readiness.get("account_readiness", False)),
            str(readiness.get("tick_data_freshness", False)),
            ",".join(failed_checks),
            ",".join(quarantine_reasons),
            str(resume_state.get("status", "unknown")),
        ]
    )
    deterministic_id = hashlib.sha256(deterministic_fingerprint.encode("utf-8")).hexdigest()[:32]
    return {
        "audit_id": (
            f"mt5-audit-{str(readiness.get('data_source', 'unknown'))}-"
            f"{mode}-{deterministic_id}"
        ),
        "mode": mode,
        "deterministic_fingerprint": deterministic_fingerprint,
        "all_checks_passed": bool(readiness_chain.get("all_checks_passed", False)),
        "failed_required_checks": failed_checks,
        "quarantine_required": bool(quarantine_state.get("quarantine_required", False)),
        "quarantine_reasons": quarantine_reasons,
        "safe_resume_applied": bool(resume_state.get("safe_resume_applied", False)),
    }


def _persist_mt5_pack3_artifacts(
    *,
    memory_root: str,
    readiness_chain: dict[str, Any],
    self_audit_report: dict[str, Any],
    quarantine_state: dict[str, Any],
    resume_state: dict[str, Any],
) -> dict[str, str]:
    root = Path(memory_root)
    paths = {
        "readiness_chain_path": root / "mt5_readiness_chain_verification.json",
        "self_audit_report_path": root / "mt5_self_audit_report.json",
        "quarantine_state_path": root / "mt5_readiness_quarantine_state.json",
        "resume_state_path": root / "mt5_runtime_resume_state.json",
    }
    write_json_atomic(paths["readiness_chain_path"], readiness_chain)
    write_json_atomic(paths["self_audit_report_path"], self_audit_report)
    write_json_atomic(paths["quarantine_state_path"], quarantine_state)
    write_json_atomic(paths["resume_state_path"], resume_state)
    return {name: str(path) for name, path in paths.items()}


def _load_mt5_controlled_execution_state(memory_root: str) -> dict[str, Any]:
    path = Path(memory_root) / "mt5_controlled_execution_state.json"
    if not path.exists():
        return {
            "consecutive_failed_executions": 0,
            "auto_stop_active": False,
            "last_failure_reasons": [],
            "total_execution_attempts": 0,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "consecutive_failed_executions": 0,
            "auto_stop_active": False,
            "last_failure_reasons": [],
            "total_execution_attempts": 0,
        }
    if not isinstance(payload, dict):
        return {
            "consecutive_failed_executions": 0,
            "auto_stop_active": False,
            "last_failure_reasons": [],
            "total_execution_attempts": 0,
        }
    return payload


def _is_replay_evaluation_step_memory_root(memory_root: Path) -> bool:
    parts = memory_root.expanduser().parts
    if not any(part.endswith("__replay_isolation") for part in parts):
        return False
    if "steps" not in parts:
        return False
    try:
        steps_index = parts.index("steps")
    except ValueError:
        return False
    return steps_index < len(parts) - 1


def _classify_mt5_execution_failure(reasons: list[str]) -> str:
    joined = "|".join(sorted({str(reason) for reason in reasons if str(reason).strip()}))
    if "auto_stop_active" in joined or "auto_stop_triggered" in joined:
        return "auto_stop_protection"
    if "pretrade_check_failed:live_execution_enabled" in joined or "live_execution_not_enabled" in joined:
        return "explicit_gate_disabled"
    if "pretrade_check_failed" in joined or "readiness" in joined:
        return "pretrade_safety_failure"
    if "mt5_module_unavailable" in joined or "mt5_initialize_failed" in joined:
        return "execution_infrastructure_unavailable"
    return "governed_refusal"


def _readiness_allows_live_order(readiness: dict[str, Any]) -> bool:
    execution_gate = str(readiness.get("execution_gate", "")).strip().lower()
    live_authorized_execution_gates = {
        "live_authorized_controlled_execution",
    }
    return all(
        [
            not bool(readiness.get("live_execution_blocked", True)),
            bool(readiness.get("order_execution_enabled", False)),
            not bool(readiness.get("execution_refused", True)),
            execution_gate in live_authorized_execution_gates,
        ]
    )


def _apply_explicit_live_authorization(
    *,
    readiness: dict[str, Any],
    mode: str,
    live_authorization_enabled: bool,
    readiness_chain: dict[str, Any],
    quarantine_state: dict[str, Any],
) -> dict[str, Any]:
    condition_checks = [
        {"name": "flag_enabled", "passed": bool(live_authorization_enabled)},
        {"name": "mode_live", "passed": mode == "live"},
        {"name": "readiness_chain_passed", "passed": bool(readiness_chain.get("all_checks_passed", False))},
        {"name": "quarantine_clear", "passed": not bool(quarantine_state.get("quarantine_required", False))},
        {"name": "ready_for_controlled_usage", "passed": bool(readiness.get("ready_for_controlled_usage", False))},
        {"name": "symbol_validity", "passed": bool(readiness.get("symbol_validity", False))},
        {"name": "account_trading_permission", "passed": bool(readiness.get("account_trading_permission", False))},
        {"name": "account_readiness", "passed": bool(readiness.get("account_readiness", False))},
        {"name": "data_freshness", "passed": bool(readiness.get("data_freshness", False))},
        {"name": "tick_data_freshness", "passed": bool(readiness.get("tick_data_freshness", False))},
        {
            "name": "execution_not_refused_pre_authorization",
            "passed": not bool(readiness.get("execution_refused", True)),
        },
        {
            "name": "no_fail_safe_blocked_reasons",
            "passed": not bool(readiness.get("fail_safe_blocked_reasons", [])),
        },
    ]
    failed_conditions = sorted(check["name"] for check in condition_checks if not bool(check["passed"]))
    audited = {
        **readiness,
        "live_authorization_audit": {
            "enabled": bool(live_authorization_enabled),
            "mode": str(mode),
            "authorized": not failed_conditions,
            "conditions": condition_checks,
            "failed_conditions": failed_conditions,
        },
    }
    if failed_conditions:
        return audited
    return {
        **audited,
        "live_execution_blocked": False,
        "order_execution_enabled": True,
        "execution_refused": False,
        "execution_gate": "live_authorized_controlled_execution",
        "live_authorization_applied": True,
    }


def _place_controlled_mt5_order(
    *,
    order_request: dict[str, Any],
    mt5_module: Any | None = None,
) -> dict[str, Any]:
    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return {
                "status": "refused",
                "order_sent": False,
                "error_reason": "mt5_module_unavailable",
                "retcode": None,
            }

    if not bool(mt5.initialize()):
        return {
            "status": "failed",
            "order_sent": False,
            "error_reason": "mt5_initialize_failed",
            "retcode": None,
        }
    try:
        order_send = getattr(mt5, "order_send", None)
        if not callable(order_send):
            return {
                "status": "failed",
                "order_sent": False,
                "error_reason": "mt5_order_send_unavailable",
                "retcode": None,
            }
        result = order_send(order_request)
        retcode = getattr(result, "retcode", None)
        retcode_done = getattr(mt5, "TRADE_RETCODE_DONE", None)
        retcode_done_partial = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", None)
        retcode_requote = getattr(mt5, "TRADE_RETCODE_REQUOTE", None)
        retcode_price_changed = getattr(mt5, "TRADE_RETCODE_PRICE_CHANGED", None)
        retcode_no_money = getattr(mt5, "TRADE_RETCODE_NO_MONEY", None)
        retcode_market_closed = getattr(mt5, "TRADE_RETCODE_MARKET_CLOSED", None)
        retcode_trade_disabled = getattr(mt5, "TRADE_RETCODE_TRADE_DISABLED", None)
        retcode_invalid_volume = getattr(mt5, "TRADE_RETCODE_INVALID_VOLUME", None)
        retcode_invalid_stops = getattr(mt5, "TRADE_RETCODE_INVALID_STOPS", None)
        retcode_price_off = getattr(mt5, "TRADE_RETCODE_PRICE_OFF", None)
        retcode_too_many_requests = getattr(mt5, "TRADE_RETCODE_TOO_MANY_REQUESTS", None)
        retcode_invalid_price = getattr(mt5, "TRADE_RETCODE_INVALID_PRICE", None)
        if retcode_done is not None and retcode == retcode_done:
            return {
                "status": "accepted",
                "order_sent": True,
                "error_reason": "",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_done_partial is not None and retcode == retcode_done_partial:
            return {
                "status": "partial",
                "order_sent": True,
                "error_reason": "mt5_partial_fill_unreconciled",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
                "requested_volume": float(order_request.get("volume", 0.0)),
                "filled_volume": None,
                "remaining_volume": None,
                "partial_outcome_quantity_truth": "unresolved",
            }
        if retcode_requote is not None and retcode == retcode_requote:
            return {
                "status": "requote",
                "order_sent": True,
                "error_reason": "mt5_requote_unretried",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_price_changed is not None and retcode == retcode_price_changed:
            return {
                "status": "price_changed",
                "order_sent": True,
                "error_reason": "mt5_price_changed_unretried",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_no_money is not None and retcode == retcode_no_money:
            return {
                "status": "insufficient_margin",
                "order_sent": True,
                "error_reason": "mt5_no_money",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_market_closed is not None and retcode == retcode_market_closed:
            return {
                "status": "market_closed",
                "order_sent": True,
                "error_reason": "mt5_market_closed",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_trade_disabled is not None and retcode == retcode_trade_disabled:
            return {
                "status": "trade_disabled",
                "order_sent": True,
                "error_reason": "mt5_trade_disabled",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_invalid_volume is not None and retcode == retcode_invalid_volume:
            return {
                "status": "invalid_volume",
                "order_sent": True,
                "error_reason": "mt5_invalid_volume",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_invalid_stops is not None and retcode == retcode_invalid_stops:
            return {
                "status": "invalid_stops",
                "order_sent": True,
                "error_reason": "mt5_invalid_stops",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_price_off is not None and retcode == retcode_price_off:
            return {
                "status": "price_off",
                "order_sent": True,
                "error_reason": "mt5_price_off",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_too_many_requests is not None and retcode == retcode_too_many_requests:
            return {
                "status": "too_many_requests",
                "order_sent": True,
                "error_reason": "mt5_too_many_requests",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        if retcode_invalid_price is not None and retcode == retcode_invalid_price:
            return {
                "status": "invalid_price",
                "order_sent": True,
                "error_reason": "mt5_invalid_price",
                "retcode": retcode,
                "order_id": int(getattr(result, "order", 0) or 0),
            }
        return {
            "status": "rejected",
            "order_sent": True,
            "error_reason": f"mt5_retcode_{retcode}",
            "retcode": retcode,
            "order_id": int(getattr(result, "order", 0) or 0),
        }
    finally:
        mt5.shutdown()


def _normalize_mt5_position_side(*, mt5_module: Any, position_type: Any) -> str | None:
    position_type_buy = getattr(mt5_module, "POSITION_TYPE_BUY", None)
    position_type_sell = getattr(mt5_module, "POSITION_TYPE_SELL", None)
    if position_type_buy is not None and position_type == position_type_buy:
        return "BUY"
    if position_type_sell is not None and position_type == position_type_sell:
        return "SELL"
    if position_type == 0:
        return "BUY"
    if position_type == 1:
        return "SELL"
    normalized = str(position_type).strip().upper()
    if normalized in {"BUY", "SELL"}:
        return normalized
    return None


def _normalize_mt5_order_side(*, mt5_module: Any, order_type: Any) -> str | None:
    order_type_buy = getattr(mt5_module, "ORDER_TYPE_BUY", None)
    order_type_sell = getattr(mt5_module, "ORDER_TYPE_SELL", None)
    if order_type_buy is not None and order_type == order_type_buy:
        return "BUY"
    if order_type_sell is not None and order_type == order_type_sell:
        return "SELL"
    if order_type == 0:
        return "BUY"
    if order_type == 1:
        return "SELL"
    normalized = str(order_type).strip().upper()
    if normalized in {"BUY", "SELL"}:
        return normalized
    return None


def _normalize_mt5_deal_side(*, mt5_module: Any, deal_type: Any) -> str | None:
    deal_type_buy = getattr(mt5_module, "DEAL_TYPE_BUY", None)
    deal_type_sell = getattr(mt5_module, "DEAL_TYPE_SELL", None)
    if deal_type_buy is not None and deal_type == deal_type_buy:
        return "BUY"
    if deal_type_sell is not None and deal_type == deal_type_sell:
        return "SELL"
    if deal_type == 0:
        return "BUY"
    if deal_type == 1:
        return "SELL"
    normalized = str(deal_type).strip().upper()
    if normalized in {"BUY", "SELL"}:
        return normalized
    return None


def _verify_partial_send_deal_quantity(
    *,
    sent_order_id: int,
    symbol: str,
    side: str,
    requested_volume: float,
    mt5_module: Any | None = None,
) -> dict[str, Any]:
    fail_closed = {
        "confirmation": "unconfirmed",
        "partial_outcome_quantity_truth": "unresolved",
        "broker_quantity_outcome": "partial_quantity_unresolved",
        "fail_closed_reason": "",
        "sent_order_id": int(sent_order_id or 0),
        "deal_lookup_source": "history_deals_get",
        "linked_deal_count": 0,
        "linkage_field_used": None,
        "linkage_value_matched": None,
        "matched_symbol": None,
        "matched_side": None,
        "requested_volume": float(requested_volume),
        "filled_volume": None,
        "remaining_volume": None,
        "symbol_match": None,
        "side_match": None,
        "quantity_consistent": None,
    }
    if int(sent_order_id or 0) <= 0:
        return {**fail_closed, "fail_closed_reason": "invalid_sent_order_id"}
    if float(requested_volume) <= 0.0:
        return {**fail_closed, "fail_closed_reason": "invalid_requested_volume"}

    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_module_unavailable"}

    initialized = False
    try:
        initialize = getattr(mt5, "initialize", None)
        if not callable(initialize) or not bool(initialize()):
            return {**fail_closed, "fail_closed_reason": "mt5_initialize_failed"}
        initialized = True
        history_deals_get = getattr(mt5, "history_deals_get", None)
        if not callable(history_deals_get):
            return {**fail_closed, "fail_closed_reason": "mt5_history_deals_get_unavailable"}
        deals_result = history_deals_get()
        if deals_result is None:
            return {**fail_closed, "fail_closed_reason": "mt5_history_deals_get_unavailable"}
        try:
            deals = list(deals_result)
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_history_deals_unreadable"}

        readable_linkage_available = False
        supporting_only_match_found = False
        linkage_match_with_support_mismatch = False
        linked_deals: list[dict[str, Any]] = []
        for deal in deals:
            linkage_value = getattr(deal, "order", None)
            if linkage_value is None:
                continue
            try:
                linkage_value_int = int(linkage_value)
            except Exception:
                continue
            readable_linkage_available = True
            deal_symbol = str(getattr(deal, "symbol", ""))
            deal_side = _normalize_mt5_deal_side(
                mt5_module=mt5,
                deal_type=getattr(deal, "type", None),
            )
            try:
                deal_volume = float(getattr(deal, "volume", None))
            except Exception:
                deal_volume = None
            symbol_match = deal_symbol == str(symbol)
            side_match = deal_side == str(side)
            volume_readable = deal_volume is not None
            if (
                symbol_match
                and side_match
                and volume_readable
                and linkage_value_int != int(sent_order_id)
            ):
                supporting_only_match_found = True
            if linkage_value_int != int(sent_order_id):
                continue
            if not (symbol_match and side_match and volume_readable):
                linkage_match_with_support_mismatch = True
                continue
            linked_deals.append(
                {
                    "deal": deal,
                    "linkage_field_used": "order",
                    "linkage_value_matched": linkage_value_int,
                    "symbol_match": symbol_match,
                    "side_match": side_match,
                    "matched_side": deal_side,
                    "matched_volume": deal_volume,
                }
            )

        if linked_deals:
            if linkage_match_with_support_mismatch:
                return {
                    **fail_closed,
                    "linked_deal_count": len(linked_deals),
                    "linkage_field_used": "order",
                    "linkage_value_matched": int(sent_order_id),
                    "symbol_match": False,
                    "side_match": False,
                    "quantity_consistent": False,
                    "fail_closed_reason": "linked_deal_supporting_mismatch",
                }
            filled_volume = float(sum(float(deal["matched_volume"]) for deal in linked_deals))
            remaining_volume = float(requested_volume) - filled_volume
            quantity_consistent = (
                filled_volume > 0.0 and filled_volume < float(requested_volume) and remaining_volume >= 0.0
            )
            if not quantity_consistent:
                return {
                    **fail_closed,
                    "linked_deal_count": len(linked_deals),
                    "linkage_field_used": "order",
                    "linkage_value_matched": int(sent_order_id),
                    "matched_symbol": str(symbol),
                    "matched_side": str(side),
                    "symbol_match": True,
                    "side_match": True,
                    "quantity_consistent": False,
                    "fail_closed_reason": "linked_deal_quantity_inconsistent",
                }
            return {
                **fail_closed,
                "confirmation": "confirmed",
                "partial_outcome_quantity_truth": "broker_confirmed_partial_quantity",
                "broker_quantity_outcome": "partial_quantity_confirmed_from_linked_deal",
                "fail_closed_reason": "",
                "linked_deal_count": len(linked_deals),
                "linkage_field_used": "order",
                "linkage_value_matched": int(sent_order_id),
                "matched_symbol": str(symbol),
                "matched_side": str(side),
                "filled_volume": filled_volume,
                "remaining_volume": remaining_volume,
                "symbol_match": True,
                "side_match": True,
                "quantity_consistent": True,
            }
        if not readable_linkage_available:
            return {**fail_closed, "fail_closed_reason": "linked_deal_order_field_unavailable_or_unreadable"}
        if supporting_only_match_found:
            return {**fail_closed, "fail_closed_reason": "deal_supporting_metadata_only_match"}
        if linkage_match_with_support_mismatch:
            return {**fail_closed, "fail_closed_reason": "linked_deal_supporting_mismatch"}
        return {**fail_closed, "fail_closed_reason": "exact_linked_deal_mismatch"}
    except Exception:
        return {**fail_closed, "fail_closed_reason": "partial_deal_verification_unavailable"}
    finally:
        if initialized:
            shutdown = getattr(mt5, "shutdown", None)
            if callable(shutdown):
                shutdown()


def _verify_accepted_send_order_acknowledgement(
    *,
    mt5_module: Any,
    sent_order_id: int,
    symbol: str,
    side: str,
    volume: float,
) -> dict[str, Any]:
    lookup_sources = (
        ("orders_get", getattr(mt5_module, "orders_get", None)),
        ("history_orders_get", getattr(mt5_module, "history_orders_get", None)),
    )
    fail_closed = {
        "order_acknowledged": False,
        "order_ack_source": None,
        "matched_order_ticket": None,
        "matched_order_symbol": None,
        "matched_order_side": None,
        "matched_order_volume": None,
        "order_symbol_match": None,
        "order_side_match": None,
        "order_volume_match": None,
        "fail_closed_reason": "order_lookup_inconclusive",
    }
    lookup_callable_available = False
    lookup_readable_available = False
    readable_linkage_available = False
    supporting_only_match_found = False
    linkage_match_with_support_mismatch = False
    candidates: list[dict[str, Any]] = []

    for source_name, source_callable in lookup_sources:
        if not callable(source_callable):
            continue
        lookup_callable_available = True
        try:
            source_result = source_callable()
        except Exception:
            continue
        if source_result is None:
            continue
        try:
            source_orders = list(source_result)
        except Exception:
            continue
        lookup_readable_available = True
        for order in source_orders:
            linkage_matches: list[tuple[str, int]] = []
            for field_name in ("ticket", "order"):
                field_value = getattr(order, field_name, None)
                if field_value is None:
                    continue
                try:
                    linkage_value = int(field_value)
                except Exception:
                    continue
                readable_linkage_available = True
                if linkage_value == int(sent_order_id):
                    linkage_matches.append((field_name, linkage_value))
            order_symbol = str(getattr(order, "symbol", ""))
            order_side = _normalize_mt5_order_side(
                mt5_module=mt5_module,
                order_type=getattr(order, "type", None),
            )
            order_volume = None
            for volume_field_name in ("volume_current", "volume_initial", "volume"):
                volume_value = getattr(order, volume_field_name, None)
                if volume_value is None:
                    continue
                try:
                    order_volume = float(volume_value)
                    break
                except Exception:
                    continue
            symbol_match = order_symbol == str(symbol)
            side_match = order_side == str(side)
            volume_match = order_volume is not None and order_volume == float(volume)
            if symbol_match and side_match and volume_match and not linkage_matches:
                supporting_only_match_found = True
            if not linkage_matches:
                continue
            if not (symbol_match and side_match and volume_match):
                linkage_match_with_support_mismatch = True
                continue
            linkage_field_used, linkage_value_matched = linkage_matches[0]
            candidates.append(
                {
                    "source_name": source_name,
                    "order": order,
                    "linkage_field_used": linkage_field_used,
                    "linkage_value_matched": linkage_value_matched,
                    "matched_side": order_side,
                    "matched_volume": order_volume,
                    "symbol_match": symbol_match,
                    "side_match": side_match,
                    "volume_match": volume_match,
                }
            )

    if len(candidates) == 1:
        candidate = candidates[0]
        matched_order = candidate["order"]
        matched_ticket = getattr(matched_order, "ticket", None)
        if matched_ticket is None:
            matched_ticket = getattr(matched_order, "order", None)
        try:
            matched_ticket = int(matched_ticket) if matched_ticket is not None else None
        except Exception:
            matched_ticket = None
        return {
            **fail_closed,
            "order_acknowledged": True,
            "order_ack_source": candidate["source_name"],
            "matched_order_ticket": matched_ticket,
            "matched_order_symbol": str(getattr(matched_order, "symbol", "")),
            "matched_order_side": candidate["matched_side"],
            "matched_order_volume": candidate["matched_volume"],
            "order_symbol_match": True,
            "order_side_match": True,
            "order_volume_match": True,
            "fail_closed_reason": "",
        }
    if len(candidates) > 1:
        return {**fail_closed, "fail_closed_reason": "non_unique_order_linkage_match"}
    if not lookup_callable_available:
        return {**fail_closed, "fail_closed_reason": "mt5_order_lookup_unavailable"}
    if not lookup_readable_available:
        return {**fail_closed, "fail_closed_reason": "mt5_order_lookup_unreadable"}
    if not readable_linkage_available:
        return {**fail_closed, "fail_closed_reason": "exact_order_linkage_unavailable_or_unreadable"}
    if supporting_only_match_found:
        return {**fail_closed, "fail_closed_reason": "order_supporting_metadata_only_match"}
    if linkage_match_with_support_mismatch:
        return {**fail_closed, "fail_closed_reason": "order_linkage_supporting_mismatch"}
    return {**fail_closed, "fail_closed_reason": "exact_order_linkage_mismatch"}


def _verify_accepted_send_position_linkage(
    *,
    sent_order_id: int,
    symbol: str,
    side: str,
    volume: float,
    mt5_module: Any | None = None,
) -> dict[str, Any]:
    fail_closed = {
        "confirmation": "unconfirmed",
        "broker_state_outcome": "accepted_send_unreconciled",
        "fail_closed_reason": "",
        "sent_order_id": int(sent_order_id or 0),
        "linkage_field_used": None,
        "linkage_value_matched": None,
        "matched_position_ticket": None,
        "matched_symbol": None,
        "matched_side": None,
        "matched_volume": None,
        "symbol_match": None,
        "side_match": None,
        "volume_match": None,
        "order_acknowledged": False,
        "order_ack_source": None,
        "matched_order_ticket": None,
        "matched_order_symbol": None,
        "matched_order_side": None,
        "matched_order_volume": None,
        "order_symbol_match": None,
        "order_side_match": None,
        "order_volume_match": None,
    }
    if int(sent_order_id or 0) <= 0:
        return {**fail_closed, "fail_closed_reason": "invalid_sent_order_id"}

    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_module_unavailable"}

    initialized = False
    try:
        initialize = getattr(mt5, "initialize", None)
        if not callable(initialize) or not bool(initialize()):
            return {**fail_closed, "fail_closed_reason": "mt5_initialize_failed"}
        initialized = True
        positions_get = getattr(mt5, "positions_get", None)
        if not callable(positions_get):
            return {**fail_closed, "fail_closed_reason": "mt5_positions_get_unavailable"}
        positions = positions_get()
        if positions is None:
            return {**fail_closed, "fail_closed_reason": "mt5_positions_get_unavailable"}
        try:
            broker_positions = list(positions)
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_positions_unreadable"}
        readable_linkage_available = False
        supporting_only_match_found = False
        linkage_match_with_support_mismatch = False
        candidates: list[dict[str, Any]] = []
        for position in broker_positions:
            linkage_matches: list[tuple[str, int]] = []
            for field_name in ("ticket", "identifier"):
                field_value = getattr(position, field_name, None)
                if field_value is None:
                    continue
                try:
                    linkage_value = int(field_value)
                except Exception:
                    continue
                readable_linkage_available = True
                if linkage_value == int(sent_order_id):
                    linkage_matches.append((field_name, linkage_value))
            position_symbol = str(getattr(position, "symbol", ""))
            position_side = _normalize_mt5_position_side(
                mt5_module=mt5,
                position_type=getattr(position, "type", None),
            )
            try:
                position_volume = float(getattr(position, "volume", None))
            except Exception:
                position_volume = None
            symbol_match = position_symbol == str(symbol)
            side_match = position_side == str(side)
            volume_match = position_volume is not None and position_volume == float(volume)
            if symbol_match and side_match and volume_match and not linkage_matches:
                supporting_only_match_found = True
            if not linkage_matches:
                continue
            if not (symbol_match and side_match and volume_match):
                linkage_match_with_support_mismatch = True
                continue
            linkage_field_used, linkage_value_matched = linkage_matches[0]
            candidates.append(
                {
                    "position": position,
                    "linkage_field_used": linkage_field_used,
                    "linkage_value_matched": linkage_value_matched,
                    "symbol_match": symbol_match,
                    "side_match": side_match,
                    "volume_match": volume_match,
                    "matched_side": position_side,
                    "matched_volume": position_volume,
                }
            )
        if len(candidates) == 1:
            candidate = candidates[0]
            matched_position = candidate["position"]
            matched_ticket = getattr(matched_position, "ticket", None)
            try:
                matched_ticket = int(matched_ticket) if matched_ticket is not None else None
            except Exception:
                matched_ticket = None
            return {
                **fail_closed,
                "confirmation": "confirmed",
                "broker_state_outcome": "accepted_send_position_confirmed",
                "fail_closed_reason": "",
                "linkage_field_used": candidate["linkage_field_used"],
                "linkage_value_matched": candidate["linkage_value_matched"],
                "matched_position_ticket": matched_ticket,
                "matched_symbol": str(getattr(matched_position, "symbol", "")),
                "matched_side": candidate["matched_side"],
                "matched_volume": candidate["matched_volume"],
                "symbol_match": True,
                "side_match": True,
                "volume_match": True,
            }
        if len(candidates) > 1:
            position_fail_closed_reason = "non_unique_linkage_match"
        elif not readable_linkage_available:
            position_fail_closed_reason = "linkage_field_unavailable_or_unreadable"
        elif supporting_only_match_found:
            position_fail_closed_reason = "supporting_metadata_only_match"
        elif linkage_match_with_support_mismatch:
            position_fail_closed_reason = "linkage_match_supporting_mismatch"
        else:
            position_fail_closed_reason = "exact_linkage_mismatch"

        order_ack_verification = _verify_accepted_send_order_acknowledgement(
            mt5_module=mt5,
            sent_order_id=int(sent_order_id),
            symbol=symbol,
            side=side,
            volume=volume,
        )
        if bool(order_ack_verification.get("order_acknowledged", False)):
            return {
                **fail_closed,
                "confirmation": "unconfirmed",
                "broker_state_outcome": "accepted_send_order_acknowledged_position_unconfirmed",
                "fail_closed_reason": position_fail_closed_reason,
                "order_acknowledged": True,
                "order_ack_source": order_ack_verification.get("order_ack_source"),
                "matched_order_ticket": order_ack_verification.get("matched_order_ticket"),
                "matched_order_symbol": order_ack_verification.get("matched_order_symbol"),
                "matched_order_side": order_ack_verification.get("matched_order_side"),
                "matched_order_volume": order_ack_verification.get("matched_order_volume"),
                "order_symbol_match": order_ack_verification.get("order_symbol_match"),
                "order_side_match": order_ack_verification.get("order_side_match"),
                "order_volume_match": order_ack_verification.get("order_volume_match"),
            }
        return {
            **fail_closed,
            "fail_closed_reason": str(
                order_ack_verification.get("fail_closed_reason") or position_fail_closed_reason
            ),
            "order_acknowledged": False,
            "order_ack_source": order_ack_verification.get("order_ack_source"),
            "matched_order_ticket": order_ack_verification.get("matched_order_ticket"),
            "matched_order_symbol": order_ack_verification.get("matched_order_symbol"),
            "matched_order_side": order_ack_verification.get("matched_order_side"),
            "matched_order_volume": order_ack_verification.get("matched_order_volume"),
            "order_symbol_match": order_ack_verification.get("order_symbol_match"),
            "order_side_match": order_ack_verification.get("order_side_match"),
            "order_volume_match": order_ack_verification.get("order_volume_match"),
        }
    except Exception:
        return {**fail_closed, "fail_closed_reason": "broker_verification_unavailable"}
    finally:
        if initialized:
            shutdown = getattr(mt5, "shutdown", None)
            if callable(shutdown):
                shutdown()


def _build_retry_metadata(*, order_result: dict[str, Any]) -> dict[str, Any]:
    status = str(order_result.get("status") or "").strip().lower()
    order_sent = bool(order_result.get("order_sent", False))
    retry_eligible = bool(order_sent and status in TRANSIENT_RETRY_ELIGIBLE_STATUSES)
    retry_eligibility_reason = (
        "transient_non_accepted_send_outcome"
        if retry_eligible
        else ("no_order_send_attempt" if not order_sent else "non_transient_non_accepted_send_outcome")
    )
    return {
        "retry_eligible": retry_eligible,
        "retry_attempted_count": 0,
        "retry_policy": "bounded_single_retry_execution_policy_for_requote_price_changed_price_off",
        "retry_policy_truth": "retry_not_attempted",
        "retry_eligibility_reason": retry_eligibility_reason,
        "retry_blocked_reason": "",
        "retry_final_outcome_status": status if status else "unknown",
    }


def _safe_positive_finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0.0:
        return None
    return numeric


def _resolve_broker_retry_price(
    *,
    symbol: str,
    decision: str,
    mt5_module: Any | None = None,
) -> tuple[float | None, str]:
    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return None, "broker_price_refresh_mt5_module_unavailable"

    symbol_info_tick = getattr(mt5, "symbol_info_tick", None)
    if not callable(symbol_info_tick):
        return None, "broker_price_refresh_symbol_info_tick_unavailable"

    initialize = getattr(mt5, "initialize", None)
    shutdown = getattr(mt5, "shutdown", None)
    initialized = False
    try:
        if callable(initialize):
            if not bool(initialize()):
                return None, "broker_price_refresh_mt5_initialize_failed"
            initialized = True
        tick = symbol_info_tick(symbol)
    except Exception:
        return None, "broker_price_refresh_tick_fetch_failed"
    finally:
        if initialized and callable(shutdown):
            shutdown()

    if tick is None:
        return None, "broker_price_refresh_tick_unavailable"

    ask_raw = tick.get("ask") if isinstance(tick, dict) else getattr(tick, "ask", None)
    bid_raw = tick.get("bid") if isinstance(tick, dict) else getattr(tick, "bid", None)
    ask = _safe_positive_finite_float(ask_raw)
    bid = _safe_positive_finite_float(bid_raw)
    if ask is None or bid is None:
        return None, "broker_price_refresh_tick_sides_invalid"
    if ask < bid:
        return None, "broker_price_refresh_tick_crossed"
    if decision == "BUY":
        return ask, ""
    if decision == "SELL":
        return bid, ""
    return None, "broker_price_refresh_decision_not_trade_side"


def _resolve_exit_close_target_from_broker_positions(
    *,
    symbol: str,
    position_id: int | None = None,
    mt5_module: Any | None = None,
) -> dict[str, Any]:
    fail_closed = {
        "target_resolved": False,
        "fail_closed_reason": "",
        "position_lookup_source": "positions_get",
        "matched_symbol_position_count": 0,
        "position_ticket": None,
        "position_symbol": None,
        "position_side": None,
        "position_volume": None,
        "close_order_side": None,
    }
    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_module_unavailable"}

    initialized = False
    try:
        initialize = getattr(mt5, "initialize", None)
        if not callable(initialize) or not bool(initialize()):
            return {**fail_closed, "fail_closed_reason": "mt5_initialize_failed"}
        initialized = True
        positions_get = getattr(mt5, "positions_get", None)
        if not callable(positions_get):
            return {**fail_closed, "fail_closed_reason": "mt5_positions_get_unavailable"}
        positions_result = positions_get()
        if positions_result is None:
            return {**fail_closed, "fail_closed_reason": "mt5_positions_get_unavailable"}
        try:
            positions = list(positions_result)
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_positions_unreadable"}

        matching_symbol_positions = [
            p for p in positions if str(getattr(p, "symbol", "")) == str(symbol)
        ]
        if len(matching_symbol_positions) == 0:
            return {**fail_closed, "fail_closed_reason": "no_symbol_position_to_close"}

        if position_id is not None:
            # Explicit position_id provided: resolve only by exact broker ticket match.
            ticket_matched = [
                p
                for p in matching_symbol_positions
                if int(getattr(p, "ticket", -1)) == position_id
            ]
            if len(ticket_matched) != 1:
                return {
                    **fail_closed,
                    "matched_symbol_position_count": len(matching_symbol_positions),
                    "fail_closed_reason": "position_id_not_found_among_broker_positions",
                }
            position = ticket_matched[0]
        else:
            # No position_id: require exactly one symbol-matched position or fail closed.
            if len(matching_symbol_positions) != 1:
                return {
                    **fail_closed,
                    "matched_symbol_position_count": len(matching_symbol_positions),
                    "fail_closed_reason": "ambiguous_symbol_positions_to_close",
                }
            position = matching_symbol_positions[0]
        try:
            position_ticket = int(getattr(position, "ticket", None))
        except Exception:
            position_ticket = None
        if position_ticket is None or position_ticket <= 0:
            return {**fail_closed, "fail_closed_reason": "position_ticket_unavailable_or_unreadable"}
        position_side = _normalize_mt5_position_side(
            mt5_module=mt5,
            position_type=getattr(position, "type", None),
        )
        if position_side not in {"BUY", "SELL"}:
            return {**fail_closed, "fail_closed_reason": "position_side_unavailable_or_unreadable"}
        position_volume = _safe_positive_finite_float(getattr(position, "volume", None))
        if position_volume is None:
            return {**fail_closed, "fail_closed_reason": "position_volume_unavailable_or_invalid"}
        close_order_side = "SELL" if position_side == "BUY" else "BUY"
        return {
            **fail_closed,
            "target_resolved": True,
            "fail_closed_reason": "",
            "matched_symbol_position_count": 1,
            "position_ticket": position_ticket,
            "position_symbol": str(getattr(position, "symbol", "")),
            "position_side": position_side,
            "position_volume": position_volume,
            "close_order_side": close_order_side,
        }
    except Exception:
        return {**fail_closed, "fail_closed_reason": "exit_close_target_resolution_unavailable"}
    finally:
        if initialized:
            shutdown = getattr(mt5, "shutdown", None)
            if callable(shutdown):
                shutdown()


def _verify_exit_close_position_disappearance(
    *,
    symbol: str,
    position_ticket: int,
    mt5_module: Any | None = None,
) -> dict[str, Any]:
    fail_closed = {
        "confirmation": "unconfirmed",
        "broker_state_outcome": "exit_send_position_unreconciled",
        "fail_closed_reason": "",
        "position_lookup_source": "positions_get",
        "position_ticket": int(position_ticket or 0),
        "position_present": None,
        "matched_position_count": 0,
    }
    if int(position_ticket or 0) <= 0:
        return {**fail_closed, "fail_closed_reason": "invalid_position_ticket"}
    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_module_unavailable"}

    initialized = False
    try:
        initialize = getattr(mt5, "initialize", None)
        if not callable(initialize) or not bool(initialize()):
            return {**fail_closed, "fail_closed_reason": "mt5_initialize_failed"}
        initialized = True
        positions_get = getattr(mt5, "positions_get", None)
        if not callable(positions_get):
            return {**fail_closed, "fail_closed_reason": "mt5_positions_get_unavailable"}
        positions_result = positions_get()
        if positions_result is None:
            return {**fail_closed, "fail_closed_reason": "mt5_positions_get_unavailable"}
        try:
            positions = list(positions_result)
        except Exception:
            return {**fail_closed, "fail_closed_reason": "mt5_positions_unreadable"}
        matched_count = 0
        for position in positions:
            if str(getattr(position, "symbol", "")) != str(symbol):
                continue
            linkage_values: list[int] = []
            for field_name in ("ticket", "identifier"):
                field_value = getattr(position, field_name, None)
                if field_value is None:
                    continue
                try:
                    linkage_values.append(int(field_value))
                except Exception:
                    continue
            if int(position_ticket) in linkage_values:
                matched_count += 1
        if matched_count == 0:
            return {
                **fail_closed,
                "confirmation": "confirmed",
                "broker_state_outcome": "exit_send_position_closed_confirmed",
                "fail_closed_reason": "",
                "position_present": False,
                "matched_position_count": 0,
            }
        return {
            **fail_closed,
            "position_present": True,
            "matched_position_count": matched_count,
            "fail_closed_reason": "position_still_present_after_close_send",
        }
    except Exception:
        return {**fail_closed, "fail_closed_reason": "exit_close_verification_unavailable"}
    finally:
        if initialized:
            shutdown = getattr(mt5, "shutdown", None)
            if callable(shutdown):
                shutdown()


def _run_controlled_mt5_live_execution(
    *,
    memory_root: str,
    mode: str,
    symbol: str,
    decision: str,
    confidence: float,
    bars: list[dict[str, Any]],
    live_execution_enabled: bool,
    live_order_volume: float,
    controlled_mt5_readiness: dict[str, Any],
    readiness_chain: dict[str, Any],
    quarantine_state: dict[str, Any],
    risk_state_valid: bool,
    fail_safe_state_clear: bool,
    trade_tags: dict[str, Any] | None = None,
    signal_lifecycle: dict[str, Any] | None = None,
    mt5_module: Any | None = None,
    position_id: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    persistent_state = _load_mt5_controlled_execution_state(memory_root)
    lifecycle_evaluation = _evaluate_signal_lifecycle(signal_lifecycle=signal_lifecycle)
    pre_trade_checks = [
        {"name": "live_execution_enabled", "passed": bool(live_execution_enabled)},
        {
            "name": "mt5_readiness_valid",
            "passed": bool(readiness_chain.get("all_checks_passed", False))
            and bool(controlled_mt5_readiness.get("ready_for_controlled_usage", False)),
        },
        {
            "name": "readiness_allows_live_order",
            "passed": _readiness_allows_live_order(controlled_mt5_readiness),
        },
        {"name": "symbol_valid", "passed": bool(controlled_mt5_readiness.get("symbol_validity", False))},
        {
            "name": "account_trading_permission_valid",
            "passed": bool(controlled_mt5_readiness.get("account_trading_permission", False))
            and bool(controlled_mt5_readiness.get("account_readiness", False)),
        },
        {
            "name": "data_freshness_valid",
            "passed": bool(controlled_mt5_readiness.get("data_freshness", False))
            and bool(controlled_mt5_readiness.get("tick_data_freshness", False)),
        },
        {"name": "risk_state_valid", "passed": bool(risk_state_valid)},
        {"name": "fail_safe_state_clear", "passed": bool(fail_safe_state_clear)},
        {
            "name": "quarantine_clear",
            "passed": not bool(quarantine_state.get("quarantine_required", False)),
        },
        {
            "name": "auto_stop_inactive",
            "passed": not bool(persistent_state.get("auto_stop_active", False)),
        },
        {
            "name": "signal_freshness_valid",
            "passed": bool(lifecycle_evaluation.get("signal_fresh", True)),
        },
    ]
    failed_checks = sorted(check["name"] for check in pre_trade_checks if not bool(check["passed"]))
    entry_decision = {
        "entry_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "mode": mode,
        "symbol": symbol,
        "decision": decision,
        "confidence": float(confidence),
        "eligible_for_order": mode == "live" and decision in {"BUY", "SELL"},
        "signal_lifecycle": lifecycle_evaluation,
    }

    order_request: dict[str, Any] = {}
    order_result: dict[str, Any] = {}
    retry_metadata: dict[str, Any] = _build_retry_metadata(order_result=order_result)
    rejection_reasons: list[str] = []
    rollback_reasons: list[str] = []
    stop_loss_take_profit = {"stop_loss": None, "take_profit": None}
    exit_branch_active = False
    exit_close_target: dict[str, Any] = {}
    exit_close_verification: dict[str, Any] = {}

    if mode == "replay" and decision in {"BUY", "SELL"}:
        last_price = float(bars[-1]["close"]) if bars else 0.0
        sl_offset = 2.0
        tp_offset = 4.0
        stop_loss = round(last_price - sl_offset, 5) if decision == "BUY" else round(last_price + sl_offset, 5)
        take_profit = round(last_price + tp_offset, 5) if decision == "BUY" else round(last_price - tp_offset, 5)
        stop_loss_take_profit = {"stop_loss": stop_loss, "take_profit": take_profit}
        order_request = {
            "action": "deal",
            "symbol": symbol,
            "volume": float(live_order_volume),
            "type": decision,
            "price": last_price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "comment": "replay_simulated_execution",
        }
        order_result = {
            "status": "accepted",
            "order_sent": False,
            "fill_price": last_price,
            "requested_price": last_price,
            "order_id": 0,
            "error_reason": "",
            "simulated": True,
        }
    elif mode != "live":
        rejection_reasons = ["non_live_mode"]
    elif decision not in {"BUY", "SELL"}:
        if failed_checks:
            rejection_reasons = [f"pretrade_check_failed:{name}" for name in failed_checks]
            if "signal_freshness_valid" in failed_checks:
                rejection_reasons.extend(
                    [
                        str(reason)
                        for reason in lifecycle_evaluation.get("signal_lifecycle_refusal_reasons", [])
                        if str(reason).strip()
                    ]
                )
        else:
            exit_close_target = _resolve_exit_close_target_from_broker_positions(
                symbol=symbol,
                position_id=position_id,
                mt5_module=mt5_module,
            )
            if not bool(exit_close_target.get("target_resolved", False)):
                exit_target_fail_closed_reason = str(
                    exit_close_target.get("fail_closed_reason") or "unavailable"
                )
                if exit_target_fail_closed_reason != "no_symbol_position_to_close":
                    exit_branch_active = True
                rejection_reasons = [
                    f"exit_close_target_resolution_failed:{exit_target_fail_closed_reason}"
                ]
            else:
                exit_branch_active = True
                close_order_side = str(exit_close_target.get("close_order_side") or "")
                close_price, close_price_failure_reason = _resolve_broker_retry_price(
                    symbol=symbol,
                    decision=close_order_side,
                    mt5_module=mt5_module,
                )
                if close_price is None:
                    rejection_reasons = [
                        f"exit_close_price_unavailable:{str(close_price_failure_reason or 'broker_price_unavailable')}"
                    ]
                else:
                    order_request = {
                        "action": "deal",
                        "symbol": symbol,
                        "volume": float(exit_close_target.get("position_volume", 0.0)),
                        "type": close_order_side,
                        "price": round(float(close_price), 5),
                        "deviation": 20,
                        "position": int(exit_close_target.get("position_ticket", 0) or 0),
                        "comment": "governed_controlled_exit_execution",
                    }
                    order_result = _place_controlled_mt5_order(
                        order_request=order_request,
                        mt5_module=mt5_module,
                    )
                    retry_metadata = _build_retry_metadata(order_result=order_result)
                    if order_result.get("status") != "accepted":
                        rejection_reasons = [str(order_result.get("error_reason") or "exit_close_order_send_refused")]
    elif failed_checks:
        rejection_reasons = [f"pretrade_check_failed:{name}" for name in failed_checks]
        if "signal_freshness_valid" in failed_checks:
            rejection_reasons.extend(
                [
                    str(reason)
                    for reason in lifecycle_evaluation.get("signal_lifecycle_refusal_reasons", [])
                    if str(reason).strip()
                ]
            )
    else:
        last_price = float(bars[-1]["close"]) if bars else 0.0
        sl_offset = 2.0
        tp_offset = 4.0
        stop_loss = round(last_price - sl_offset, 5) if decision == "BUY" else round(last_price + sl_offset, 5)
        take_profit = round(last_price + tp_offset, 5) if decision == "BUY" else round(last_price - tp_offset, 5)
        stop_loss_take_profit = {"stop_loss": stop_loss, "take_profit": take_profit}
        order_request = {
            "action": "deal",
            "symbol": symbol,
            "volume": float(live_order_volume),
            "type": decision,
            "price": last_price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "comment": "governed_controlled_execution",
        }
        order_result = _place_controlled_mt5_order(order_request=order_request, mt5_module=mt5_module)
        retry_metadata = _build_retry_metadata(order_result=order_result)
        first_status = str(order_result.get("status") or "").strip().lower()
        first_order_sent = bool(order_result.get("order_sent", False))
        retry_attempted_count = 0
        retry_blocked_reason = ""
        retry_policy_truth = "retry_not_attempted"
        if first_status != "accepted":
            retry_guard_checks = [
                {"name": "live_mode", "passed": mode == "live"},
                {"name": "decision_trade_side", "passed": decision in {"BUY", "SELL"}},
                {"name": "initial_pretrade_checks_passed", "passed": not failed_checks},
                {"name": "first_order_send_occurred", "passed": first_order_sent},
                {
                    "name": "first_non_accepted_non_partial",
                    "passed": first_status not in {"accepted", "partial"},
                },
                {"name": "retry_attempted_count_zero", "passed": retry_attempted_count == 0},
                {"name": "auto_stop_inactive", "passed": not bool(persistent_state.get("auto_stop_active", False))},
                {
                    "name": "readiness_explicit_live_authorized",
                    "passed": _readiness_allows_live_order(controlled_mt5_readiness),
                },
                {
                    "name": "first_status_in_retry_slice",
                    "passed": first_status in BOUNDED_SINGLE_RETRY_EXECUTION_STATUSES,
                },
            ]
            refreshed_price = None
            refreshed_price_failure_reason = ""
            if first_status in BOUNDED_SINGLE_RETRY_EXECUTION_STATUSES:
                refreshed_price, refreshed_price_failure_reason = _resolve_broker_retry_price(
                    symbol=symbol,
                    decision=decision,
                    mt5_module=mt5_module,
                )
            refreshed_price_valid = (
                refreshed_price is not None
                if first_status in BOUNDED_SINGLE_RETRY_EXECUTION_STATUSES
                else True
            )
            retry_guard_checks.append(
                {"name": "refreshed_price_valid", "passed": bool(refreshed_price_valid)}
            )
            failed_retry_guards = [check["name"] for check in retry_guard_checks if not bool(check["passed"])]
            if (
                first_status in BOUNDED_SINGLE_RETRY_EXECUTION_STATUSES
                and not refreshed_price_valid
                and refreshed_price_failure_reason
            ):
                failed_retry_guards.append(str(refreshed_price_failure_reason))
            if not failed_retry_guards and retry_metadata.get("retry_eligible", False):
                time.sleep(BOUNDED_SINGLE_RETRY_DELAY_SECONDS)
                retry_request = {**order_request, "price": round(float(refreshed_price), 5)}
                order_result = _place_controlled_mt5_order(order_request=retry_request, mt5_module=mt5_module)
                retry_attempted_count = 1
                retry_policy_truth = "retry_attempted_bounded_single_retry_execution_policy"
            else:
                retry_blocked_reason = (
                    ";".join(failed_retry_guards)
                    if failed_retry_guards
                    else str(retry_metadata.get("retry_eligibility_reason") or "retry_not_eligible")
                )
                retry_policy_truth = "retry_not_attempted_fail_closed_guard_blocked"
            retry_metadata = {
                **retry_metadata,
                "retry_attempted_count": int(retry_attempted_count),
                "retry_policy_truth": retry_policy_truth,
                "retry_blocked_reason": str(retry_blocked_reason),
                "retry_final_outcome_status": str(order_result.get("status") or "unknown"),
            }
        else:
            retry_metadata = {
                **retry_metadata,
                "retry_policy_truth": "retry_not_attempted_accepted_on_first_send",
                "retry_final_outcome_status": "accepted",
            }
        if order_result.get("status") != "accepted":
            rejection_reasons = [str(order_result.get("error_reason") or "order_send_refused")]

    if rejection_reasons:
        rollback_reasons = sorted(set(rejection_reasons))
        order_sent = bool(order_result.get("order_sent", False))
        if (
            int(retry_metadata.get("retry_attempted_count", 0)) == 0
            and not str(retry_metadata.get("retry_blocked_reason", "")).strip()
        ):
            retry_metadata = {
                **retry_metadata,
                "retry_policy_truth": "retry_not_attempted_fail_closed_guard_blocked",
                "retry_blocked_reason": str(
                    retry_metadata.get("retry_eligibility_reason") or "retry_not_eligible"
                ),
                "retry_final_outcome_status": str(order_result.get("status") or "refused"),
            }
        order_result = {
            **order_result,
            "status": order_result.get("status", "refused"),
            "order_sent": order_sent,
            "rejection_reason": rollback_reasons[0],
            "broker_state_confirmation": "unconfirmed" if order_sent else "not_applicable",
            "broker_state_outcome": (
                "unconfirmed_non_accepted_send_outcome" if order_sent else "no_order_send_attempt"
            ),
            **retry_metadata,
        }
    else:
        if bool(order_result.get("simulated", False)):
            order_result = {
                **order_result,
                "rejection_reason": "",
                "broker_state_confirmation": "simulated",
                "broker_state_outcome": "replay_simulated_accepted",
                **retry_metadata,
            }
        elif exit_branch_active:
            sent_position_ticket = int(exit_close_target.get("position_ticket", 0) or 0)
            exit_close_verification = _verify_exit_close_position_disappearance(
                symbol=symbol,
                position_ticket=sent_position_ticket,
                mt5_module=mt5_module,
            )
            if (
                sent_position_ticket > 0
                and exit_close_verification.get("confirmation") != "confirmed"
            ):
                time.sleep(BOUNDED_DELAYED_BROKER_RECHECK_SECONDS)
                delayed_exit_close_verification = _verify_exit_close_position_disappearance(
                    symbol=symbol,
                    position_ticket=sent_position_ticket,
                    mt5_module=mt5_module,
                )
                if delayed_exit_close_verification.get("confirmation") == "confirmed":
                    exit_close_verification = delayed_exit_close_verification
            order_result = {
                **order_result,
                "status": "accepted",
                "order_sent": True,
                "rejection_reason": "",
                "broker_state_confirmation": exit_close_verification["confirmation"],
                "broker_state_outcome": exit_close_verification["broker_state_outcome"],
                "broker_exit_verification": exit_close_verification,
                **retry_metadata,
            }
        else:
            sent_order_id = int(order_result.get("order_id", 0) or 0)
            broker_position_verification = _verify_accepted_send_position_linkage(
                sent_order_id=sent_order_id,
                symbol=symbol,
                side=decision,
                volume=float(order_request.get("volume", 0.0)),
                mt5_module=mt5_module,
            )
            if (
                sent_order_id > 0
                and broker_position_verification.get("confirmation") != "confirmed"
            ):
                time.sleep(BOUNDED_DELAYED_BROKER_RECHECK_SECONDS)
                delayed_broker_position_verification = _verify_accepted_send_position_linkage(
                    sent_order_id=sent_order_id,
                    symbol=symbol,
                    side=decision,
                    volume=float(order_request.get("volume", 0.0)),
                    mt5_module=mt5_module,
                )
                if delayed_broker_position_verification.get("confirmation") == "confirmed":
                    broker_position_verification = delayed_broker_position_verification
            order_result = {
                **order_result,
                "status": "accepted",
                "order_sent": True,
                "rejection_reason": "",
                "broker_state_confirmation": broker_position_verification["confirmation"],
                "broker_state_outcome": broker_position_verification["broker_state_outcome"],
                "broker_position_verification": broker_position_verification,
                **retry_metadata,
            }

    is_live_trade_attempt = mode == "live" and decision in {"BUY", "SELL"}
    is_failure_state = is_live_trade_attempt and order_result.get("status") != "accepted"
    consecutive_failed = int(persistent_state.get("consecutive_failed_executions", 0))
    if is_failure_state:
        consecutive_failed += 1
    elif is_live_trade_attempt:
        consecutive_failed = 0
    auto_stop_active = bool(persistent_state.get("auto_stop_active", False)) or consecutive_failed >= 3
    if consecutive_failed >= 3:
        rollback_reasons = sorted(set(rollback_reasons + ["auto_stop_triggered_repeated_failures"]))

    order_status = str(order_result.get("status") or "")
    if order_status == "accepted":
        if exit_branch_active:
            exit_close_confirmed = (
                order_result.get("broker_state_confirmation") == "confirmed"
                and order_result.get("broker_state_outcome") == "exit_send_position_closed_confirmed"
            )
            if exit_close_confirmed:
                open_position_state = {
                    "status": "flat",
                    "position_id": None,
                    "symbol": symbol,
                    "side": "NONE",
                    "entry_price": None,
                    "stop_loss": None,
                    "take_profit": None,
                    "broker_position_confirmation": "confirmed",
                    "position_state_outcome": "broker_confirmed_closed_position",
                }
                exit_decision = {"decision": "no_position_exit", "reason": "broker_confirmed_closed_position"}
            else:
                open_position_state = {
                    "status": "open",
                    "position_id": int(exit_close_target.get("position_ticket", 0) or 0) or None,
                    "symbol": str(exit_close_target.get("position_symbol") or symbol),
                    "side": str(exit_close_target.get("position_side") or "UNKNOWN"),
                    "entry_price": None,
                    "stop_loss": None,
                    "take_profit": None,
                    "broker_position_confirmation": "unconfirmed",
                    "position_state_outcome": "exit_close_unresolved_open_position",
                }
                exit_decision = {
                    "decision": "exit_required_unresolved_open_position",
                    "reason": "exit_close_unresolved_open_position",
                }
        else:
            broker_position_verification = dict(order_result.get("broker_position_verification") or {})
            broker_position_confirmed = (
                order_result.get("broker_state_confirmation") == "confirmed"
                and order_result.get("broker_state_outcome") == "accepted_send_position_confirmed"
            )
            open_position_state = {
                "status": "open",
                "position_id": (
                    int(broker_position_verification.get("matched_position_ticket"))
                    if broker_position_verification.get("matched_position_ticket") is not None
                    else int(order_result.get("order_id", 0) or 0)
                ),
                "symbol": (
                    str(broker_position_verification.get("matched_symbol"))
                    if broker_position_verification.get("matched_symbol")
                    else symbol
                ),
                "side": (
                    str(broker_position_verification.get("matched_side"))
                    if broker_position_verification.get("matched_side")
                    else decision
                ),
                "entry_price": float(order_request.get("price", 0.0)),
                "stop_loss": stop_loss_take_profit["stop_loss"],
                "take_profit": stop_loss_take_profit["take_profit"],
                "broker_position_confirmation": "confirmed" if broker_position_confirmed else "unconfirmed",
                "position_state_outcome": (
                    "broker_confirmed_open_position"
                    if broker_position_confirmed
                    else "assumed_open_from_accepted_send_unreconciled"
                ),
            }
            exit_decision = {
                "decision": "hold_open_position",
                "reason": (
                    "broker_confirmed_open_position"
                    if broker_position_confirmed
                    else "assumed_open_position_from_accepted_send_unreconciled"
                ),
            }
    elif order_status == "partial":
        sent_order_id = int(order_result.get("order_id", 0) or 0)
        partial_quantity_verification = _verify_partial_send_deal_quantity(
            sent_order_id=sent_order_id,
            symbol=symbol,
            side=decision,
            requested_volume=float(order_result.get("requested_volume", order_request.get("volume", 0.0))),
            mt5_module=mt5_module,
        )
        if sent_order_id > 0 and partial_quantity_verification.get("confirmation") != "confirmed":
            time.sleep(BOUNDED_DELAYED_BROKER_RECHECK_SECONDS)
            delayed_partial_quantity_verification = _verify_partial_send_deal_quantity(
                sent_order_id=sent_order_id,
                symbol=symbol,
                side=decision,
                requested_volume=float(order_result.get("requested_volume", order_request.get("volume", 0.0))),
                mt5_module=mt5_module,
            )
            if delayed_partial_quantity_verification.get("confirmation") == "confirmed":
                partial_quantity_verification = delayed_partial_quantity_verification
        if partial_quantity_verification.get("confirmation") == "confirmed":
            order_result = {
                **order_result,
                "filled_volume": partial_quantity_verification.get("filled_volume"),
                "remaining_volume": partial_quantity_verification.get("remaining_volume"),
                "partial_outcome_quantity_truth": partial_quantity_verification.get(
                    "partial_outcome_quantity_truth",
                    "unresolved",
                ),
            }
        else:
            order_result = {
                **order_result,
                "filled_volume": None,
                "remaining_volume": None,
                "partial_outcome_quantity_truth": "unresolved",
            }
        order_result = {
            **order_result,
            "partial_quantity_verification": partial_quantity_verification,
        }
        open_position_state = {
            "status": "partial_exposure_unresolved",
            "position_id": None,
            "symbol": symbol,
            "side": decision,
            "entry_price": None,
            "stop_loss": stop_loss_take_profit["stop_loss"],
            "take_profit": stop_loss_take_profit["take_profit"],
            "broker_position_confirmation": "unconfirmed",
            "position_state_outcome": "partial_fill_exposure_unresolved",
            "requested_volume": float(order_result.get("requested_volume", order_request.get("volume", 0.0))),
            "filled_volume": order_result.get("filled_volume"),
            "remaining_volume": order_result.get("remaining_volume"),
            "partial_outcome_quantity_truth": str(
                order_result.get("partial_outcome_quantity_truth", "unresolved")
            ),
        }
        exit_decision = {
            "decision": "defer_exit_partial_exposure_unresolved",
            "reason": "partial_fill_exposure_unresolved",
        }
    else:
        if exit_branch_active:
            open_position_state = {
                "status": "open",
                "position_id": int(exit_close_target.get("position_ticket", 0) or 0) or None,
                "symbol": str(exit_close_target.get("position_symbol") or symbol),
                "side": str(exit_close_target.get("position_side") or "UNKNOWN"),
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "broker_position_confirmation": "unconfirmed",
                "position_state_outcome": "exit_close_unresolved_open_position",
            }
            exit_decision = {
                "decision": "exit_required_unresolved_open_position",
                "reason": "exit_close_unresolved_open_position",
            }
        else:
            open_position_state = {
                "status": "flat",
                "position_id": None,
                "symbol": symbol,
                "side": "NONE",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "broker_position_confirmation": "not_applicable",
                "position_state_outcome": "no_open_position_state",
            }
            exit_decision = {"decision": "no_position_exit", "reason": "no_open_position"}

    pnl_position_open = (
        True
        if open_position_state["status"] == "open"
        else None if open_position_state["status"] == "partial_exposure_unresolved" else False
    )
    pnl_snapshot = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "symbol": symbol,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "position_open": pnl_position_open,
        "position_open_truth": (
            (
                "broker_confirmed_open_position"
                if open_position_state.get("broker_position_confirmation") == "confirmed"
                else "assumed_from_accepted_send_unreconciled"
            )
            if open_position_state["status"] == "open"
            else (
                "partial_fill_exposure_unresolved"
                if open_position_state["status"] == "partial_exposure_unresolved"
                else "not_applicable"
            )
        ),
    }
    failure_classification = (
        _classify_mt5_execution_failure(rollback_reasons) if rollback_reasons else "none"
    )
    replay_feedback_hook = {
        "enabled": True,
        "hook_status": "queued_for_feedback",
        "mistake_classification": failure_classification,
    }

    controlled_execution_artifact = {
        "entry_decision": entry_decision,
        "pre_trade_checks": {
            "checks": pre_trade_checks,
            "failed_checks": failed_checks,
            "all_checks_passed": not failed_checks,
        },
        "order_request": order_request,
        "order_result": order_result,
        "stop_loss_take_profit": stop_loss_take_profit,
        "rejection_reason": rollback_reasons[0] if rollback_reasons else "",
        "rollback_refusal_reasons": rollback_reasons,
        "trade_tags": dict(trade_tags or {}),
        "refusal_tags": dict(trade_tags or {}) if rollback_reasons else {},
        "failure_tags": dict(trade_tags or {}) if is_failure_state else {},
        "open_position_state": open_position_state,
        "exit_decision": exit_decision,
        "pnl_snapshot": pnl_snapshot,
        "mistake_failure_classification": failure_classification,
        "replay_feedback_hook": replay_feedback_hook,
        "auto_stop_active": auto_stop_active,
        "signal_lifecycle": lifecycle_evaluation,
    }

    updated_state = {
        "consecutive_failed_executions": consecutive_failed,
        "auto_stop_active": auto_stop_active,
        "last_failure_reasons": rollback_reasons,
        "total_execution_attempts": int(persistent_state.get("total_execution_attempts", 0))
        + (1 if is_live_trade_attempt else 0),
    }

    root = Path(memory_root)
    artifact_paths = {
        "execution_artifact_path": root / "mt5_controlled_execution_artifact.json",
        "execution_state_path": root / "mt5_controlled_execution_state.json",
        "execution_history_path": root / "mt5_controlled_execution_history.json",
    }
    write_json_atomic(artifact_paths["execution_artifact_path"], controlled_execution_artifact)
    write_json_atomic(artifact_paths["execution_state_path"], updated_state)
    history_path = artifact_paths["execution_history_path"]
    history: list[dict[str, Any]] = []
    if history_path.exists():
        try:
            loaded = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                history = loaded
        except Exception:
            history = []
    history.append(controlled_execution_artifact)
    write_json_atomic(history_path, history[-100:])

    return (
        {
            **controlled_execution_artifact,
            **{name: str(path) for name, path in artifact_paths.items()},
        },
        updated_state,
        {name: str(path) for name, path in artifact_paths.items()},
    )


def run_evolution_kernel(config: RuntimeConfig) -> dict[str, Any]:
    if not config.evolution_enabled:
        return {
            "enabled": False,
            "inspection": {},
            "gaps": [],
            "lifecycle": [],
            "status_counts": {
                "proposed": 0,
                "verified": 0,
                "promoted": 0,
                "rejected": 0,
                "archived": 0,
            },
        }

    if _is_replay_evaluation_step_memory_root(Path(config.memory_root)):
        return {
            "enabled": True,
            "inspection": {
                "skipped": True,
                "skip_reason": "replay_evaluation_step_isolation",
            },
            "gaps": [],
            "lifecycle": [],
            "status_counts": {
                "proposed": 0,
                "verified": 0,
                "promoted": 0,
                "rejected": 0,
                "archived": 0,
            },
        }

    project_root = Path.cwd()
    generated_registry_path = Path(config.generated_registry_path)
    evolution_registry = EvolutionRegistry(Path(config.evolution_registry_path))

    inspector = SelfInspector(
        project_root=project_root,
        generated_registry_path=generated_registry_path,
        evolution_registry_path=Path(config.evolution_registry_path),
    )
    inspection = inspector.inspect()
    gaps = GapDiscovery().discover(inspection)

    generator = CodeGenerator(Path(config.evolution_artifact_root))
    verifier = Verifier()
    guard = ArchitectureGuard(project_root)
    duplication = DuplicationAudit(project_root)
    promoter = Promoter(evolution_registry)

    lifecycle: list[dict[str, Any]] = []
    for gap in gaps[: config.evolution_max_proposals]:
        generated = generator.generate_proposal(gap)
        artifact_path = Path(generated["artifact_path"])
        proposal = generated["proposal"]

        duplicate_check = duplication.check_proposal(
            artifact_path=artifact_path,
            proposal=proposal,
            existing_registry_entries=evolution_registry.latest(limit=1000),
        )
        validation = verifier.verify(artifact_path, proposal)
        architecture_check = guard.evaluate(proposal, symbol=config.symbol)

        entry = evolution_registry.append_entry(
            gap=gap,
            artifact_path=str(artifact_path),
            artifact_type="code_proposal",
            status="proposed",
            validation=validation,
            duplicate_check={**duplicate_check, "architecture_check": architecture_check},
        )
        promoted = promoter.decide_status(
            entry_id=entry["entry_id"],
            verification=validation,
            duplicate_check=duplicate_check,
            architecture_check=architecture_check,
        )
        lifecycle.append(promoted)

        register_generated_artifact(
            registry_path=generated_registry_path,
            artifact_type="evolution_proposal",
            artifact_path=str(artifact_path),
            metadata={
                "gap_id": gap["gap_id"],
                "validation_passed": validation["passed"],
                "final_status": promoted["status"],
                "symbol": config.symbol,
            },
        )

    return {
        "enabled": True,
        "inspection": inspection,
        "gaps": gaps,
        "lifecycle": lifecycle,
        "status_counts": evolution_registry.count_by_status(),
    }


def _build_persistable_replay_evaluation_report(report: dict[str, Any]) -> dict[str, Any]:
    records = report.get("records")
    if (
        bool(report.get("replay_isolated", False))
        and isinstance(records, list)
        and len(records) > 1000
    ):
        persisted = dict(report)
        persisted.pop("records", None)
        persisted["persisted_record_count"] = len(records)
        persisted["persisted_records_omitted"] = True
        return persisted
    return report


def _build_compact_signal_payload(signal_payload: dict[str, Any]) -> dict[str, Any]:
    """Return reduced-detail signal payload for downstream consumers when configured."""
    compact = {
        "symbol": signal_payload.get("symbol", "XAUUSD"),
        "action": signal_payload.get("action", "WAIT"),
        "signal_score": signal_payload.get("signal_score", 0.0),
        "confidence": signal_payload.get("confidence", 0.0),
        "feature_contributors": signal_payload.get("feature_contributors", {}),
        "trade_tags": signal_payload.get("trade_tags", {}),
        "macro_state": signal_payload.get("macro_state", {}),
        "reasons": signal_payload.get("reasons", []),
        "blocked": signal_payload.get("blocked", False),
        "setup_classification": signal_payload.get("setup_classification", "observe"),
        "blocker_reasons": signal_payload.get("blocker_reasons", []),
        "memory_context": signal_payload.get("memory_context", {}),
        "rule_context": signal_payload.get("rule_context", {}),
        "schema_version": signal_payload.get("schema_version", "phase3.v1"),
        "consumer_hints": signal_payload.get("consumer_hints", {}),
        "advanced_modules": {
            "final_direction": signal_payload.get("advanced_modules", {}).get("final_direction", "WAIT"),
            "final_confidence": signal_payload.get("advanced_modules", {}).get("final_confidence", 0.0),
            "module_count": len(signal_payload.get("advanced_modules", {}).get("module_results", {})),
            "ready_count": sum(
                1
                for h in signal_payload.get("advanced_modules", {}).get("module_health", {}).values()
                if bool(h.get("ready", False))
            ),
        },
        "generated_code_visibility": signal_payload.get("generated_code_visibility", {}),
        "capital_guard": signal_payload.get("capital_guard", {}),
        "strategy_promotion_policy": signal_payload.get("strategy_promotion_policy", {}),
        "live_learning_loop": signal_payload.get("live_learning_loop", {}),
        "evolution_kernel": {
            "enabled": signal_payload.get("evolution_kernel", {}).get("enabled", False),
            "gap_count": signal_payload.get("evolution_kernel", {}).get("gap_count", 0),
        },
    }
    return compact


def _build_entry_exit_decision_contract(
    *,
    decision: str,
    effective_signal_confidence: float,
    bars: list[dict[str, Any]],
    reasons: list[str],
    controlled_execution: dict[str, Any],
) -> dict[str, Any]:
    action_map = {"BUY": "LONG_ENTRY", "SELL": "SHORT_ENTRY", "WAIT": "NO_TRADE"}
    action = action_map.get(str(decision), "NO_TRADE")
    last_price = float(bars[-1].get("close", 0.0)) if bars else 0.0
    stop_loss_take_profit = dict(controlled_execution.get("stop_loss_take_profit", {}))
    stop_loss = stop_loss_take_profit.get("stop_loss")
    take_profit = stop_loss_take_profit.get("take_profit")
    rollback_reasons = list(controlled_execution.get("rollback_refusal_reasons", []))
    order_result = dict(controlled_execution.get("order_result", {}))
    open_position_state = dict(controlled_execution.get("open_position_state", {}))
    exit_decision = dict(controlled_execution.get("exit_decision", {}))

    if (
        decision not in {"BUY", "SELL"}
        and str(open_position_state.get("status", "")) in {"open", "partial_exposure_unresolved"}
    ):
        action = "EXIT"

    invalidation_reason = (
        "; ".join(str(r) for r in rollback_reasons if str(r).strip())
        if rollback_reasons
        else ("; ".join(str(r) for r in reasons if str(r).strip()) if action == "NO_TRADE" else "")
    )

    decision_contract = {
        "action": action,
        "entry_price": None,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "exit_rule": None,
        "invalidation_reason": invalidation_reason,
        "confidence": float(effective_signal_confidence),
        "why_this_trade": "",
        "why_not_trade": "",
    }

    if action in {"LONG_ENTRY", "SHORT_ENTRY"}:
        entry_price = order_result.get("fill_price")
        if entry_price is None:
            entry_price = order_result.get("requested_price")
        if entry_price is None:
            entry_price = last_price
        decision_contract["entry_price"] = float(entry_price)
        decision_contract["why_this_trade"] = (
            f"{action} because final decision={decision} and entry gate accepted signal."
        )
        decision_contract.pop("exit_rule", None)
    elif action == "EXIT":
        decision_contract["entry_price"] = open_position_state.get("entry_price")
        current_price_raw = bars[-1].get("close") if bars else None
        current_price: float | None
        try:
            current_price = float(current_price_raw) if current_price_raw is not None else None
        except (TypeError, ValueError):
            current_price = None

        side = str(open_position_state.get("side", "")).upper()
        position_status = str(open_position_state.get("status", "")).lower()

        sl_value: float | None
        tp_value: float | None
        try:
            sl_source = (
                open_position_state.get("stop_loss")
                if open_position_state.get("stop_loss") is not None
                else stop_loss
            )
            sl_value = float(sl_source) if sl_source is not None else None
        except (TypeError, ValueError):
            sl_value = None
        try:
            tp_source = (
                open_position_state.get("take_profit")
                if open_position_state.get("take_profit") is not None
                else take_profit
            )
            tp_value = float(tp_source) if tp_source is not None else None
        except (TypeError, ValueError):
            tp_value = None

        derived_exit_rule = ""
        if position_status == "partial_exposure_unresolved":
            derived_exit_rule = (
                "partial_exposure_unresolved_manage_exit: await_quantity_reconciliation_before_new_entry"
            )
        elif (
            current_price is not None
            and sl_value is not None
            and (
                (side in {"BUY", "LONG"} and current_price <= sl_value)
                or (side in {"SELL", "SHORT"} and current_price >= sl_value)
            )
        ):
            derived_exit_rule = (
                f"stop_loss_breached_exit: side={side or 'UNKNOWN'} price={current_price:.5f} stop_loss={sl_value:.5f}"
            )
        elif (
            current_price is not None
            and tp_value is not None
            and (
                (side in {"BUY", "LONG"} and current_price >= tp_value)
                or (side in {"SELL", "SHORT"} and current_price <= tp_value)
            )
        ):
            derived_exit_rule = (
                f"take_profit_reached_exit: side={side or 'UNKNOWN'} price={current_price:.5f} take_profit={tp_value:.5f}"
            )
        elif position_status == "open" and (
            side in {"BUY", "SELL", "LONG", "SHORT"}
            or current_price is not None
            or sl_value is not None
            or tp_value is not None
        ):
            derived_exit_rule = (
                "open_position_management_exit: monitor_until_stop_loss_or_take_profit_trigger"
            )

        decision_contract["exit_rule"] = (
            derived_exit_rule
            if derived_exit_rule
            else str(exit_decision.get("reason", "exit_required_open_position"))
        )
        decision_contract["take_profit"] = open_position_state.get("take_profit")
        decision_contract["stop_loss"] = open_position_state.get("stop_loss")
        decision_contract["why_not_trade"] = (
            "No new entry because an open/partial position exists; explicit exit rule provided."
        )
    else:
        decision_contract["entry_price"] = None
        decision_contract["stop_loss"] = None
        decision_contract["take_profit"] = None
        decision_contract["why_not_trade"] = (
            f"NO_TRADE due to blocking/refusal: {invalidation_reason}" if invalidation_reason else "NO_TRADE."
        )
        decision_contract.pop("exit_rule", None)

    if action in {"LONG_ENTRY", "SHORT_ENTRY"}:
        decision_contract.pop("why_not_trade", None)
    elif action == "EXIT":
        decision_contract.pop("why_this_trade", None)
        decision_contract.pop("take_profit", None)
    else:
        decision_contract.pop("why_this_trade", None)

    return decision_contract


def run_pipeline(config: RuntimeConfig) -> dict[str, Any]:
    validate_runtime_config(config)
    sample_path = Path(config.sample_path)
    ensure_sample_data(sample_path)

    store = PatternStore(PatternStoreConfig(root=config.memory_root))

    if config.mode == "replay":
        if config.replay_source == "csv":
            bars = load_bars_from_csv(Path(config.replay_csv_path), config.bars)
            data_source = "replay_csv"
        elif config.replay_source == "memory":
            bars = load_bars_from_memory(store, config.bars)
            data_source = "replay_memory"
        else:
            raise ValueError(f"Unsupported replay_source: {config.replay_source}")
        mt5_attempted = False
        controlled_mt5_readiness = _build_non_live_mt5_readiness(
            symbol=config.symbol,
            bars=bars,
            data_source=data_source,
        )
    else:
        adapter = MT5Adapter(
            MT5Config(
                symbol=config.symbol,
                timeframe=config.timeframe,
                bars=config.bars,
                csv_fallback_path=str(sample_path),
            )
        )
        bars = adapter.get_bars()
        controlled_mt5_readiness = adapter.get_controlled_readiness_state()
        data_source = "mt5_or_csv_fallback"
        mt5_attempted = True
    controlled_mt5_readiness_path = _persist_controlled_mt5_readiness(
        config.memory_root,
        controlled_mt5_readiness,
    )
    controlled_mt5_readiness = {
        **controlled_mt5_readiness,
        "artifact_path": controlled_mt5_readiness_path,
    }
    readiness_chain = _verify_mt5_readiness_chain(
        readiness=controlled_mt5_readiness,
        mode=config.mode,
    )
    quarantine_state = _build_mt5_quarantine_state(
        readiness=controlled_mt5_readiness,
        mode=config.mode,
        readiness_chain=readiness_chain,
    )
    previous_resume_state = _load_mt5_resume_state(config.memory_root)
    resume_state = _build_mt5_resume_state(
        previous_resume_state=previous_resume_state,
        readiness_chain=readiness_chain,
        quarantine_state=quarantine_state,
    )
    self_audit_report = _build_mt5_self_audit_report(
        readiness=controlled_mt5_readiness,
        mode=config.mode,
        readiness_chain=readiness_chain,
        quarantine_state=quarantine_state,
        resume_state=resume_state,
    )
    pack3_artifact_paths = _persist_mt5_pack3_artifacts(
        memory_root=config.memory_root,
        readiness_chain=readiness_chain,
        self_audit_report=self_audit_report,
        quarantine_state=quarantine_state,
        resume_state=resume_state,
    )
    controlled_mt5_readiness = {
        **controlled_mt5_readiness,
        "readiness_chain_verification": {
            **readiness_chain,
            "artifact_path": pack3_artifact_paths["readiness_chain_path"],
        },
        "self_audit_report": {
            **self_audit_report,
            "artifact_path": pack3_artifact_paths["self_audit_report_path"],
        },
        "quarantine_state": {
            **quarantine_state,
            "artifact_path": pack3_artifact_paths["quarantine_state_path"],
        },
        "resume_state": {
            **resume_state,
            "artifact_path": pack3_artifact_paths["resume_state_path"],
        },
    }
    mt5_unsafe_refusal = bool(quarantine_state.get("quarantine_required", False)) or (
        config.mode == "live"
        and (
            not controlled_mt5_readiness.get("ready_for_controlled_usage", False)
            or not bool(readiness_chain.get("all_checks_passed", False))
        )
    )
    if mt5_unsafe_refusal:
        controlled_mt5_readiness = {
            **controlled_mt5_readiness,
            "execution_gate": (
                "quarantined_invalid_readiness"
                if bool(quarantine_state.get("quarantine_required", False))
                else "refused_unsafe_readiness"
            ),
            "execution_refused": True,
            "rollback_applied": True,
        }
    elif bool(resume_state.get("safe_resume_applied", False)):
        controlled_mt5_readiness = {
            **controlled_mt5_readiness,
            "execution_gate": "safe_resumed_non_live_blocked",
            "execution_refused": False,
            "safe_resume_applied": True,
        }
    controlled_mt5_readiness = _apply_explicit_live_authorization(
        readiness=controlled_mt5_readiness,
        mode=config.mode,
        live_authorization_enabled=bool(config.live_authorization_enabled),
        readiness_chain=readiness_chain,
        quarantine_state=quarantine_state,
    )

    execution_state = ExecutionState(
        symbol=config.symbol,
        mode=config.mode,
        replay_source=config.replay_source,
        mt5_attempted=mt5_attempted,
        data_source=data_source,
        ready=not mt5_unsafe_refusal,
        reasons=[
            "validated",
            f"data_source={data_source}",
            f"mt5_controlled_ready={controlled_mt5_readiness.get('ready_for_controlled_usage', False)}",
            (
                "mt5_execution_refused_unsafe_readiness"
                if mt5_unsafe_refusal
                else "mt5_execution_refusal_not_required"
            ),
        ]
        + (
            [
                f"refusal:{reason}"
                for reason in controlled_mt5_readiness.get("fail_safe_blocked_reasons", [])
            ]
            if mt5_unsafe_refusal
            else []
        ),
        controlled_mt5_readiness=controlled_mt5_readiness,
        live_execution_blocked=True,
        mt5_execution_gate=str(controlled_mt5_readiness.get("execution_gate", "blocked")),
        mt5_execution_refused=bool(controlled_mt5_readiness.get("execution_refused", True)),
        mt5_chain_verified=bool(readiness_chain.get("all_checks_passed", False)),
        mt5_quarantined=bool(quarantine_state.get("quarantine_required", False)),
        mt5_safe_resume_state=str(resume_state.get("status", "unknown")),
        mt5_live_execution_enabled=bool(config.live_execution_enabled),
        mt5_auto_stop_active=bool(
            controlled_mt5_readiness.get("controlled_execution_state", {}).get("auto_stop_active", False)
        ),
        mt5_controlled_execution=dict(controlled_mt5_readiness.get("controlled_execution_artifact", {})),
    )

    structure = classify_market_structure(bars)
    liquidity = assess_liquidity_state(bars)
    score = compute_confidence(structure, liquidity)

    blocked_setups = store.load("blocked_setups")
    trade_outcomes = store.load("trade_outcomes")

    director = OversoulDirector()
    advanced_state = run_advanced_modules(
        director=director,
        bars=bars,
        base_direction=score["direction"],
        structure=structure,
        liquidity=liquidity,
        base_confidence=score["confidence"],
        blocked_setups=blocked_setups,
        trade_outcomes=trade_outcomes,
        symbol=config.symbol,
        mode=config.mode,
        quarantined_modules=list(config.quarantined_modules),
    )
    session_state = str(advanced_state.module_results.get("sessions", {}).payload.get("state", "unknown"))
    volatility_regime = str(advanced_state.module_results.get("volatility", {}).payload.get("state", "unknown"))
    macro_state = collect_xauusd_macro_state(
        memory_root=config.memory_root,
        bars=bars,
        session_state=session_state,
        volatility_regime=volatility_regime,
        config=MacroFeedConfig(
            alpha_vantage_api_key=config.alpha_vantage_api_key,
            fred_api_key=config.fred_api_key,
            treasury_endpoint=config.treasury_yields_endpoint,
            economic_calendar_endpoint=config.economic_calendar_endpoint,
            comex_open_interest_endpoint=config.comex_open_interest_endpoint,
            gold_etf_flows_endpoint=config.gold_etf_flows_endpoint,
            option_magnet_levels_endpoint=config.option_magnet_levels_endpoint,
            physical_premium_discount_endpoint=config.physical_premium_discount_endpoint,
            central_bank_reserve_endpoint=config.central_bank_reserve_endpoint,
            enabled=bool(config.macro_feed_enabled)
            and (config.mode == "live" or bool(config.macro_feed_allow_replay_fetch)),
        ),
    )
    macro_tags = dict(macro_state.get("trade_tags", {}))
    macro_risk = dict(macro_state.get("risk_behavior", {}))

    blocker = LossBlocker(min_confidence=0.6, max_spread_points=60.0)
    spread_points = float(
        advanced_state.module_results.get("spread_state", {}).payload.get("spread_points", 25.0)
    )
    block = blocker.evaluate(
        confidence=advanced_state.final_confidence,
        structure=structure,
        liquidity=liquidity,
        spread_points=spread_points,
    )
    strategy_intelligence = score_signal_intelligence(
        memory_root=config.memory_root,
        symbol=config.symbol,
        decision=advanced_state.final_direction,
        base_confidence=advanced_state.final_confidence,
        module_results=advanced_state.as_module_payload(),
        outcomes=trade_outcomes,
    )
    macro_confidence_penalty = float(macro_risk.get("confidence_penalty", 0.0) or 0.0)
    effective_signal_confidence = round(
        max(0.0, float(strategy_intelligence["confidence"]) - macro_confidence_penalty),
        4,
    )
    macro_adjusted_volume = round(
        float(config.live_order_volume) * float(macro_risk.get("size_multiplier", 1.0) or 1.0),
        4,
    )
    capital_guard = evaluate_capital_protection(
        memory_root=config.memory_root,
        latest_bar_time=int(bars[-1].get("time", 0)) if bars else 0,
        requested_volume=max(MIN_TRADE_VOLUME, macro_adjusted_volume),
        volatility_value=float(
            advanced_state.module_results.get("volatility", {}).payload.get("volatility_ratio", 1.0)
        ),
        latest_outcome=trade_outcomes[-1] if trade_outcomes else {},
        max_daily_loss_points=float(config.max_daily_loss_points),
        max_total_drawdown_points=float(config.max_total_drawdown_points),
        max_consecutive_loss_streak=int(config.max_consecutive_loss_streak),
        max_anomaly_clusters=int(config.max_anomaly_clusters),
    )

    refusal_reasons = [
        "mt5_execution_refused_unsafe_readiness",
        *(
            ["mt5_quarantined_invalid_readiness"]
            if bool(quarantine_state.get("quarantine_required", False))
            else []
        ),
        *[
            f"mt5_fail_safe:{reason}"
            for reason in controlled_mt5_readiness.get("fail_safe_blocked_reasons", [])
        ],
    ]
    combined_blocked = block["blocked"] or advanced_state.blocked or mt5_unsafe_refusal
    combined_reasons = normalize_reasons(
        block["reasons"] + advanced_state.blocked_reasons + (refusal_reasons if mt5_unsafe_refusal else [])
    )
    if bool(capital_guard.get("trade_refused", False)):
        combined_blocked = True
        combined_reasons = normalize_reasons(
            combined_reasons
            + [
                "capital_guard_daily_loss_limit_exceeded",
                f"capital_guard_volume={capital_guard.get('effective_volume', 0.0)}",
            ]
            + [f"capital_guard:{reason}" for reason in capital_guard.get("trigger_reasons", [])]
        )
    if bool(macro_risk.get("pause_trading", False)) and config.mode == "live":
        combined_blocked = True
        combined_reasons = normalize_reasons(
            combined_reasons
            + ["macro_feed_unsafe_pause"]
            + [f"macro_risk:{reason}" for reason in macro_risk.get("reasons", [])]
        )

    decision = advanced_state.final_direction
    structure_bias = str(structure.get("bias", "neutral")).lower()
    liquidity_hint = str(liquidity.get("direction_hint", "neutral")).lower()
    liquidity_state = str(liquidity.get("liquidity_state", "unknown")).lower()
    liquidity_score = float(liquidity.get("score", 0.0))
    agreement_override_applied = False
    hard_liquidity_conflict = (
        structure_bias in {"buy", "sell"}
        and liquidity_hint in {"buy", "sell"}
        and structure_bias != liquidity_hint
        and liquidity_state == "sweep"
        and liquidity_score >= 0.7
    )
    should_apply_override, override_guard_reason = _should_apply_replay_wait_structure_override(
        decision=decision,
        structure_bias=structure_bias,
        advanced_confidence=float(advanced_state.final_confidence),
        hard_liquidity_conflict=hard_liquidity_conflict,
        memory_root=str(config.memory_root),
        combined_reasons=combined_reasons,
        effective_signal_confidence=effective_signal_confidence,
    )
    if should_apply_override:
        decision = structure_bias.upper()
        agreement_override_applied = True
    reasons = (
        combined_reasons if combined_blocked else [f"advanced_direction={decision}"] + score["reasons"]
    )
    if agreement_override_applied and not combined_blocked:
        reasons = normalize_reasons(
            reasons
            + [
                "advanced_wait_structure_bias_override",
                f"agreement_direction={decision}",
                f"liquidity_hint={liquidity_hint}",
            ]
        )
    elif override_guard_reason and not combined_blocked:
        reasons = normalize_reasons(reasons + [override_guard_reason])
    if combined_blocked:
        decision = "WAIT"
    directional_votes: list[str] = []
    for module in advanced_state.module_results.values():
        normalized_vote = str(module.direction_vote).lower()
        if normalized_vote in {"buy", "sell"}:
            directional_votes.append(normalized_vote)
    buy_votes = sum(1 for vote in directional_votes if vote == "buy")
    sell_votes = sum(1 for vote in directional_votes if vote == "sell")
    directional_vote_total = buy_votes + sell_votes
    directional_vote_margin = abs(buy_votes - sell_votes)
    selected_votes = buy_votes if decision == "BUY" else sell_votes if decision == "SELL" else 0
    directional_support_ratio = selected_votes / max(1, directional_vote_total)
    directional_margin_ratio = directional_vote_margin / max(1, directional_vote_total)
    directional_conviction = round(
        (float(advanced_state.final_confidence) * 0.7)
        + (directional_support_ratio * 0.2)
        + (directional_margin_ratio * 0.1),
        4,
    )
    conflict_filter_result = advanced_state.module_results.get("conflict_filter")
    conflict_blocked = bool(conflict_filter_result.blocked) if conflict_filter_result is not None else False
    if decision in {"BUY", "SELL"} and not combined_blocked:
        weak_directional_conviction = directional_conviction < 0.62
        insufficient_vote_margin = directional_vote_margin < 2
        if weak_directional_conviction or insufficient_vote_margin or conflict_blocked:
            decision = "WAIT"
            reasons = normalize_reasons(
                reasons
                + (
                    ["directional_conviction_below_threshold"]
                    if weak_directional_conviction
                    else []
                )
                + (
                    ["directional_vote_margin_insufficient"]
                    if insufficient_vote_margin
                    else []
                )
                + (["directional_conflict_active"] if conflict_blocked else [])
            )

    signal_lifecycle = _build_signal_lifecycle_context(
        enabled=bool(config.signal_lifecycle_enabled),
        max_age_seconds=int(config.signal_max_age_seconds),
        bars=bars,
    )
    fail_safe_state_clear = len(controlled_mt5_readiness.get("fail_safe_blocked_reasons", [])) == 0
    risk_state_valid = not bool(block.get("blocked", False)) and not bool(capital_guard.get("trade_refused", False))

    # Load persisted position_id from the last execution artifact if available.
    _persisted_position_id: int | None = None
    try:
        _artifact_path = Path(config.memory_root) / "mt5_controlled_execution_artifact.json"
        if _artifact_path.exists():
            _artifact_payload = json.loads(_artifact_path.read_text(encoding="utf-8"))
            if isinstance(_artifact_payload, dict):
                _open_state = _artifact_payload.get("open_position_state")
                if isinstance(_open_state, dict) and _open_state.get("status") == "open":
                    _raw_pid = _open_state.get("position_id")
                    if _raw_pid is not None:
                        _persisted_position_id = int(_raw_pid) if int(_raw_pid) > 0 else None
    except Exception:
        _persisted_position_id = None

    controlled_execution, controlled_execution_state, controlled_execution_paths = _run_controlled_mt5_live_execution(
        memory_root=config.memory_root,
        mode=config.mode,
        symbol=config.symbol,
        decision=decision,
        confidence=effective_signal_confidence,
        bars=bars,
        live_execution_enabled=config.live_execution_enabled,
        live_order_volume=float(capital_guard.get("effective_volume", config.live_order_volume)),
        controlled_mt5_readiness=controlled_mt5_readiness,
        readiness_chain=readiness_chain,
        quarantine_state=quarantine_state,
        risk_state_valid=risk_state_valid,
        fail_safe_state_clear=fail_safe_state_clear,
        trade_tags=macro_tags,
        signal_lifecycle=signal_lifecycle,
        position_id=_persisted_position_id,
    )
    if decision in {"BUY", "SELL"} and controlled_execution.get("order_result", {}).get("status") != "accepted":
        decision = "WAIT"
        reasons = normalize_reasons(
            reasons
            + ["mt5_controlled_execution_refused"]
            + [
                f"mt5_controlled_refusal:{reason}"
                for reason in controlled_execution.get("rollback_refusal_reasons", [])
            ]
        )
    controlled_mt5_readiness = {
        **controlled_mt5_readiness,
        "live_execution_enabled": bool(config.live_execution_enabled),
        "signal_lifecycle_enabled": bool(config.signal_lifecycle_enabled),
        "signal_max_age_seconds": int(config.signal_max_age_seconds),
        "signal_lifecycle": dict(controlled_execution.get("signal_lifecycle", {})),
        "controlled_execution_state": controlled_execution_state,
        "controlled_execution_artifact": controlled_execution,
        "controlled_execution_paths": controlled_execution_paths,
    }
    execution_state = ExecutionState(
        symbol=config.symbol,
        mode=config.mode,
        replay_source=config.replay_source,
        mt5_attempted=mt5_attempted,
        data_source=data_source,
        ready=not mt5_unsafe_refusal,
        reasons=[
            "validated",
            f"data_source={data_source}",
            f"mt5_controlled_ready={controlled_mt5_readiness.get('ready_for_controlled_usage', False)}",
            (
                "mt5_execution_refused_unsafe_readiness"
                if mt5_unsafe_refusal
                else "mt5_execution_refusal_not_required"
            ),
        ]
        + (
            [
                f"refusal:{reason}"
                for reason in controlled_mt5_readiness.get("fail_safe_blocked_reasons", [])
            ]
            if mt5_unsafe_refusal
            else []
        ),
        controlled_mt5_readiness=controlled_mt5_readiness,
        live_execution_blocked=True,
        mt5_execution_gate=str(controlled_mt5_readiness.get("execution_gate", "blocked")),
        mt5_execution_refused=bool(controlled_mt5_readiness.get("execution_refused", True)),
        mt5_chain_verified=bool(readiness_chain.get("all_checks_passed", False)),
        mt5_quarantined=bool(quarantine_state.get("quarantine_required", False)),
        mt5_safe_resume_state=str(resume_state.get("status", "unknown")),
        mt5_live_execution_enabled=bool(config.live_execution_enabled),
        mt5_auto_stop_active=bool(controlled_execution_state.get("auto_stop_active", False)),
        mt5_controlled_execution=dict(controlled_execution),
        capital_guard=dict(capital_guard),
        strategy_intelligence={
            "signal_score": strategy_intelligence["signal_score"],
            "confidence": effective_signal_confidence,
            "feature_contributors": strategy_intelligence["feature_contributors"],
            "macro_confidence_penalty": macro_confidence_penalty,
        },
        macro_state=macro_state,
    )

    snapshot_id = store.record_snapshot(
        {
            "symbol": config.symbol,
            "mode": config.mode,
            "execution_state": execution_state.to_dict(),
            "structure": structure,
            "liquidity": liquidity,
            "base_confidence": score,
            "advanced_state": state_to_dict(advanced_state),
            "bars": bars,
            "controlled_mt5_execution": controlled_execution,
        }
    )
    if decision == "WAIT":
        store.record_blocked(
            {
                "symbol": config.symbol,
                "snapshot_id": snapshot_id,
                "direction": advanced_state.final_direction,
                "reasons": reasons,
                "trade_tags": macro_tags,
            }
        )
        trade_id = f"blocked_{snapshot_id}"
    else:
        trade_id = store.record_promoted(
            {
                "symbol": config.symbol,
                "snapshot_id": snapshot_id,
                "direction": decision,
                "confidence": advanced_state.final_confidence,
                "reasons": reasons,
                "trade_tags": macro_tags,
            }
        )

    tracker = OutcomeTracker(store)
    outcome = tracker.evaluate_and_record(
        trade_id=trade_id,
        decision=decision,
        bars=bars,
        confidence=effective_signal_confidence,
        reasons=reasons,
        trade_tags=macro_tags,
    )
    updated_trade_outcomes = store.load("trade_outcomes")
    promotion_policy = evaluate_module_promotion_policy(
        memory_root=config.memory_root,
        outcomes=updated_trade_outcomes,
        thresholds=PromotionThresholds(
            minimum_replay_sample_size=int(config.promotion_minimum_replay_sample_size),
            minimum_expectancy_points=float(config.promotion_minimum_expectancy_points),
            maximum_drawdown_points=float(config.promotion_maximum_drawdown_points),
            minimum_stability_score=float(config.promotion_minimum_stability_score),
        ),
    )
    live_learning = process_live_trade_feedback(
        memory_root=Path(config.memory_root),
        trade_outcomes=updated_trade_outcomes,
        feature_contributors=strategy_intelligence["feature_contributors"],
        replay_scope="full_replay" if config.mode == "replay" else "recent_live_window",
    )

    generated_rules = SelfCoder(store).generate_rules_from_outcomes()
    summary = tracker.summarize_recent_outcomes(limit=100)

    rules_registry_entry = register_generated_artifact(
        registry_path=Path(config.generated_registry_path),
        artifact_type="generated_rules",
        artifact_path=str(Path(config.memory_root) / "generated_rules.json"),
        metadata={
            "symbol": config.symbol,
            "mode": config.mode,
            "rule_count": len(generated_rules),
            "snapshot_id": snapshot_id,
        },
    )
    profile_registry_entry = register_generated_artifact(
        registry_path=Path(config.generated_registry_path),
        artifact_type="meta_adaptive_profile",
        artifact_path=config.meta_adaptive_profile_path,
        metadata={"symbol": config.symbol, "mode": config.mode, "snapshot_id": snapshot_id},
    )

    evolution_result = run_evolution_kernel(config)

    memory_context = {
        "latest_snapshot_id": snapshot_id,
        "last_blocked_count": len(store.load("blocked_setups")),
        "last_promoted_count": len(store.load("promoted_setups")),
        "latest_trade_outcome": outcome,
    }

    # Keep setup classification aligned with publicly exposed confidence.
    signal_input_confidence = effective_signal_confidence
    if combined_blocked and not combined_reasons:
        combined_reasons = ["blocked_without_explicit_reason"]

    signal = build_signal_output(
        symbol=config.symbol,
        action=decision,
        confidence=signal_input_confidence,
        reasons=reasons,
        block_result={"blocked": combined_blocked, "reasons": combined_reasons},
        structure=structure,
        liquidity=liquidity,
        memory_context=memory_context,
        generated_rules=generated_rules,
    )

    signal_payload = signal.to_dict()
    signal_payload["advanced_modules"] = {
        "director_module_map": director.as_dict(),
        "discovered_modules": director.discovered_as_dict(),
        "module_results": advanced_state.as_module_payload(),
        "module_health": advanced_state.as_health_payload(),
        "connector_hooks": advanced_state.as_connector_payload(),
        "final_direction": advanced_state.final_direction,
        "final_confidence": advanced_state.final_confidence,
    }
    signal_payload["generated_code_visibility"] = {
        "registry_path": config.generated_registry_path,
        "latest_entries": [rules_registry_entry, profile_registry_entry],
    }
    signal_payload["evolution_kernel"] = {
        "enabled": evolution_result["enabled"],
        "inspection": evolution_result["inspection"],
        "gap_count": len(evolution_result["gaps"]),
        "lifecycle": evolution_result["lifecycle"],
    }
    signal_payload["signal_score"] = strategy_intelligence["signal_score"]
    signal_payload["confidence"] = effective_signal_confidence
    signal_payload["feature_contributors"] = strategy_intelligence["feature_contributors"]
    signal_payload["macro_state"] = macro_state
    signal_payload["trade_tags"] = macro_tags
    signal_payload["live_learning_loop"] = {
        "latest_trade_evaluation": live_learning["latest_trade_evaluation"],
        "mutation_candidate": live_learning["mutation_candidate"],
    }
    signal_payload["strategy_promotion_policy"] = promotion_policy
    signal_payload["capital_guard"] = {
        "effective_volume": capital_guard["effective_volume"],
        "trade_refused": capital_guard["trade_refused"],
        "daily_loss_check": capital_guard["daily_loss_check"],
        "trigger_reasons": capital_guard.get("trigger_reasons", []),
        "macro_size_multiplier": float(macro_risk.get("size_multiplier", 1.0) or 1.0),
    }
    signal_payload["signal_lifecycle"] = dict(controlled_execution.get("signal_lifecycle", {}))

    if config.compact_output:
        signal_payload = _build_compact_signal_payload(signal_payload)

    chart_objects = build_chart_objects(
        symbol=config.symbol,
        structure=structure,
        liquidity=liquidity,
        signal_payload=signal_payload,
    )

    status_panel = build_status_panel(
        structure=structure,
        liquidity=liquidity,
        signal_payload=signal_payload,
        memory_result={"latest_trade_outcome": outcome, "outcome_summary": summary},
        rule_result={
            "generated_rule_count": len(generated_rules),
            "matching_rule_ids": signal_payload["rule_context"]["matching_rule_ids"],
        },
    )
    status_panel["advanced_module_result"] = {
        "blocked": advanced_state.blocked,
        "blocked_reasons": advanced_state.blocked_reasons,
        "module_count": len(advanced_state.module_results),
        "ready_count": sum(1 for h in advanced_state.module_health.values() if h.ready),
    }
    status_counts = evolution_result.get("status_counts", {})
    status_panel["evolution_result"] = {
        "enabled": evolution_result["enabled"],
        "gaps_found": len(evolution_result["gaps"]),
        "proposals_processed": len(evolution_result["lifecycle"]),
        "proposed": int(status_counts.get("proposed", 0)),
        "verified": int(status_counts.get("verified", 0)),
        "promoted": int(status_counts.get("promoted", 0)),
        "rejected": int(status_counts.get("rejected", 0)),
        "archived": int(status_counts.get("archived", 0)),
    }
    monitoring_state = update_system_monitor_state(
        memory_root=config.memory_root,
        execution_state=execution_state.to_dict(),
        controlled_execution=controlled_execution,
        trade_outcomes=updated_trade_outcomes,
        strategy_version="institutional_v1",
    )
    execution_state.monitoring_state = monitoring_state["system_state"]
    execution_state.live_learning_loop = {
        "latest_trade_evaluation": live_learning["latest_trade_evaluation"],
        "mutation_candidate": live_learning["mutation_candidate"],
    }
    status_panel["execution_state"] = execution_state.to_dict()
    status_panel["system_monitor"] = monitoring_state["system_state"]
    status_panel["macro_state"] = macro_state
    status_panel["trade_tags"] = macro_tags
    status_panel["strategy_promotion_policy"] = promotion_policy
    status_panel["entry_exit_decision"] = _build_entry_exit_decision_contract(
        decision=decision,
        effective_signal_confidence=effective_signal_confidence,
        bars=bars,
        reasons=reasons,
        controlled_execution=controlled_execution,
    )

    return build_indicator_output(
        symbol=config.symbol,
        signal_payload=signal_payload,
        chart_objects=chart_objects,
        status_panel=status_panel,
    )



def run_replay_evaluation(config: RuntimeConfig) -> dict[str, Any]:
    """Run replay evaluation using the existing replay pipeline path."""
    validate_runtime_config(config)
    ensure_sample_data(Path(config.sample_path))

    report = evaluate_replay(
        pipeline_runner=run_pipeline,
        config_factory=RuntimeConfig,
        symbol=config.symbol,
        timeframe=config.timeframe,
        bars=config.bars,
        replay_csv_path=config.replay_csv_path,
        sample_path=config.sample_path,
        memory_root=config.memory_root,
        generated_registry_path=config.generated_registry_path,
        meta_adaptive_profile_path=config.meta_adaptive_profile_path,
        evolution_enabled=config.evolution_enabled,
        evolution_registry_path=config.evolution_registry_path,
        evolution_artifact_root=config.evolution_artifact_root,
        evolution_max_proposals=config.evolution_max_proposals,
        compact_output=config.compact_output,
        evaluation_steps=config.evaluation_steps,
        evaluation_stride=config.evaluation_stride,
        walk_forward_enabled=config.walk_forward_enabled,
        walk_forward_context_bars=config.walk_forward_context_bars,
        walk_forward_test_bars=config.walk_forward_test_bars,
        walk_forward_step_bars=config.walk_forward_step_bars,
        execution_spread_cost_points=config.execution_spread_cost_points,
        execution_commission_cost_points=config.execution_commission_cost_points,
        execution_slippage_cost_points=config.execution_slippage_cost_points,
        execution_realism_v2_enabled=config.execution_realism_v2_enabled,
        execution_latency_penalty_points=config.execution_latency_penalty_points,
        execution_slippage_multiplier=config.execution_slippage_multiplier,
        execution_no_fill_spread_threshold=config.execution_no_fill_spread_threshold,
        execution_min_fill_confidence=config.execution_min_fill_confidence,
        knowledge_expansion_enabled=config.knowledge_expansion_enabled,
        knowledge_expansion_root=config.knowledge_expansion_root,
        knowledge_candidate_limit=config.knowledge_candidate_limit,
        signal_lifecycle_enabled=config.signal_lifecycle_enabled,
        signal_max_age_seconds=config.signal_max_age_seconds,
        quarantined_modules=list(config.quarantined_modules),
    )

    if config.knowledge_expansion_enabled:
        report["knowledge_expansion_phase_a"] = run_knowledge_expansion_phase_a(
            replay_report=report,
            root=Path(config.knowledge_expansion_root),
            candidate_limit=config.knowledge_candidate_limit,
        )
        report["continuous_governed_improvement_cycle"] = run_continuous_governed_improvement_cycle(
            Path("."),
            mode="replay",
            baseline_summary=report.get("summary", {}),
            replay_scope="evaluation_replay",
            iteration_id="replay_evaluation",
        )

    def _persist_report() -> None:
        persisted_report = _build_persistable_replay_evaluation_report(report)
        Path(config.evaluation_output_path).write_text(
            json.dumps(persisted_report, indent=2), encoding="utf-8"
        )

    # Decision-completeness gate — validates every record is decisive.
    completeness_artifact = str(
        Path(config.memory_root) / "decision_completeness_report.json"
    )
    completeness_report = run_decision_completeness_gate(
        records=report.get("records", []),
        artifact_path=completeness_artifact,
    )
    report["decision_completeness"] = completeness_report
    _persist_report()

    # Decision-quality gate — validates distribution & reason quality.
    quality_artifact = str(
        Path(config.memory_root) / "decision_quality_report.json"
    )
    quality_report = run_decision_quality_gate(
        records=report.get("records", []),
        completeness_report=completeness_report,
        artifact_path=quality_artifact,
        strict=False,  # replay/diagnostic: warn but don't block
    )
    report["decision_quality"] = quality_report
    _persist_report()

    # Replay-outcome gate — validates economic outcomes.
    outcome_artifact = str(
        Path(config.memory_root) / "replay_outcome_report.json"
    )
    try:
        outcome_report = run_replay_outcome_gate(
            records=report.get("records", []),
            quality_report=quality_report,
            artifact_path=outcome_artifact,
        )
    except ReplayOutcomeError:
        # Gate wrote its own artifact (including drawdown_attribution_path)
        # before raising.  Read it back so the main evaluation report on disk
        # surfaces the drawdown attribution path for downstream consumers
        # (e.g. A/B comparison tooling).
        outcome_artifact_path = Path(outcome_artifact)
        if outcome_artifact_path.exists():
            outcome_report = json.loads(
                outcome_artifact_path.read_text(encoding="utf-8")
            )
        else:
            outcome_report = {"passed": False}
        report["replay_outcome"] = outcome_report
        _persist_report()
        raise
    report["replay_outcome"] = outcome_report
    _persist_report()

    if config.quarantined_modules and outcome_report.get("drawdown_attribution_path"):
        included_report = evaluate_replay(
            pipeline_runner=run_pipeline,
            config_factory=RuntimeConfig,
            symbol=config.symbol,
            timeframe=config.timeframe,
            bars=config.bars,
            replay_csv_path=config.replay_csv_path,
            sample_path=config.sample_path,
            memory_root=config.memory_root,
            generated_registry_path=config.generated_registry_path,
            meta_adaptive_profile_path=config.meta_adaptive_profile_path,
            evolution_enabled=config.evolution_enabled,
            evolution_registry_path=config.evolution_registry_path,
            evolution_artifact_root=config.evolution_artifact_root,
            evolution_max_proposals=config.evolution_max_proposals,
            compact_output=config.compact_output,
            evaluation_steps=config.evaluation_steps,
            evaluation_stride=config.evaluation_stride,
            walk_forward_enabled=config.walk_forward_enabled,
            walk_forward_context_bars=config.walk_forward_context_bars,
            walk_forward_test_bars=config.walk_forward_test_bars,
            walk_forward_step_bars=config.walk_forward_step_bars,
            execution_spread_cost_points=config.execution_spread_cost_points,
            execution_commission_cost_points=config.execution_commission_cost_points,
            execution_slippage_cost_points=config.execution_slippage_cost_points,
            execution_realism_v2_enabled=config.execution_realism_v2_enabled,
            execution_latency_penalty_points=config.execution_latency_penalty_points,
            execution_slippage_multiplier=config.execution_slippage_multiplier,
            execution_no_fill_spread_threshold=config.execution_no_fill_spread_threshold,
            execution_min_fill_confidence=config.execution_min_fill_confidence,
            knowledge_expansion_enabled=False,
            knowledge_expansion_root=config.knowledge_expansion_root,
            knowledge_candidate_limit=config.knowledge_candidate_limit,
            signal_lifecycle_enabled=config.signal_lifecycle_enabled,
            signal_max_age_seconds=config.signal_max_age_seconds,
            quarantined_modules=[],
        )
        included_quality_artifact = str(
            Path(config.memory_root) / "decision_quality_report_included.json"
        )
        included_quality_report = run_decision_quality_gate(
            records=included_report.get("records", []),
            completeness_report={"passed": True},
            artifact_path=included_quality_artifact,
            strict=False,
        )
        included_outcome_artifact = str(
            Path(config.memory_root) / "replay_outcome_report_included.json"
        )
        try:
            included_outcome_report = run_replay_outcome_gate(
                records=included_report.get("records", []),
                quality_report=included_quality_report,
                artifact_path=included_outcome_artifact,
            )
        except ReplayOutcomeError:
            included_outcome_artifact_path = Path(included_outcome_artifact)
            if included_outcome_artifact_path.exists():
                included_outcome_report = json.loads(
                    included_outcome_artifact_path.read_text(encoding="utf-8")
                )
            else:
                included_outcome_report = {"passed": False}
        included_drawdown_path = included_outcome_report.get("drawdown_attribution_path")
        if included_drawdown_path:
            drawdown_comparison_artifact = str(
                Path(config.memory_root) / "replay_drawdown_comparison_report.json"
            )
            drawdown_comparison_report = compare_drawdown_files(
                included_path=included_drawdown_path,
                quarantined_path=outcome_report["drawdown_attribution_path"],
                output_path=drawdown_comparison_artifact,
            )
            report["drawdown_comparison"] = drawdown_comparison_report
            report["drawdown_comparison_path"] = drawdown_comparison_artifact
            report["drawdown_comparison_schema_version"] = str(
                drawdown_comparison_report.get("schema_version", "")
            )
            _persist_report()

    # Threshold-calibration report — diagnostic, never blocks.
    calibration_artifact = str(
        Path(config.memory_root) / "threshold_calibration_report.json"
    )
    calibration_report = run_threshold_calibration(
        records=report.get("records", []),
        outcome_report=outcome_report,
        artifact_path=calibration_artifact,
    )
    report["threshold_calibration"] = calibration_report
    _persist_report()

    return report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XAUUSD indicator runner")
    parser.add_argument("--config", default="config/settings.json")
    parser.add_argument("--mode", choices=["live", "replay"], default=None)
    parser.add_argument("--replay-source", choices=["csv", "memory"], default=None)
    parser.add_argument("--replay-csv", default=None)
    parser.add_argument("--evaluation-output-path", default=None)
    parser.add_argument("--evolution-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--compact-output", choices=["true", "false"], default=None)
    parser.add_argument("--evaluate-replay", choices=["true", "false"], default=None)
    parser.add_argument("--evaluation-steps", type=int, default=None)
    parser.add_argument("--evaluation-stride", type=int, default=None)
    parser.add_argument("--walk-forward-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--walk-forward-context-bars", type=int, default=None)
    parser.add_argument("--walk-forward-test-bars", type=int, default=None)
    parser.add_argument("--walk-forward-step-bars", type=int, default=None)
    parser.add_argument("--quarantined-modules", default=None)
    parser.add_argument("--knowledge-expansion-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--live-execution-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--live-authorization-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--live-order-volume", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_runtime_config(Path(args.config))
    if args.mode is not None:
        config = RuntimeConfig(**{**config.__dict__, "mode": args.mode})
    if args.replay_source is not None:
        config = RuntimeConfig(**{**config.__dict__, "replay_source": args.replay_source})
    if args.replay_csv is not None:
        config = RuntimeConfig(**{**config.__dict__, "replay_csv_path": args.replay_csv})
    if args.evaluation_output_path is not None:
        config = RuntimeConfig(
            **{**config.__dict__, "evaluation_output_path": args.evaluation_output_path}
        )
    if args.evolution_enabled is not None:
        config = RuntimeConfig(
            **{**config.__dict__, "evolution_enabled": args.evolution_enabled.lower() == "true"}
        )
    if args.compact_output is not None:
        config = RuntimeConfig(
            **{**config.__dict__, "compact_output": args.compact_output.lower() == "true"}
        )
    if args.evaluation_steps is not None:
        config = RuntimeConfig(**{**config.__dict__, "evaluation_steps": int(args.evaluation_steps)})
    if args.evaluation_stride is not None:
        config = RuntimeConfig(**{**config.__dict__, "evaluation_stride": int(args.evaluation_stride)})
    if args.walk_forward_enabled is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "walk_forward_enabled": args.walk_forward_enabled.lower() == "true",
            }
        )
    if args.walk_forward_context_bars is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "walk_forward_context_bars": int(args.walk_forward_context_bars),
            }
        )
    if args.walk_forward_test_bars is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "walk_forward_test_bars": int(args.walk_forward_test_bars),
            }
        )
    if args.walk_forward_step_bars is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "walk_forward_step_bars": int(args.walk_forward_step_bars),
            }
        )
    if args.quarantined_modules is not None:
        parsed_quarantine = [
            item.strip()
            for item in str(args.quarantined_modules).split(",")
            if item.strip()
        ]
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "quarantined_modules": parsed_quarantine,
            }
        )
    if args.knowledge_expansion_enabled is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "knowledge_expansion_enabled": args.knowledge_expansion_enabled.lower() == "true",
            }
        )
    if args.live_execution_enabled is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "live_execution_enabled": args.live_execution_enabled.lower() == "true",
            }
        )
    if args.live_authorization_enabled is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "live_authorization_enabled": args.live_authorization_enabled.lower() == "true",
            }
        )
    if args.live_order_volume is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "live_order_volume": float(args.live_order_volume),
            }
        )

    evaluate_replay_mode = args.evaluate_replay is not None and args.evaluate_replay.lower() == "true"
    if evaluate_replay_mode:
        print(run_replay_evaluation(config))
    else:
        print(run_pipeline(config))


if __name__ == "__main__":
    main()
