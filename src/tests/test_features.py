from __future__ import annotations

from src.features.liquidity import assess_liquidity_state
from src.features.market_structure import classify_market_structure


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
