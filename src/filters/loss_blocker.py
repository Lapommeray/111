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
                blocked_reasons.append("structure_liquidity_conflict")

        return {
            "blocked": len(blocked_reasons) > 0,
            "reasons": blocked_reasons,
        }
