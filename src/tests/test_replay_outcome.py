"""Tests for the replay-outcome / economic truth gate.

Covers fail conditions (actionable but no closed trades), flag conditions
(negative expectancy, 0% win rate, net P&L non-positive), pass conditions
(healthy mixed run), metric correctness, and artifact persistence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.replay_outcome import (
    ReplayOutcomeError,
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

    def test_all_losses_flagged(self) -> None:
        records = [
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
            _closed_rec(pnl_points=-1.5, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertTrue(report["passed"])  # flags, not hard fail
        self.assertTrue(any("0% win rate" in f for f in report["flags"]))
        self.assertTrue(any("negative net expectancy" in f for f in report["flags"]))

    def test_negative_expectancy_flagged(self) -> None:
        records = [
            _closed_rec(pnl_points=1.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-5.0, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertTrue(report["passed"])
        self.assertTrue(any("negative net expectancy" in f for f in report["flags"]))

    def test_non_positive_net_with_drawdown_flagged(self) -> None:
        records = [
            _closed_rec(pnl_points=2.0, result="win"),
            _closed_rec(direction="SELL", pnl_points=-3.0, result="loss"),
        ]
        report = assess_replay_outcome(records, _quality(actionable=2))
        self.assertTrue(report["passed"])
        self.assertTrue(any("net P&L non-positive" in f for f in report["flags"]))

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

    def test_schema_version_present(self) -> None:
        report = assess_replay_outcome([], _quality(actionable=0))
        self.assertEqual(report["schema_version"], "replay_outcome.v1")

    def test_flat_trade_not_flagged(self) -> None:
        """A flat trade (result='flat') counts as closed but not win or loss."""
        records = [_closed_rec(pnl_points=0.0, result="flat")]
        report = assess_replay_outcome(records, _quality(actionable=1))
        self.assertTrue(report["passed"])
        self.assertEqual(report["wins"], 0)
        self.assertEqual(report["losses"], 0)
        self.assertEqual(report["closed_trades"], 1)
        # 0% win rate is flagged even for flat trades
        self.assertTrue(any("0% win rate" in f for f in report["flags"]))

    def test_record_missing_status_panel_ignored(self) -> None:
        """Records without status_panel are silently skipped (not closed)."""
        records: list[dict[str, Any]] = [{"signal": {"action": "BUY"}}]
        report = assess_replay_outcome(records, _quality(actionable=1))
        self.assertFalse(report["passed"])
        self.assertEqual(report["closed_trades"], 0)


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


if __name__ == "__main__":
    unittest.main()
