from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from run import RuntimeConfig, ensure_sample_data, run_pipeline
from src.state import ModuleResult, PipelineState


def _bars(count: int = 80) -> list[dict[str, float]]:
    return [
        {
            "time": float(1_700_000_000 + (idx * 60)),
            "open": 2100.0,
            "high": 2100.6,
            "low": 2099.4,
            "close": 2100.2,
            "tick_volume": 120.0 + idx,
        }
        for idx in range(count)
    ]


def _runtime_config(sample_path: Path, memory_root: Path, *, mode: str) -> RuntimeConfig:
    return RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=60,
        sample_path=str(sample_path),
        memory_root=str(memory_root),
        mode=mode,
        replay_source="csv",
        replay_csv_path=str(sample_path),
        evolution_enabled=False,
        live_execution_enabled=False,
        macro_feed_enabled=False,
    )


def _macro_state(*, pause_trading: bool, confidence_penalty: float = 0.0) -> dict[str, object]:
    return {
        "trade_tags": {"session": "london", "dxy_state": "stable"},
        "risk_behavior": {
            "pause_trading": pause_trading,
            "confidence_penalty": confidence_penalty,
            "size_multiplier": 1.0,
            "reasons": ["macro_test_state"],
        },
        "macro_states": {},
        "feed_states": {},
    }


def _capital_ok() -> dict[str, object]:
    return {
        "effective_volume": 0.01,
        "trade_refused": False,
        "daily_loss_check": {"allowed": True},
        "trigger_reasons": [],
    }


def _state_with_votes(
    *,
    bars: list[dict[str, float]],
    mode: str,
    final_direction: str,
    final_confidence: float,
    buy_votes: int,
    sell_votes: int,
    conflict_blocked: bool,
) -> PipelineState:
    module_results: dict[str, ModuleResult] = {
        "sessions": ModuleResult(
            name="sessions",
            role="session_classifier",
            direction_vote="neutral",
            confidence_delta=0.0,
            blocked=False,
            reasons=[],
            payload={"state": "london"},
        ),
        "spread_state": ModuleResult(
            name="spread_state",
            role="spread_proxy_estimator",
            direction_vote="neutral",
            confidence_delta=0.0,
            blocked=False,
            reasons=[],
            payload={"spread_points": 12.0},
        ),
        "volatility": ModuleResult(
            name="volatility",
            role="volatility_regime",
            direction_vote="neutral",
            confidence_delta=0.0,
            blocked=False,
            reasons=[],
            payload={"volatility_ratio": 1.0, "state": "balanced"},
        ),
        "conflict_filter": ModuleResult(
            name="conflict_filter",
            role="vote_conflict_gate",
            direction_vote="neutral",
            confidence_delta=-0.05 if conflict_blocked else 0.01,
            blocked=conflict_blocked,
            reasons=["direction_conflict"] if conflict_blocked else [],
            payload={},
        ),
    }
    for idx in range(buy_votes):
        module_results[f"buy_vote_{idx}"] = ModuleResult(
            name=f"buy_vote_{idx}",
            role="vote_buy",
            direction_vote="buy",
            confidence_delta=0.02,
            blocked=False,
            reasons=[],
            payload={},
        )
    for idx in range(sell_votes):
        module_results[f"sell_vote_{idx}"] = ModuleResult(
            name=f"sell_vote_{idx}",
            role="vote_sell",
            direction_vote="sell",
            confidence_delta=0.02,
            blocked=False,
            reasons=[],
            payload={},
        )
    return PipelineState(
        symbol="XAUUSD",
        mode=mode,
        bars=bars,
        structure={"state": "trend_up", "bias": "buy", "strength": 0.9},
        liquidity={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        base_confidence=0.9,
        base_direction="BUY",
        final_confidence=final_confidence,
        final_direction=final_direction,
        blocked=False,
        blocked_reasons=[],
        module_results=module_results,
    )


def test_strong_setup_allows_entry_with_consistent_direction_and_confidence(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="BUY",
        final_confidence=0.9,
        buy_votes=3,
        sell_votes=0,
        conflict_blocked=False,
    )
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_strong", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "BUY"
    assert signal["blocked"] is False
    assert signal["confidence"] == 0.88
    assert signal["advanced_modules"]["final_direction"] == "BUY"
    assert signal["advanced_modules"]["final_confidence"] == 0.9


def test_low_effective_confidence_blocks_entry_with_explicit_reason(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="BUY",
        final_confidence=0.9,
        buy_votes=3,
        sell_votes=0,
        conflict_blocked=False,
    )
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.65)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_low_effective", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is True
    assert "confidence_below_threshold" in signal["blocker_reasons"]


def test_manipulated_setup_conflict_votes_abstains_with_explicit_reason(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="BUY",
        final_confidence=0.85,
        buy_votes=2,
        sell_votes=2,
        conflict_blocked=True,
    )
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.86, "confidence": 0.86, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_conflict", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is False
    assert signal["blocker_reasons"] == []
    assert "directional_conflict_active" in signal["reasons"]


def test_slight_majority_setup_rebases_confidence_after_directional_degradation(tmp_path: Path) -> None:
    """3:2 directional split should abstain and confidence should be degraded, not stay high."""
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="BUY",
        final_confidence=0.9,
        buy_votes=3,
        sell_votes=2,
        conflict_blocked=False,
    )
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_slight_majority", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is False
    assert signal["blocker_reasons"] == []
    assert "directional_vote_margin_insufficient" in signal["reasons"]
    assert signal["confidence"] <= 0.59


def test_invalidated_setup_with_open_position_surfaces_exit_contract(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="BUY",
        final_confidence=0.85,
        buy_votes=1,
        sell_votes=0,
        conflict_blocked=False,
    )
    simulated_open_position = {
        "entry_decision": {"decision": "WAIT", "eligible_for_order": False},
        "pre_trade_checks": {"checks": [], "failed_checks": [], "all_checks_passed": True},
        "order_request": {},
        "order_result": {"status": "accepted", "order_sent": False, "simulated": True},
        "stop_loss_take_profit": {"stop_loss": None, "take_profit": None},
        "rejection_reason": "",
        "rollback_refusal_reasons": [],
        "trade_tags": {},
        "refusal_tags": {},
        "failure_tags": {},
        "open_position_state": {
            "status": "open",
            "position_id": 77,
            "symbol": "XAUUSD",
            "side": "BUY",
            "entry_price": 2100.2,
            "stop_loss": 2098.2,
            "take_profit": 2104.2,
            "broker_position_confirmation": "unconfirmed",
            "position_state_outcome": "assumed_open_from_accepted_send_unreconciled",
        },
        "exit_decision": {"decision": "hold_open_position", "reason": "assumed_open_position_from_accepted_send_unreconciled"},
        "pnl_snapshot": {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "XAUUSD",
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "position_open": True,
            "position_open_truth": "assumed_from_accepted_send_unreconciled",
        },
        "mistake_failure_classification": "none",
        "replay_feedback_hook": {"enabled": True, "hook_status": "queued_for_feedback", "mistake_classification": "none"},
        "auto_stop_active": False,
        "signal_lifecycle": {"signal_fresh": True, "signal_lifecycle_refusal_reasons": []},
    }
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.8, "confidence": 0.8, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
        patch(
            "run._run_controlled_mt5_live_execution",
            return_value=(simulated_open_position, {"auto_stop_active": False}, {"artifact_path": "stub"}),
        ),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_exit", mode="replay"))

    decision_contract = output["status_panel"]["entry_exit_decision"]
    assert output["signal"]["action"] == "WAIT"
    assert decision_contract["action"] == "EXIT"
    assert "open/partial position exists" in decision_contract["why_not_trade"]


def test_execution_refusal_degrades_wait_confidence_and_reasons(tmp_path: Path) -> None:
    """Execution refusal should not leave abstain confidence in trade-ready range."""
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="BUY",
        final_confidence=0.9,
        buy_votes=3,
        sell_votes=0,
        conflict_blocked=False,
    )
    refused_execution = {
        "entry_decision": {"decision": "BUY", "eligible_for_order": True},
        "pre_trade_checks": {"checks": [], "failed_checks": [], "all_checks_passed": True},
        "order_request": {"type": "BUY"},
        "order_result": {"status": "refused", "order_sent": False, "error_reason": "order_send_refused"},
        "stop_loss_take_profit": {"stop_loss": None, "take_profit": None},
        "rejection_reason": "order_send_refused",
        "rollback_refusal_reasons": ["order_send_refused"],
        "trade_tags": {},
        "refusal_tags": {},
        "failure_tags": {},
        "open_position_state": {"status": "flat"},
        "exit_decision": {"decision": "no_position_exit", "reason": "no_open_position"},
        "pnl_snapshot": {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "XAUUSD",
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "position_open": False,
            "position_open_truth": "not_applicable",
        },
        "mistake_failure_classification": "transient",
        "replay_feedback_hook": {"enabled": True, "hook_status": "queued_for_feedback", "mistake_classification": "transient"},
        "auto_stop_active": False,
        "signal_lifecycle": {"signal_fresh": True, "signal_lifecycle_refusal_reasons": []},
    }
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
        patch(
            "run._run_controlled_mt5_live_execution",
            return_value=(refused_execution, {"auto_stop_active": False}, {"artifact_path": "stub"}),
        ),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_exec_refusal", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is False
    assert signal["blocker_reasons"] == []
    assert "mt5_controlled_execution_refused" in signal["reasons"]
    assert signal["confidence"] <= 0.59


def test_unblocked_wait_direction_rebases_confidence_to_abstain_band(tmp_path: Path) -> None:
    """WAIT (without hard block) should not retain trade-ready confidence."""
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="WAIT",
        final_confidence=0.9,
        buy_votes=0,
        sell_votes=0,
        conflict_blocked=False,
    )
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_wait_rebase", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is False
    assert signal["blocker_reasons"] == []
    assert signal["confidence"] <= 0.59
    assert "abstain_confidence_rebased" in signal["reasons"]


def test_open_position_valid_hold_path_attaches_transition_reason_and_coherent_outputs(
    tmp_path: Path,
) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="WAIT",
        final_confidence=0.9,
        buy_votes=0,
        sell_votes=0,
        conflict_blocked=False,
    )
    open_position_hold = {
        "entry_decision": {"decision": "WAIT", "eligible_for_order": False},
        "pre_trade_checks": {"checks": [], "failed_checks": [], "all_checks_passed": True},
        "order_request": {},
        "order_result": {"status": "accepted", "order_sent": False, "simulated": True},
        "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
        "rejection_reason": "",
        "rollback_refusal_reasons": [],
        "trade_tags": {},
        "refusal_tags": {},
        "failure_tags": {},
        "open_position_state": {
            "status": "open",
            "position_id": 88,
            "symbol": "XAUUSD",
            "side": "BUY",
            "entry_price": 2100.2,
            "stop_loss": 2098.2,
            "take_profit": 2104.2,
            "broker_position_confirmation": "confirmed",
            "position_state_outcome": "broker_confirmed_open_position",
        },
        "exit_decision": {"decision": "hold_open_position", "reason": "broker_confirmed_open_position"},
        "pnl_snapshot": {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "XAUUSD",
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "position_open": True,
            "position_open_truth": "broker_confirmed_open_position",
        },
        "mistake_failure_classification": "none",
        "replay_feedback_hook": {"enabled": True, "hook_status": "queued_for_feedback", "mistake_classification": "none"},
        "auto_stop_active": False,
        "signal_lifecycle": {"signal_fresh": True, "signal_lifecycle_refusal_reasons": []},
    }
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
        patch(
            "run._run_controlled_mt5_live_execution",
            return_value=(open_position_hold, {"auto_stop_active": False}, {"artifact_path": "stub"}),
        ),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_open_hold", mode="replay"))

    signal = output["signal"]
    decision_contract = output["status_panel"]["entry_exit_decision"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is False
    assert signal["blocker_reasons"] == []
    assert signal["confidence"] <= 0.59
    assert decision_contract["action"] == "EXIT"
    assert "open/partial position exists" in decision_contract["why_not_trade"]
    assert "open_position_exit_management:broker_confirmed_open_position" in signal["reasons"]


def test_partial_exposure_degradation_attaches_transition_reason_and_exit_contract(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    state = _state_with_votes(
        bars=_bars(),
        mode="replay",
        final_direction="WAIT",
        final_confidence=0.9,
        buy_votes=0,
        sell_votes=0,
        conflict_blocked=False,
    )
    partial_exposure = {
        "entry_decision": {"decision": "WAIT", "eligible_for_order": False},
        "pre_trade_checks": {"checks": [], "failed_checks": [], "all_checks_passed": True},
        "order_request": {},
        "order_result": {"status": "partial", "order_sent": True, "error_reason": ""},
        "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
        "rejection_reason": "",
        "rollback_refusal_reasons": [],
        "trade_tags": {},
        "refusal_tags": {},
        "failure_tags": {},
        "open_position_state": {
            "status": "partial_exposure_unresolved",
            "position_id": None,
            "symbol": "XAUUSD",
            "side": "BUY",
            "entry_price": None,
            "stop_loss": 2098.2,
            "take_profit": 2104.2,
            "broker_position_confirmation": "unconfirmed",
            "position_state_outcome": "partial_fill_exposure_unresolved",
        },
        "exit_decision": {"decision": "defer_exit_partial_exposure_unresolved", "reason": "partial_fill_exposure_unresolved"},
        "pnl_snapshot": {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "XAUUSD",
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "position_open": None,
            "position_open_truth": "partial_fill_exposure_unresolved",
        },
        "mistake_failure_classification": "none",
        "replay_feedback_hook": {"enabled": True, "hook_status": "queued_for_feedback", "mistake_classification": "none"},
        "auto_stop_active": False,
        "signal_lifecycle": {"signal_fresh": True, "signal_lifecycle_refusal_reasons": []},
    }
    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.0)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.9, "confidence": 0.88, "feature_contributors": {"buy_vote_0": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
        patch(
            "run._run_controlled_mt5_live_execution",
            return_value=(partial_exposure, {"auto_stop_active": False}, {"artifact_path": "stub"}),
        ),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_partial_exposure", mode="replay"))

    signal = output["signal"]
    decision_contract = output["status_panel"]["entry_exit_decision"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is False
    assert signal["blocker_reasons"] == []
    assert signal["confidence"] <= 0.59
    assert decision_contract["action"] == "EXIT"
    assert "partial_exposure_unresolved_manage_exit" in decision_contract["exit_rule"]
    assert "open_position_exit_management:partial_fill_exposure_unresolved" in signal["reasons"]
