from __future__ import annotations

from src.indicator.indicator_output import build_indicator_output, build_status_panel


def test_build_status_panel_includes_expected_sections() -> None:
    panel = build_status_panel(
        structure={"state": "trend_up"},
        liquidity={"liquidity_state": "sweep"},
        signal_payload={
            "confidence": 0.82,
            "blocked": True,
            "blocker_reasons": ["structure_liquidity_conflict"],
        },
        memory_result={"latest_trade_outcome": {"status": "closed"}},
        rule_result={"generated_rule_count": 1, "matching_rule_ids": ["rule_buy_3"]},
    )

    assert panel["structure_state"] == "trend_up"
    assert panel["liquidity_state"] == "sweep"
    assert panel["confidence"] == 0.82
    assert panel["blocker_result"]["blocked"] is True
    assert panel["memory_result"]["latest_trade_outcome"]["status"] == "closed"
    assert panel["generated_rule_result"]["generated_rule_count"] == 1


def test_build_indicator_output_schema_and_payload_shape() -> None:
    output = build_indicator_output(
        symbol="XAUUSD",
        signal_payload={"action": "WAIT", "confidence": 0.5},
        chart_objects=[{"type": "label", "id": "test"}],
        status_panel={"structure_state": "range"},
    )

    assert output["schema_version"] == "phase3.output.v1"
    assert output["symbol"] == "XAUUSD"
    assert output["signal"]["action"] == "WAIT"
    assert output["chart_objects"][0]["id"] == "test"
    assert output["status_panel"]["structure_state"] == "range"
