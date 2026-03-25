from __future__ import annotations

from typing import Any


class LossBlocker:
    """Final baseline gate for core signal quality only.

    Advanced spread/session/memory gating is handled by dedicated modules in the
    Oversoul pipeline. This blocker intentionally stays narrow to avoid
    duplicating those responsibilities.
    """

    def __init__(self, min_confidence: float = 0.6, max_spread_points: float = 60.0) -> None:
        self.min_confidence = min_confidence
        self.max_spread_points = max_spread_points

    def evaluate(
        self,
        confidence: float,
        structure: dict[str, Any],
        liquidity: dict[str, Any],
        spread_points: float = 0.0,
    ) -> dict[str, Any]:
        blocked_reasons: list[str] = []

        if confidence < self.min_confidence:
            blocked_reasons.append("confidence_below_threshold")

        if structure.get("bias") == "neutral":
            blocked_reasons.append("market_structure_neutral")

        if structure.get("bias") != "neutral" and liquidity.get("direction_hint") != "neutral":
            if structure.get("bias") != liquidity.get("direction_hint"):
                liquidity_state = str(liquidity.get("liquidity_state", "unknown")).lower()
                liquidity_score = float(liquidity.get("score", 0.0))
                hard_conflict = liquidity_state == "sweep" and liquidity_score >= 0.7
                if hard_conflict:
                    blocked_reasons.append("structure_liquidity_conflict")
                else:
                    blocked_reasons.append("structure_liquidity_conflict_soft")

        hard_block_reasons = [reason for reason in blocked_reasons if reason != "structure_liquidity_conflict_soft"]
        return {
            "blocked": len(hard_block_reasons) > 0,
            "reasons": blocked_reasons,
            "metrics": {
                "confidence": confidence,
                "min_confidence": self.min_confidence,
                "spread_points": spread_points,
                "max_spread_points": self.max_spread_points,
            },
        }
