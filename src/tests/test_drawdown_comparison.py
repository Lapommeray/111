"""Tests for drawdown comparison utility.

Covers:
* Shared segment identification
* Divergence detection (included-only / quarantined-only)
* Trade ID and record index intersection
* Replay window overlap
* Blocker/reason annotation extraction
* File-based comparison with persistence
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.drawdown_comparison import (
    compare_drawdown_attributions,
    compare_drawdown_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attribution(
    max_dd: float = 84.43,
    segments: list[dict[str, Any]] | None = None,
    closed_trade_count: int = 10,
) -> dict[str, Any]:
    """Build a minimal drawdown attribution payload."""
    if segments is None:
        segments = [
            {
                "segment_id": "segment_1",
                "peak_event_index": 3,
                "trough_event_index": 8,
                "peak_equity_points": 10.0,
                "trough_equity_points": -74.43,
                "drawdown_points": max_dd,
                "contributing_trade_ids": ["t4", "t5", "t6", "t7", "t8"],
                "contributing_record_indexes": [5, 7, 9, 12, 15],
                "contributing_replay_windows": [10, 15, 20, 25, 30],
                "equity_path_peak_to_trough": [
                    {"trade_id": "t4", "direction": "BUY", "net_points": -15.0},
                    {"trade_id": "t5", "direction": "SELL", "net_points": -20.0},
                    {"trade_id": "t6", "direction": "BUY", "net_points": 5.0},
                    {"trade_id": "t7", "direction": "SELL", "net_points": -30.0},
                    {"trade_id": "t8", "direction": "BUY", "net_points": -24.43},
                ],
                "equity_path_window": [],
                "segment_signature": "3->8|dd=84.430|records=5,7,9,12,15",
                "segment_fingerprint": "3->8|dd=84.430|trades=t4,t5,t6,t7,t8",
            }
        ]
    return {
        "schema_version": "replay.drawdown_attribution.v1",
        "closed_trade_count": closed_trade_count,
        "max_drawdown_points": max_dd,
        "worst_drawdown_segment_count": len(segments),
        "worst_drawdown_segments": segments,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompareDrawdownAttributions(unittest.TestCase):
    """Unit tests for compare_drawdown_attributions."""

    def test_identical_attributions_produce_one_shared_segment(self) -> None:
        inc = _make_attribution()
        quar = _make_attribution()
        result = compare_drawdown_attributions(inc, quar)
        self.assertEqual(result["schema_version"], "drawdown_comparison.v1")
        self.assertEqual(result["shared_segment_count"], 1)
        self.assertEqual(result["included_only_segment_count"], 0)
        self.assertEqual(result["quarantined_only_segment_count"], 0)
        self.assertTrue(result["identical_worst_drawdown"])

    def test_shared_segment_contains_trade_ids(self) -> None:
        inc = _make_attribution()
        quar = _make_attribution()
        result = compare_drawdown_attributions(inc, quar)
        seg = result["shared_segments"][0]
        self.assertEqual(seg["shared_trade_ids"], ["t4", "t5", "t6", "t7", "t8"])
        self.assertEqual(seg["shared_record_indexes"], [5, 7, 9, 12, 15])

    def test_divergent_segments_separated(self) -> None:
        inc = _make_attribution(max_dd=40.0, segments=[
            {
                "segment_id": "segment_1",
                "peak_event_index": 0,
                "trough_event_index": 2,
                "drawdown_points": 40.0,
                "contributing_trade_ids": ["t1"],
                "contributing_record_indexes": [1],
                "contributing_replay_windows": [5],
                "equity_path_peak_to_trough": [],
                "segment_signature": "inc_sig",
                "segment_fingerprint": "inc_fp",
            }
        ])
        quar = _make_attribution(max_dd=50.0, segments=[
            {
                "segment_id": "segment_1",
                "peak_event_index": 1,
                "trough_event_index": 5,
                "drawdown_points": 50.0,
                "contributing_trade_ids": ["t2"],
                "contributing_record_indexes": [3],
                "contributing_replay_windows": [10],
                "equity_path_peak_to_trough": [],
                "segment_signature": "quar_sig",
                "segment_fingerprint": "quar_fp",
            }
        ])
        result = compare_drawdown_attributions(inc, quar)
        self.assertEqual(result["shared_segment_count"], 0)
        self.assertEqual(result["included_only_segment_count"], 1)
        self.assertEqual(result["quarantined_only_segment_count"], 1)
        self.assertFalse(result["identical_worst_drawdown"])

    def test_partial_trade_overlap(self) -> None:
        inc = _make_attribution(segments=[
            {
                "segment_id": "segment_1",
                "peak_event_index": 3,
                "trough_event_index": 8,
                "drawdown_points": 84.43,
                "contributing_trade_ids": ["t4", "t5", "t6"],
                "contributing_record_indexes": [5, 7, 9],
                "contributing_replay_windows": [10, 15, 20],
                "equity_path_peak_to_trough": [],
                "segment_signature": "sig_a",
                "segment_fingerprint": "fp_a",
            }
        ])
        quar = _make_attribution(segments=[
            {
                "segment_id": "segment_1",
                "peak_event_index": 3,
                "trough_event_index": 8,
                "drawdown_points": 84.43,
                "contributing_trade_ids": ["t5", "t6", "t7"],
                "contributing_record_indexes": [7, 9, 12],
                "contributing_replay_windows": [15, 20, 25],
                "equity_path_peak_to_trough": [],
                "segment_signature": "sig_b",
                "segment_fingerprint": "fp_b",
            }
        ])
        result = compare_drawdown_attributions(inc, quar)
        self.assertEqual(result["shared_segment_count"], 1)
        seg = result["shared_segments"][0]
        self.assertEqual(seg["shared_trade_ids"], ["t5", "t6"])
        self.assertEqual(seg["shared_record_indexes"], [7, 9])

    def test_blockers_extracted_from_equity_path(self) -> None:
        inc = _make_attribution()
        quar = _make_attribution()
        result = compare_drawdown_attributions(inc, quar)
        seg = result["shared_segments"][0]
        # Only losing trades contribute blockers
        self.assertEqual(len(seg["blockers_reasons"]), 4)  # t4, t5, t7, t8

    def test_empty_attributions(self) -> None:
        inc = _make_attribution(max_dd=0, segments=[], closed_trade_count=0)
        quar = _make_attribution(max_dd=0, segments=[], closed_trade_count=0)
        result = compare_drawdown_attributions(inc, quar)
        self.assertEqual(result["shared_segment_count"], 0)
        self.assertTrue(result["identical_worst_drawdown"])

    def test_drawdown_values_surfaced(self) -> None:
        inc = _make_attribution(max_dd=84.43)
        quar = _make_attribution(max_dd=84.43)
        result = compare_drawdown_attributions(inc, quar)
        self.assertEqual(result["included_max_drawdown_points"], 84.43)
        self.assertEqual(result["quarantined_max_drawdown_points"], 84.43)


class TestCompareDrawdownFiles(unittest.TestCase):
    """File-based comparison tests."""

    def test_file_comparison_roundtrip(self) -> None:
        inc = _make_attribution()
        quar = _make_attribution()
        with tempfile.TemporaryDirectory() as tmpdir:
            inc_path = Path(tmpdir) / "included.json"
            quar_path = Path(tmpdir) / "quarantined.json"
            out_path = Path(tmpdir) / "comparison.json"

            inc_path.write_text(json.dumps(inc, indent=2))
            quar_path.write_text(json.dumps(quar, indent=2))

            result = compare_drawdown_files(inc_path, quar_path, out_path)
            self.assertTrue(out_path.exists())
            self.assertEqual(result["schema_version"], "drawdown_comparison.v1")

            reloaded = json.loads(out_path.read_text())
            self.assertEqual(reloaded["shared_segment_count"], 1)

    def test_file_comparison_without_output(self) -> None:
        inc = _make_attribution()
        quar = _make_attribution()
        with tempfile.TemporaryDirectory() as tmpdir:
            inc_path = Path(tmpdir) / "included.json"
            quar_path = Path(tmpdir) / "quarantined.json"

            inc_path.write_text(json.dumps(inc, indent=2))
            quar_path.write_text(json.dumps(quar, indent=2))

            result = compare_drawdown_files(inc_path, quar_path)
            self.assertEqual(result["schema_version"], "drawdown_comparison.v1")

    def test_file_comparison_creates_parent_dirs(self) -> None:
        inc = _make_attribution()
        quar = _make_attribution()
        with tempfile.TemporaryDirectory() as tmpdir:
            inc_path = Path(tmpdir) / "included.json"
            quar_path = Path(tmpdir) / "quarantined.json"
            out_path = Path(tmpdir) / "deep" / "nested" / "comparison.json"

            inc_path.write_text(json.dumps(inc, indent=2))
            quar_path.write_text(json.dumps(quar, indent=2))

            result = compare_drawdown_files(inc_path, quar_path, out_path)
            self.assertTrue(out_path.exists())

    def test_file_not_found_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "does_not_exist.json"
            other = Path(tmpdir) / "other.json"
            other.write_text(json.dumps(_make_attribution()))
            with self.assertRaises(FileNotFoundError):
                compare_drawdown_files(missing, other)
            with self.assertRaises(FileNotFoundError):
                compare_drawdown_files(other, missing)

    def test_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.json"
            good = Path(tmpdir) / "good.json"
            bad.write_text("not valid json {{{")
            good.write_text(json.dumps(_make_attribution()))
            with self.assertRaises(json.JSONDecodeError):
                compare_drawdown_files(bad, good)


if __name__ == "__main__":
    unittest.main()
