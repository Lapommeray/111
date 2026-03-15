from __future__ import annotations

from collections import Counter
from typing import Any


def build_governance_report(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(item.get("decision", "HOLD_FOR_MORE_DATA")) for item in decisions)
    for key in ("KEEP", "MERGE", "REJECT", "HOLD_FOR_MORE_DATA"):
        counts.setdefault(key, 0)

    return {
        "total_candidates": len(decisions),
        "decision_counts": dict(counts),
        "accepted_candidates": [
            item.get("candidate_id", "unknown")
            for item in decisions
            if str(item.get("decision", "")) in {"KEEP", "MERGE"}
        ],
        "rejected_candidates": [
            item.get("candidate_id", "unknown")
            for item in decisions
            if str(item.get("decision", "")) == "REJECT"
        ],
    }
