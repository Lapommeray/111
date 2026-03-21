"""Tests for macro feed safety bypass during replay mode.

Verifies that:
- Replay mode is NOT globally blocked when macro feeds are unavailable.
- Live mode still blocks when macro feeds report pause_trading=True.
- Macro unavailable state is still surfaced in replay signal artifacts.
"""
from __future__ import annotations

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from run import (
    RuntimeConfig,
    ensure_sample_data,
    run_pipeline,
)
from src.state import ModuleResult, PipelineState


def _bars(count: int = 60) -> list[dict]:
    return [
        {
            "time": 1_700_000_000 + (idx * 60),
            "open": 2100.0,
            "high": 2100.5,
            "low": 2099.5,
            "close": 2100.2,
            "tick_volume": 140.0,
        }
        for idx in range(count)
    ]


def _strong_buy_state(bars: list[dict], mode: str) -> PipelineState:
    """PipelineState with strong BUY signals and enough directional votes."""
    structure = {"state": "trend_up", "bias": "buy", "strength": 0.9}
    liquidity = {"liquidity_state": "stable", "direction_hint": "buy", "score": 0.8}
    return PipelineState(
        symbol="XAUUSD",
        mode=mode,
        bars=bars,
        structure=structure,
        liquidity=liquidity,
        base_confidence=0.92,
        base_direction="BUY",
        final_confidence=0.92,
        final_direction="BUY",
        blocked=False,
        blocked_reasons=[],
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
                payload={"spread_points": 15.0},
            ),
            "volatility": ModuleResult(
                name="volatility",
                role="volatility_regime",
                direction_vote="neutral",
                confidence_delta=0.0,
                blocked=False,
                reasons=[],
                payload={"volatility_ratio": 1.0, "state": "balanced", "metrics": {"ratio": 1.0}},
            ),
            "direction_buy_a": ModuleResult(
                name="direction_buy_a", role="vote_a", direction_vote="buy",
                confidence_delta=0.02, blocked=False, reasons=[], payload={},
            ),
            "direction_buy_b": ModuleResult(
                name="direction_buy_b", role="vote_b", direction_vote="buy",
                confidence_delta=0.02, blocked=False, reasons=[], payload={},
            ),
            "direction_buy_c": ModuleResult(
                name="direction_buy_c", role="vote_c", direction_vote="buy",
                confidence_delta=0.02, blocked=False, reasons=[], payload={},
            ),
            "conflict_filter": ModuleResult(
                name="conflict_filter", role="vote_conflict_gate",
                direction_vote="neutral", confidence_delta=0.01, blocked=False,
                reasons=["buy_votes=3", "sell_votes=0"], payload={},
            ),
        },
    )


_MACRO_STATE_PAUSE = {
    "trade_tags": {"session": "london", "dxy_state": "unavailable"},
    "risk_behavior": {
        "pause_trading": True,
        "confidence_penalty": 0.05,
        "size_multiplier": 0.5,
        "reasons": [
            "feeds_unavailable:alpha_vantage,fred,treasury",
            "macro_feed_state_unsafe_or_stale",
        ],
    },
    "macro_states": {"dxy_state": "unavailable"},
    "feed_states": {},
}

_CAPITAL_OK = {
    "effective_volume": 0.01,
    "trade_refused": False,
    "daily_loss_check": {"allowed": True},
    "trigger_reasons": [],
}


class TestMacroReplayBypass(unittest.TestCase):

    def setUp(self) -> None:
        self._temp_dirs: list[str] = []

    def tearDown(self) -> None:
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _mkdtemp(self, prefix: str = "macro_replay_") -> str:
        d = tempfile.mkdtemp(prefix=prefix)
        self._temp_dirs.append(d)
        return d

    # ------------------------------------------------------------------
    # 1. Replay mode: macro pause does NOT globally block signals
    # ------------------------------------------------------------------
    def test_replay_mode_not_blocked_by_macro_pause(self) -> None:
        sample_path = Path(self._mkdtemp(prefix="replay_macro_samples_")) / "xauusd.csv"
        ensure_sample_data(sample_path)
        bars = _bars()
        structure = {"state": "trend_up", "bias": "buy", "strength": 0.9}
        liquidity = {"liquidity_state": "stable", "direction_hint": "buy", "score": 0.8}
        state = _strong_buy_state(bars, mode="replay")

        with (
            patch("run.classify_market_structure", return_value=structure),
            patch("run.assess_liquidity_state", return_value=liquidity),
            patch("run.compute_confidence", return_value={"confidence": 0.92, "direction": "BUY", "reasons": ["seed_buy"]}),
            patch("run.run_advanced_modules", return_value=state),
            patch("run.collect_xauusd_macro_state", return_value=_MACRO_STATE_PAUSE),
            patch("run.evaluate_capital_protection", return_value=_CAPITAL_OK),
        ):
            output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    replay_source="csv",
                    replay_csv_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="replay_macro_mem_"),
                    mode="replay",
                    evolution_enabled=False,
                    live_execution_enabled=False,
                    macro_feed_enabled=False,
                )
            )

        reasons = output["signal"]["reasons"]
        self.assertNotIn("macro_feed_unsafe_pause", reasons)

    # ------------------------------------------------------------------
    # 2. Live mode: macro pause STILL globally blocks (unchanged)
    # ------------------------------------------------------------------
    def test_live_mode_blocked_by_macro_pause(self) -> None:
        sample_path = Path(self._mkdtemp(prefix="live_macro_samples_")) / "xauusd.csv"
        ensure_sample_data(sample_path)
        bars = _bars()
        structure = {"state": "trend_up", "bias": "buy", "strength": 0.9}
        liquidity = {"liquidity_state": "stable", "direction_hint": "buy", "score": 0.8}
        state = _strong_buy_state(bars, mode="live")

        with (
            patch("run.classify_market_structure", return_value=structure),
            patch("run.assess_liquidity_state", return_value=liquidity),
            patch("run.compute_confidence", return_value={"confidence": 0.92, "direction": "BUY", "reasons": ["seed_buy"]}),
            patch("run.run_advanced_modules", return_value=state),
            patch("run.collect_xauusd_macro_state", return_value=_MACRO_STATE_PAUSE),
            patch("run.evaluate_capital_protection", return_value=_CAPITAL_OK),
        ):
            output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    replay_source="csv",
                    replay_csv_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="live_macro_mem_"),
                    mode="live",
                    evolution_enabled=False,
                    live_execution_enabled=False,
                    macro_feed_enabled=True,
                )
            )

        reasons = output["signal"]["reasons"]
        self.assertIn("macro_feed_unsafe_pause", reasons)
        self.assertEqual(output["signal"]["action"], "WAIT")

    # ------------------------------------------------------------------
    # 3. Replay: macro state is still surfaced honestly in artifacts
    # ------------------------------------------------------------------
    def test_replay_mode_surfaces_macro_state_in_artifacts(self) -> None:
        sample_path = Path(self._mkdtemp(prefix="replay_macro_artifacts_")) / "xauusd.csv"
        ensure_sample_data(sample_path)
        bars = _bars()
        structure = {"state": "trend_up", "bias": "buy", "strength": 0.9}
        liquidity = {"liquidity_state": "stable", "direction_hint": "buy", "score": 0.8}
        state = _strong_buy_state(bars, mode="replay")

        with (
            patch("run.classify_market_structure", return_value=structure),
            patch("run.assess_liquidity_state", return_value=liquidity),
            patch("run.compute_confidence", return_value={"confidence": 0.92, "direction": "BUY", "reasons": ["seed_buy"]}),
            patch("run.run_advanced_modules", return_value=state),
            patch("run.collect_xauusd_macro_state", return_value=_MACRO_STATE_PAUSE),
            patch("run.evaluate_capital_protection", return_value=_CAPITAL_OK),
        ):
            output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    replay_source="csv",
                    replay_csv_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="replay_macro_art_mem_"),
                    mode="replay",
                    evolution_enabled=False,
                    live_execution_enabled=False,
                    macro_feed_enabled=False,
                )
            )

        # Macro state is still fully present in signal output
        macro_state = output["signal"]["macro_state"]
        self.assertTrue(macro_state["risk_behavior"]["pause_trading"])
        self.assertIn(
            "macro_feed_state_unsafe_or_stale",
            macro_state["risk_behavior"]["reasons"],
        )
        # Trade tags also surfaced
        trade_tags = output["signal"]["trade_tags"]
        self.assertEqual(trade_tags["dxy_state"], "unavailable")


if __name__ == "__main__":
    unittest.main()
