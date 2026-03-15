from __future__ import annotations

from pathlib import Path

from src.memory.meta_adaptive_ai import MetaAdaptiveAI, MetaAdaptiveConfig
from src.memory.pattern_store import PatternStore, PatternStoreConfig
from src.memory.self_coder import SelfCoder, SelfCoderConfig
from src.memory.tracker import OutcomeTracker


def _bars_trending_up(count: int = 16) -> list[dict[str, float]]:
    bars: list[dict[str, float]] = []
    base = 2000.0
    for i in range(count):
        close = base + (i * 0.5)
        bars.append(
            {
                "time": 1700000000 + i * 60,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.3,
                "close": close,
                "tick_volume": 100 + i,
            }
        )
    return bars


def test_tracker_records_closed_buy_outcome(tmp_path: Path) -> None:
    store = PatternStore(PatternStoreConfig(root=str(tmp_path / "memory")))
    tracker = OutcomeTracker(store)

    outcome = tracker.evaluate_and_record(
        trade_id="trade_1",
        decision="BUY",
        bars=_bars_trending_up(16),
        confidence=0.8,
        reasons=["test"],
    )

    assert outcome["status"] == "closed"
    assert outcome["result"] == "win"
    recorded = store.load("trade_outcomes")
    assert any(x.get("trade_id") == "trade_1" for x in recorded)


def test_self_coder_generates_rule_from_closed_wins(tmp_path: Path) -> None:
    store = PatternStore(PatternStoreConfig(root=str(tmp_path / "memory")))

    for i in range(3):
        store.record_trade_outcome(
            {
                "trade_id": f"t{i}",
                "symbol": "XAUUSD",
                "direction": "BUY",
                "status": "closed",
                "result": "win",
                "pnl_points": 1.2,
                "confidence": 0.75,
            }
        )

    rules = SelfCoder(store, SelfCoderConfig(min_examples=3, min_win_rate=0.6)).generate_rules_from_outcomes()
    assert len(rules) == 1
    rule = rules[0]
    assert rule["symbol"] == "XAUUSD"
    assert rule["direction"] == "BUY"
    assert rule["status"] == "active"
    assert len(rule["evidence"]["trade_ids"]) == 3


def test_meta_adaptive_ai_updates_profile_from_internal_memory(tmp_path: Path) -> None:
    profile_path = tmp_path / "memory" / "meta_profile.json"
    ai = MetaAdaptiveAI(MetaAdaptiveConfig(profile_path=str(profile_path)))

    outcomes = [
        {"symbol": "XAUUSD", "status": "closed", "direction": "BUY", "result": "win"},
        {"symbol": "XAUUSD", "status": "closed", "direction": "BUY", "result": "win"},
        {"symbol": "XAUUSD", "status": "closed", "direction": "SELL", "result": "loss"},
    ]

    profile = ai.update_from_internal_memory(outcomes)
    assert profile["symbol"] == "XAUUSD"
    assert profile["preferred_direction"] == "BUY"
    module_output = ai.profile_as_module_output(profile, current_direction="BUY")
    assert module_output["module"] == "meta_adaptive_ai"
    assert module_output["direction_vote"] in {"buy", "neutral"}
