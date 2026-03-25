"""Replay-outcome gate for economic truth validation.

Runs on top of the decision-quality gate.  While quality proves the output is
structurally believable, this gate proves the *economic* output is measurable
and enforces minimum economic sanity:

* If actionable records exist, at least one must produce a closed trade.
* Win rate, average P&L (gross/net), expectancy, and max drawdown are reported.
* With ≥ ``_MIN_CLOSED_FOR_ECONOMIC_GATE`` closed trades, the following are
  hard-fail conditions (not just flags):
  - 0% win rate
  - Negative net expectancy
  - Non-positive net P&L with drawdown present
  - Max drawdown exceeding ``_MAX_DRAWDOWN_POINTS_THRESHOLD``
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRADE_DIRECTIONS = {"BUY", "SELL"}

# Minimum closed-trade count before economic fail rules apply.  Runs with
# fewer closed trades are too small to judge economically and only get flags.
_MIN_CLOSED_FOR_ECONOMIC_GATE = 2

# Absolute max-drawdown threshold (in points).  Exceeding this is a hard fail.
_MAX_DRAWDOWN_POINTS_THRESHOLD = 50.0


# ---------------------------------------------------------------------------
# Trade outcome extraction
# ---------------------------------------------------------------------------


def _extract_latest_outcome(record: dict[str, Any]) -> dict[str, Any]:
    """Extract ``latest_trade_outcome`` from a record's status panel."""
    panel = record.get("status_panel")
    if not isinstance(panel, dict):
        return {}
    mem = panel.get("memory_result")
    if not isinstance(mem, dict):
        return {}
    outcome = mem.get("latest_trade_outcome")
    if not isinstance(outcome, dict):
        return {}
    return outcome


def _is_closed_trade(outcome: dict[str, Any]) -> bool:
    """Return True when *outcome* represents a closed BUY/SELL trade."""
    return (
        str(outcome.get("status", "")).lower() == "closed"
        and str(outcome.get("direction", "")).upper() in _TRADE_DIRECTIONS
    )


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute economic metrics from closed trade outcomes in *records*."""
    closed_trades = 0
    wins = 0
    losses = 0
    gross_total = 0.0
    net_total = 0.0
    net_series: list[float] = []

    for record in records:
        outcome = _extract_latest_outcome(record)
        if not _is_closed_trade(outcome):
            continue

        gross = round(
            float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))),
            3,
        )
        net = round(float(outcome.get("pnl_points_net", gross)), 3)
        result = str(outcome.get("result", "")).lower()

        closed_trades += 1
        gross_total = round(gross_total + gross, 3)
        net_total = round(net_total + net, 3)
        net_series.append(net)

        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1

    # Derived metrics
    win_rate = round(wins / closed_trades, 4) if closed_trades else 0.0
    avg_gross = round(gross_total / closed_trades, 3) if closed_trades else 0.0
    avg_net = round(net_total / closed_trades, 3) if closed_trades else 0.0
    net_expectancy = avg_net  # expectancy == mean net P&L per trade

    # Max drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for val in net_series:
        cumulative = round(cumulative + val, 3)
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    max_drawdown = round(abs(max_dd), 3)

    return {
        "closed_trades": closed_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "gross_pnl_points": gross_total,
        "net_pnl_points": net_total,
        "avg_gross_pnl_per_trade": avg_gross,
        "avg_net_pnl_per_trade": avg_net,
        "net_expectancy": net_expectancy,
        "max_drawdown_points": max_drawdown,
    }


def _build_drawdown_attribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build deterministic max-drawdown attribution details for closed trades."""
    trade_events: list[dict[str, Any]] = []
    cumulative = 0.0
    peak_equity = 0.0
    peak_event_index = -1
    max_drawdown_points = 0.0
    worst_segments: list[dict[str, Any]] = []
    event_index = 0

    for record_index, record in enumerate(records):
        outcome = _extract_latest_outcome(record)
        if not _is_closed_trade(outcome):
            continue
        gross = round(
            float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))),
            3,
        )
        net = round(float(outcome.get("pnl_points_net", gross)), 3)
        cumulative = round(cumulative + net, 3)
        if cumulative > peak_equity:
            peak_equity = cumulative
            peak_event_index = event_index
        drawdown = round(peak_equity - cumulative, 3)
        trade_event = {
            "event_index": event_index,
            "record_index": record_index,
            "trade_id": str(outcome.get("trade_id", f"record_{record_index}")),
            "direction": str(outcome.get("direction", "")),
            "result": str(outcome.get("result", "")),
            "gross_points": gross,
            "net_points": net,
            "cumulative_equity_points": cumulative,
            "peak_equity_points": peak_equity,
            "drawdown_points": drawdown,
            "evaluation_step": record.get("evaluation_step"),
            "walk_forward_cycle": record.get("walk_forward_cycle"),
        }
        trade_events.append(trade_event)

        if drawdown > max_drawdown_points:
            max_drawdown_points = drawdown
            worst_segments = [
                {
                    "segment_id": "segment_1",
                    "peak_event_index": peak_event_index,
                    "trough_event_index": event_index,
                    "peak_equity_points": peak_equity,
                    "trough_equity_points": cumulative,
                    "drawdown_points": drawdown,
                }
            ]
        elif drawdown == max_drawdown_points and drawdown > 0:
            segment_id = f"segment_{len(worst_segments) + 1}"
            worst_segments.append(
                {
                    "segment_id": segment_id,
                    "peak_event_index": peak_event_index,
                    "trough_event_index": event_index,
                    "peak_equity_points": peak_equity,
                    "trough_equity_points": cumulative,
                    "drawdown_points": drawdown,
                }
            )

        event_index += 1

    for segment in worst_segments:
        peak_idx = int(segment["peak_event_index"])
        trough_idx = int(segment["trough_event_index"])
        left = max(0, peak_idx - 3)
        right = min(len(trade_events) - 1, trough_idx + 3)
        segment_events = trade_events[peak_idx : trough_idx + 1] if trough_idx >= peak_idx >= 0 else []
        contributing_trade_ids = [
            str(event.get("trade_id", ""))
            for event in segment_events
            if float(event.get("net_points", 0.0)) < 0
        ]
        contributing_record_indexes = [
            int(event.get("record_index", -1))
            for event in segment_events
            if float(event.get("net_points", 0.0)) < 0
        ]
        contributing_steps = [
            event.get("evaluation_step")
            for event in segment_events
            if event.get("evaluation_step") is not None
        ]
        segment["contributing_trade_ids"] = contributing_trade_ids
        segment["contributing_record_indexes"] = contributing_record_indexes
        segment["contributing_replay_windows"] = contributing_steps
        segment["equity_path_window"] = trade_events[left : right + 1]
        segment["equity_path_peak_to_trough"] = segment_events
        segment["segment_signature"] = (
            f"{segment['peak_event_index']}->{segment['trough_event_index']}"
            f"|dd={segment['drawdown_points']:.3f}"
            f"|records={','.join(str(idx) for idx in contributing_record_indexes)}"
        )
        segment["segment_fingerprint"] = (
            f"{segment['peak_event_index']}->{segment['trough_event_index']}"
            f"|dd={segment['drawdown_points']:.3f}"
            f"|trades={','.join(contributing_trade_ids)}"
        )

    return {
        "schema_version": "replay.drawdown_attribution.v1",
        "closed_trade_count": len(trade_events),
        "max_drawdown_points": round(max_drawdown_points, 3),
        "worst_drawdown_segment_count": len(worst_segments),
        "worst_drawdown_segments": worst_segments,
    }


# ---------------------------------------------------------------------------
# Core outcome assessment
# ---------------------------------------------------------------------------


def assess_replay_outcome(
    records: list[dict[str, Any]],
    quality_report: dict[str, Any],
) -> dict[str, Any]:
    """Produce a replay-outcome report.

    Parameters
    ----------
    records:
        Evaluation records list.
    quality_report:
        The report dict from the quality gate (must have ``actionable_count``).
    """
    actionable = int(quality_report.get("actionable_count", 0))
    metrics = _compute_metrics(records)
    closed = metrics["closed_trades"]

    failures: list[str] = []
    flags: list[str] = []

    # Hard fail: actionable decisions exist but no trades closed.
    if actionable > 0 and closed == 0:
        failures.append(
            f"{actionable} actionable record(s) but 0 closed trades — "
            f"trade simulation produced no measurable outcomes"
        )

    # --- Economic sanity enforcement ---
    # When closed trades meet the minimum threshold, economic degeneracy is a
    # hard fail.  Below the threshold the same conditions are flagged as
    # warnings — too few trades to be statistically meaningful.
    meaningful = closed >= _MIN_CLOSED_FOR_ECONOMIC_GATE

    if closed > 0 and metrics["win_rate"] == 0.0:
        msg = f"0% win rate across {closed} closed trade(s)"
        if meaningful:
            failures.append(msg)
        else:
            flags.append(msg)

    if closed > 0 and metrics["net_expectancy"] < 0:
        msg = (
            f"negative net expectancy: "
            f"{metrics['net_expectancy']:.3f} points/trade"
        )
        if meaningful:
            failures.append(msg)
        else:
            flags.append(msg)

    if (
        closed > 0
        and metrics["max_drawdown_points"] > 0
        and metrics["net_pnl_points"] <= 0
    ):
        msg = (
            f"net P&L non-positive ({metrics['net_pnl_points']:.3f}) with "
            f"max drawdown {metrics['max_drawdown_points']:.3f} points"
        )
        if meaningful:
            failures.append(msg)
        else:
            flags.append(msg)

    if closed > 0 and metrics["max_drawdown_points"] > _MAX_DRAWDOWN_POINTS_THRESHOLD:
        msg = (
            f"max drawdown {metrics['max_drawdown_points']:.3f} points "
            f"exceeds threshold {_MAX_DRAWDOWN_POINTS_THRESHOLD:.1f}"
        )
        if meaningful:
            failures.append(msg)
        else:
            flags.append(msg)

    passed = len(failures) == 0

    return {
        "schema_version": "replay_outcome.v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "actionable_count": actionable,
        "closed_trades": closed,
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "win_rate": metrics["win_rate"],
        "gross_pnl_points": metrics["gross_pnl_points"],
        "net_pnl_points": metrics["net_pnl_points"],
        "avg_gross_pnl_per_trade": metrics["avg_gross_pnl_per_trade"],
        "avg_net_pnl_per_trade": metrics["avg_net_pnl_per_trade"],
        "net_expectancy": metrics["net_expectancy"],
        "max_drawdown_points": metrics["max_drawdown_points"],
        "passed": passed,
        "failure_count": len(failures),
        "failures": failures,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Gate entry-point
# ---------------------------------------------------------------------------


class ReplayOutcomeError(Exception):
    """Raised when evaluation output fails the outcome gate."""


def run_replay_outcome_gate(
    records: list[dict[str, Any]],
    quality_report: dict[str, Any],
    artifact_path: str | Path,
) -> dict[str, Any]:
    """Run the replay-outcome gate and persist the report artifact.

    Parameters
    ----------
    records:
        The ``records`` list produced by :func:`evaluate_replay`.
    quality_report:
        The report dict returned by the quality gate.
    artifact_path:
        Filesystem path where the JSON outcome report will be written.

    Returns
    -------
    dict
        The outcome report (also persisted to *artifact_path*).

    Raises
    ------
    ReplayOutcomeError
        If any hard-fail condition is met.
    """
    report = assess_replay_outcome(records, quality_report)

    drawdown_attribution = _build_drawdown_attribution(records)
    dest = Path(artifact_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    drawdown_dest = dest.with_name(f"{dest.stem}_drawdown_attribution{dest.suffix}")
    drawdown_dest.write_text(
        json.dumps(drawdown_attribution, indent=2),
        encoding="utf-8",
    )
    report["drawdown_attribution_path"] = str(drawdown_dest)
    report["drawdown_attribution_schema_version"] = str(
        drawdown_attribution.get("schema_version", "")
    )
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not report["passed"]:
        lines = [
            f"Replay-outcome gate FAILED: {report['failure_count']} issue(s).",
        ]
        for f in report["failures"]:
            lines.append(f"  - {f}")
        raise ReplayOutcomeError("\n".join(lines))

    return report
