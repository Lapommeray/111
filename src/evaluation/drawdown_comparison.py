"""Compare drawdown attribution artifacts from included vs quarantined replays.

Reads two drawdown-attribution JSON artifacts (produced by the replay-outcome
gate) and emits a deterministic comparison report identifying:

* Shared worst-segment signatures / fingerprints
* Contributing trade IDs that appear in both runs
* Overlapping replay windows
* Per-segment reason/blocker annotations (from the equity-path events)

The output is a plain dict suitable for JSON serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _segment_key(segment: dict[str, Any]) -> str:
    """Return a deterministic key for a worst-drawdown segment."""
    return (
        f"{segment.get('peak_event_index', '?')}"
        f"->{segment.get('trough_event_index', '?')}"
        f"|dd={float(segment.get('drawdown_points', 0)):.3f}"
    )


def _trade_ids(segment: dict[str, Any]) -> list[str]:
    """Return contributing trade IDs from a segment."""
    return [str(t) for t in segment.get("contributing_trade_ids", [])]


def _record_indexes(segment: dict[str, Any]) -> list[int]:
    """Return contributing record indexes from a segment."""
    return [int(r) for r in segment.get("contributing_record_indexes", [])]


def _replay_windows(segment: dict[str, Any]) -> list[Any]:
    """Return contributing replay windows from a segment."""
    return list(segment.get("contributing_replay_windows", []))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare_drawdown_attributions(
    included: dict[str, Any],
    quarantined: dict[str, Any],
) -> dict[str, Any]:
    """Compare two drawdown-attribution payloads and return a comparison report.

    Parameters
    ----------
    included:
        Drawdown-attribution dict from the "included" (no quarantine) replay.
    quarantined:
        Drawdown-attribution dict from the "quarantined" replay.

    Returns
    -------
    dict
        A comparison report with shared segments, divergences, and
        matched trade IDs.
    """
    inc_segments = included.get("worst_drawdown_segments", [])
    quar_segments = quarantined.get("worst_drawdown_segments", [])

    # Build lookup maps keyed by deterministic segment key
    inc_by_key = {_segment_key(s): s for s in inc_segments}
    quar_by_key = {_segment_key(s): s for s in quar_segments}

    shared_keys = sorted(set(inc_by_key) & set(quar_by_key))
    included_only_keys = sorted(set(inc_by_key) - set(quar_by_key))
    quarantined_only_keys = sorted(set(quar_by_key) - set(inc_by_key))

    shared_segments: list[dict[str, Any]] = []
    for key in shared_keys:
        inc_seg = inc_by_key[key]
        quar_seg = quar_by_key[key]

        inc_trades = set(_trade_ids(inc_seg))
        quar_trades = set(_trade_ids(quar_seg))
        shared_trades = sorted(inc_trades & quar_trades)

        inc_windows = _replay_windows(inc_seg)
        quar_windows = _replay_windows(quar_seg)

        inc_records = set(_record_indexes(inc_seg))
        quar_records = set(_record_indexes(quar_seg))
        shared_records = sorted(inc_records & quar_records)

        # Extract blocker/reason annotations from equity-path events
        blockers: list[str] = []
        for event in inc_seg.get("equity_path_peak_to_trough", []):
            if float(event.get("net_points", 0.0)) < 0:
                trade_id = str(event.get("trade_id", ""))
                direction = str(event.get("direction", ""))
                net = float(event.get("net_points", 0.0))
                blockers.append(
                    f"trade={trade_id} dir={direction} net={net:.3f}"
                )

        shared_segments.append({
            "segment_key": key,
            "segment_signature_included": str(inc_seg.get("segment_signature", "")),
            "segment_signature_quarantined": str(quar_seg.get("segment_signature", "")),
            "segment_fingerprint_included": str(inc_seg.get("segment_fingerprint", "")),
            "segment_fingerprint_quarantined": str(quar_seg.get("segment_fingerprint", "")),
            "drawdown_points": float(inc_seg.get("drawdown_points", 0)),
            "shared_trade_ids": shared_trades,
            "shared_record_indexes": shared_records,
            "included_replay_windows": inc_windows,
            "quarantined_replay_windows": quar_windows,
            "included_trade_ids": sorted(inc_trades),
            "quarantined_trade_ids": sorted(quar_trades),
            "blockers_reasons": blockers,
        })

    return {
        "schema_version": "drawdown_comparison.v1",
        "included_max_drawdown_points": float(
            included.get("max_drawdown_points", 0)
        ),
        "quarantined_max_drawdown_points": float(
            quarantined.get("max_drawdown_points", 0)
        ),
        "included_closed_trade_count": int(
            included.get("closed_trade_count", 0)
        ),
        "quarantined_closed_trade_count": int(
            quarantined.get("closed_trade_count", 0)
        ),
        "shared_segment_count": len(shared_segments),
        "included_only_segment_count": len(included_only_keys),
        "quarantined_only_segment_count": len(quarantined_only_keys),
        "shared_segments": shared_segments,
        "included_only_segment_keys": included_only_keys,
        "quarantined_only_segment_keys": quarantined_only_keys,
        "identical_worst_drawdown": (
            float(included.get("max_drawdown_points", -1))
            == float(quarantined.get("max_drawdown_points", -2))
        ),
    }


def compare_drawdown_files(
    included_path: str | Path,
    quarantined_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load two attribution JSON files, compare, and optionally persist.

    Parameters
    ----------
    included_path:
        Path to included (no quarantine) drawdown attribution JSON.
    quarantined_path:
        Path to quarantined drawdown attribution JSON.
    output_path:
        If provided, write the comparison report here.

    Returns
    -------
    dict
        The comparison report.
    """
    included = json.loads(Path(included_path).read_text(encoding="utf-8"))
    quarantined = json.loads(
        Path(quarantined_path).read_text(encoding="utf-8")
    )
    result = compare_drawdown_attributions(included, quarantined)

    if output_path is not None:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result
