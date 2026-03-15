from __future__ import annotations

from src.features.liquidity import assess_liquidity_state, detect_liquidity_sweep_state
from src.features.market_structure import classify_market_regime, classify_market_structure
from src.features.sessions import track_session_behavior
from src.features.spread_state import track_execution_quality
from src.features.volatility import detect_compression_expansion_state


def make_bars(count: int, drift: float = 0.2) -> list[dict[str, float]]:
    bars: list[dict[str, float]] = []
    base = 2000.0
    for i in range(count):
        close = base + (i * drift)
        bars.append(
            {
                "time": 1700000000 + (i * 60),
                "open": close - 0.2,
                "high": close + 0.4,
                "low": close - 0.4,
                "close": close,
                "tick_volume": 100 + i,
            }
        )
    return bars


def test_market_structure_insufficient_bars_returns_neutral_range() -> None:
    result = classify_market_structure(make_bars(4), lookback=20)
    assert result["state"] == "range"
    assert result["bias"] == "neutral"
    assert "insufficient_bars" in result["reasons"]


def test_market_structure_uptrend_detected() -> None:
    result = classify_market_structure(make_bars(30), lookback=20)
    assert result["state"] == "trend_up"
    assert result["bias"] == "buy"
    assert result["strength"] > 0.5


def test_liquidity_insufficient_bars_returns_unknown() -> None:
    result = assess_liquidity_state(make_bars(8), lookback=30)
    assert result["liquidity_state"] == "unknown"
    assert result["direction_hint"] == "neutral"


def test_liquidity_sweep_high_returns_sell_hint() -> None:
    bars = make_bars(35)
    recent_high = max(b["high"] for b in bars[-30:-1])
    bars[-1]["high"] = recent_high + 1.0
    bars[-1]["close"] = recent_high - 0.1
    result = assess_liquidity_state(bars, lookback=30)
    assert result["liquidity_state"] == "sweep"
    assert result["sweep"] == "high"
    assert result["direction_hint"] == "sell"


def test_liquidity_sweep_detector_finds_zones_and_confidence() -> None:
    bars = make_bars(40)
    recent_high = max(b["high"] for b in bars[-30:-1])
    bars[-1]["high"] = recent_high + 1.2
    bars[-1]["close"] = recent_high - 0.2
    bars[-1]["tick_volume"] = bars[-2]["tick_volume"] * 2.0
    result = detect_liquidity_sweep_state(bars, lookback=30)
    assert result["module"] == "liquidity_sweep"
    assert result["state"] == "computed"
    assert result["direction_vote"] == "sell"
    assert result["confidence_level"] in {"medium", "high"}
    assert result["metrics"]["liquidity_zones"]


def test_compression_expansion_detector_reports_breakout_probability() -> None:
    bars = make_bars(28)
    for idx in range(8, 27):
        center = bars[idx]["close"]
        bars[idx]["high"] = center + 0.1
        bars[idx]["low"] = center - 0.1
        bars[idx]["open"] = center - 0.02
        bars[idx]["close"] = center + 0.02
    bars[-1]["high"] = bars[-1]["close"] + 0.9
    bars[-1]["low"] = bars[-1]["close"] - 0.1
    result = detect_compression_expansion_state(bars, lookback=20)
    assert result["module"] == "compression_expansion"
    assert "breakout_probability" in result["metrics"]
    assert 0.0 <= result["metrics"]["breakout_probability"] <= 1.0
    assert result["confidence_level"] in {"low", "medium", "high"}


def test_session_behavior_tracker_learns_from_outcomes() -> None:
    bars = make_bars(35)
    bars[-1]["time"] = 4_000_000_000
    outcomes = [
        {"status": "closed", "result": "win", "timestamp": "2026-03-15T08:30:00+00:00"},
        {"status": "closed", "result": "loss", "timestamp": "2026-03-15T08:50:00+00:00"},
        {"status": "closed", "result": "win", "timestamp": "2026-03-15T08:59:00+00:00"},
    ]
    result = track_session_behavior(bars, outcomes)
    assert result["module"] == "session_behavior"
    assert "session_stats" in result["metrics"]
    assert result["confidence_level"] in {"low", "medium", "high"}


def test_market_regime_classifier_confidence_and_state() -> None:
    structure = {"state": "trend_up", "bias": "buy", "strength": 0.8}
    volatility = {"state": "balanced", "metrics": {"ratio": 1.0}}
    result = classify_market_regime(structure, volatility)
    assert result["module"] == "market_regime"
    assert result["state"] == "trend"
    assert result["direction_vote"] == "buy"
    assert result["confidence_delta"] > 0
    assert result["confidence_level"] in {"medium", "high"}


def test_execution_quality_tracker_reports_slippage_spread_and_timing() -> None:
    bars = make_bars(10)
    bars[-1]["open"] = bars[-2]["close"] + 0.05
    bars[-1]["time"] = bars[-2]["time"] + 60
    result = track_execution_quality(bars, baseline_points=40.0)
    assert result["module"] == "execution_quality"
    assert "slippage_proxy" in result["metrics"]
    assert "spread_condition" in result["metrics"]
    assert "fill_timing_ratio" in result["metrics"]
    assert result["confidence_level"] in {"low", "medium", "high"}
