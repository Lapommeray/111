from __future__ import annotations

from typing import Any


def build_module_contribution_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize module vote/delta behavior across replay records."""
    module_stats: dict[str, dict[str, Any]] = {}

    for record in records:
        signal = record.get("signal", {})
        action = str(signal.get("action", "WAIT"))
        confidence = float(signal.get("confidence", 0.0))
        advanced = signal.get("advanced_modules", {})
        module_results = advanced.get("module_results", {})

        for module_name, module_payload in module_results.items():
            stats = module_stats.setdefault(
                module_name,
                {
                    "samples": 0,
                    "buy_votes": 0,
                    "sell_votes": 0,
                    "wait_votes": 0,
                    "neutral_votes": 0,
                    "avg_confidence_delta": 0.0,
                    "high_conf_signal_hits": 0,
                    "low_conf_signal_hits": 0,
                    "buy_action_hits": 0,
                    "sell_action_hits": 0,
                    "wait_action_hits": 0,
                },
            )

            vote = str(module_payload.get("direction_vote", "neutral")).lower()
            delta = float(module_payload.get("confidence_delta", 0.0))

            stats["samples"] += 1
            if vote == "buy":
                stats["buy_votes"] += 1
            elif vote == "sell":
                stats["sell_votes"] += 1
            elif vote == "wait":
                stats["wait_votes"] += 1
            else:
                stats["neutral_votes"] += 1

            samples = stats["samples"]
            prev_avg = stats["avg_confidence_delta"]
            stats["avg_confidence_delta"] = round(prev_avg + ((delta - prev_avg) / samples), 6)

            if confidence >= 0.75:
                stats["high_conf_signal_hits"] += 1
            if confidence <= 0.5:
                stats["low_conf_signal_hits"] += 1

            if action == "BUY":
                stats["buy_action_hits"] += 1
            elif action == "SELL":
                stats["sell_action_hits"] += 1
            else:
                stats["wait_action_hits"] += 1

    return {
        "module_count": len(module_stats),
        "modules": module_stats,
    }
