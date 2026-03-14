from __future__ import annotations

from src.filters.conflict_filter import apply_conflict_filter
from src.filters.memory_filter import apply_memory_filter
from src.filters.self_destruct_protocol import apply_self_destruct_protocol
from src.filters.session_filter import apply_session_filter


def test_memory_filter_blocks_loss_cluster() -> None:
    outcomes = [
        {"direction": "BUY", "result": "loss"},
        {"direction": "BUY", "result": "loss"},
        {"direction": "BUY", "result": "loss"},
        {"direction": "SELL", "result": "win"},
    ]
    result = apply_memory_filter("BUY", blocked_setups=[], trade_outcomes=outcomes)
    assert result["blocked"] is True
    assert result["direction_vote"] == "wait"
    assert "memory_loss_cluster_block" in result["reasons"]


def test_conflict_filter_blocks_near_balanced_opposite_votes() -> None:
    result = apply_conflict_filter(votes=["buy", "sell", "buy", "sell"], base_direction="BUY")
    assert result["blocked"] is True
    assert result["direction_vote"] == "wait"
    assert "direction_conflict" in result["reasons"]


def test_self_destruct_protocol_triggers_after_loss_threshold() -> None:
    outcomes = [{"result": "loss"} for _ in range(4)]
    module_outputs = {
        "fvg": {"confidence_delta": 0.0},
        "human_lag_exploit": {"confidence_delta": 0.0},
        "invisible_data_miner": {"confidence_delta": 0.0},
    }
    result = apply_self_destruct_protocol(outcomes, module_outputs, loss_threshold=4)
    assert result["blocked"] is True
    assert result["state"] == "triggered"
    assert set(result["disabled_modules"]) == {"fvg", "human_lag_exploit", "invisible_data_miner"}


def test_session_filter_blocks_off_hours() -> None:
    blocked = apply_session_filter({"state": "off_hours"})
    allowed = apply_session_filter({"state": "london"})

    assert blocked["blocked"] is True
    assert blocked["direction_vote"] == "wait"
    assert allowed["blocked"] is False
