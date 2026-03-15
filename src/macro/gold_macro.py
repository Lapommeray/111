from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.macro.adapters import AlphaVantageAdapter, EconomicCalendarAdapter, FREDAdapter, TreasuryYieldsAdapter
from src.utils import clamp, normalize_reasons, read_json_safe, write_json_atomic

_MACRO_STATE_CACHE: dict[str, Any] = {}
ROUND_NUMBER_NEAR_THRESHOLD = 0.25
ROUND_NUMBER_APPROACHING_THRESHOLD = 0.75
DXY_YIELD_SIZE_MULTIPLIER = 0.55
DXY_YIELD_CONFIDENCE_PENALTY = 0.12
HIGH_RISK_EVENT_SIZE_MULTIPLIER = 0.5
HIGH_RISK_EVENT_CONFIDENCE_PENALTY = 0.08
WATCH_EVENT_SIZE_MULTIPLIER = 0.75
WATCH_EVENT_CONFIDENCE_PENALTY = 0.04
SESSION_EVENT_SIZE_MULTIPLIER = 0.8
SESSION_EVENT_CONFIDENCE_PENALTY = 0.04


@dataclass(frozen=True)
class MacroFeedConfig:
    alpha_vantage_api_key: str
    fred_api_key: str
    treasury_endpoint: str
    economic_calendar_endpoint: str
    enabled: bool = True


def _feed_disabled_state(name: str, reason: str) -> dict[str, Any]:
    return {
        "feed": name,
        "available": False,
        "stale": True,
        "state": "unavailable",
        "reason_codes": [reason],
        "metrics": {},
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


def _price_change(bars: list[dict[str, Any]]) -> float:
    if len(bars) < 2:
        return 0.0
    prev = float(bars[-2].get("close", 0.0) or 0.0)
    latest = float(bars[-1].get("close", 0.0) or 0.0)
    if prev == 0:
        return 0.0
    return (latest - prev) / prev


def _round_number_proximity(price: float, step: float = 10.0) -> dict[str, Any]:
    if step <= 0:
        return {"state": "unknown", "distance": None}
    nearest = round(price / step) * step
    distance = abs(price - nearest)
    if distance <= ROUND_NUMBER_NEAR_THRESHOLD:
        state = "near_round_number"
    elif distance <= ROUND_NUMBER_APPROACHING_THRESHOLD:
        state = "approaching_round_number"
    else:
        state = "clear_round_number"
    return {"state": state, "distance": round(distance, 4), "nearest_level": round(nearest, 4)}


def _derive_yield_state(*, yield_pressure: str, curve_10y_2y: Any) -> str:
    if yield_pressure != "neutral":
        return yield_pressure
    if isinstance(curve_10y_2y, (int, float)) and curve_10y_2y > 0:
        return "steepening"
    return "flat_or_inverted"


def collect_xauusd_macro_state(
    *,
    memory_root: str,
    bars: list[dict[str, Any]],
    session_state: str,
    volatility_regime: str,
    config: MacroFeedConfig,
) -> dict[str, Any]:
    if config.enabled:
        alpha_state = AlphaVantageAdapter(config.alpha_vantage_api_key).fetch_dxy_proxy()
        fred_state = FREDAdapter(config.fred_api_key).fetch_core_macro()
        treasury_state = TreasuryYieldsAdapter(config.treasury_endpoint).fetch_yields()
        calendar_state = EconomicCalendarAdapter(config.economic_calendar_endpoint).fetch_events()
    else:
        alpha_state = _feed_disabled_state("alpha_vantage", "external_fetch_disabled")
        fred_state = {
            "DGS10": {"available": False, "stale": True, "value": None, "change": None, "reason_codes": ["external_fetch_disabled"]},
            "DGS2": {"available": False, "stale": True, "value": None, "change": None, "reason_codes": ["external_fetch_disabled"]},
            "T10YIE": {"available": False, "stale": True, "value": None, "change": None, "reason_codes": ["external_fetch_disabled"]},
            "REAL_RATE_PROXY": {"available": False, "stale": True, "value": None, "change": None, "reason_codes": ["external_fetch_disabled"]},
        }
        treasury_state = _feed_disabled_state("treasury", "external_fetch_disabled")
        calendar_state = _feed_disabled_state("economic_calendar", "external_fetch_disabled")

    price_change = _price_change(bars)
    last_price = float(bars[-1].get("close", 0.0)) if bars else 0.0

    dxy_change = float(alpha_state.get("metrics", {}).get("usd_proxy_change", 0.0) or 0.0)
    dxy_state = str(alpha_state.get("state", "unavailable"))
    yield_change = float(fred_state.get("DGS10", {}).get("change") or 0.0)
    inflation_change = float(fred_state.get("T10YIE", {}).get("change") or 0.0)
    real_rate = fred_state.get("REAL_RATE_PROXY", {}).get("value")
    high_impact_count = int(calendar_state.get("metrics", {}).get("high_impact_count", 0) or 0)
    major_event_count = int(calendar_state.get("metrics", {}).get("major_event_count", 0) or 0)
    curve_10y_2y = treasury_state.get("metrics", {}).get("curve_10y_2y")

    dxy_divergence = "neutral"
    if dxy_change > 0.002 and price_change > 0:
        dxy_divergence = "gold_up_vs_usd_up"
    elif dxy_change < -0.002 and price_change < 0:
        dxy_divergence = "gold_down_vs_usd_down"

    yield_pressure = "neutral"
    if yield_change > 0.03:
        yield_pressure = "bearish_gold"
    elif yield_change < -0.03:
        yield_pressure = "supportive_gold"

    real_rate_state = "unknown"
    if isinstance(real_rate, (int, float)):
        real_rate_state = "high_real_rate" if float(real_rate) >= 1.6 else "low_real_rate" if float(real_rate) <= 0.2 else "balanced_real_rate"

    event_state = "high_risk" if major_event_count > 0 or high_impact_count >= 2 else "watch" if high_impact_count > 0 else "calm"
    session_event_state = (
        "major_session_event_overlap"
        if event_state in {"high_risk", "watch"} and session_state in {"london", "new_york"}
        else "no_overlap"
    )
    round_number_state = _round_number_proximity(last_price)

    size_multiplier = 1.0
    confidence_penalty = 0.0
    risk_reasons: list[str] = []
    if dxy_state == "strong_usd" and yield_pressure == "bearish_gold":
        size_multiplier *= DXY_YIELD_SIZE_MULTIPLIER
        confidence_penalty += DXY_YIELD_CONFIDENCE_PENALTY
        risk_reasons.append("dxy_yield_against_gold")
    if event_state == "high_risk":
        size_multiplier *= HIGH_RISK_EVENT_SIZE_MULTIPLIER
        confidence_penalty += HIGH_RISK_EVENT_CONFIDENCE_PENALTY
        risk_reasons.append("major_news_risk")
    elif event_state == "watch":
        size_multiplier *= WATCH_EVENT_SIZE_MULTIPLIER
        confidence_penalty += WATCH_EVENT_CONFIDENCE_PENALTY
        risk_reasons.append("elevated_news_risk")
    if session_event_state == "major_session_event_overlap":
        size_multiplier *= SESSION_EVENT_SIZE_MULTIPLIER
        confidence_penalty += SESSION_EVENT_CONFIDENCE_PENALTY
        risk_reasons.append("session_event_overlap")

    feed_unavailable = []
    if not bool(alpha_state.get("available", False)):
        feed_unavailable.append("alpha_vantage")
    if not bool(fred_state.get("DGS10", {}).get("available", False)):
        feed_unavailable.append("fred_DGS10")
    if not bool(fred_state.get("DGS2", {}).get("available", False)):
        feed_unavailable.append("fred_DGS2")
    if not bool(fred_state.get("T10YIE", {}).get("available", False)):
        feed_unavailable.append("fred_T10YIE")
    if not bool(calendar_state.get("available", False)):
        feed_unavailable.append("economic_calendar")
    if not bool(treasury_state.get("available", False)):
        feed_unavailable.append("treasury")
    if feed_unavailable:
        confidence_penalty += min(0.18, 0.03 * len(feed_unavailable))
        risk_reasons.append(f"feeds_unavailable:{','.join(sorted(feed_unavailable))}")

    feed_stale_or_unsafe = (
        bool(alpha_state.get("stale", False))
        and bool(fred_state.get("DGS10", {}).get("stale", False))
        and bool(fred_state.get("T10YIE", {}).get("stale", False))
    )
    pause_trading = bool(feed_stale_or_unsafe)
    if pause_trading:
        risk_reasons.append("macro_feed_state_unsafe_or_stale")

    macro_states = {
        "dxy_state": dxy_state,
        "yield_state": _derive_yield_state(yield_pressure=yield_pressure, curve_10y_2y=curve_10y_2y),
        "inflation_real_rate_state": real_rate_state if real_rate_state != "unknown" else ("inflation_rising" if inflation_change > 0.03 else "inflation_stable"),
        "event_news_state": event_state,
    }
    detectors = {
        "dxy_divergence_detector": {
            "state": dxy_divergence,
            "active": dxy_divergence != "neutral",
            "metrics": {"gold_return": round(price_change, 6), "usd_proxy_change": round(dxy_change, 6)},
        },
        "yield_pressure_detector": {
            "state": yield_pressure,
            "active": yield_pressure != "neutral",
            "metrics": {"dgs10_change": round(yield_change, 6), "curve_10y_2y": curve_10y_2y},
        },
        "real_rate_detector": {
            "state": real_rate_state,
            "active": real_rate_state in {"high_real_rate", "low_real_rate"},
            "metrics": {"real_rate_proxy": real_rate, "t10yie_change": round(inflation_change, 6)},
        },
        "news_event_risk_detector": {
            "state": event_state,
            "active": event_state in {"high_risk", "watch"},
            "metrics": {"high_impact_count": high_impact_count, "major_event_count": major_event_count},
        },
        "session_event_interaction_detector": {
            "state": session_event_state,
            "active": session_event_state == "major_session_event_overlap",
            "metrics": {"session": session_state, "event_state": event_state},
        },
    }

    trade_tags = {
        "session": session_state,
        "volatility_regime": volatility_regime,
        "dxy_state": macro_states["dxy_state"],
        "yield_state": macro_states["yield_state"],
        "event_news_state": macro_states["event_news_state"],
        "round_number_proximity": round_number_state["state"],
    }
    risk_behavior = {
        "size_multiplier": round(clamp(size_multiplier, 0.1, 1.0), 4),
        "confidence_penalty": round(clamp(confidence_penalty, 0.0, 0.35), 4),
        "pause_trading": pause_trading,
        "reasons": normalize_reasons(risk_reasons),
    }

    macro_state = {
        "feed_states": {
            "alpha_vantage": alpha_state,
            "fred": fred_state,
            "treasury": treasury_state,
            "economic_calendar": calendar_state,
        },
        "macro_states": macro_states,
        "detectors": detectors,
        "risk_behavior": risk_behavior,
        "trade_tags": trade_tags,
        "round_number": round_number_state,
        "logged_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    root = Path(memory_root) / "macro_state"
    latest_path = root / "macro_state_latest.json"
    history_path = root / "macro_state_history.json"
    write_json_atomic(latest_path, macro_state)
    history = read_json_safe(history_path, default=[])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "logged_at": macro_state["logged_at"],
            "macro_states": macro_state["macro_states"],
            "risk_behavior": macro_state["risk_behavior"],
            "trade_tags": macro_state["trade_tags"],
            "feed_availability": {
                "alpha_vantage": bool(alpha_state.get("available", False)),
                "fred_dgs10": bool(fred_state.get("DGS10", {}).get("available", False)),
                "fred_dgs2": bool(fred_state.get("DGS2", {}).get("available", False)),
                "fred_t10yie": bool(fred_state.get("T10YIE", {}).get("available", False)),
                "treasury": bool(treasury_state.get("available", False)),
                "economic_calendar": bool(calendar_state.get("available", False)),
            },
        }
    )
    write_json_atomic(history_path, history[-300:])

    cache_key = str(Path(memory_root).resolve())
    _MACRO_STATE_CACHE[cache_key] = macro_state
    macro_state["paths"] = {"latest": str(latest_path), "history": str(history_path)}
    return macro_state


def get_cached_macro_state(memory_root: str) -> dict[str, Any]:
    return dict(_MACRO_STATE_CACHE.get(str(Path(memory_root).resolve()), {}))
