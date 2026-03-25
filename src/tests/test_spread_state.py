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
    # avg_range=30 × 2.0 = 60 → wide (> 40*1.4=56)
    wide = compute_spread_state(_bars_with_range(6, 30.0), baseline_points=40.0)
    # avg_range=1.0 × 2.0 = 2.0 → clamped to 5.0 → tight (< 40*0.8=32)
    tight = compute_spread_state(_bars_with_range(6, 1.0), baseline_points=40.0)
    # avg_range=20 × 2.0 = 40 → normal (32 ≤ 40 ≤ 56)
    normal = compute_spread_state(_bars_with_range(6, 20.0), baseline_points=40.0)

    assert wide["state"] == "wide"
    assert wide["confidence_delta"] < 0

    assert tight["state"] == "tight"
    assert tight["confidence_delta"] > 0

    assert normal["state"] == "normal"
    assert normal["confidence_delta"] == 0.0


def test_xauusd_normal_range_not_wide() -> None:
    """Typical XAUUSD 5-min bars have avg_range ~$3-5.  With the corrected
    multiplier these must NOT map to absurd spread values or trigger 'wide'."""
    baseline = 40.0
    spread_filter_threshold = 60.0  # max_spread_points in apply_spread_filter
    for avg_range in [3.0, 3.5, 4.0, 5.0]:
        result = compute_spread_state(_bars_with_range(6, avg_range), baseline_points=baseline)
        assert result["spread_points"] < spread_filter_threshold, (
            f"avg_range={avg_range} produced spread_points={result['spread_points']}, "
            "which would trigger the spread_filter hard-block"
        )
        assert result["state"] != "wide", (
            f"avg_range={avg_range} classified as 'wide' — normal XAUUSD "
            "ranges must not trigger wide-spread blocking"
        )


def test_extreme_range_still_triggers_wide() -> None:
    """Genuinely extreme bar ranges (e.g. $35+ avg_range) must still be able
    to produce 'wide' classification and trigger spread blocking."""
    baseline = 40.0
    wide_threshold = baseline * 1.4
    result = compute_spread_state(_bars_with_range(6, 35.0), baseline_points=baseline)
    assert result["state"] == "wide"
    assert result["spread_points"] > wide_threshold
    assert result["confidence_delta"] < 0
