from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    raise ValueError(f"Unsupported runtime config schema type for key '{key}': {expected}")


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
            parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
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
    enabled = bool(lifecycle.get("signal_lifecycle_enabled", False))
    raw_max_age_seconds = lifecycle.get("signal_max_age_seconds", 900)
    try:
        max_age_seconds = int(raw_max_age_seconds)
    except Exception:
        max_age_seconds = 900
    execution_ts = int(datetime.now(tz=timezone.utc).timestamp())
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
    signal_age_seconds = max(0, execution_ts - source_ts) if source_ts is not None else None
    if not enabled:
        signal_fresh = True
        lifecycle_reason = "signal_lifecycle_disabled"
        refusal_reasons: list[str] = []
    elif max_age_seconds <= 0:
        signal_fresh = False
        lifecycle_reason = "signal_lifecycle_invalid_max_age"
        refusal_reasons = ["signal_stale", "signal_lifecycle_invalid_max_age"]
    elif signal_age_seconds is None:
        signal_fresh = False
        lifecycle_reason = "signal_timestamp_missing"
        refusal_reasons = ["signal_stale", "signal_timestamp_missing"]
    elif future_timestamp:
        signal_fresh = False
        lifecycle_reason = "signal_timestamp_in_future"
        refusal_reasons = ["signal_stale", "signal_timestamp_in_future"]
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
        "execution_checked_at": datetime.now(tz=timezone.utc).isoformat(),
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
        if retcode_done is not None and retcode == retcode_done:
            return {
                "status": "accepted",
                "order_sent": True,
                "error_reason": "",
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
    rejection_reasons: list[str] = []
    rollback_reasons: list[str] = []
    stop_loss_take_profit = {"stop_loss": None, "take_profit": None}

    if mode != "live":
        rejection_reasons = ["non_live_mode"]
    elif decision not in {"BUY", "SELL"}:
        rejection_reasons = ["no_trade_signal"]
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
        if order_result.get("status") != "accepted":
            rejection_reasons = [str(order_result.get("error_reason") or "order_send_refused")]

    if rejection_reasons:
        rollback_reasons = sorted(set(rejection_reasons))
        order_result = {
            **order_result,
            "status": order_result.get("status", "refused"),
            "order_sent": bool(order_result.get("order_sent", False)),
            "rejection_reason": rollback_reasons[0],
        }
    else:
        order_result = {
            **order_result,
            "status": "accepted",
            "order_sent": True,
            "rejection_reason": "",
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

    open_position_state = (
        {
            "status": "open",
            "position_id": int(order_result.get("order_id", 0) or 0),
            "symbol": symbol,
            "side": decision,
            "entry_price": float(order_request.get("price", 0.0)),
            "stop_loss": stop_loss_take_profit["stop_loss"],
            "take_profit": stop_loss_take_profit["take_profit"],
        }
        if order_result.get("status") == "accepted"
        else {
            "status": "flat",
            "position_id": None,
            "symbol": symbol,
            "side": "NONE",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
        }
    )
    exit_decision = (
        {"decision": "hold_open_position", "reason": "position_active_under_governed_controls"}
        if open_position_state["status"] == "open"
        else {"decision": "no_position_exit", "reason": "no_open_position"}
    )
    pnl_snapshot = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "symbol": symbol,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "position_open": open_position_state["status"] == "open",
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
    if bool(macro_risk.get("pause_trading", False)):
        combined_blocked = True
        combined_reasons = normalize_reasons(
            combined_reasons
            + ["macro_feed_unsafe_pause"]
            + [f"macro_risk:{reason}" for reason in macro_risk.get("reasons", [])]
        )

    decision = advanced_state.final_direction
    reasons = (
        combined_reasons if combined_blocked else [f"advanced_direction={decision}"] + score["reasons"]
    )
    if combined_blocked:
        decision = "WAIT"

    signal_lifecycle = _build_signal_lifecycle_context(
        enabled=bool(config.signal_lifecycle_enabled),
        max_age_seconds=int(config.signal_max_age_seconds),
        bars=bars,
    )
    fail_safe_state_clear = len(controlled_mt5_readiness.get("fail_safe_blocked_reasons", [])) == 0
    risk_state_valid = not bool(block.get("blocked", False)) and not bool(capital_guard.get("trade_refused", False))
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

    signal = build_signal_output(
        symbol=config.symbol,
        action=decision,
        confidence=strategy_intelligence["confidence"],
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

    Path(config.evaluation_output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XAUUSD indicator runner")
    parser.add_argument("--config", default="config/settings.json")
    parser.add_argument("--mode", choices=["live", "replay"], default=None)
    parser.add_argument("--replay-source", choices=["csv", "memory"], default=None)
    parser.add_argument("--replay-csv", default=None)
    parser.add_argument("--evolution-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--compact-output", choices=["true", "false"], default=None)
    parser.add_argument("--evaluate-replay", choices=["true", "false"], default=None)
    parser.add_argument("--evaluation-steps", type=int, default=None)
    parser.add_argument("--evaluation-stride", type=int, default=None)
    parser.add_argument("--knowledge-expansion-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--live-execution-enabled", choices=["true", "false"], default=None)
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
