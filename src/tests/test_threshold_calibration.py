"""Tests for the replay-threshold calibration report.

Covers distribution stat computation (percentile, stdev), calibration with
healthy runs, degenerate runs, empty runs, recommendation logic for each
threshold, artifact persistence, and edge cases.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.replay_outcome import (
    _MAX_DRAWDOWN_POINTS_THRESHOLD,
    _MIN_CLOSED_FOR_ECONOMIC_GATE,
)
from src.evaluation.threshold_calibration import (
    _percentile,
    _stdev,
    calibrate_thresholds,
    run_threshold_calibration,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _closed_rec(
    direction: str = "BUY",
    pnl_points: float = 2.0,
    result: str = "win",
    pnl_gross: float | None = None,
    pnl_net: float | None = None,
) -> dict[str, Any]:
    """Build a record with a closed trade outcome."""
    outcome: dict[str, Any] = {
        "trade_id": "test_trade",
        "symbol": "XAUUSD",
        "direction": direction,
        "status": "closed",
        "result": result,
        "pnl_points": pnl_points,
    }
    if pnl_gross is not None:
        outcome["pnl_points_gross"] = pnl_gross
    if pnl_net is not None:
        outcome["pnl_points_net"] = pnl_net

    return {
        "signal": {
            "action": direction,
            "confidence": 0.85,
            "blocked": False,
            "blocker_reasons": [],
            "reasons": ["test reason"],
        },
        "status_panel": {
            "memory_result": {
                "latest_trade_outcome": outcome,
            },
        },
    }


def _skipped_rec() -> dict[str, Any]:
    """Build a record with a skipped (WAIT) outcome."""
    return {
        "signal": {
            "action": "WAIT",
            "confidence": 0.0,
            "blocked": False,
            "blocker_reasons": [],
            "reasons": ["no setup"],
        },
        "status_panel": {
            "memory_result": {
                "latest_trade_outcome": {
                    "status": "skipped",
                    "direction": "WAIT",
                    "result": "n/a",
                    "pnl_points": 0.0,
                },
            },
        },
    }


def _outcome_report(
    win_rate: float = 0.5,
    net_expectancy: float = 1.0,
    max_drawdown_points: float = 5.0,
    closed_trades: int = 4,
) -> dict[str, Any]:
    """Build a minimal outcome report stub."""
    return {
        "win_rate": win_rate,
        "net_expectancy": net_expectancy,
        "max_drawdown_points": max_drawdown_points,
        "closed_trades": closed_trades,
    }


# ---------------------------------------------------------------------------
# _percentile unit tests
# ---------------------------------------------------------------------------


class TestPercentile(unittest.TestCase):

    def test_empty(self) -> None:
        self.assertEqual(_percentile([], 50), 0.0)

    def test_single_value(self) -> None:
        self.assertAlmostEqual(_percentile([3.0], 50), 3.0)

    def test_median_even(self) -> None:
        # [1, 2, 3, 4] → p50 → ceil(0.5*4)-1 = 1 → val = 2
        self.assertAlmostEqual(_percentile([1.0, 2.0, 3.0, 4.0], 50), 2.0)

    def test_p10(self) -> None:
        vals = sorted([float(i) for i in range(1, 11)])
        self.assertAlmostEqual(_percentile(vals, 10), 1.0)

    def test_p90(self) -> None:
        vals = sorted([float(i) for i in range(1, 11)])
        self.assertAlmostEqual(_percentile(vals, 90), 9.0)

    def test_p100(self) -> None:
        vals = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(_percentile(vals, 100), 3.0)


# ---------------------------------------------------------------------------
# _stdev unit tests
# ---------------------------------------------------------------------------


class TestStdev(unittest.TestCase):

    def test_single_value(self) -> None:
        self.assertEqual(_stdev([5.0], 5.0), 0.0)

    def test_known_stdev(self) -> None:
        # [2, 4, 4, 4, 5, 5, 7, 9] → mean=5, pop stdev=2.0
        vals = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        self.assertAlmostEqual(_stdev(vals, 5.0), 2.0, places=3)

    def test_zero_variance(self) -> None:
        self.assertAlmostEqual(_stdev([3.0, 3.0, 3.0], 3.0), 0.0)


# ---------------------------------------------------------------------------
# calibrate_thresholds tests
# ---------------------------------------------------------------------------


class TestCalibrateThresholds(unittest.TestCase):

    def test_healthy_run_basic_stats(self) -> None:
        """A healthy run with multiple trades produces correct distribution stats."""
        records = [
            _closed_rec(pnl_points=5.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-2.0, result="loss"),
            _closed_rec(pnl_points=3.0, result="win"),
            _closed_rec(pnl_points=1.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-1.0, result="loss"),
            _closed_rec(pnl_points=4.0, result="win"),
        ]
        outcome = _outcome_report(
            win_rate=4 / 6,
            net_expectancy=round(10.0 / 6, 3),
            max_drawdown_points=2.0,
            closed_trades=6,
        )
        report = calibrate_thresholds(records, outcome)

        self.assertEqual(report["schema_version"], "threshold_calibration.v1")
        self.assertEqual(report["closed_trades"], 6)
        self.assertEqual(report["net_pnl_distribution"]["count"], 6)
        self.assertAlmostEqual(report["net_pnl_distribution"]["min"], -2.0)
        self.assertAlmostEqual(report["net_pnl_distribution"]["max"], 5.0)
        self.assertIn("mean", report["net_pnl_distribution"])
        self.assertIn("stdev", report["net_pnl_distribution"])
        self.assertIn("median", report["net_pnl_distribution"])

    def test_empty_run(self) -> None:
        """Empty records produce zero-valued distributions."""
        report = calibrate_thresholds([], _outcome_report(closed_trades=0))
        self.assertEqual(report["closed_trades"], 0)
        self.assertEqual(report["net_pnl_distribution"]["count"], 0)
        self.assertEqual(report["net_pnl_distribution"]["mean"], 0.0)
        self.assertEqual(report["drawdown_distribution"]["observations"], 0)

    def test_single_trade(self) -> None:
        """Single trade produces valid but minimal distribution."""
        records = [_closed_rec(pnl_points=3.0, result="win")]
        outcome = _outcome_report(win_rate=1.0, net_expectancy=3.0, closed_trades=1)
        report = calibrate_thresholds(records, outcome)
        self.assertEqual(report["closed_trades"], 1)
        self.assertAlmostEqual(report["net_pnl_distribution"]["min"], 3.0)
        self.assertAlmostEqual(report["net_pnl_distribution"]["max"], 3.0)
        self.assertEqual(report["net_pnl_distribution"]["stdev"], 0.0)

    def test_drawdown_distribution(self) -> None:
        """Drawdown stats are computed from peak-to-trough observations."""
        # Series: +5, -3, -4, +2 → cumulative: 5, 2, -2, 0
        # Peak:                      5, 5,  5, 5
        # DD:                        0, 3,  7, 5
        records = [
            _closed_rec(pnl_points=5.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
            _closed_rec(direction="SELL", pnl_points=-4.0, result="loss"),
            _closed_rec(pnl_points=2.0, result="win"),
        ]
        outcome = _outcome_report(max_drawdown_points=7.0, closed_trades=4)
        report = calibrate_thresholds(records, outcome)
        self.assertAlmostEqual(report["drawdown_distribution"]["max"], 7.0)
        self.assertEqual(report["drawdown_distribution"]["observations"], 3)

    def test_no_drawdown_run(self) -> None:
        """All winning trades → no drawdown observations."""
        records = [
            _closed_rec(pnl_points=2.0, result="win"),
            _closed_rec(pnl_points=3.0, result="win"),
        ]
        outcome = _outcome_report(
            win_rate=1.0, net_expectancy=2.5, max_drawdown_points=0.0
        )
        report = calibrate_thresholds(records, outcome)
        self.assertEqual(report["drawdown_distribution"]["observations"], 0)
        self.assertAlmostEqual(report["drawdown_distribution"]["max"], 0.0)

    def test_current_thresholds_reported(self) -> None:
        """Report includes the actual constant values from replay_outcome."""
        report = calibrate_thresholds([], _outcome_report())
        ct = report["current_thresholds"]
        self.assertEqual(ct["min_closed_for_economic_gate"], _MIN_CLOSED_FOR_ECONOMIC_GATE)
        self.assertEqual(ct["max_drawdown_points_threshold"], _MAX_DRAWDOWN_POINTS_THRESHOLD)

    def test_observed_values_from_outcome_report(self) -> None:
        """Observed values are extracted from the outcome report."""
        outcome = _outcome_report(win_rate=0.6, net_expectancy=2.5, max_drawdown_points=8.0)
        report = calibrate_thresholds([], outcome)
        self.assertAlmostEqual(report["observed"]["win_rate"], 0.6)
        self.assertAlmostEqual(report["observed"]["net_expectancy"], 2.5)
        self.assertAlmostEqual(report["observed"]["max_drawdown_points"], 8.0)

    def test_skipped_records_ignored(self) -> None:
        """Skipped/WAIT records do not affect trade distributions."""
        records = [
            _closed_rec(pnl_points=2.0, result="win"),
            _skipped_rec(),
            _skipped_rec(),
        ]
        outcome = _outcome_report(closed_trades=1)
        report = calibrate_thresholds(records, outcome)
        self.assertEqual(report["closed_trades"], 1)

    def test_gross_net_split(self) -> None:
        """Gross and net distributions use appropriate fields."""
        records = [
            _closed_rec(pnl_points=5.0, pnl_gross=5.0, pnl_net=4.0, result="win"),
            _closed_rec(pnl_points=-2.0, pnl_gross=-2.0, pnl_net=-2.5, result="loss"),
        ]
        outcome = _outcome_report(closed_trades=2)
        report = calibrate_thresholds(records, outcome)
        self.assertAlmostEqual(report["gross_pnl_distribution"]["mean"], 1.5)
        self.assertAlmostEqual(report["net_pnl_distribution"]["mean"], 0.75)

    # -- recommendation logic tests ----------------------------------------

    def test_trade_count_confirmed_when_abundant(self) -> None:
        """Many trades → min_closed threshold is confirmed."""
        records = [_closed_rec(pnl_points=1.0, result="win") for _ in range(10)]
        outcome = _outcome_report(win_rate=1.0, net_expectancy=1.0, closed_trades=10)
        report = calibrate_thresholds(records, outcome)
        rec = report["recommendations"]["min_closed_for_economic_gate"]
        self.assertEqual(rec["state"], "confirmed")

    def test_trade_count_tighten_when_scarce(self) -> None:
        """Few trades → min_closed threshold flagged for tightening."""
        records = [
            _closed_rec(pnl_points=1.0, result="win"),
            _closed_rec(pnl_points=2.0, result="win"),
        ]
        outcome = _outcome_report(closed_trades=2)
        report = calibrate_thresholds(records, outcome)
        rec = report["recommendations"]["min_closed_for_economic_gate"]
        self.assertEqual(rec["state"], "tighten")

    def test_drawdown_tighten_when_well_below(self) -> None:
        """p95 drawdown far below threshold → recommend tightening."""
        # Single small drawdown, well below 50-point threshold
        records = [
            _closed_rec(pnl_points=5.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-1.0, result="loss"),
            _closed_rec(pnl_points=3.0, result="win"),
        ]
        outcome = _outcome_report(max_drawdown_points=1.0)
        report = calibrate_thresholds(records, outcome)
        rec = report["recommendations"]["max_drawdown_points_threshold"]
        self.assertEqual(rec["state"], "tighten")
        self.assertIn("suggested_cap", rec)

    def test_drawdown_confirmed_when_close(self) -> None:
        """p95 drawdown near threshold → confirmed."""
        # Build a series with large drawdown near the threshold
        big_loss = -(_MAX_DRAWDOWN_POINTS_THRESHOLD * 0.8)
        records = [
            _closed_rec(pnl_points=_MAX_DRAWDOWN_POINTS_THRESHOLD, result="win"),
            _closed_rec(direction="SELL", pnl_points=big_loss, result="loss"),
        ]
        outcome = _outcome_report(
            max_drawdown_points=abs(big_loss),
        )
        report = calibrate_thresholds(records, outcome)
        rec = report["recommendations"]["max_drawdown_points_threshold"]
        self.assertEqual(rec["state"], "confirmed")

    def test_expectancy_confirmed_when_clearly_positive(self) -> None:
        """Expectancy well above 0 → confirmed."""
        outcome = _outcome_report(net_expectancy=3.0)
        report = calibrate_thresholds([], outcome)
        rec = report["recommendations"]["expectancy_floor"]
        self.assertEqual(rec["state"], "confirmed")

    def test_expectancy_tighten_when_marginally_positive(self) -> None:
        """Expectancy marginally above 0 → recommend tightening."""
        outcome = _outcome_report(net_expectancy=0.3)
        report = calibrate_thresholds([], outcome)
        rec = report["recommendations"]["expectancy_floor"]
        self.assertEqual(rec["state"], "tighten")
        self.assertIn("suggested_floor", rec)

    def test_expectancy_confirmed_when_non_positive(self) -> None:
        """Expectancy at or below 0 → confirmed (hard fail already handles)."""
        outcome = _outcome_report(net_expectancy=-1.0)
        report = calibrate_thresholds([], outcome)
        rec = report["recommendations"]["expectancy_floor"]
        self.assertEqual(rec["state"], "confirmed")

    def test_win_rate_confirmed_when_healthy(self) -> None:
        """Win rate well above 0% → confirmed."""
        outcome = _outcome_report(win_rate=0.5)
        report = calibrate_thresholds([], outcome)
        rec = report["recommendations"]["win_rate_floor"]
        self.assertEqual(rec["state"], "confirmed")

    def test_win_rate_tighten_when_low(self) -> None:
        """Win rate above 0% but very low → recommend tightening."""
        outcome = _outcome_report(win_rate=0.1)
        report = calibrate_thresholds([], outcome)
        rec = report["recommendations"]["win_rate_floor"]
        self.assertEqual(rec["state"], "tighten")
        self.assertIn("suggested_floor", rec)

    def test_win_rate_confirmed_when_zero(self) -> None:
        """Win rate at 0% → confirmed (hard fail already handles)."""
        outcome = _outcome_report(win_rate=0.0)
        report = calibrate_thresholds([], outcome)
        rec = report["recommendations"]["win_rate_floor"]
        self.assertEqual(rec["state"], "confirmed")


# ---------------------------------------------------------------------------
# run_threshold_calibration tests
# ---------------------------------------------------------------------------


class TestRunThresholdCalibration(unittest.TestCase):

    def test_persists_artifact(self) -> None:
        """Calibration report is written to disk."""
        records = [
            _closed_rec(pnl_points=3.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-1.0, result="loss"),
        ]
        outcome = _outcome_report(closed_trades=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "calibration.json"
            report = run_threshold_calibration(records, outcome, path)
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertEqual(persisted["schema_version"], "threshold_calibration.v1")
            self.assertEqual(persisted["closed_trades"], 2)

    def test_creates_parent_dirs(self) -> None:
        """Nested artifact path is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "cal.json"
            report = run_threshold_calibration([], _outcome_report(), path)
            self.assertTrue(path.exists())

    def test_never_raises(self) -> None:
        """Calibration is diagnostic — never raises even on degenerate input."""
        records = [_closed_rec(pnl_points=-99.0, result="loss")]
        outcome = _outcome_report(
            win_rate=0.0,
            net_expectancy=-99.0,
            max_drawdown_points=99.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cal.json"
            report = run_threshold_calibration(records, outcome, path)
            # Should not raise
            self.assertIn("recommendations", report)

    def test_report_matches_returned(self) -> None:
        """Returned dict matches persisted artifact."""
        records = [_closed_rec(pnl_points=2.0, result="win")]
        outcome = _outcome_report(closed_trades=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cal.json"
            report = run_threshold_calibration(records, outcome, path)
            persisted = json.loads(path.read_text())
            self.assertEqual(report, persisted)


if __name__ == "__main__":
    unittest.main()
