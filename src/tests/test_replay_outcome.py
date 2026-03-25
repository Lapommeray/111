"""Tests for the replay-outcome / economic truth gate.

Covers hard-fail conditions (actionable but no closed trades, 0% win rate,
negative expectancy, non-positive net P&L with drawdown, excessive drawdown),
sub-threshold flag conditions (single-trade runs), pass conditions (healthy
mixed run), metric correctness, threshold constants, and artifact persistence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.replay_outcome import (
    ReplayOutcomeError,
    _MAX_DRAWDOWN_POINTS_THRESHOLD,
    _MIN_CLOSED_FOR_ECONOMIC_GATE,
    _build_drawdown_attribution,
    _compute_metrics,
    _is_closed_trade,
    assess_replay_outcome,
    run_replay_outcome_gate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _closed_rec(
    direction: str = "BUY",
    pnl_points: float = 2.0,
    result: str = "win",
    confidence: float = 0.85,
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
        "confidence": confidence,
    }
    if pnl_gross is not None:
        outcome["pnl_points_gross"] = pnl_gross
    if pnl_net is not None:
        outcome["pnl_points_net"] = pnl_net

    return {
        "signal": {
            "action": direction,
            "confidence": confidence,
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


def _blocked_rec() -> dict[str, Any]:
    """Build a record with a blocked outcome."""
    return {
        "signal": {
            "action": "WAIT",
            "confidence": 0.0,
            "blocked": True,
            "blocker_reasons": ["spread_filter"],
            "reasons": [],
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


def _quality(actionable: int = 2) -> dict[str, Any]:
    """Minimal quality report stub with actionable_count."""
    return {"actionable_count": actionable}


# ---------------------------------------------------------------------------
# _is_closed_trade unit tests
# ---------------------------------------------------------------------------


class TestIsClosedTrade(unittest.TestCase):

    def test_closed_buy(self) -> None:
        self.assertTrue(_is_closed_trade({"status": "closed", "direction": "BUY"}))

    def test_closed_sell(self) -> None:
        self.assertTrue(_is_closed_trade({"status": "closed", "direction": "SELL"}))

    def test_skipped_wait(self) -> None:
        self.assertFalse(_is_closed_trade({"status": "skipped", "direction": "WAIT"}))

    def test_missing_fields(self) -> None:
        self.assertFalse(_is_closed_trade({}))

    def test_non_closed_status(self) -> None:
        self.assertFalse(_is_closed_trade({"status": "open", "direction": "BUY"}))


# ---------------------------------------------------------------------------
# _compute_metrics unit tests
# ---------------------------------------------------------------------------


class TestComputeMetrics(unittest.TestCase):

    def test_empty_records(self) -> None:
        m = _compute_metrics([])
        self.assertEqual(m["closed_trades"], 0)
        self.assertEqual(m["win_rate"], 0.0)
        self.assertEqual(m["net_expectancy"], 0.0)
        self.assertEqual(m["max_drawdown_points"], 0.0)

    def test_single_winning_trade(self) -> None:
        m = _compute_metrics([_closed_rec(pnl_points=3.5, result="win")])
        self.assertEqual(m["closed_trades"], 1)
        self.assertEqual(m["wins"], 1)
        self.assertEqual(m["losses"], 0)
        self.assertAlmostEqual(m["win_rate"], 1.0)
        self.assertAlmostEqual(m["gross_pnl_points"], 3.5)
        self.assertAlmostEqual(m["net_expectancy"], 3.5)
        self.assertAlmostEqual(m["max_drawdown_points"], 0.0)

    def test_mixed_trades(self) -> None:
        records = [
            _closed_rec(pnl_points=5.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-2.0, result="loss"),
            _closed_rec(pnl_points=1.0, result="win"),
        ]
        m = _compute_metrics(records)
        self.assertEqual(m["closed_trades"], 3)
        self.assertEqual(m["wins"], 2)
        self.assertEqual(m["losses"], 1)
        self.assertAlmostEqual(m["win_rate"], round(2 / 3, 4))
        self.assertAlmostEqual(m["gross_pnl_points"], 4.0)
        self.assertAlmostEqual(m["avg_gross_pnl_per_trade"], round(4.0 / 3, 3))

    def test_skipped_records_ignored(self) -> None:
        records = [
            _closed_rec(pnl_points=2.0, result="win"),
            _skipped_rec(),
            _blocked_rec(),
        ]
        m = _compute_metrics(records)
        self.assertEqual(m["closed_trades"], 1)

    def test_execution_costs_use_gross_net(self) -> None:
        records = [
            _closed_rec(pnl_points=5.0, result="win", pnl_gross=5.0, pnl_net=4.2),
        ]
        m = _compute_metrics(records)
        self.assertAlmostEqual(m["gross_pnl_points"], 5.0)
        self.assertAlmostEqual(m["net_pnl_points"], 4.2)
        self.assertAlmostEqual(m["avg_net_pnl_per_trade"], 4.2)

    def test_max_drawdown_calculation(self) -> None:
        # Series: +5, -3, -4, +2  → cumulative: 5, 2, -2, 0
        # Peak: 5, 5, 5, 5 → DD: 0, -3, -7, -5 → max_dd = 7
        records = [
            _closed_rec(pnl_points=5.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
            _closed_rec(direction="SELL", pnl_points=-4.0, result="loss"),
            _closed_rec(pnl_points=2.0, result="win"),
        ]
        m = _compute_metrics(records)
        self.assertAlmostEqual(m["max_drawdown_points"], 7.0)


# ---------------------------------------------------------------------------
# _build_drawdown_attribution unit tests
# ---------------------------------------------------------------------------


class TestDrawdownAttribution(unittest.TestCase):

    def test_peak_to_trough_attribution(self) -> None:
        records = [
            _closed_rec(pnl_points=8.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-2.0, result="loss"),
            _closed_rec(direction="SELL", pnl_points=-5.0, result="loss"),
            _closed_rec(pnl_points=1.0, result="win"),
        ]
        payload = _build_drawdown_attribution(records)
        self.assertEqual(payload["schema_version"], "replay.drawdown_attribution.v1")
        self.assertEqual(payload["max_drawdown_points"], 7.0)
        self.assertEqual(payload["worst_drawdown_segment_count"], 1)
        segment = payload["worst_drawdown_segments"][0]
        self.assertEqual(segment["peak_event_index"], 0)
        self.assertEqual(segment["trough_event_index"], 2)
        self.assertEqual(segment["contributing_trade_ids"], ["test_trade", "test_trade"])
        self.assertTrue(segment["equity_path_peak_to_trough"])
        self.assertIn("segment_signature", segment)
        self.assertIn("segment_fingerprint", segment)

    def test_no_closed_trades(self) -> None:
        payload = _build_drawdown_attribution([_skipped_rec(), _blocked_rec()])
        self.assertEqual(payload["closed_trade_count"], 0)
        self.assertEqual(payload["max_drawdown_points"], 0.0)
        self.assertEqual(payload["worst_drawdown_segments"], [])


# ---------------------------------------------------------------------------
# assess_replay_outcome tests
# ---------------------------------------------------------------------------


class TestAssessReplayOutcome(unittest.TestCase):

    def test_healthy_mixed_run_passes(self) -> None:
        records = [
            _closed_rec(pnl_points=5.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-2.0, result="loss"),
            _closed_rec(pnl_points=3.0, result="win"),
            _skipped_rec(),
        ]
        report = assess_replay_outcome(records, _quality(actionable=3))
        self.assertTrue(report["passed"])
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["closed_trades"], 3)
        self.assertEqual(report["wins"], 2)
        self.assertEqual(report["losses"], 1)
        self.assertGreater(report["net_expectancy"], 0)
        self.assertEqual(len(report["flags"]), 0)

    def test_actionable_but_no_closed_trades_fails(self) -> None:
        records = [_skipped_rec(), _skipped_rec()]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertFalse(report["passed"])
        self.assertTrue(any("0 closed trades" in f for f in report["failures"]))

    def test_no_actionable_no_closed_passes(self) -> None:
        records = [_skipped_rec(), _blocked_rec()]
        report = assess_replay_outcome(records, _quality(actionable=0))
        self.assertTrue(report["passed"])

    def test_empty_run_passes(self) -> None:
        report = assess_replay_outcome([], _quality(actionable=0))
        self.assertTrue(report["passed"])

    # -- hard-fail rules (≥ _MIN_CLOSED_FOR_ECONOMIC_GATE trades) ----------

    def test_all_losses_hard_fail(self) -> None:
        """≥2 closed trades all losing → hard fail (0% win + neg expectancy)."""
        records = [
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
            _closed_rec(pnl_points=-1.5, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertFalse(report["passed"])
        self.assertTrue(any("0% win rate" in f for f in report["failures"]))
        self.assertTrue(
            any("negative net expectancy" in f for f in report["failures"])
        )

    def test_negative_expectancy_hard_fail(self) -> None:
        """≥2 closed trades with net-negative expectancy → hard fail."""
        records = [
            _closed_rec(pnl_points=1.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-5.0, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("negative net expectancy" in f for f in report["failures"])
        )

    def test_non_positive_net_with_drawdown_hard_fail(self) -> None:
        """≥2 closed trades, net P&L ≤ 0, drawdown > 0 → hard fail."""
        records = [
            _closed_rec(pnl_points=2.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("net P&L non-positive" in f for f in report["failures"])
        )

    def test_excessive_drawdown_hard_fail(self) -> None:
        """Max drawdown exceeding threshold → hard fail."""
        # 2 trades: +1, -(threshold+1) → drawdown > threshold
        big_loss = -(_MAX_DRAWDOWN_POINTS_THRESHOLD + 1.0)
        records = [
            _closed_rec(pnl_points=1.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=big_loss, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("exceeds threshold" in f for f in report["failures"])
        )

    def test_drawdown_at_threshold_passes(self) -> None:
        """Drawdown exactly at threshold → not a fail."""
        # Series: +threshold, -threshold → drawdown == threshold exactly, not >
        records = [
            _closed_rec(pnl_points=_MAX_DRAWDOWN_POINTS_THRESHOLD, result="win"),
            _closed_rec(
                direction="SELL",
                pnl_points=-_MAX_DRAWDOWN_POINTS_THRESHOLD,
                result="loss",
            ),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        # net pnl = 0, drawdown == threshold exactly → not > threshold
        # But non-positive net with drawdown still triggers:
        self.assertTrue(
            any("net P&L non-positive" in f for f in report["failures"])
        )
        # Drawdown at threshold, not exceeding:
        self.assertFalse(
            any("exceeds threshold" in f for f in report["failures"])
        )

    # -- sub-threshold: single trade → flags, not failures -----------------

    def test_single_loss_flagged_not_failed(self) -> None:
        """Only 1 closed trade (< threshold) → flags, not hard fail."""
        records = [_closed_rec(pnl_points=-2.0, result="loss")]
        report = assess_replay_outcome(records, _quality(actionable=1))
        self.assertTrue(report["passed"])
        self.assertGreater(len(report["flags"]), 0)
        self.assertTrue(any("0% win rate" in f for f in report["flags"]))
        self.assertTrue(
            any("negative net expectancy" in f for f in report["flags"])
        )

    def test_single_flat_trade_flagged_not_failed(self) -> None:
        """Single flat trade has 0% win rate → flag, not fail."""
        records = [_closed_rec(pnl_points=0.0, result="flat")]
        report = assess_replay_outcome(records, _quality(actionable=1))
        self.assertTrue(report["passed"])
        self.assertTrue(any("0% win rate" in f for f in report["flags"]))

    # -- pass conditions ---------------------------------------------------

    def test_all_wins_no_flags(self) -> None:
        records = [
            _closed_rec(pnl_points=2.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=3.0, result="win"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["flags"]), 0)

    def test_single_winning_trade_passes(self) -> None:
        records = [_closed_rec(pnl_points=1.5, result="win")]
        report = assess_replay_outcome(records, _quality(actionable=1))
        self.assertTrue(report["passed"])
        self.assertAlmostEqual(report["win_rate"], 1.0)
        self.assertAlmostEqual(report["net_expectancy"], 1.5)

    def test_schema_version_v2(self) -> None:
        report = assess_replay_outcome([], _quality(actionable=0))
        self.assertEqual(report["schema_version"], "replay_outcome.v2")

    def test_record_missing_status_panel_ignored(self) -> None:
        """Records without status_panel are silently skipped (not closed)."""
        records: list[dict[str, Any]] = [{"signal": {"action": "BUY"}}]
        report = assess_replay_outcome(records, _quality(actionable=1))
        self.assertFalse(report["passed"])
        self.assertEqual(report["closed_trades"], 0)

    # -- threshold constant sanity -----------------------------------------

    def test_min_closed_threshold_is_reasonable(self) -> None:
        self.assertGreaterEqual(_MIN_CLOSED_FOR_ECONOMIC_GATE, 2)

    def test_max_drawdown_threshold_is_positive(self) -> None:
        self.assertGreater(_MAX_DRAWDOWN_POINTS_THRESHOLD, 0)


# ---------------------------------------------------------------------------
# run_replay_outcome_gate tests
# ---------------------------------------------------------------------------


class TestReplayOutcomeGate(unittest.TestCase):

    def test_gate_passes_and_persists(self) -> None:
        records = [
            _closed_rec(pnl_points=4.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-1.0, result="loss"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcome.json"
            report = run_replay_outcome_gate(records, qual, path)
            self.assertTrue(report["passed"])
            self.assertTrue(path.exists())
            drawdown_path = Path(report["drawdown_attribution_path"])
            self.assertTrue(drawdown_path.exists())
            drawdown_payload = json.loads(drawdown_path.read_text())
            self.assertEqual(drawdown_payload["schema_version"], "replay.drawdown_attribution.v1")
            persisted = json.loads(path.read_text())
            self.assertTrue(persisted["passed"])
            self.assertEqual(persisted["closed_trades"], 2)

    def test_gate_fails_and_persists(self) -> None:
        records = [_skipped_rec()]
        qual = _quality(actionable=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError):
                run_replay_outcome_gate(records, qual, path)
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertFalse(persisted["passed"])

    def test_gate_creates_parent_dirs(self) -> None:
        records = [_closed_rec(pnl_points=2.0, result="win")]
        qual = _quality(actionable=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "outcome.json"
            report = run_replay_outcome_gate(records, qual, path)
            self.assertTrue(path.exists())
            self.assertTrue(report["passed"])

    def test_gate_error_message_contains_failure(self) -> None:
        records = [_skipped_rec()]
        qual = _quality(actionable=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError) as ctx:
                run_replay_outcome_gate(records, qual, path)
            self.assertIn("0 closed trades", str(ctx.exception))
            self.assertIn("3 actionable", str(ctx.exception))

    def test_gate_economic_hard_fail_persists_then_raises(self) -> None:
        """All losses (≥2 trades) → gate raises, artifact persisted first."""
        records = [
            _closed_rec(pnl_points=-2.0, result="loss"),
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError) as ctx:
                run_replay_outcome_gate(records, qual, path)
            self.assertIn("0% win rate", str(ctx.exception))
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertFalse(persisted["passed"])
            self.assertGreater(persisted["failure_count"], 0)

    def test_gate_drawdown_hard_fail(self) -> None:
        """Excessive drawdown → gate raises."""
        big_loss = -(_MAX_DRAWDOWN_POINTS_THRESHOLD + 10.0)
        records = [
            _closed_rec(pnl_points=1.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=big_loss, result="loss"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError) as ctx:
                run_replay_outcome_gate(records, qual, path)
            self.assertIn("exceeds threshold", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
