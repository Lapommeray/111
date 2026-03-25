"""Decision-completeness gate for replay/evaluation outputs.

Every evaluation record must end in exactly one valid terminal state:
  1. actionable  – action present, confidence present, not blocked
  2. blocked     – blocked flag set, blocking reason explicit
  3. abstain     – action intentionally absent (WAIT), reasons explain why
  4. invalid     – incomplete or contradictory → must be counted, must fail run

An unblocked record must NEVER leave evaluation with all of these empty/zero:
  action (missing or WAIT with no reasons), confidence, blocker_reasons, reasons.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Record classification
# ---------------------------------------------------------------------------

_TRADE_ACTIONS = {"BUY", "SELL"}


def classify_record(record: dict[str, Any]) -> tuple[str, str]:
    """Classify a single evaluation record into a terminal decision state.

    Returns ``(state, reason)`` where *state* is one of
    ``"actionable"``, ``"blocked"``, ``"abstain"``, ``"invalid"``.
    """
    signal = record.get("signal")
    if not isinstance(signal, dict):
        return "invalid", "missing or malformed signal dict"

    action = signal.get("action")
    confidence = signal.get("confidence")
    blocked = bool(signal.get("blocked", False))
    blocker_reasons: list[str] = list(signal.get("blocker_reasons") or [])
    reasons: list[str] = list(signal.get("reasons") or [])

    # ---- blocked ---------------------------------------------------------
    if blocked:
        if not blocker_reasons:
            return "invalid", "blocked without blocker_reasons"
        return "blocked", f"blocked by: {', '.join(blocker_reasons)}"

    # ---- actionable (BUY / SELL) -----------------------------------------
    if action in _TRADE_ACTIONS:
        if confidence is None or confidence <= 0:
            return "invalid", f"action={action} but confidence={confidence}"
        return "actionable", f"{action} @ confidence={confidence:.4f}"

    # ---- abstain / no-trade (WAIT or missing) ----------------------------
    if action == "WAIT":
        if reasons:
            return "abstain", f"WAIT because: {', '.join(reasons[:3])}"
        return "invalid", "WAIT without reasons (why_not_trade missing)"

    # ---- anything else is invalid ----------------------------------------
    if action is None or action == "":
        # All decision fields empty on an unblocked row
        return "invalid", "unblocked record with no action"

    return "invalid", f"unrecognised action={action!r}"


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------


def validate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate every record and produce a completeness report.

    Returns a dict suitable for JSON serialisation.
    """
    classifications: list[dict[str, Any]] = []
    counts = {"actionable": 0, "blocked": 0, "abstain": 0, "invalid": 0}
    failures: list[dict[str, Any]] = []

    for idx, record in enumerate(records):
        state, reason = classify_record(record)
        counts[state] += 1
        entry: dict[str, Any] = {
            "index": idx,
            "state": state,
            "reason": reason,
        }
        classifications.append(entry)
        if state == "invalid":
            failures.append(entry)

    passed = len(failures) == 0
    return {
        "schema_version": "decision_completeness.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "counts": counts,
        "passed": passed,
        "failure_count": len(failures),
        "failures": failures,
        "classifications": classifications,
    }


# ---------------------------------------------------------------------------
# Gate entry-point
# ---------------------------------------------------------------------------


class DecisionCompletenessError(Exception):
    """Raised when evaluation output fails the completeness gate."""


def run_decision_completeness_gate(
    records: list[dict[str, Any]],
    artifact_path: str | Path,
) -> dict[str, Any]:
    """Run the decision-completeness gate and persist the report artifact.

    Parameters
    ----------
    records:
        The ``records`` list produced by :func:`evaluate_replay`.
    artifact_path:
        Filesystem path where the JSON report will be written.

    Returns
    -------
    dict
        The completeness report (also persisted to *artifact_path*).

    Raises
    ------
    DecisionCompletenessError
        If any record is classified as ``invalid``.
    """
    report = validate_records(records)

    # Persist deterministic artifact
    dest = Path(artifact_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not report["passed"]:
        summary_lines = [
            f"Decision-completeness gate FAILED: {report['failure_count']}/{report['total_records']} records invalid.",
        ]
        for f in report["failures"][:10]:
            summary_lines.append(f"  record[{f['index']}]: {f['reason']}")
        if report["failure_count"] > 10:
            summary_lines.append(f"  ... and {report['failure_count'] - 10} more")
        raise DecisionCompletenessError("\n".join(summary_lines))

    return report
