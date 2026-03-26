"""Tests for drawdown attribution plumbing in run_replay_evaluation.

Validates that ``drawdown_attribution_path`` is present in the persisted
evaluation report even when the replay-outcome gate raises
``ReplayOutcomeError`` (i.e. the gate fails).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

from src.evaluation.replay_outcome import (
    ReplayOutcomeError,
    run_replay_outcome_gate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _closed_rec(
    direction: str = "BUY",
    pnl_points: float = 2.0,
    result: str = "win",
    trade_id: str = "test_trade",
) -> dict[str, Any]:
    """Build a record with a closed trade outcome."""
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
                "latest_trade_outcome": {
                    "trade_id": trade_id,
                    "symbol": "XAUUSD",
                    "direction": direction,
                    "status": "closed",
                    "result": result,
                    "pnl_points": pnl_points,
                    "confidence": 0.85,
                },
            },
        },
    }


def _quality(actionable: int = 2) -> dict[str, Any]:
    return {"actionable_count": actionable}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDrawdownAttributionPlumbing(unittest.TestCase):
    """Verify drawdown_attribution_path survives gate failure."""

    def test_drawdown_attribution_path_present_on_gate_pass(self) -> None:
        """When the gate passes, drawdown_attribution_path is in the report."""
        records = [
            _closed_rec(pnl_points=4.0, result="win", trade_id="t1"),
            _closed_rec(direction="SELL", pnl_points=-1.0, result="loss", trade_id="t2"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "outcome.json"
            report = run_replay_outcome_gate(records, qual, artifact)
            self.assertIn("drawdown_attribution_path", report)
            self.assertIsNotNone(report["drawdown_attribution_path"])
            self.assertTrue(Path(report["drawdown_attribution_path"]).exists())

    def test_drawdown_attribution_path_present_on_gate_fail(self) -> None:
        """When the gate fails, the artifact is still written with the path."""
        records = [
            _closed_rec(pnl_points=-30.0, result="loss", trade_id="t1"),
            _closed_rec(direction="SELL", pnl_points=-60.0, result="loss", trade_id="t2"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError):
                run_replay_outcome_gate(records, qual, artifact)
            # The gate persists its own report before raising.
            self.assertTrue(artifact.exists())
            persisted = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertIn("drawdown_attribution_path", persisted)
            self.assertIsNotNone(persisted["drawdown_attribution_path"])
            ddpath = Path(persisted["drawdown_attribution_path"])
            self.assertTrue(ddpath.exists())

    def test_drawdown_attribution_artifact_schema_on_fail(self) -> None:
        """Drawdown attribution artifact has correct schema even on gate failure."""
        records = [
            _closed_rec(pnl_points=-30.0, result="loss", trade_id="t1"),
            _closed_rec(direction="SELL", pnl_points=-60.0, result="loss", trade_id="t2"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError):
                run_replay_outcome_gate(records, qual, artifact)
            persisted = json.loads(artifact.read_text(encoding="utf-8"))
            dd_path = Path(persisted["drawdown_attribution_path"])
            dd = json.loads(dd_path.read_text(encoding="utf-8"))
            self.assertEqual(dd["schema_version"], "replay.drawdown_attribution.v1")
            self.assertGreater(dd["max_drawdown_points"], 0)
            self.assertGreater(len(dd["worst_drawdown_segments"]), 0)

    def test_failed_gate_report_can_be_read_back_for_main_report(self) -> None:
        """Simulate the run_replay_evaluation pattern: catch, read back, persist."""
        records = [
            _closed_rec(pnl_points=-30.0, result="loss", trade_id="t1"),
            _closed_rec(direction="SELL", pnl_points=-60.0, result="loss", trade_id="t2"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            outcome_artifact = Path(tmpdir) / "outcome.json"
            eval_report: dict[str, Any] = {"records": records}

            try:
                outcome_report = run_replay_outcome_gate(records, qual, outcome_artifact)
            except ReplayOutcomeError:
                # Replicate the fixed plumbing in run_replay_evaluation
                outcome_report = json.loads(
                    outcome_artifact.read_text(encoding="utf-8")
                )

            eval_report["replay_outcome"] = outcome_report

            # Persist main evaluation report
            main_path = Path(tmpdir) / "evaluation.json"
            main_path.write_text(json.dumps(eval_report, indent=2), encoding="utf-8")

            reloaded = json.loads(main_path.read_text(encoding="utf-8"))
            self.assertIn("replay_outcome", reloaded)
            self.assertIn("drawdown_attribution_path", reloaded["replay_outcome"])
            self.assertIsNotNone(reloaded["replay_outcome"]["drawdown_attribution_path"])

    def test_drawdown_attribution_segments_have_signature(self) -> None:
        """Each worst segment must have a deterministic signature and fingerprint."""
        records = [
            _closed_rec(pnl_points=5.0, result="win", trade_id="t1"),
            _closed_rec(direction="SELL", pnl_points=-60.0, result="loss", trade_id="t2"),
        ]
        qual = _quality(actionable=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "outcome.json"
            with self.assertRaises(ReplayOutcomeError):
                run_replay_outcome_gate(records, qual, artifact)
            persisted = json.loads(artifact.read_text(encoding="utf-8"))
            dd_path = Path(persisted["drawdown_attribution_path"])
            dd = json.loads(dd_path.read_text(encoding="utf-8"))
            for seg in dd["worst_drawdown_segments"]:
                self.assertIn("segment_signature", seg)
                self.assertIn("segment_fingerprint", seg)
                self.assertIn("contributing_trade_ids", seg)
                self.assertIn("contributing_record_indexes", seg)


if __name__ == "__main__":
    unittest.main()
