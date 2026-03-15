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
                    "alignment_hits": 0,
                    "misalignment_hits": 0,
                    "wait_alignment_hits": 0,
                    # enrichment metric accumulators
                    "_regime_samples": 0,
                    "_regime_alignment_hits": 0,
                    "_contradiction_prevention_hits": 0,
                    "_blocked_samples": 0,
                    "_blocker_protection_hits": 0,
                    "_aligned_delta_sum": 0.0,
                    "_aligned_delta_count": 0,
                    "_misaligned_delta_sum": 0.0,
                    "_misaligned_delta_count": 0,
                    "_drawdown_wait_hits": 0,
                    "_low_conf_samples": 0,
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
                stats["_low_conf_samples"] += 1

            is_aligned = (
                (action == "BUY" and vote == "buy")
                or (action == "SELL" and vote == "sell")
                or (COUNT_WAIT_ALIGNMENT and action == "WAIT" and vote == "wait")
            )
            if action == "WAIT" and vote == "wait":
                stats["wait_alignment_hits"] += 1

            if is_aligned:
                stats["alignment_hits"] += 1
                stats["_aligned_delta_sum"] += delta
                stats["_aligned_delta_count"] += 1
            else:
                stats["misalignment_hits"] += 1
                stats["_misaligned_delta_sum"] += delta
                stats["_misaligned_delta_count"] += 1

            if regime_label == dominant_regime:
                stats["_regime_samples"] += 1
                if is_aligned:
                    stats["_regime_alignment_hits"] += 1

            contradiction_prevented = blocked and action == "WAIT" and vote in {"wait", "neutral"}
            if contradiction_prevented:
                stats["_contradiction_prevention_hits"] += 1

            if blocked:
                stats["_blocked_samples"] += 1
                if _is_blocker_protective(module_name=str(module_name), vote=vote, blocker_reasons=blocker_reasons):
                    stats["_blocker_protection_hits"] += 1

            if confidence <= 0.5 and action == "WAIT" and vote in {"wait", "neutral"}:
                stats["_drawdown_wait_hits"] += 1

    for stats in module_stats.values():
        samples = int(stats.get("samples", 0))
        aligned = int(stats.get("alignment_hits", 0))
        misaligned = int(stats.get("misalignment_hits", 0))
        wait_aligned = int(stats.get("wait_alignment_hits", 0))

        stats["action_alignment"] = {
            "aligned": aligned,
            "misaligned": misaligned,
            "wait_aligned": wait_aligned,
            "alignment_ratio": round((aligned / samples), 6) if samples > 0 else 0.0,
            "count_wait_alignment": COUNT_WAIT_ALIGNMENT,
        }

        regime_samples = int(stats.get("_regime_samples", 0))
        regime_hits = int(stats.get("_regime_alignment_hits", 0))
        stats["regime_specific_alignment"] = {
            "dominant_regime": dominant_regime,
            "samples": regime_samples,
            "aligned": regime_hits,
            "ratio": round((regime_hits / regime_samples), 6) if regime_samples > 0 else 0.0,
        }

        contradiction_hits = int(stats.get("_contradiction_prevention_hits", 0))
        stats["contradiction_reduction_proxy"] = round((contradiction_hits / samples), 6) if samples > 0 else 0.0

        blocked_samples = int(stats.get("_blocked_samples", 0))
        blocker_hits = int(stats.get("_blocker_protection_hits", 0))
        stats["blocker_protection_strength"] = round((blocker_hits / blocked_samples), 6) if blocked_samples > 0 else 0.0

        aligned_delta_count = int(stats.get("_aligned_delta_count", 0))
        misaligned_delta_count = int(stats.get("_misaligned_delta_count", 0))
        aligned_delta_avg = (
            float(stats.get("_aligned_delta_sum", 0.0)) / aligned_delta_count if aligned_delta_count > 0 else 0.0
        )
        misaligned_delta_avg = (
            float(stats.get("_misaligned_delta_sum", 0.0)) / misaligned_delta_count if misaligned_delta_count > 0 else 0.0
        )
        stats["confidence_calibration_shift"] = round(aligned_delta_avg - misaligned_delta_avg, 6)

        low_conf_samples = int(stats.get("_low_conf_samples", 0))
        drawdown_hits = int(stats.get("_drawdown_wait_hits", 0))
        stats["drawdown_prevention_proxy"] = round((drawdown_hits / low_conf_samples), 6) if low_conf_samples > 0 else 0.0

        for key in list(stats.keys()):
            if key.startswith("_"):
                del stats[key]

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


def _derive_regime(record: dict[str, Any]) -> str:
    status_panel = record.get("status_panel", {}) if isinstance(record.get("status_panel"), dict) else {}
    structure_state = str(status_panel.get("structure_state", "")).strip()
    if structure_state:
        return f"structure:{structure_state}"

    signal = record.get("signal", {}) if isinstance(record.get("signal"), dict) else {}
    confidence = float(signal.get("confidence", 0.0))
    if confidence >= 0.75:
        return "confidence:high"
    if confidence >= 0.5:
        return "confidence:medium"
    return "confidence:low"


def _is_blocker_protective(module_name: str, vote: str, blocker_reasons: list[Any]) -> bool:
    reasons_text = " ".join(str(item).lower() for item in blocker_reasons)
    if module_name.lower() in reasons_text:
        return True
    if vote in {"wait", "neutral"}:
        return True
    if "conflict" in reasons_text and vote in {"buy", "sell"}:
        return True
    return False
