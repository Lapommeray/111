"""Replay-threshold calibration report.

Runs on top of the replay-outcome gate.  While the outcome gate enforces
hard-fail economic sanity using fixed thresholds, this module analyses the
*actual* replay result distributions to produce an evidence-based calibration
report that can justify or tighten those thresholds.

The calibration report computes:
* Per-trade P&L distribution stats (min, max, mean, median, stdev, p10, p90)
* Drawdown distribution stats
* Win-rate distribution across the run
* Observed trade count vs minimum-meaningful-trade threshold
* Observed max drawdown vs threshold
* Observed net expectancy vs threshold (floor = 0)
* Recommendation state per threshold: ``confirmed`` or ``tighten``

No thresholds are *changed* automatically — the calibration report is purely
diagnostic.  A human or a future policy layer reads the artifact and decides.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.evaluation.replay_outcome import (
    _MAX_DRAWDOWN_POINTS_THRESHOLD,
    _MIN_CLOSED_FOR_ECONOMIC_GATE,
    _compute_metrics,
    _extract_latest_outcome,
    _is_closed_trade,
)


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Return the *pct*-th percentile from an already-sorted list.

    Uses nearest-rank (ceiling) method.  Returns 0.0 for empty input.
    """
    if not sorted_vals:
        return 0.0
    k = max(0, math.ceil(pct / 100.0 * len(sorted_vals)) - 1)
    return round(sorted_vals[k], 4)


def _stdev(vals: list[float], mean: float) -> float:
    """Population standard deviation."""
    if len(vals) < 2:
        return 0.0
    ss = sum((v - mean) ** 2 for v in vals)
    return round(math.sqrt(ss / len(vals)), 4)


# ---------------------------------------------------------------------------
# Core calibration
# ---------------------------------------------------------------------------


def calibrate_thresholds(
    records: list[dict[str, Any]],
    outcome_report: dict[str, Any],
) -> dict[str, Any]:
    """Produce a threshold-calibration report from replay results.

    Parameters
    ----------
    records:
        The evaluation records list (same as passed to outcome gate).
    outcome_report:
        The report dict returned by :func:`run_replay_outcome_gate`.
    """
    # -- extract per-trade P&L series --
    net_pnls: list[float] = []
    gross_pnls: list[float] = []
    for record in records:
        outcome = _extract_latest_outcome(record)
        if not _is_closed_trade(outcome):
            continue
        gross = round(
            float(outcome.get("pnl_points_gross", outcome.get("pnl_points", 0.0))),
            4,
        )
        net = round(float(outcome.get("pnl_points_net", gross)), 4)
        gross_pnls.append(gross)
        net_pnls.append(net)

    closed_trades = len(net_pnls)
    sorted_net = sorted(net_pnls)
    sorted_gross = sorted(gross_pnls)

    # -- basic stats --
    net_mean = round(sum(net_pnls) / closed_trades, 4) if closed_trades else 0.0
    gross_mean = round(sum(gross_pnls) / closed_trades, 4) if closed_trades else 0.0

    net_dist = {
        "count": closed_trades,
        "min": round(sorted_net[0], 4) if sorted_net else 0.0,
        "max": round(sorted_net[-1], 4) if sorted_net else 0.0,
        "mean": net_mean,
        "median": _percentile(sorted_net, 50),
        "stdev": _stdev(net_pnls, net_mean),
        "p10": _percentile(sorted_net, 10),
        "p90": _percentile(sorted_net, 90),
    }
    gross_dist = {
        "count": closed_trades,
        "min": round(sorted_gross[0], 4) if sorted_gross else 0.0,
        "max": round(sorted_gross[-1], 4) if sorted_gross else 0.0,
        "mean": gross_mean,
        "median": _percentile(sorted_gross, 50),
        "stdev": _stdev(gross_pnls, gross_mean),
        "p10": _percentile(sorted_gross, 10),
        "p90": _percentile(sorted_gross, 90),
    }

    # -- drawdown series (peak-to-trough per cumulative curve) --
    cumulative = 0.0
    peak = 0.0
    drawdowns: list[float] = []
    for val in net_pnls:
        cumulative = round(cumulative + val, 4)
        peak = max(peak, cumulative)
        dd = round(peak - cumulative, 4)
        if dd > 0:
            drawdowns.append(dd)
    sorted_dd = sorted(drawdowns)
    max_drawdown = round(max(drawdowns), 4) if drawdowns else 0.0

    dd_dist = {
        "observations": len(drawdowns),
        "max": max_drawdown,
        "mean": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else 0.0,
        "median": _percentile(sorted_dd, 50),
        "p90": _percentile(sorted_dd, 90),
        "p95": _percentile(sorted_dd, 95),
    }

    # -- current thresholds --
    current_thresholds = {
        "min_closed_for_economic_gate": _MIN_CLOSED_FOR_ECONOMIC_GATE,
        "max_drawdown_points_threshold": _MAX_DRAWDOWN_POINTS_THRESHOLD,
        "expectancy_floor": 0.0,  # hard fail when < 0
        "win_rate_floor": 0.0,    # hard fail when == 0% (i.e. floor is > 0%)
    }

    # -- observed values from outcome report --
    observed_win_rate = float(outcome_report.get("win_rate", 0.0))
    observed_expectancy = float(outcome_report.get("net_expectancy", 0.0))
    observed_max_dd = float(outcome_report.get("max_drawdown_points", 0.0))

    # -- calibration recommendations --
    recommendations: dict[str, Any] = {}

    # Trade count: if we have many more trades than the threshold, it's
    # confirmed.  If we're at or below, the threshold may be generous.
    if closed_trades >= _MIN_CLOSED_FOR_ECONOMIC_GATE * 3:
        recommendations["min_closed_for_economic_gate"] = {
            "state": "confirmed",
            "reason": (
                f"observed {closed_trades} closed trades, "
                f"well above threshold {_MIN_CLOSED_FOR_ECONOMIC_GATE}"
            ),
        }
    else:
        recommendations["min_closed_for_economic_gate"] = {
            "state": "tighten",
            "reason": (
                f"observed only {closed_trades} closed trades vs "
                f"threshold {_MIN_CLOSED_FOR_ECONOMIC_GATE} — "
                f"sample may be too small for robust calibration"
            ),
        }

    # Drawdown cap: if p95 of drawdown observations is well below the
    # threshold, the threshold is generous and could be tightened.
    dd_p95 = dd_dist["p95"]
    dd_headroom = _MAX_DRAWDOWN_POINTS_THRESHOLD - dd_p95 if dd_p95 > 0 else _MAX_DRAWDOWN_POINTS_THRESHOLD
    if dd_p95 > 0 and dd_headroom > _MAX_DRAWDOWN_POINTS_THRESHOLD * 0.5:
        recommendations["max_drawdown_points_threshold"] = {
            "state": "tighten",
            "reason": (
                f"p95 drawdown {dd_p95:.3f} is far below "
                f"threshold {_MAX_DRAWDOWN_POINTS_THRESHOLD:.1f} — "
                f"headroom {dd_headroom:.1f} points suggests tightening"
            ),
            "suggested_cap": round(dd_p95 * 2, 1),
        }
    else:
        recommendations["max_drawdown_points_threshold"] = {
            "state": "confirmed",
            "reason": (
                f"p95 drawdown {dd_p95:.3f} vs "
                f"threshold {_MAX_DRAWDOWN_POINTS_THRESHOLD:.1f} — "
                f"headroom is appropriate"
            ),
        }

    # Expectancy floor: if observed expectancy is well above 0, confirmed.
    # If marginally above or at 0, consider tightening to require positive.
    if observed_expectancy > 1.0:
        recommendations["expectancy_floor"] = {
            "state": "confirmed",
            "reason": (
                f"observed net expectancy {observed_expectancy:.3f} "
                f"is clearly positive"
            ),
        }
    elif observed_expectancy > 0:
        recommendations["expectancy_floor"] = {
            "state": "tighten",
            "reason": (
                f"observed net expectancy {observed_expectancy:.3f} "
                f"is marginally positive — consider requiring > 0.5"
            ),
            "suggested_floor": 0.5,
        }
    else:
        recommendations["expectancy_floor"] = {
            "state": "confirmed",
            "reason": (
                f"observed net expectancy {observed_expectancy:.3f} "
                f"is non-positive — hard fail already enforces this"
            ),
        }

    # Win rate floor: if observed win rate is well above 0%, confirmed.
    if observed_win_rate >= 0.3:
        recommendations["win_rate_floor"] = {
            "state": "confirmed",
            "reason": (
                f"observed win rate {observed_win_rate:.2%} "
                f"is well above 0% floor"
            ),
        }
    elif observed_win_rate > 0:
        recommendations["win_rate_floor"] = {
            "state": "tighten",
            "reason": (
                f"observed win rate {observed_win_rate:.2%} "
                f"is low — consider raising floor above 0%"
            ),
            "suggested_floor": 0.1,
        }
    else:
        recommendations["win_rate_floor"] = {
            "state": "confirmed",
            "reason": (
                f"observed win rate {observed_win_rate:.2%} "
                f"is at 0% — hard fail already enforces this"
            ),
        }

    return {
        "schema_version": "threshold_calibration.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "closed_trades": closed_trades,
        "net_pnl_distribution": net_dist,
        "gross_pnl_distribution": gross_dist,
        "drawdown_distribution": dd_dist,
        "observed": {
            "win_rate": observed_win_rate,
            "net_expectancy": observed_expectancy,
            "max_drawdown_points": observed_max_dd,
        },
        "current_thresholds": current_thresholds,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Gate entry-point (non-blocking — always passes, purely diagnostic)
# ---------------------------------------------------------------------------


def run_threshold_calibration(
    records: list[dict[str, Any]],
    outcome_report: dict[str, Any],
    artifact_path: str | Path,
) -> dict[str, Any]:
    """Run threshold calibration and persist the report artifact.

    This is a *diagnostic* step — it never raises.  The artifact is always
    persisted so consumers can inspect calibration evidence.

    Parameters
    ----------
    records:
        The evaluation records list.
    outcome_report:
        The report dict returned by the outcome gate.
    artifact_path:
        Filesystem path where the JSON calibration report will be written.

    Returns
    -------
    dict
        The calibration report (also persisted to *artifact_path*).
    """
    report = calibrate_thresholds(records, outcome_report)

    dest = Path(artifact_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report
