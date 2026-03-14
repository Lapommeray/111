from __future__ import annotations

from typing import Any


def build_blocker_effect_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize blocker activity and a simple protective proxy."""
    reason_counts: dict[str, int] = {}
    blocked_total = 0
    protective_proxy = 0

    for record in records:
        signal = record.get("signal", {})
        blocked = bool(signal.get("blocked", False))
        reasons = list(signal.get("blocker_reasons", []))
        confidence = float(signal.get("confidence", 0.0))

        if blocked:
            blocked_total += 1

        for reason in reasons:
            reason_key = str(reason)
            reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1

            # Protective heuristic (explicitly proxy): blocked low-confidence/conflict events
            if (
                "conflict" in reason_key
                or "neutral" in reason_key
                or "memory_loss_cluster_block" in reason_key
                or confidence <= 0.6
            ):
                protective_proxy += 1

    sorted_reasons = sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "blocked_total": blocked_total,
        "reason_counts": reason_counts,
        "top_reasons": [{"reason": k, "count": v} for k, v in sorted_reasons[:10]],
        "protective_proxy_hits": protective_proxy,
    }
