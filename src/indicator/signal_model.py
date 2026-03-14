from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class MemoryContext:
    latest_snapshot_id: str
    last_blocked_count: int
    last_promoted_count: int
    latest_trade_outcome: dict[str, Any]


@dataclass(frozen=True)
class RuleContext:
    active_rule_count: int
    matching_rule_ids: list[str]


@dataclass(frozen=True)
class SignalOutput:
    symbol: str
    action: str
    confidence: float
    reasons: list[str]
    blocked: bool
    setup_classification: str
    blocker_reasons: list[str]
    memory_context: MemoryContext
    rule_context: RuleContext

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = "phase3.v1"
        payload["consumer_hints"] = {
            "action_values": ["BUY", "SELL", "WAIT"],
            "confidence_range": [0.0, 1.0],
        }
        return payload


def classify_setup(
    action: str,
    blocked: bool,
    confidence: float,
    structure_state: str,
    liquidity_state: str,
) -> str:
    """Explicit and traceable setup classification from computed states only."""
    if blocked:
        return "blocked"
    if action == "WAIT":
        return "observe"

    if confidence >= 0.75 and structure_state.startswith("trend") and liquidity_state in {"sweep", "stable"}:
        return "high_confluence"

    if confidence >= 0.6:
        return "moderate_confluence"

    return "low_confluence"


def build_signal_output(
    symbol: str,
    action: str,
    confidence: float,
    reasons: list[str],
    block_result: dict[str, Any],
    structure: dict[str, Any],
    liquidity: dict[str, Any],
    memory_context: dict[str, Any],
    generated_rules: list[dict[str, Any]],
) -> SignalOutput:
    blocked = bool(block_result.get("blocked", False))
    blocker_reasons = list(block_result.get("reasons", []))

    matching_rule_ids = [
        rule.get("rule_id", "")
        for rule in generated_rules
        if rule.get("symbol") == symbol and rule.get("direction") == action and rule.get("status") == "active"
    ]

    setup_classification = classify_setup(
        action=action,
        blocked=blocked,
        confidence=confidence,
        structure_state=str(structure.get("state", "unknown")),
        liquidity_state=str(liquidity.get("liquidity_state", "unknown")),
    )

    return SignalOutput(
        symbol=symbol,
        action=action,
        confidence=confidence,
        reasons=reasons,
        blocked=blocked,
        setup_classification=setup_classification,
        blocker_reasons=blocker_reasons,
        memory_context=MemoryContext(
            latest_snapshot_id=str(memory_context.get("latest_snapshot_id", "")),
            last_blocked_count=int(memory_context.get("last_blocked_count", 0)),
            last_promoted_count=int(memory_context.get("last_promoted_count", 0)),
            latest_trade_outcome=dict(memory_context.get("latest_trade_outcome", {})),
        ),
        rule_context=RuleContext(
            active_rule_count=len([r for r in generated_rules if r.get("status") == "active"]),
            matching_rule_ids=matching_rule_ids,
        ),
    )
