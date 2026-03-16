from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.macro.adapters import (
    AlphaVantageAdapter,
    CentralBankReserveAdapter,
    COMEXOpenInterestAdapter,
    EconomicCalendarAdapter,
    FREDAdapter,
    GoldEtfFlowsAdapter,
    GoldOptionMagnetAdapter,
    GoldPhysicalPremiumAdapter,
    TreasuryYieldsAdapter,
)
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
ASIA_SESSION_SIZE_MULTIPLIER = 0.7
LONDON_SESSION_SIZE_MULTIPLIER = 1.0
NEW_YORK_SESSION_SIZE_MULTIPLIER = 0.85
FRIDAY_AFTERNOON_DISABLE_HOUR_UTC = 16
NEWS_BLACKOUT_SIZE_MULTIPLIER = 0.25
NEWS_POST_RELEASE_SIZE_MULTIPLIER = 0.6
MAJOR_ROUND_LEVELS = [1800.0, 1850.0, 1900.0, 1950.0, 2000.0]
MAJOR_ROUND_NEAR_THRESHOLD = 1.5
FEED_UNAVAILABLE_CONFIDENCE_STEP = 0.03
FEED_UNAVAILABLE_CONFIDENCE_CAP = 0.18
CORRELATION_WINDOW_SIZE = 30
CORRELATION_MIN_SAMPLES = 5
CORRELATION_BREAKDOWN_DROP = 0.55
CORRELATION_BREAKDOWN_WEAK = 0.2
CORRELATION_BREAK_SIZE_MULTIPLIER = 0.65
CORRELATION_BREAK_CONFIDENCE_PENALTY = 0.07
DEFAULT_NEGATIVE_CORRELATION = -0.5
DEFAULT_POSITIVE_CORRELATION = 0.5
HIGH_REAL_RATE_THRESHOLD = 1.6
LOW_REAL_RATE_THRESHOLD = 0.2


@dataclass(frozen=True)
class MacroFeedConfig:
    alpha_vantage_api_key: str
    fred_api_key: str
    treasury_endpoint: str
    economic_calendar_endpoint: str
    comex_open_interest_endpoint: str = ""
    gold_etf_flows_endpoint: str = ""
    option_magnet_levels_endpoint: str = ""
    physical_premium_discount_endpoint: str = ""
    central_bank_reserve_endpoint: str = ""
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


def _major_round_number_proximity(price: float) -> dict[str, Any]:
    if not MAJOR_ROUND_LEVELS:
        return {"state": "unknown", "distance": None, "nearest_level": None}
    nearest = min(MAJOR_ROUND_LEVELS, key=lambda level: abs(price - level))
    distance = abs(price - nearest)
    state = "near_major_round_number" if distance <= MAJOR_ROUND_NEAR_THRESHOLD else "clear_major_round_number"
    return {"state": state, "distance": round(distance, 4), "nearest_level": round(nearest, 4)}


def _pearson_correlation(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) != len(y_values) or len(x_values) < CORRELATION_MIN_SAMPLES:
        return None
    n = len(x_values)
    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n
    x_centered = [x - x_mean for x in x_values]
    y_centered = [y - y_mean for y in y_values]
    x_var = sum(item * item for item in x_centered)
    y_var = sum(item * item for item in y_centered)
    if x_var <= 0 or y_var <= 0:
        return None
    covariance = sum(xc * yc for xc, yc in zip(x_centered, y_centered))
    return round(covariance / ((x_var * y_var) ** 0.5), 6)


def _detect_correlation_shift(
    *,
    previous_corr: float | None,
    current_corr: float | None,
    expected_sign: int,
) -> dict[str, Any]:
    if current_corr is None:
        return {
            "break_detected": False,
            "state": "insufficient_data",
            "reason": "insufficient_samples",
            "expected_sign": expected_sign,
        }

    prior = previous_corr
    if prior is None:
        prior = DEFAULT_NEGATIVE_CORRELATION if expected_sign < 0 else DEFAULT_POSITIVE_CORRELATION
    sign_flip = (prior * current_corr) < 0 and abs(current_corr) >= CORRELATION_BREAKDOWN_WEAK
    sharp_breakdown = abs(prior) >= 0.5 and (abs(prior) - abs(current_corr)) >= CORRELATION_BREAKDOWN_DROP
    break_detected = bool(sign_flip or sharp_breakdown)
    state = "correlation_break_detected" if break_detected else "correlation_stable"
    reason = "sign_flip" if sign_flip else "sharp_breakdown" if sharp_breakdown else "stable"
    return {
        "break_detected": break_detected,
        "state": state,
        "reason": reason,
        "expected_sign": expected_sign,
    }


def _compute_correlation_regime(
    *,
    macro_root: Path,
    latest_time: int,
    xau_return: float,
    dxy_change: float | None,
    us10y_change: float | None,
) -> dict[str, Any]:
    state_path = macro_root / "correlation_regime_state.json"
    history_path = macro_root / "correlation_regime_history.json"
    state_payload = read_json_safe(
        state_path,
        default={
            "samples": [],
            "last_correlations": {"xau_dxy": None, "xau_us10y": None},
        },
    )
    if not isinstance(state_payload, dict):
        state_payload = {"samples": [], "last_correlations": {"xau_dxy": None, "xau_us10y": None}}
    samples = state_payload.get("samples", [])
    if not isinstance(samples, list):
        samples = []

    samples.append(
        {
            "time": int(latest_time),
            "xau_return": round(float(xau_return), 8),
            "dxy_change": None if dxy_change is None else round(float(dxy_change), 8),
            "us10y_change": None if us10y_change is None else round(float(us10y_change), 8),
        }
    )
    samples = samples[-(CORRELATION_WINDOW_SIZE * 3) :]

    dxy_pairs = [
        (float(item["xau_return"]), float(item["dxy_change"]))
        for item in samples
        if isinstance(item, dict) and item.get("dxy_change") is not None
    ]
    us10y_pairs = [
        (float(item["xau_return"]), float(item["us10y_change"]))
        for item in samples
        if isinstance(item, dict) and item.get("us10y_change") is not None
    ]
    dxy_pairs = dxy_pairs[-CORRELATION_WINDOW_SIZE:]
    us10y_pairs = us10y_pairs[-CORRELATION_WINDOW_SIZE:]

    current_corr_dxy = _pearson_correlation(
        [pair[0] for pair in dxy_pairs],
        [pair[1] for pair in dxy_pairs],
    )
    current_corr_us10y = _pearson_correlation(
        [pair[0] for pair in us10y_pairs],
        [pair[1] for pair in us10y_pairs],
    )

    last_corr = state_payload.get("last_correlations", {})
    previous_corr_dxy = last_corr.get("xau_dxy") if isinstance(last_corr, dict) else None
    previous_corr_us10y = last_corr.get("xau_us10y") if isinstance(last_corr, dict) else None

    dxy_shift = _detect_correlation_shift(
        previous_corr=previous_corr_dxy if isinstance(previous_corr_dxy, (int, float)) else None,
        current_corr=current_corr_dxy,
        expected_sign=-1,
    )
    us10y_shift = _detect_correlation_shift(
        previous_corr=previous_corr_us10y if isinstance(previous_corr_us10y, (int, float)) else None,
        current_corr=current_corr_us10y,
        expected_sign=-1,
    )

    break_detected = bool(dxy_shift["break_detected"] or us10y_shift["break_detected"])
    state = "correlation_break_detected" if break_detected else (
        "insufficient_data" if current_corr_dxy is None and current_corr_us10y is None else "correlation_stable"
    )
    break_reasons = []
    if dxy_shift["break_detected"]:
        break_reasons.append(f"xau_dxy:{dxy_shift['reason']}")
    if us10y_shift["break_detected"]:
        break_reasons.append(f"xau_us10y:{us10y_shift['reason']}")

    correlation_state = {
        "state": state,
        "break_detected": break_detected,
        "rolling_correlations": {
            "xau_dxy": current_corr_dxy,
            "xau_us10y": current_corr_us10y,
        },
        "previous_correlations": {
            "xau_dxy": previous_corr_dxy if isinstance(previous_corr_dxy, (int, float)) else None,
            "xau_us10y": previous_corr_us10y if isinstance(previous_corr_us10y, (int, float)) else None,
        },
        "window_samples": {
            "xau_dxy": len(dxy_pairs),
            "xau_us10y": len(us10y_pairs),
        },
        "break_reasons": break_reasons,
        "pairs": {
            "xau_dxy": dxy_shift,
            "xau_us10y": us10y_shift,
        },
        "logged_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    state_payload["samples"] = samples
    state_payload["last_correlations"] = {
        "xau_dxy": current_corr_dxy,
        "xau_us10y": current_corr_us10y,
    }
    state_payload["last_state"] = correlation_state
    write_json_atomic(state_path, state_payload)

    history = read_json_safe(history_path, default=[])
    if not isinstance(history, list):
        history = []
    history.append(correlation_state)
    write_json_atomic(history_path, history[-300:])

    correlation_state["paths"] = {
        "state": str(state_path),
        "history": str(history_path),
    }
    return correlation_state


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
        comex_oi_state = COMEXOpenInterestAdapter(config.comex_open_interest_endpoint).fetch_state()
        etf_flow_state = GoldEtfFlowsAdapter(config.gold_etf_flows_endpoint).fetch_state()
        option_magnet_state = GoldOptionMagnetAdapter(config.option_magnet_levels_endpoint).fetch_state()
        physical_premium_state = GoldPhysicalPremiumAdapter(config.physical_premium_discount_endpoint).fetch_state()
        central_bank_reserve_state = CentralBankReserveAdapter(config.central_bank_reserve_endpoint).fetch_state()
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
        comex_oi_state = _feed_disabled_state("comex_open_interest", "external_fetch_disabled")
        etf_flow_state = _feed_disabled_state("gold_etf_flows", "external_fetch_disabled")
        option_magnet_state = _feed_disabled_state("gold_option_magnet_levels", "external_fetch_disabled")
        physical_premium_state = _feed_disabled_state("gold_physical_premium_discount", "external_fetch_disabled")
        central_bank_reserve_state = _feed_disabled_state("central_bank_gold_reserves", "external_fetch_disabled")

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
        if real_rate >= HIGH_REAL_RATE_THRESHOLD:
            real_rate_state = "high_real_rate"
        elif real_rate <= LOW_REAL_RATE_THRESHOLD:
            real_rate_state = "low_real_rate"
        else:
            real_rate_state = "balanced_real_rate"

    event_state = "high_risk" if major_event_count > 0 or high_impact_count >= 2 else "watch" if high_impact_count > 0 else "calm"
    session_event_state = (
        "major_session_event_overlap"
        if event_state in {"high_risk", "watch"} and session_state in {"london", "new_york"}
        else "no_overlap"
    )
    round_number_state = _round_number_proximity(last_price)
    major_round_state = _major_round_number_proximity(last_price)
    last_bar_time = int(bars[-1].get("time", 0)) if bars else 0
    bar_dt = datetime.fromtimestamp(last_bar_time, tz=timezone.utc) if last_bar_time > 0 else datetime.now(tz=timezone.utc)
    is_friday_afternoon = bar_dt.weekday() == 4 and bar_dt.hour >= FRIDAY_AFTERNOON_DISABLE_HOUR_UTC
    session_policy_state = "normal_size"
    session_size_multiplier = 1.0
    if session_state == "asia":
        session_policy_state = "asia_reduced_size"
        session_size_multiplier = ASIA_SESSION_SIZE_MULTIPLIER
    elif session_state == "new_york":
        session_policy_state = "new_york_moderate_size"
        session_size_multiplier = NEW_YORK_SESSION_SIZE_MULTIPLIER
    elif session_state == "london":
        session_policy_state = "london_normal_size"
        session_size_multiplier = LONDON_SESSION_SIZE_MULTIPLIER

    macro_root = Path(memory_root) / "macro_state"
    correlation_regime = _compute_correlation_regime(
        macro_root=macro_root,
        latest_time=last_bar_time,
        xau_return=price_change,
        dxy_change=dxy_change if bool(alpha_state.get("available", False)) else None,
        us10y_change=yield_change if bool(fred_state.get("DGS10", {}).get("available", False)) else None,
    )

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
    size_multiplier *= session_size_multiplier
    if is_friday_afternoon:
        risk_reasons.append("friday_afternoon_trading_disabled")
    upcoming_major_events_60m = int(calendar_state.get("metrics", {}).get("upcoming_major_events_60m", 0) or 0)
    recent_major_events_30m = int(calendar_state.get("metrics", {}).get("recent_major_events_30m", 0) or 0)
    if upcoming_major_events_60m > 0:
        size_multiplier *= NEWS_BLACKOUT_SIZE_MULTIPLIER
        risk_reasons.append("news_blackout_before_major_event")
    elif recent_major_events_30m > 0:
        size_multiplier *= NEWS_POST_RELEASE_SIZE_MULTIPLIER
        risk_reasons.append("size_reduced_post_major_release")
    if major_round_state.get("state") == "near_major_round_number":
        size_multiplier *= 0.7
        risk_reasons.append("near_major_round_number")
    if bool(correlation_regime.get("break_detected", False)):
        size_multiplier *= CORRELATION_BREAK_SIZE_MULTIPLIER
        confidence_penalty += CORRELATION_BREAK_CONFIDENCE_PENALTY
        risk_reasons.append("correlation_regime_break_detected")

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
    if not bool(comex_oi_state.get("available", False)):
        feed_unavailable.append("comex_open_interest")
    if not bool(etf_flow_state.get("available", False)):
        feed_unavailable.append("gold_etf_flows")
    if not bool(option_magnet_state.get("available", False)):
        feed_unavailable.append("gold_option_magnet_levels")
    if not bool(physical_premium_state.get("available", False)):
        feed_unavailable.append("gold_physical_premium_discount")
    if not bool(central_bank_reserve_state.get("available", False)):
        feed_unavailable.append("central_bank_gold_reserves")
    if feed_unavailable:
        confidence_penalty += min(FEED_UNAVAILABLE_CONFIDENCE_CAP, FEED_UNAVAILABLE_CONFIDENCE_STEP * len(feed_unavailable))
        risk_reasons.append(f"feeds_unavailable:{','.join(sorted(feed_unavailable))}")

    feed_stale_or_unsafe = (
        bool(alpha_state.get("stale", False))
        and bool(fred_state.get("DGS10", {}).get("stale", False))
        and bool(fred_state.get("T10YIE", {}).get("stale", False))
    )
    pause_trading = bool(feed_stale_or_unsafe) or bool(is_friday_afternoon) or bool(upcoming_major_events_60m > 0)
    if feed_stale_or_unsafe:
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
        "correlation_regime_break_detector": {
            "state": str(correlation_regime.get("state", "insufficient_data")),
            "active": bool(correlation_regime.get("break_detected", False)),
            "metrics": {
                "xau_dxy_corr": correlation_regime.get("rolling_correlations", {}).get("xau_dxy"),
                "xau_us10y_corr": correlation_regime.get("rolling_correlations", {}).get("xau_us10y"),
                "reasons": correlation_regime.get("break_reasons", []),
            },
        },
    }

    trade_tags = {
        "session": session_state,
        "volatility_regime": volatility_regime,
        "macro_state": (
            "risk_off" if dxy_state == "strong_usd" and macro_states["yield_state"] in {"bearish_gold", "steepening"} else "balanced"
        ),
        "dxy_state": macro_states["dxy_state"],
        "yield_state": macro_states["yield_state"],
        "event_news_state": macro_states["event_news_state"],
        "round_number_proximity": round_number_state["state"],
        "correlation_regime_state": str(correlation_regime.get("state", "insufficient_data")),
        "major_round_number_proximity": major_round_state["state"],
        "event_type": str(calendar_state.get("metrics", {}).get("event_type", "unknown")),
        "session_policy": session_policy_state,
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
            "comex_open_interest": comex_oi_state,
            "gold_etf_flows": etf_flow_state,
            "gold_option_magnet_levels": option_magnet_state,
            "gold_physical_premium_discount": physical_premium_state,
            "central_bank_gold_reserves": central_bank_reserve_state,
        },
        "macro_states": macro_states,
        "detectors": detectors,
        "risk_behavior": risk_behavior,
        "trade_tags": trade_tags,
        "round_number": round_number_state,
        "major_round_number": major_round_state,
        "session_policy": {
            "state": session_policy_state,
            "size_multiplier": round(session_size_multiplier, 4),
            "friday_afternoon_disabled": is_friday_afternoon,
        },
        "news_policy": {
            "pause_before_major_events": upcoming_major_events_60m > 0,
            "reduce_after_major_release": recent_major_events_30m > 0,
            "event_type": str(calendar_state.get("metrics", {}).get("event_type", "unknown")),
        },
        "correlation_regime": correlation_regime,
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
                "comex_open_interest": bool(comex_oi_state.get("available", False)),
                "gold_etf_flows": bool(etf_flow_state.get("available", False)),
                "gold_option_magnet_levels": bool(option_magnet_state.get("available", False)),
                "gold_physical_premium_discount": bool(physical_premium_state.get("available", False)),
                "central_bank_gold_reserves": bool(central_bank_reserve_state.get("available", False)),
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
