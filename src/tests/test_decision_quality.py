"""Tests for the decision-quality / distribution sanity gate.

Covers fail conditions (no actionable, all abstain, bad reasons, flat
confidence) and pass conditions (healthy mixed run).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.decision_quality import (
    DecisionQualityError,
    _is_bad_reason,
    assess_decision_quality,
    run_decision_quality_gate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rec(
    action: str = "BUY",
    confidence: float = 0.85,
    blocked: bool = False,
    blocker_reasons: list[str] | None = None,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "signal": {
            "action": action,
            "confidence": confidence,
            "blocked": blocked,
            "blocker_reasons": blocker_reasons or [],
            "reasons": reasons or [],
        }
    }


def _completeness_counts(
    actionable: int = 0,
    blocked: int = 0,
    abstain: int = 0,
    invalid: int = 0,
) -> dict[str, int]:
    return {
        "actionable": actionable,
        "blocked": blocked,
        "abstain": abstain,
        "invalid": invalid,
    }


# ---------------------------------------------------------------------------
# _is_bad_reason unit tests
# ---------------------------------------------------------------------------


class TestIsBadReason(unittest.TestCase):

    def test_empty_string(self) -> None:
        self.assertTrue(_is_bad_reason(""))

    def test_whitespace_only(self) -> None:
        self.assertTrue(_is_bad_reason("   "))

    def test_placeholder_todo(self) -> None:
        self.assertTrue(_is_bad_reason("TODO"))

    def test_placeholder_na(self) -> None:
        self.assertTrue(_is_bad_reason("N/A"))

    def test_placeholder_none(self) -> None:
        self.assertTrue(_is_bad_reason("none"))

    def test_placeholder_dots(self) -> None:
        self.assertTrue(_is_bad_reason("..."))

    def test_valid_reason(self) -> None:
        self.assertFalse(_is_bad_reason("displacement detected in M5"))

    def test_non_string(self) -> None:
        self.assertTrue(_is_bad_reason(123))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# assess_decision_quality tests
# ---------------------------------------------------------------------------


class TestAssessDecisionQuality(unittest.TestCase):

    def test_healthy_mixed_run_passes(self) -> None:
        records = [
            _rec(action="BUY", confidence=0.85, reasons=["displacement detected"]),
            _rec(action="SELL", confidence=0.72, reasons=["trend reversal"]),
            _rec(action="WAIT", confidence=0.0, reasons=["no setup"]),
            _rec(action="WAIT", blocked=True, blocker_reasons=["session_filter"]),
        ]
        counts = _completeness_counts(actionable=2, blocked=1, abstain=1)
        report = assess_decision_quality(records, counts)
        self.assertTrue(report["passed"])
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["actionable_count"], 2)
        self.assertEqual(report["blocked_count"], 1)
        self.assertEqual(report["abstain_count"], 1)
        self.assertGreater(report["actionable_ratio"], 0)
        self.assertEqual(report["buy_vs_sell_distribution"], {"BUY": 1, "SELL": 1})

    def test_all_abstain_fails(self) -> None:
        records = [
            _rec(action="WAIT", confidence=0.0, reasons=["no setup"]),
            _rec(action="WAIT", confidence=0.0, reasons=["ranging"]),
            _rec(action="WAIT", confidence=0.0, reasons=["low volume"]),
        ]
        counts = _completeness_counts(abstain=3)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("0 actionable" in f for f in report["failures"]))

    def test_no_actionable_records_fails(self) -> None:
        records = [
            _rec(blocked=True, blocker_reasons=["spread_filter"]),
            _rec(action="WAIT", confidence=0.0, reasons=["low confluence"]),
        ]
        counts = _completeness_counts(blocked=1, abstain=1)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("0 actionable" in f for f in report["failures"]))

    def test_flat_confidence_flagged(self) -> None:
        records = [
            _rec(action="BUY", confidence=0.5, reasons=["reason a"]),
            _rec(action="SELL", confidence=0.5, reasons=["reason b"]),
            _rec(action="BUY", confidence=0.5, reasons=["reason c"]),
        ]
        counts = _completeness_counts(actionable=3)
        report = assess_decision_quality(records, counts)
        # Should pass (flat confidence is a flag, not hard fail)
        self.assertTrue(report["passed"])
        self.assertTrue(report["confidence_summary"]["flat_confidence"])
        self.assertTrue(len(report["flags"]) > 0)
        self.assertTrue(any("flat confidence" in f for f in report["flags"]))

    def test_empty_string_reasons_fails(self) -> None:
        records = [
            _rec(action="BUY", confidence=0.8, reasons=[""]),
        ]
        counts = _completeness_counts(actionable=1)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("bad reasons" in f for f in report["failures"]))

    def test_whitespace_reasons_fails(self) -> None:
        records = [
            _rec(action="BUY", confidence=0.8, reasons=["  "]),
        ]
        counts = _completeness_counts(actionable=1)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])

    def test_placeholder_reasons_fails(self) -> None:
        records = [
            _rec(action="SELL", confidence=0.7, reasons=["TODO"]),
        ]
        counts = _completeness_counts(actionable=1)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])

    def test_placeholder_blocker_reasons_fails(self) -> None:
        records = [
            _rec(blocked=True, blocker_reasons=["n/a"]),
        ]
        counts = _completeness_counts(blocked=1, actionable=1)
        # Need at least one actionable to not also fail the no-actionable check
        # when combined — but here we test reason quality in isolation:
        # Actually we need actionable to exist. Let's add one.
        records.append(_rec(action="BUY", confidence=0.9, reasons=["real reason"]))
        counts = _completeness_counts(blocked=1, actionable=1)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("bad reasons" in f for f in report["failures"]))

    def test_degenerate_abstain_ratio_fails(self) -> None:
        """96% abstain exceeds the 95% threshold."""
        records = [_rec(action="WAIT", confidence=0.0, reasons=["low vol"])] * 96
        records.append(_rec(action="BUY", confidence=0.8, reasons=["ok"]))
        # remaining 3 are blocked
        records.extend([_rec(blocked=True, blocker_reasons=["filter"])] * 3)
        counts = _completeness_counts(actionable=1, blocked=3, abstain=96)
        report = assess_decision_quality(records, counts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("degenerate" in f for f in report["failures"]))

    def test_non_string_reason_in_record_fails(self) -> None:
        """Non-string reason values (e.g. int) must be caught at record level."""
        record: dict[str, Any] = {
            "signal": {
                "action": "BUY",
                "confidence": 0.8,
                "blocked": False,
                "blocker_reasons": [],
                "reasons": [123],  # type: ignore[list-item]
            }
        }
        counts = _completeness_counts(actionable=1)
        report = assess_decision_quality([record], counts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("bad reasons" in f for f in report["failures"]))

    def test_empty_run_passes(self) -> None:
        report = assess_decision_quality([], _completeness_counts())
        self.assertTrue(report["passed"])

    def test_single_actionable_record_passes(self) -> None:
        records = [_rec(action="BUY", confidence=0.9, reasons=["strong setup"])]
        counts = _completeness_counts(actionable=1)
        report = assess_decision_quality(records, counts)
        self.assertTrue(report["passed"])
        # Single record can't be flat
        self.assertFalse(report["confidence_summary"]["flat_confidence"])

    def test_confidence_summary_values(self) -> None:
        records = [
            _rec(action="BUY", confidence=0.6, reasons=["a"]),
            _rec(action="SELL", confidence=0.9, reasons=["b"]),
            _rec(action="BUY", confidence=0.75, reasons=["c"]),
        ]
        counts = _completeness_counts(actionable=3)
        report = assess_decision_quality(records, counts)
        conf = report["confidence_summary"]
        self.assertEqual(conf["count"], 3)
        self.assertAlmostEqual(conf["min"], 0.6)
        self.assertAlmostEqual(conf["max"], 0.9)
        self.assertAlmostEqual(conf["mean"], 0.75)
        self.assertEqual(conf["unique_count"], 3)


# ---------------------------------------------------------------------------
# run_decision_quality_gate tests
# ---------------------------------------------------------------------------


class TestDecisionQualityGate(unittest.TestCase):

    def test_gate_passes_and_persists(self) -> None:
        records = [
            _rec(action="BUY", confidence=0.85, reasons=["displacement"]),
            _rec(action="SELL", confidence=0.70, reasons=["reversal"]),
            _rec(action="WAIT", confidence=0.0, reasons=["no setup"]),
        ]
        comp = {"counts": _completeness_counts(actionable=2, abstain=1)}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "quality.json"
            report = run_decision_quality_gate(records, comp, path)
            self.assertTrue(report["passed"])
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertTrue(persisted["passed"])
            self.assertEqual(persisted["total_records"], 3)

    def test_gate_fails_and_persists(self) -> None:
        records = [
            _rec(action="WAIT", confidence=0.0, reasons=["no setup"]),
        ]
        comp = {"counts": _completeness_counts(abstain=1)}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "quality.json"
            with self.assertRaises(DecisionQualityError):
                run_decision_quality_gate(records, comp, path)
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertFalse(persisted["passed"])

    def test_gate_creates_parent_dirs(self) -> None:
        records = [_rec(action="BUY", confidence=0.9, reasons=["setup ok"])]
        comp = {"counts": _completeness_counts(actionable=1)}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "quality.json"
            report = run_decision_quality_gate(records, comp, path)
            self.assertTrue(path.exists())
            self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
