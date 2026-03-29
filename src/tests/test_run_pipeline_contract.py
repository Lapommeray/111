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


def _strong_buy_state(
    bars: list[dict[str, float]],
    *,
    mode: str,
    blocked: bool = False,
    blocked_reasons: list[str] | None = None,
) -> PipelineState:
    structure = {"state": "trend_up", "bias": "buy", "strength": 0.9}
    liquidity = {"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85}
    return PipelineState(
        symbol="XAUUSD",
        mode=mode,
        bars=bars,
        structure=structure,
        liquidity=liquidity,
        base_confidence=0.9,
        base_direction="BUY",
        final_confidence=0.9,
        final_direction="BUY",
        blocked=blocked,
        blocked_reasons=list(blocked_reasons or []),
        module_results={
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
            "buy_vote_a": ModuleResult(
                name="buy_vote_a",
                role="vote_a",
                direction_vote="buy",
                confidence_delta=0.02,
                blocked=False,
                reasons=[],
                payload={},
            ),
            "buy_vote_b": ModuleResult(
                name="buy_vote_b",
                role="vote_b",
                direction_vote="buy",
                confidence_delta=0.02,
                blocked=False,
                reasons=[],
                payload={},
            ),
            "buy_vote_c": ModuleResult(
                name="buy_vote_c",
                role="vote_c",
                direction_vote="buy",
                confidence_delta=0.02,
                blocked=False,
                reasons=[],
                payload={},
            ),
            "conflict_filter": ModuleResult(
                name="conflict_filter",
                role="vote_conflict_gate",
                direction_vote="neutral",
                confidence_delta=0.01,
                blocked=False,
                reasons=["buy_votes=3", "sell_votes=0"],
                payload={},
            ),
        },
    )


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


def test_run_pipeline_output_envelope_and_required_indicator_keys(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory", mode="replay"))

    assert output["schema_version"] == "phase3.output.v1"
    assert set(output.keys()) == {"schema_version", "symbol", "signal", "chart_objects", "status_panel"}
    assert output["symbol"] == "XAUUSD"

    signal = output["signal"]
    for key in (
        "symbol",
        "action",
        "confidence",
        "reasons",
        "blocked",
        "blocker_reasons",
        "setup_classification",
        "advanced_modules",
    ):
        assert key in signal

    advanced_modules = signal["advanced_modules"]
    assert "final_direction" in advanced_modules
    assert "final_confidence" in advanced_modules
    assert "module_results" in advanced_modules
    assert "module_health" in advanced_modules


def test_run_pipeline_blocked_signal_always_has_blocker_reason(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    bars = _bars()
    state = _strong_buy_state(bars, mode="replay", blocked=True, blocked_reasons=[])

    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False)),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_blocked", mode="replay"))

    assert output["signal"]["blocked"] is True
    assert output["signal"]["action"] == "WAIT"
    assert output["signal"]["blocker_reasons"], "blocked signal must include at least one blocker reason"
    assert output["status_panel"]["blocker_result"]["blocked"] is True
    assert output["status_panel"]["blocker_result"]["blocker_reasons"]


def test_run_pipeline_replay_macro_penalty_updates_public_confidence_and_classification(
    tmp_path: Path,
) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    bars = _bars()
    state = _strong_buy_state(bars, mode="replay", blocked=False)

    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=False, confidence_penalty=0.25)),
        patch(
            "run.score_signal_intelligence",
            return_value={"signal_score": 0.8, "confidence": 0.8, "feature_contributors": {"buy_vote_a": 1.0}},
        ),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_penalty", mode="replay"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is True
    assert "confidence_below_threshold" in signal["blocker_reasons"]
    assert signal["confidence"] == 0.55
    assert signal["advanced_modules"]["final_direction"] == "BUY"
    assert signal["advanced_modules"]["final_confidence"] == 0.9
    assert signal["setup_classification"] == "low_confluence"


def test_run_pipeline_live_macro_pause_blocks_with_reason(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    bars = _bars()
    state = _strong_buy_state(bars, mode="live", blocked=False)

    with (
        patch("run.classify_market_structure", return_value={"state": "trend_up", "bias": "buy", "strength": 0.9}),
        patch(
            "run.assess_liquidity_state",
            return_value={"liquidity_state": "stable", "direction_hint": "buy", "score": 0.85},
        ),
        patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
        patch("run.run_advanced_modules", return_value=state),
        patch("run.collect_xauusd_macro_state", return_value=_macro_state(pause_trading=True)),
        patch("run.evaluate_capital_protection", return_value=_capital_ok()),
    ):
        output = run_pipeline(_runtime_config(sample_path, tmp_path / "memory_live_pause", mode="live"))

    signal = output["signal"]
    assert signal["action"] == "WAIT"
    assert signal["blocked"] is True
    assert "macro_feed_unsafe_pause" in signal["blocker_reasons"]
