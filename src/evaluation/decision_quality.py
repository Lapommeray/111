"""Decision-quality / distribution sanity gate for replay evaluation outputs.

Runs on top of the decision-completeness gate.  While completeness proves
every row reaches a valid terminal state, this gate proves the *aggregate*
output is structurally believable:

* There must be at least one actionable (BUY/SELL) record in a non-empty run.
* A run that is effectively all-abstain is degenerate — fail.
* Reasons and blocker_reasons must not contain empty, whitespace-only, or
  obviously placeholder strings.
* BUY/SELL confidence values must show real diversity (flat patterns flagged).
* Buy-vs-sell distribution and ratios are reported for inspection.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRADE_ACTIONS = {"BUY", "SELL"}

_PLACEHOLDER_REASONS = frozenset({
    "todo",
    "placeholder",
    "test",
    "none",
    "n/a",
    "na",
    "tbd",
    "unknown",
    ".",
    "-",
    "--",
    "...",
})

# If abstain_ratio exceeds this the run is considered degenerate.
_DEGENERATE_ABSTAIN_RATIO = 0.95


# ---------------------------------------------------------------------------
# Reason quality helpers
# ---------------------------------------------------------------------------


def _is_bad_reason(reason: str) -> bool:
    """Return True if *reason* is empty, whitespace-only, or placeholder."""
    if not isinstance(reason, str):
        return True
    stripped = reason.strip()
    if not stripped:
        return True
    if stripped.lower() in _PLACEHOLDER_REASONS:
        return True
    return False


def _check_reason_quality(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan all reasons and blocker_reasons for bad entries."""
    bad_entries: list[dict[str, Any]] = []
    total_reasons_checked = 0

    for idx, record in enumerate(records):
        signal = record.get("signal") or {}
        for field_name in ("reasons", "blocker_reasons"):
            for reason in (signal.get(field_name) or []):
                total_reasons_checked += 1
                if _is_bad_reason(reason):
                    bad_entries.append({
                        "record_index": idx,
                        "field": field_name,
                        "value": repr(reason),
                    })

    return {
        "total_reasons_checked": total_reasons_checked,
        "bad_reason_count": len(bad_entries),
        "bad_reasons": bad_entries[:20],  # cap for readability
        "passed": len(bad_entries) == 0,
    }


# ---------------------------------------------------------------------------
# Confidence analysis
# ---------------------------------------------------------------------------


def _confidence_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute min/max/mean/unique-count over actionable confidence values."""
    values: list[float] = []
    for record in records:
        signal = record.get("signal") or {}
        if signal.get("action") in _TRADE_ACTIONS:
            conf = signal.get("confidence")
            if isinstance(conf, (int, float)) and not math.isnan(conf):
                values.append(float(conf))

    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "unique_count": 0,
            "flat_confidence": False,
        }

    unique = set(round(v, 8) for v in values)
    mean_val = sum(values) / len(values)
    flat = len(unique) == 1 and len(values) > 1

    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean": round(mean_val, 6),
        "unique_count": len(unique),
        "flat_confidence": flat,
    }


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------


def _buy_sell_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"BUY": 0, "SELL": 0}
    for record in records:
        action = (record.get("signal") or {}).get("action")
        if action in counts:
            counts[action] += 1
    return counts


# ---------------------------------------------------------------------------
# Core quality assessment
# ---------------------------------------------------------------------------


def assess_decision_quality(
    records: list[dict[str, Any]],
    completeness_counts: dict[str, int],
) -> dict[str, Any]:
    """Produce a decision-quality report.

    Parameters
    ----------
    records:
        Evaluation records list.
    completeness_counts:
        The ``counts`` dict from the completeness report
        (keys: actionable, blocked, abstain, invalid).
    """
    total = len(records)
    actionable = completeness_counts.get("actionable", 0)
    blocked = completeness_counts.get("blocked", 0)
    abstain = completeness_counts.get("abstain", 0)
    invalid = completeness_counts.get("invalid", 0)

    actionable_ratio = actionable / total if total else 0.0
    abstain_ratio = abstain / total if total else 0.0

    conf = _confidence_summary(records)
    buy_sell = _buy_sell_distribution(records)
    reason_quality = _check_reason_quality(records)

    # ---- fail conditions --------------------------------------------------
    failures: list[str] = []
    flags: list[str] = []

    if total > 0 and actionable == 0:
        failures.append("non-empty run with 0 actionable records")

    if total > 0 and abstain_ratio > _DEGENERATE_ABSTAIN_RATIO:
        failures.append(
            f"degenerate output: abstain_ratio={abstain_ratio:.2%} "
            f"(>{_DEGENERATE_ABSTAIN_RATIO:.0%} threshold)"
        )

    if not reason_quality["passed"]:
        failures.append(
            f"bad reasons found: {reason_quality['bad_reason_count']} "
            f"empty/placeholder reason strings"
        )

    # Flat confidence is a flag (suspicious) rather than hard fail
    if conf["flat_confidence"]:
        flags.append(
            f"flat confidence: all {conf['count']} actionable records "
            f"have confidence={conf['min']}"
        )

    passed = len(failures) == 0

    return {
        "schema_version": "decision_quality.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records": total,
        "actionable_count": actionable,
        "blocked_count": blocked,
        "abstain_count": abstain,
        "invalid_count": invalid,
        "actionable_ratio": round(actionable_ratio, 4),
        "abstain_ratio": round(abstain_ratio, 4),
        "buy_vs_sell_distribution": buy_sell,
        "confidence_summary": conf,
        "reason_quality": reason_quality,
        "passed": passed,
        "failure_count": len(failures),
        "failures": failures,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Gate entry-point
# ---------------------------------------------------------------------------


class DecisionQualityError(Exception):
    """Raised when evaluation output fails the quality gate."""


def run_decision_quality_gate(
    records: list[dict[str, Any]],
    completeness_report: dict[str, Any],
    artifact_path: str | Path,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Run the decision-quality gate and persist the report artifact.

    Parameters
    ----------
    records:
        The ``records`` list produced by :func:`evaluate_replay`.
    completeness_report:
        The report dict returned by the completeness gate (must contain
        a ``"counts"`` key).
    artifact_path:
        Filesystem path where the JSON quality report will be written.
    strict:
        When ``True`` (default), a failed gate raises
        :class:`DecisionQualityError`.  When ``False`` (replay/diagnostic
        mode), the report is persisted and returned with
        ``gate_action = "warn"`` instead of raising, allowing downstream
        evaluation to complete and emit diagnostic artifacts.

    Returns
    -------
    dict
        The quality report (also persisted to *artifact_path*).

    Raises
    ------
    DecisionQualityError
        If any hard-fail condition is met **and** *strict* is ``True``.
    """
    counts = completeness_report.get("counts", {})
    report = assess_decision_quality(records, counts)

    dest = Path(artifact_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not report["passed"]:
        if strict:
            lines = [
                f"Decision-quality gate FAILED: {report['failure_count']} issue(s).",
            ]
            for f in report["failures"]:
                lines.append(f"  - {f}")
            raise DecisionQualityError("\n".join(lines))
        # Non-strict (replay/diagnostic): surface the failure honestly
        # but do not block evaluation completion.
        report["gate_action"] = "warn"

    return report
