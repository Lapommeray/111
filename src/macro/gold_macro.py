from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

from src.macro.adapters import (
    AlphaVantageAdapter,
    CentralBankReserveAdapter,
    COMEXOpenInterestAdapter,
    EconomicCalendarAdapter,
    FREDAdapter,
    GoldEtfFlowsAdapter,
    MT5DXYProxyAdapter,
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
CORRELATION_BREAK_SIZE_MULTIPLIER = 0.65
CORRELATION_BREAK_CONFIDENCE_PENALTY = 0.07
DEFAULT_NEGATIVE_CORRELATION = -0.5
DEFAULT_POSITIVE_CORRELATION = 0.5
HIGH_REAL_RATE_THRESHOLD = 1.6
LOW_REAL_RATE_THRESHOLD = 0.2
CORRELATION_STRONG_INVERSE = -0.6
CORRELATION_BREAKDOWN = -0.3
CORRELATION_FLIP = 0.0
CORRELATION_MAJOR_WARNING = 0.3
CORRELATION_DELTA_CUT_TRIGGER = 0.4
CORRELATION_MAJOR_WARNING_SIZE_MULTIPLIER = 0.3
CORRELATION_MAJOR_WARNING_CONFIDENCE_PENALTY = 0.1
STOP_HUNT_LOOKBACK = 20
STOP_HUNT_REVERSION_SIZE_MULTIPLIER = 0.85
STOP_HUNT_REVERSION_CONFIDENCE_BONUS = 0.02
LONDON_FIX_SPIKE_THRESHOLD = 0.0012
LONDON_FIX_REVERSAL_SIZE_MULTIPLIER = 0.75
ROUND_CLUSTER_ZONE_B_MIN = 0.5
ROUND_CLUSTER_ZONE_B_MAX = 1.5
ROUND_CLUSTER_ZONE_C_MIN = 2.0
ROUND_CLUSTER_ZONE_C_MAX = 3.0
ROUND_CLUSTER_REVERSION_CONFIDENCE_BONUS = 0.03
TOKYO_VACUUM_SPREAD_FACTOR = 1.8
TOKYO_VACUUM_TICK_VELOCITY_FACTOR = 0.6
TOKYO_VACUUM_AUTOPAUSE_SECONDS = 600
BLOWOFF_RETURN_THRESHOLD = 0.0022
BLOWOFF_VOLUME_RATIO_THRESHOLD = 1.35
BLOWOFF_WICK_RATIO_THRESHOLD = 0.35
BLOWOFF_SIZE_MULTIPLIER = 0.65
NFP_PRE_EVENT_SIZE_MULTIPLIER = 0.7
NFP_POST_BLOCK_SECONDS = 120
NFP_POST_WATCH_SECONDS = 300
NFP_POST_RELEASE_SIZE_MULTIPLIER = 0.8
ARCHAEOLOGY_MIN_BARS = 90
ARCHAEOLOGY_MAX_BARS = 180
ARCHAEOLOGY_RANGE_THRESHOLD = 0.0015
ARCHAEOLOGY_MIN_SPAN_BARS = 12
ARCHAEOLOGY_REVISIT_DISTANCE = 1.8
GAMMA_PROXY_STRIKES = [1850.0, 1900.0, 1950.0, 2000.0, 2050.0]
GAMMA_PROXY_STRIKE_DISTANCE = 1.8
GAMMA_PROXY_ACCELERATION_THRESHOLD = 0.0018


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _bar_close(bar: dict[str, Any]) -> float:
    return _safe_float(bar.get("close"), 0.0)


def _bar_high(bar: dict[str, Any]) -> float:
    high = _safe_float(bar.get("high"), 0.0)
    if high > 0:
        return high
    return _bar_close(bar)


def _bar_low(bar: dict[str, Any]) -> float:
    low = _safe_float(bar.get("low"), 0.0)
    if low > 0:
        return low
    return _bar_close(bar)


def _bar_open(bar: dict[str, Any]) -> float:
    value = _safe_float(bar.get("open"), 0.0)
    if value != 0.0:
        return value
    return _bar_close(bar)


def _bar_volume(bar: dict[str, Any]) -> float:
    value = _safe_float(bar.get("volume"), 0.0)
    if value > 0:
        return value
    value = _safe_float(bar.get("tick_volume"), 0.0)
    return max(0.0, value)


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


def _feed_registry_entry(*, feed_name: str, state: dict[str, Any], fallback_state: str) -> dict[str, Any]:
    available = bool(state.get("available", False))
    status = str(state.get("status", "available" if available else "unavailable"))
    health_status = str(state.get("health_status", "healthy" if available else "degraded"))
    return {
        "feed_name": feed_name,
        "status": status,
        "health_status": health_status,
        "last_update_timestamp": str(state.get("last_update_timestamp") or state.get("timestamp") or datetime.now(tz=timezone.utc).isoformat()),
        "symbol_scope": "XAUUSD",
        "data_confidence": float(state.get("data_confidence", 0.8 if available else 0.35)),
        "fallback_state": fallback_state,
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
            "tier": "insufficient_data",
        }

    prior = previous_corr
    if prior is None:
        prior = DEFAULT_NEGATIVE_CORRELATION if expected_sign < 0 else DEFAULT_POSITIVE_CORRELATION
    corr_delta = current_corr - prior
    tier = "strong_inverse_regime"
    if current_corr > CORRELATION_MAJOR_WARNING:
        tier = "major_warning"
    elif current_corr > CORRELATION_FLIP:
        tier = "flip"
    elif current_corr > CORRELATION_BREAKDOWN:
        tier = "breakdown"
    elif current_corr < CORRELATION_STRONG_INVERSE:
        tier = "strong_inverse_regime"
    else:
        tier = "normal_inverse_regime"

    sign_flip = current_corr > CORRELATION_FLIP
    breakdown = current_corr > CORRELATION_BREAKDOWN
    major_warning = current_corr > CORRELATION_MAJOR_WARNING
    roc_trigger = corr_delta > CORRELATION_DELTA_CUT_TRIGGER
    break_detected = bool(breakdown or sign_flip or major_warning or roc_trigger)
    state = "correlation_break_detected" if break_detected else "correlation_stable"
    reason = "stable"
    if major_warning:
        reason = "major_warning"
    elif sign_flip:
        reason = "flip"
    elif breakdown:
        reason = "breakdown"
    elif roc_trigger:
        reason = "rate_of_change_trigger"
    return {
        "break_detected": break_detected,
        "state": state,
        "reason": reason,
        "expected_sign": expected_sign,
        "tier": tier,
        "corr_delta_short": round(corr_delta, 6),
        "roc_trigger": roc_trigger,
        "major_warning": major_warning,
        "breakdown": breakdown,
        "flip": sign_flip,
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

    dxy_break = bool(dxy_shift["break_detected"])
    yield_break = bool(us10y_shift["break_detected"])
    confirmation = "dual_stable"
    if dxy_break and yield_break:
        confirmation = "dual_break"
    elif dxy_break:
        confirmation = "dxy_break_only"
    elif yield_break:
        confirmation = "yield_break_only"

    break_detected = bool(dxy_break or yield_break)
    state = "correlation_break_detected" if break_detected else (
        "insufficient_data" if current_corr_dxy is None and current_corr_us10y is None else "correlation_stable"
    )
    break_reasons = []
    if dxy_break:
        break_reasons.append(f"xau_dxy:{dxy_shift['reason']}")
    if yield_break:
        break_reasons.append(f"xau_us10y:{us10y_shift['reason']}")
    if confirmation != "dual_stable":
        break_reasons.append(f"confirmation:{confirmation}")

    correlation_state = {
        "state": state,
        "break_detected": break_detected,
        "confirmation": confirmation,
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
        "correlation_regime_tags": normalize_reasons(break_reasons),
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


def _detect_stop_hunt_footprint(*, bars: list[dict[str, Any]], macro_root: Path) -> dict[str, Any]:
    state_path = macro_root / "stop_hunt_state.json"
    state_payload = read_json_safe(state_path, default={"swept_levels": {}})
    if not isinstance(state_payload, dict):
        state_payload = {"swept_levels": {}}
    swept_levels = state_payload.get("swept_levels", {})
    if not isinstance(swept_levels, dict):
        swept_levels = {}

    if len(bars) < STOP_HUNT_LOOKBACK + 1:
        result = {"state": "insufficient_data", "active": False, "events": [], "favorite_zones": []}
        write_json_atomic(state_path, {"swept_levels": swept_levels, "last": result})
        return result

    last_bar = bars[-1]
    recent = bars[-(STOP_HUNT_LOOKBACK + 1) : -1]
    recent_high = max(_bar_high(bar) for bar in recent)
    recent_low = min(_bar_low(bar) for bar in recent)
    events: list[dict[str, Any]] = []
    if _bar_high(last_bar) > recent_high and _bar_close(last_bar) < recent_high:
        key = f"{round(recent_high, 2)}"
        swept_levels[key] = int(swept_levels.get(key, 0)) + 1
        events.append({"type": "upside_sweep", "level": round(recent_high, 4), "opposite_bias": "sell"})
    if _bar_low(last_bar) < recent_low and _bar_close(last_bar) > recent_low:
        key = f"{round(recent_low, 2)}"
        swept_levels[key] = int(swept_levels.get(key, 0)) + 1
        events.append({"type": "downside_sweep", "level": round(recent_low, 4), "opposite_bias": "buy"})

    favorite_zones = sorted(
        [{"level": float(level), "sweeps": count} for level, count in swept_levels.items()],
        key=lambda item: item["sweeps"],
        reverse=True,
    )[:5]
    result = {
        "state": "sweep_detected" if events else "no_sweep",
        "active": bool(events),
        "events": events,
        "favorite_zones": favorite_zones,
    }
    write_json_atomic(state_path, {"swept_levels": swept_levels, "last": result})
    return result


def _detect_london_fix_imbalance(*, bars: list[dict[str, Any]], bar_dt: datetime) -> dict[str, Any]:
    if not bars:
        return {"state": "insufficient_data", "active": False, "partial": True}
    # London PM fix at 15:00 UTC modeled with a 14:45-15:15 UTC liquidity-impact window.
    current_mins = bar_dt.hour * 60 + bar_dt.minute
    in_fix_window = (14 * 60 + 45) <= current_mins <= (15 * 60 + 15)
    if not in_fix_window or len(bars) < 12:
        return {"state": "outside_fix_window", "active": False, "partial": False}

    recent = bars[-12:]
    fix_level = median(_bar_close(bar) for bar in recent[:6])
    pre_fix = recent[:6]
    around_fix = recent[6:9]
    post_fix = recent[9:]
    pre_fix_range = max(_bar_high(bar) for bar in pre_fix) - min(_bar_low(bar) for bar in pre_fix)
    spike = max(abs((_bar_close(bar) - fix_level) / fix_level) for bar in around_fix) if fix_level else 0.0
    reversal = False
    if post_fix:
        reversal = any((_bar_close(bar) - fix_level) * (_bar_close(around_fix[-1]) - fix_level) < 0 for bar in post_fix)
    state = "fix_imbalance_detected" if spike > LONDON_FIX_SPIKE_THRESHOLD and reversal else "fix_orderly"
    return {
        "state": state,
        "active": state == "fix_imbalance_detected",
        "fix_level": round(fix_level, 4),
        "pre_fix_liquidity_thinning": round(pre_fix_range, 6),
        "fix_spike": round(spike, 6),
        "reversal_through_fix": reversal,
    }


def _round_number_stop_cluster_map(*, bars: list[dict[str, Any]], round_number_state: dict[str, Any]) -> dict[str, Any]:
    nearest_level = round_number_state.get("nearest_level")
    if not isinstance(nearest_level, (int, float)) or len(bars) < 4:
        return {"state": "insufficient_data", "active": False}
    level = float(nearest_level)
    touched_zone = "zone_a"
    quick_reversal = False
    for bar in bars[-4:]:
        dist = abs(_bar_close(bar) - level)
        if ROUND_CLUSTER_ZONE_B_MIN <= dist <= ROUND_CLUSTER_ZONE_B_MAX:
            touched_zone = "zone_b"
        elif ROUND_CLUSTER_ZONE_C_MIN <= dist <= ROUND_CLUSTER_ZONE_C_MAX:
            touched_zone = "zone_c"
    if touched_zone == "zone_b":
        latest = bars[-1]
        prior = bars[-2]
        quick_reversal = abs(_bar_close(latest) - level) < abs(_bar_close(prior) - level)
    state = "zone_b_sweep_reversion" if touched_zone == "zone_b" and quick_reversal else f"{touched_zone}_interaction"
    return {
        "state": state,
        "active": touched_zone in {"zone_b", "zone_c"},
        "nearest_round_level": round(level, 4),
        "first_hit_zone": touched_zone,
        "zone_b_quick_reversal": quick_reversal,
    }


def _session_transition_volatility_decay(*, bars: list[dict[str, Any]], bar_dt: datetime, session_state: str) -> dict[str, Any]:
    if len(bars) < 24:
        return {"state": "insufficient_data", "active": False, "partial": True, "size_multiplier": 1.0, "confidence_penalty": 0.0}
    returns = []
    for idx in range(1, min(61, len(bars))):
        prev = _bar_close(bars[-idx - 1])
        cur = _bar_close(bars[-idx])
        if prev != 0:
            returns.append(abs((cur - prev) / prev))
    short_vol = sum(returns[:12]) / max(1, len(returns[:12]))
    long_vol = sum(returns) / max(1, len(returns))
    ratio = short_vol / long_vol if long_vol > 0 else 1.0
    hour = bar_dt.hour
    transition = "none"
    if hour in {7, 8}:
        transition = "asia_to_london"
    elif hour in {12, 13}:
        transition = "london_to_newyork"
    decay = ratio < 0.85
    size_multiplier = 0.9 if transition != "none" and not decay else 0.8 if transition != "none" else 1.0
    confidence_penalty = 0.03 if transition != "none" and ratio > 1.25 else 0.0
    return {
        "state": "transition_decay" if decay and transition != "none" else "transition_expansion" if transition != "none" else "session_stable",
        "active": transition != "none",
        "transition": transition,
        "session": session_state,
        "volatility_ratio": round(ratio, 6),
        "size_multiplier": size_multiplier,
        "confidence_penalty": confidence_penalty,
    }


def _tokyo_open_liquidity_vacuum(*, bars: list[dict[str, Any]], bar_dt: datetime) -> dict[str, Any]:
    if len(bars) < 20:
        return {"state": "insufficient_data", "active": False, "partial": True}
    tokyo_window = bar_dt.hour in {0, 1}
    spreads = [_safe_float(bar.get("spread"), 0.0) for bar in bars[-20:]]
    spread_known = any(item > 0 for item in spreads)
    spread_series = [item for item in spreads if item > 0]
    spread_median = median(spread_series) if spread_series else 0.0
    spread_now = spread_series[-1] if spread_series else 0.0
    volumes = [_bar_volume(bar) for bar in bars[-20:]]
    volume_median = median(volumes[:-1]) if len(volumes) > 1 else 0.0
    volume_now = volumes[-1] if volumes else 0.0
    spread_expand = spread_now > (spread_median * TOKYO_VACUUM_SPREAD_FACTOR) if spread_median > 0 else False
    velocity_collapse = volume_now < (volume_median * TOKYO_VACUUM_TICK_VELOCITY_FACTOR) if volume_median > 0 else False
    active = bool(tokyo_window and spread_expand and velocity_collapse)
    return {
        "state": "tokyo_liquidity_vacuum" if active else "tokyo_normal_liquidity",
        "active": active,
        "partial": not spread_known,
        "auto_pause_seconds": TOKYO_VACUUM_AUTOPAUSE_SECONDS if active else 0,
        "spread_now": round(spread_now, 6),
        "spread_median": round(spread_median, 6),
        "tick_velocity_now": round(volume_now, 6),
        "tick_velocity_median": round(volume_median, 6),
    }


def _blowoff_top_fingerprint(*, bars: list[dict[str, Any]]) -> dict[str, Any]:
    if len(bars) < 6:
        return {"state": "insufficient_data", "active": False}
    seq = bars[-6:]
    price_start = _bar_close(seq[0])
    price_end = _bar_close(seq[-2])
    price_jump = ((price_end - price_start) / price_start) if price_start else 0.0
    volumes = [_bar_volume(bar) for bar in seq]
    avg_volume = sum(volumes[:-1]) / max(1, len(volumes[:-1]))
    vol_ratio = (volumes[-2] / avg_volume) if avg_volume > 0 else 1.0
    candle = seq[-2]
    body_high = max(_bar_open(candle), _bar_close(candle))
    upper_wick = max(0.0, _bar_high(candle) - body_high)
    total_range = max(1e-9, _bar_high(candle) - _bar_low(candle))
    wick_ratio = upper_wick / total_range
    close_position = (_bar_close(candle) - _bar_low(candle)) / total_range
    next_lower_high = _bar_high(seq[-1]) < _bar_high(candle)
    active = (
        price_jump > BLOWOFF_RETURN_THRESHOLD
        and vol_ratio > BLOWOFF_VOLUME_RATIO_THRESHOLD
        and wick_ratio > BLOWOFF_WICK_RATIO_THRESHOLD
        and close_position < 0.4
        and next_lower_high
    )
    return {
        "state": "blowoff_top_detected" if active else "no_blowoff",
        "active": active,
        "price_jump": round(price_jump, 6),
        "volume_ratio": round(vol_ratio, 6),
        "upper_wick_ratio": round(wick_ratio, 6),
        "close_bottom_fraction": round(close_position, 6),
        "next_candle_lower_high": next_lower_high,
    }


def _next_nfp_timestamp(reference: datetime) -> datetime:
    # NFP proxy schedule: first Friday monthly at 13:30 UTC (08:30 ET), found by scanning from day 1.
    probe = datetime(reference.year, reference.month, 1, 13, 30, tzinfo=timezone.utc)
    while probe.weekday() != 4:
        probe += timedelta(days=1)
    if probe < reference - timedelta(hours=24):
        month = reference.month + 1
        year = reference.year
        if month > 12:
            month = 1
            year += 1
        probe = datetime(year, month, 1, 13, 30, tzinfo=timezone.utc)
        while probe.weekday() != 4:
            probe += timedelta(days=1)
    return probe


def _nfp_front_run_layer(*, bars: list[dict[str, Any]], bar_dt: datetime) -> dict[str, Any]:
    nfp_ts = _next_nfp_timestamp(bar_dt)
    secs_to_nfp = (nfp_ts - bar_dt).total_seconds()
    phase = "normal"
    size_multiplier = 1.0
    pause_trading = False
    if 0 <= secs_to_nfp <= 900:
        phase = "nfp_pre_15m"
        size_multiplier = NFP_PRE_EVENT_SIZE_MULTIPLIER
    elif -NFP_POST_BLOCK_SECONDS <= secs_to_nfp < 0:
        phase = "nfp_post_0_2m_block"
        pause_trading = True
    elif -(NFP_POST_WATCH_SECONDS) <= secs_to_nfp < -NFP_POST_BLOCK_SECONDS:
        phase = "nfp_post_2_5m_watch"
        size_multiplier = NFP_POST_RELEASE_SIZE_MULTIPLIER
    elif secs_to_nfp < -NFP_POST_WATCH_SECONDS and secs_to_nfp > -(6 * 3600):
        phase = "nfp_post_5m_reentry_window"
        size_multiplier = 0.9

    drift = 0.0
    if bars:
        lookback = min(len(bars), 288)
        start = _bar_close(bars[-lookback])
        end = _bar_close(bars[-1])
        if start != 0:
            drift = (end - start) / start
    return {
        "state": phase,
        "active": phase != "normal",
        "nfp_timestamp": nfp_ts.isoformat(),
        "seconds_to_nfp": int(secs_to_nfp),
        "pre_nfp_24h_drift": round(drift, 6),
        "size_multiplier": size_multiplier,
        "pause_trading": pause_trading,
    }


def _price_archaeologist_layer(*, bars: list[dict[str, Any]], macro_root: Path, last_price: float) -> dict[str, Any]:
    state_path = macro_root / "price_archaeologist_state.json"
    state_payload = read_json_safe(state_path, default={"zones": []})
    if not isinstance(state_payload, dict):
        state_payload = {"zones": []}
    zones = state_payload.get("zones", [])
    if not isinstance(zones, list):
        zones = []

    segment = bars[-ARCHAEOLOGY_MAX_BARS:]
    if len(segment) >= ARCHAEOLOGY_MIN_BARS:
        chunk = segment[-ARCHAEOLOGY_MIN_BARS:]
        closes = [_bar_close(bar) for bar in chunk]
        mean = sum(closes) / max(1, len(closes))
        high = max(closes)
        low = min(closes)
        range_ratio = ((high - low) / mean) if mean else 0.0
        if range_ratio <= ARCHAEOLOGY_RANGE_THRESHOLD:
            zones.append(
                {
                    "midpoint": round((high + low) / 2.0, 4),
                    "range_ratio": round(range_ratio, 6),
                    "span_bars": len(chunk),
                    "logged_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )
    zones = zones[-50:]
    revisits = [zone for zone in zones if abs(last_price - _safe_float(zone.get("midpoint"), 0.0)) <= ARCHAEOLOGY_REVISIT_DISTANCE]
    result = {
        "state": "structural_magnet_revisit" if revisits else "no_revisit",
        "active": bool(revisits),
        "partial": len(segment) < ARCHAEOLOGY_MIN_BARS,
        "zones": zones,
        "revisit_candidates": revisits[:5],
    }
    write_json_atomic(state_path, {"zones": zones, "last": result})
    return result


def _dealer_gamma_flip_proxy(*, bars: list[dict[str, Any]], last_price: float) -> dict[str, Any]:
    nearest = min(GAMMA_PROXY_STRIKES, key=lambda strike: abs(strike - last_price))
    distance = abs(nearest - last_price)
    momentum = 0.0
    acceleration = 0.0
    if len(bars) >= 3:
        r1 = _price_change(bars[-3:-1])
        r2 = _price_change(bars[-2:])
        momentum = r2
        acceleration = r2 - r1
    near_strike = distance <= GAMMA_PROXY_STRIKE_DISTANCE
    short_gamma = near_strike and acceleration > GAMMA_PROXY_ACCELERATION_THRESHOLD
    long_gamma_cap = near_strike and abs(acceleration) <= (GAMMA_PROXY_ACCELERATION_THRESHOLD * 0.2)
    state = "short_gamma_extension_proxy" if short_gamma else "long_gamma_cap_proxy" if long_gamma_cap else "neutral_proxy"
    return {
        "state": state,
        "active": near_strike,
        "proxy": True,
        "partial": True,
        "nearest_strike": nearest,
        "distance_to_strike": round(distance, 6),
        "momentum": round(momentum, 6),
        "acceleration": round(acceleration, 6),
    }


def collect_xauusd_macro_state(
    *,
    memory_root: str,
    bars: list[dict[str, Any]],
    session_state: str,
    volatility_regime: str,
    config: MacroFeedConfig,
) -> dict[str, Any]:
    if config.enabled:
        dxy_proxy_state = MT5DXYProxyAdapter().fetch_state(memory_root=memory_root)
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
        dxy_proxy_state = _feed_disabled_state("dxy_proxy", "external_fetch_disabled")
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

    primary_dxy_state = dxy_proxy_state if bool(dxy_proxy_state.get("available", False)) else alpha_state
    dxy_change = float(primary_dxy_state.get("metrics", {}).get("usd_proxy_change", 0.0) or 0.0)
    dxy_state = str(primary_dxy_state.get("state", "unavailable"))
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
    stop_hunt_state = _detect_stop_hunt_footprint(bars=bars, macro_root=macro_root)
    london_fix_state = _detect_london_fix_imbalance(bars=bars, bar_dt=bar_dt)
    round_cluster_state = _round_number_stop_cluster_map(bars=bars, round_number_state=round_number_state)
    transition_decay_state = _session_transition_volatility_decay(bars=bars, bar_dt=bar_dt, session_state=session_state)
    tokyo_vacuum_state = _tokyo_open_liquidity_vacuum(bars=bars, bar_dt=bar_dt)
    blowoff_state = _blowoff_top_fingerprint(bars=bars)
    nfp_state = _nfp_front_run_layer(bars=bars, bar_dt=bar_dt)
    archaeology_state = _price_archaeologist_layer(bars=bars, macro_root=macro_root, last_price=last_price)
    gamma_proxy_state = _dealer_gamma_flip_proxy(bars=bars, last_price=last_price)
    gld_flow = etf_flow_state.get("metrics", {}).get("gld_flow")
    gld_flow_state = "unavailable"
    gld_confidence_adjustment = 0.0
    if isinstance(gld_flow, (int, float)):
        if gld_flow > 0:
            gld_flow_state = "gld_inflow"
            gld_confidence_adjustment = -0.01
        elif gld_flow < 0:
            gld_flow_state = "gld_outflow"
            gld_confidence_adjustment = 0.01
        else:
            gld_flow_state = "gld_neutral"
    elif bool(etf_flow_state.get("available", False)):
        gld_flow_state = "degraded"

    size_multiplier = 1.0
    confidence_penalty = 0.0
    confidence_bonus = 0.0
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
    if (
        correlation_regime.get("confirmation") == "dual_break"
        and (
            correlation_regime.get("pairs", {}).get("xau_dxy", {}).get("major_warning")
            or correlation_regime.get("pairs", {}).get("xau_us10y", {}).get("major_warning")
        )
    ):
        size_multiplier *= CORRELATION_MAJOR_WARNING_SIZE_MULTIPLIER
        confidence_penalty += CORRELATION_MAJOR_WARNING_CONFIDENCE_PENALTY
        risk_reasons.append("correlation_major_warning_cap")
    if (
        correlation_regime.get("pairs", {}).get("xau_dxy", {}).get("roc_trigger")
        or correlation_regime.get("pairs", {}).get("xau_us10y", {}).get("roc_trigger")
    ):
        size_multiplier *= 0.7
        risk_reasons.append("correlation_roc_immediate_cut")
    if stop_hunt_state.get("active"):
        size_multiplier *= STOP_HUNT_REVERSION_SIZE_MULTIPLIER
        confidence_bonus += STOP_HUNT_REVERSION_CONFIDENCE_BONUS
        risk_reasons.append("stop_hunt_sweep_detected")
    if london_fix_state.get("active"):
        size_multiplier *= LONDON_FIX_REVERSAL_SIZE_MULTIPLIER
        confidence_penalty += 0.03
        risk_reasons.append("london_fix_imbalance")
    if round_cluster_state.get("state") == "zone_b_sweep_reversion":
        confidence_bonus += ROUND_CLUSTER_REVERSION_CONFIDENCE_BONUS
        risk_reasons.append("round_cluster_zone_b_reversion")
    transition_size = _safe_float(transition_decay_state.get("size_multiplier"), 1.0)
    transition_penalty = _safe_float(transition_decay_state.get("confidence_penalty"), 0.0)
    size_multiplier *= transition_size
    confidence_penalty += transition_penalty
    if transition_decay_state.get("active"):
        risk_reasons.append(f"session_transition:{transition_decay_state.get('state')}")
    if tokyo_vacuum_state.get("active"):
        size_multiplier *= 0.6
        confidence_penalty += 0.06
        risk_reasons.append("tokyo_liquidity_vacuum")
    if blowoff_state.get("active"):
        size_multiplier *= BLOWOFF_SIZE_MULTIPLIER
        confidence_penalty += 0.05
        risk_reasons.append("blowoff_top_fingerprint")
    if nfp_state.get("active"):
        size_multiplier *= _safe_float(nfp_state.get("size_multiplier"), 1.0)
        if str(nfp_state.get("state")) == "nfp_post_2_5m_watch":
            confidence_penalty += 0.03
        risk_reasons.append(f"nfp_layer:{nfp_state.get('state')}")
    if archaeology_state.get("active"):
        size_multiplier *= 0.9
        confidence_bonus += 0.02
        risk_reasons.append("price_archaeologist_revisit")
    if gamma_proxy_state.get("state") == "short_gamma_extension_proxy":
        size_multiplier *= 0.85
        confidence_penalty += 0.02
        risk_reasons.append("dealer_gamma_proxy_short_gamma")
    elif gamma_proxy_state.get("state") == "long_gamma_cap_proxy":
        size_multiplier *= 0.9
        risk_reasons.append("dealer_gamma_proxy_long_gamma_cap")
    confidence_penalty += gld_confidence_adjustment
    if not bool(dxy_proxy_state.get("available", False)):
        confidence_penalty += 0.03
        risk_reasons.append("dxy_proxy_degraded_fallback_alpha")

    feed_unavailable = []
    if not bool(dxy_proxy_state.get("available", False)):
        feed_unavailable.append("dxy_proxy")
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
        risk_reasons.append("gld_flow_optional_unavailable")
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
    pause_seconds = 0
    if bool(tokyo_vacuum_state.get("active")):
        pause_trading = True
        pause_seconds = max(pause_seconds, int(tokyo_vacuum_state.get("auto_pause_seconds", TOKYO_VACUUM_AUTOPAUSE_SECONDS)))
    if bool(nfp_state.get("pause_trading")):
        pause_trading = True
        pause_seconds = max(pause_seconds, NFP_POST_BLOCK_SECONDS)
    if feed_stale_or_unsafe:
        risk_reasons.append("macro_feed_state_unsafe_or_stale")

    macro_states = {
        "dxy_state": dxy_state,
        "yield_state": _derive_yield_state(yield_pressure=yield_pressure, curve_10y_2y=curve_10y_2y),
        "inflation_real_rate_state": real_rate_state if real_rate_state != "unknown" else ("inflation_rising" if inflation_change > 0.03 else "inflation_stable"),
        "event_news_state": event_state,
        "gld_flow_state": gld_flow_state,
    }
    feed_registry = {
        "dxy_proxy": _feed_registry_entry(feed_name="dxy_proxy", state=dxy_proxy_state, fallback_state="alpha_vantage_dxy_proxy"),
        "gld_flow": _feed_registry_entry(feed_name="gld_flow", state=etf_flow_state, fallback_state="optional_no_hard_dependency"),
    }
    feed_health_status = "healthy"
    if any(entry["health_status"] == "degraded" for entry in feed_registry.values()):
        feed_health_status = "degraded"
    if all(entry["status"] == "unavailable" for entry in feed_registry.values()):
        feed_health_status = "unavailable"
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
                "confirmation": correlation_regime.get("confirmation"),
            },
        },
        "stop_hunt_footprint_analyzer": stop_hunt_state,
        "london_fix_imbalance_detector": london_fix_state,
        "round_number_stop_cluster_map": round_cluster_state,
        "session_transition_volatility_decay_model": transition_decay_state,
        "tokyo_open_liquidity_vacuum_detector": tokyo_vacuum_state,
        "blowoff_top_fingerprint": blowoff_state,
        "nfp_front_run_layer": nfp_state,
        "price_archaeologist_layer": archaeology_state,
        "dealer_gamma_flip_proxy": gamma_proxy_state,
    }
    active_surgical_layers = [
        name
        for name, payload in detectors.items()
        if isinstance(payload, dict) and bool(payload.get("active", False))
    ]

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
        "correlation_confirmation": str(correlation_regime.get("confirmation", "dual_stable")),
        "surgical_layer_triggers": active_surgical_layers,
        "dxy_proxy_state": str(dxy_proxy_state.get("state", "unavailable")),
        "gld_flow_state": gld_flow_state,
        "macro_feed_health": feed_health_status,
        "synthetic_feature_state": "sandbox_pending",
        "negative_space_state": "sandbox_pending",
        "invariant_break_state": "sandbox_pending",
        "pain_geometry_risk": 0.0,
        "counterfactual_evaluation": "sandbox_pending",
        "liquidity_decay_state": "sandbox_pending",
    }
    risk_behavior = {
        "size_multiplier": round(clamp(size_multiplier, 0.1, 1.0), 4),
        "confidence_penalty": round(clamp(confidence_penalty - confidence_bonus, 0.0, 0.35), 4),
        "pause_trading": pause_trading,
        "pause_seconds": pause_seconds,
        "reasons": normalize_reasons(risk_reasons),
    }

    macro_state = {
        "feed_states": {
            "dxy_proxy": dxy_proxy_state,
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
        "feed_registry": feed_registry,
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
        "surgical_layers": {
            "stop_hunt_footprint": stop_hunt_state,
            "london_fix_imbalance": london_fix_state,
            "round_number_cluster": round_cluster_state,
            "session_transition_volatility_decay": transition_decay_state,
            "tokyo_open_liquidity_vacuum": tokyo_vacuum_state,
            "blowoff_top_fingerprint": blowoff_state,
            "nfp_front_run": nfp_state,
            "price_archaeologist": archaeology_state,
            "dealer_gamma_flip_proxy": gamma_proxy_state,
        },
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
                "dxy_proxy": bool(dxy_proxy_state.get("available", False)),
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
            "feed_registry_health": feed_health_status,
            "surgical_layer_triggers": active_surgical_layers,
        }
    )
    write_json_atomic(history_path, history[-300:])

    feed_health_latest_path = root / "feed_health_latest.json"
    feed_health_history_path = root / "feed_health_history.json"
    feed_health_payload = {
        "logged_at": macro_state["logged_at"],
        "feed_registry": feed_registry,
        "trade_tags_subset": {
            "dxy_proxy_state": trade_tags["dxy_proxy_state"],
            "gld_flow_state": trade_tags["gld_flow_state"],
            "macro_feed_health": trade_tags["macro_feed_health"],
        },
    }
    write_json_atomic(feed_health_latest_path, feed_health_payload)
    feed_health_history = read_json_safe(feed_health_history_path, default=[])
    if not isinstance(feed_health_history, list):
        feed_health_history = []
    feed_health_history.append(feed_health_payload)
    write_json_atomic(feed_health_history_path, feed_health_history[-500:])

    surgical_latest_path = root / "surgical_layers_latest.json"
    surgical_history_path = root / "surgical_layers_history.json"
    surgical_payload = {
        "logged_at": macro_state["logged_at"],
        "trade_tags": trade_tags,
        "detectors": {
            "correlation_regime": correlation_regime,
            "stop_hunt_footprint": stop_hunt_state,
            "london_fix_imbalance": london_fix_state,
            "round_number_cluster": round_cluster_state,
            "session_transition_volatility_decay": transition_decay_state,
            "tokyo_open_liquidity_vacuum": tokyo_vacuum_state,
            "blowoff_top_fingerprint": blowoff_state,
            "nfp_front_run": nfp_state,
            "price_archaeologist": archaeology_state,
            "dealer_gamma_flip_proxy": gamma_proxy_state,
        },
        "partial_layers": [
            name
            for name, payload in {
                "tokyo_open_liquidity_vacuum": tokyo_vacuum_state,
                "price_archaeologist": archaeology_state,
                "dealer_gamma_flip_proxy": gamma_proxy_state,
            }.items()
            if isinstance(payload, dict) and bool(payload.get("partial", False))
        ],
    }
    write_json_atomic(surgical_latest_path, surgical_payload)
    surgical_history = read_json_safe(surgical_history_path, default=[])
    if not isinstance(surgical_history, list):
        surgical_history = []
    surgical_history.append(surgical_payload)
    write_json_atomic(surgical_history_path, surgical_history[-500:])

    cache_key = str(Path(memory_root).resolve())
    _MACRO_STATE_CACHE[cache_key] = macro_state
    macro_state["paths"] = {
        "latest": str(latest_path),
        "history": str(history_path),
        "surgical_latest": str(surgical_latest_path),
        "surgical_history": str(surgical_history_path),
        "feed_health_latest": str(feed_health_latest_path),
        "feed_health_history": str(feed_health_history_path),
    }
    return macro_state


def get_cached_macro_state(memory_root: str) -> dict[str, Any]:
    return dict(_MACRO_STATE_CACHE.get(str(Path(memory_root).resolve()), {}))
