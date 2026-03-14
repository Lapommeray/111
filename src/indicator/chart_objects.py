from __future__ import annotations

from typing import Any


def build_chart_objects(
    symbol: str,
    structure: dict[str, Any],
    liquidity: dict[str, Any],
    signal_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return chart-ready objects using only already-computed values."""
    return [
        {
            "type": "label",
            "id": "structure_state",
            "symbol": symbol,
            "text": f"Structure: {structure.get('state', 'unknown')}",
            "value": structure.get("strength", 0.0),
        },
        {
            "type": "label",
            "id": "liquidity_state",
            "symbol": symbol,
            "text": (
                f"Liquidity: {liquidity.get('liquidity_state', 'unknown')}"
                f" / sweep={liquidity.get('sweep', 'none')}"
            ),
            "value": liquidity.get("score", 0.0),
        },
        {
            "type": "signal_tag",
            "id": "signal_action",
            "symbol": symbol,
            "text": f"Action: {signal_payload.get('action', 'WAIT')}",
            "value": signal_payload.get("confidence", 0.0),
            "blocked": signal_payload.get("blocked", False),
        },
    ]
