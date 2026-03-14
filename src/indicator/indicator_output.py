from __future__ import annotations

from typing import Any


def build_status_panel(
    structure: dict[str, Any],
    liquidity: dict[str, Any],
    signal_payload: dict[str, Any],
    memory_result: dict[str, Any],
    rule_result: dict[str, Any],
) -> dict[str, Any]:
    """Summarize core status sections for UI or downstream module use."""
    return {
        "structure_state": structure.get("state", "unknown"),
        "liquidity_state": liquidity.get("liquidity_state", "unknown"),
        "confidence": signal_payload.get("confidence", 0.0),
        "blocker_result": {
            "blocked": signal_payload.get("blocked", False),
            "blocker_reasons": signal_payload.get("blocker_reasons", []),
        },
        "memory_result": memory_result,
        "generated_rule_result": rule_result,
    }


def build_indicator_output(
    symbol: str,
    signal_payload: dict[str, Any],
    chart_objects: list[dict[str, Any]],
    status_panel: dict[str, Any],
) -> dict[str, Any]:
    """Structured indicator output designed for machine consumption."""
    return {
        "schema_version": "phase3.output.v1",
        "symbol": symbol,
        "signal": signal_payload,
        "chart_objects": chart_objects,
        "status_panel": status_panel,
    }
