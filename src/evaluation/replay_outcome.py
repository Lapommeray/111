"""Replay-outcome gate for economic truth validation.

Runs on top of the decision-quality gate.  While quality proves the output is
structurally believable, this gate proves the *economic* output is measurable:

* If actionable records exist, at least one must produce a closed trade.
* Win rate, average P&L (gross/net), expectancy, and max drawdown are reported.
* Negative net expectancy and zero win rate are flagged.
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

    # Flags for economic degeneracy (reported, not hard fail).
    if closed > 0 and metrics["win_rate"] == 0.0:
        flags.append(f"0% win rate across {closed} closed trade(s)")

    if closed > 0 and metrics["net_expectancy"] < 0:
        flags.append(
            f"negative net expectancy: {metrics['net_expectancy']:.3f} points/trade"
        )

    if (
        closed > 0
        and metrics["max_drawdown_points"] > 0
        and metrics["net_pnl_points"] <= 0
    ):
        flags.append(
            f"net P&L non-positive ({metrics['net_pnl_points']:.3f}) with "
            f"max drawdown {metrics['max_drawdown_points']:.3f} points"
        )

    passed = len(failures) == 0

    return {
        "schema_version": "replay_outcome.v1",
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

    dest = Path(artifact_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not report["passed"]:
        lines = [
            f"Replay-outcome gate FAILED: {report['failure_count']} issue(s).",
        ]
        for f in report["failures"]:
            lines.append(f"  - {f}")
        raise ReplayOutcomeError("\n".join(lines))

    return report
