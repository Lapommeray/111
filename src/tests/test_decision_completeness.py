"""Tests for the decision-completeness gate.

Covers every terminal state (actionable, blocked, abstain, invalid) and all
failure conditions required by the gate specification.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.decision_completeness import (
    DecisionCompletenessError,
    classify_record,
    run_decision_completeness_gate,
    validate_records,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    action: str = "BUY",
    confidence: float = 0.85,
    blocked: bool = False,
    blocker_reasons: list[str] | None = None,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal evaluation record with the given signal fields."""
    return {
        "signal": {
            "action": action,
            "confidence": confidence,
            "blocked": blocked,
            "blocker_reasons": blocker_reasons or [],
            "reasons": reasons or [],
        }
    }


# ---------------------------------------------------------------------------
# classify_record tests
# ---------------------------------------------------------------------------


class TestClassifyRecord(unittest.TestCase):
    """Unit tests for classify_record()."""

    # -- valid states -------------------------------------------------------

    def test_valid_action_buy(self) -> None:
        state, _ = classify_record(_make_record(action="BUY", confidence=0.8))
        self.assertEqual(state, "actionable")

    def test_valid_action_sell(self) -> None:
        state, _ = classify_record(_make_record(action="SELL", confidence=0.6))
        self.assertEqual(state, "actionable")

    def test_valid_blocked(self) -> None:
        state, _ = classify_record(
            _make_record(blocked=True, blocker_reasons=["spread_filter"])
        )
        self.assertEqual(state, "blocked")

    def test_valid_abstain(self) -> None:
        state, _ = classify_record(
            _make_record(action="WAIT", confidence=0.0, reasons=["low confluence"])
        )
        self.assertEqual(state, "abstain")

    # -- invalid / failure states -------------------------------------------

    def test_unblocked_empty_decision_fields(self) -> None:
        """Unblocked record with no action → invalid."""
        record: dict[str, Any] = {
            "signal": {
                "action": None,
                "confidence": None,
                "blocked": False,
                "blocker_reasons": [],
                "reasons": [],
            }
        }
        state, _ = classify_record(record)
        self.assertEqual(state, "invalid")

    def test_blocked_without_reason(self) -> None:
        state, _ = classify_record(
            _make_record(blocked=True, blocker_reasons=[])
        )
        self.assertEqual(state, "invalid")

    def test_wait_without_reasons(self) -> None:
        """No-trade / abstain without why_not_trade → invalid."""
        state, _ = classify_record(
            _make_record(action="WAIT", confidence=0.0, reasons=[])
        )
        self.assertEqual(state, "invalid")

    def test_action_without_confidence(self) -> None:
        state, _ = classify_record(
            _make_record(action="BUY", confidence=0.0)
        )
        self.assertEqual(state, "invalid")

    def test_action_with_none_confidence(self) -> None:
        record: dict[str, Any] = {
            "signal": {
                "action": "SELL",
                "confidence": None,
                "blocked": False,
                "blocker_reasons": [],
                "reasons": [],
            }
        }
        state, _ = classify_record(record)
        self.assertEqual(state, "invalid")

    def test_missing_signal_key(self) -> None:
        state, _ = classify_record({})
        self.assertEqual(state, "invalid")

    def test_empty_action_string(self) -> None:
        state, _ = classify_record(
            _make_record(action="", confidence=0.5)
        )
        self.assertEqual(state, "invalid")

    def test_unrecognised_action(self) -> None:
        state, _ = classify_record(
            _make_record(action="HOLD", confidence=0.5)
        )
        self.assertEqual(state, "invalid")


# ---------------------------------------------------------------------------
# validate_records tests
# ---------------------------------------------------------------------------


class TestValidateRecords(unittest.TestCase):

    def test_all_valid_records(self) -> None:
        records = [
            _make_record(action="BUY", confidence=0.9),
            _make_record(blocked=True, blocker_reasons=["session_filter"]),
            _make_record(action="WAIT", confidence=0.0, reasons=["no setup"]),
        ]
        report = validate_records(records)
        self.assertTrue(report["passed"])
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["counts"]["actionable"], 1)
        self.assertEqual(report["counts"]["blocked"], 1)
        self.assertEqual(report["counts"]["abstain"], 1)
        self.assertEqual(report["counts"]["invalid"], 0)

    def test_mixed_valid_and_invalid(self) -> None:
        records = [
            _make_record(action="BUY", confidence=0.9),
            _make_record(action="WAIT", confidence=0.0, reasons=[]),  # invalid
        ]
        report = validate_records(records)
        self.assertFalse(report["passed"])
        self.assertEqual(report["failure_count"], 1)
        self.assertEqual(report["counts"]["actionable"], 1)
        self.assertEqual(report["counts"]["invalid"], 1)

    def test_empty_records_list(self) -> None:
        report = validate_records([])
        self.assertTrue(report["passed"])
        self.assertEqual(report["total_records"], 0)


# ---------------------------------------------------------------------------
# run_decision_completeness_gate tests
# ---------------------------------------------------------------------------


class TestDecisionCompletenessGate(unittest.TestCase):

    def test_gate_passes_and_persists_artifact(self) -> None:
        records = [
            _make_record(action="SELL", confidence=0.7),
            _make_record(blocked=True, blocker_reasons=["spread_filter"]),
            _make_record(action="WAIT", confidence=0.0, reasons=["ranging market"]),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            report = run_decision_completeness_gate(records, path)
            self.assertTrue(report["passed"])
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertEqual(persisted["total_records"], 3)
            self.assertEqual(persisted["failure_count"], 0)

    def test_gate_fails_on_invalid_records(self) -> None:
        records = [
            _make_record(action="BUY", confidence=0.0),  # invalid
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            with self.assertRaises(DecisionCompletenessError):
                run_decision_completeness_gate(records, path)
            # Artifact is still persisted even on failure
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text())
            self.assertFalse(persisted["passed"])

    def test_gate_creates_parent_directories(self) -> None:
        records = [_make_record(action="BUY", confidence=0.9)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "deep" / "report.json"
            report = run_decision_completeness_gate(records, path)
            self.assertTrue(path.exists())
            self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
