from __future__ import annotations

from src.indicator.chart_objects import build_chart_objects


def test_build_chart_objects_uses_computed_inputs_only() -> None:
    objects = build_chart_objects(
        symbol="XAUUSD",
        structure={"state": "trend_down", "strength": 0.74},
        liquidity={"liquidity_state": "stable", "sweep": "none", "score": 0.4},
        signal_payload={"action": "SELL", "confidence": 0.73, "blocked": False},
    )

    assert len(objects) == 3
    assert objects[0]["id"] == "structure_state"
    assert objects[0]["text"] == "Structure: trend_down"
    assert objects[1]["id"] == "liquidity_state"
    assert "Liquidity: stable" in objects[1]["text"]
    assert objects[2]["id"] == "signal_action"
    assert objects[2]["text"] == "Action: SELL"
    assert objects[2]["blocked"] is False


def test_build_chart_objects_defaults_when_fields_missing() -> None:
    objects = build_chart_objects(
        symbol="XAUUSD",
        structure={},
        liquidity={},
        signal_payload={},
    )

    assert objects[0]["text"] == "Structure: unknown"
    assert "Liquidity: unknown" in objects[1]["text"]
    assert objects[2]["text"] == "Action: WAIT"
    assert objects[2]["value"] == 0.0
