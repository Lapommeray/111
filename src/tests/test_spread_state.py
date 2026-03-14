from __future__ import annotations

from src.features.spread_state import compute_spread_state


def _bars_with_range(count: int, rng: float) -> list[dict[str, float]]:
    bars: list[dict[str, float]] = []
    base = 2000.0
    for i in range(count):
        close = base + i * 0.1
        bars.append(
            {
                "time": 1700000000 + i * 60,
                "open": close,
                "high": close + (rng / 2.0),
                "low": close - (rng / 2.0),
                "close": close,
                "tick_volume": 100 + i,
            }
        )
    return bars


def test_spread_state_insufficient_data_uses_baseline() -> None:
    result = compute_spread_state(_bars_with_range(3, 1.0), baseline_points=40.0)
    assert result["state"] == "insufficient_data"
    assert result["spread_points"] == 40.0
    assert result["direction_vote"] == "neutral"


def test_spread_state_detects_wide_tight_and_normal() -> None:
    wide = compute_spread_state(_bars_with_range(6, 4.0), baseline_points=40.0)
    tight = compute_spread_state(_bars_with_range(6, 1.0), baseline_points=40.0)
    normal = compute_spread_state(_bars_with_range(6, 2.2), baseline_points=40.0)

    assert wide["state"] == "wide"
    assert wide["confidence_delta"] < 0

    assert tight["state"] == "tight"
    assert tight["confidence_delta"] > 0

    assert normal["state"] == "normal"
    assert normal["confidence_delta"] == 0.0
