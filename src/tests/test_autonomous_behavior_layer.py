from __future__ import annotations

import json
from pathlib import Path

from src.learning.autonomous_behavior_layer import run_autonomous_behavior_layer


def test_autonomous_behavior_layer_pauses_and_logs_on_anomalies(tmp_path: Path) -> None:
    stale_artifact = tmp_path / "memory" / "autonomous_behavior" / "legacy.stale.json"
    stale_artifact.parent.mkdir(parents=True, exist_ok=True)
    stale_artifact.write_text(json.dumps({"stale": True}), encoding="utf-8")
    trade_outcomes = [
        {
            "trade_id": "t-1",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.2,
            "direction": "BUY",
            "source_reasons": ["late_entry"],
            "failure_cause": "execution_failure",
            "setup_type": "breakout",
            "session": "london",
        },
        {
            "trade_id": "t-2",
            "status": "closed",
            "result": "loss",
            "pnl_points": -1.0,
            "direction": "BUY",
            "source_reasons": ["spread_spike"],
            "failure_cause": "execution_failure",
            "setup_type": "breakout",
            "session": "london",
        },
        {
            "trade_id": "t-3",
            "status": "closed",
            "result": "loss",
            "pnl_points": -0.8,
            "direction": "SELL",
            "source_reasons": ["weak_setup"],
            "failure_cause": "mt5_reject",
            "setup_type": "reversal",
            "session": "new_york",
        },
    ]

    result = run_autonomous_behavior_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={
            "structure_state": "range",
            "volatility_ratio": 1.6,
            "spread_ratio": 2.1,
            "slippage_ratio": 1.9,
            "stale_price_data": True,
            "mt5_ready": False,
            "recent_setup_confidence": 0.35,
            "base_signal_confidence": 0.4,
            "base_risk_size": 1.0,
        },
        feature_contributors={"execution_quality": -0.5, "market_regime": -0.2},
        mutation_candidates=[
            {
                "candidate_id": "mut-a",
                "mutation_score": 0.9,
                "replay_validation": {"required": True, "passed": False},
            }
        ],
    )

    assert result["market_regime_classifier"]["regime"] == "unstable"
    assert result["behavior_adjustment_engine"]["trading_enabled"] is False
    assert result["behavior_adjustment_engine"]["refuse_weak_setups"] is True
    assert result["environment_anomaly_detection"]["trigger_refusal"] is True
    assert result["capital_survival_engine"]["pause_trading"] is True
    assert result["continuous_survival_loop"]["decision"] == "pause"
    assert Path(result["trade_review_engine"]["path"]).match("*/trade_review/trade_reviews.json")

    strategy_payload = json.loads(Path(result["strategy_comparison_engine"]["path"]).read_text(encoding="utf-8"))
    assert strategy_payload["promoted_strategies"] == []
    assert strategy_payload["quarantined_strategies"][0]["replay_validation_required"] is True

    maintenance_payload = json.loads(Path(result["memory_maintenance_engine"]["path"]).read_text(encoding="utf-8"))
    assert str(stale_artifact) in maintenance_payload["deleted_stale_artifacts"]
    assert stale_artifact.exists() is False

    research_payload = json.loads(Path(result["research_generator"]["path"]).read_text(encoding="utf-8"))
    assert research_payload["replay_experiments"][0]["sandbox_governance"]["replay_validation_required"] is True


def test_autonomous_behavior_layer_resumes_under_stable_conditions(tmp_path: Path) -> None:
    trade_outcomes = [
        {
            "trade_id": "t-1",
            "status": "closed",
            "result": "win",
            "pnl_points": 1.2,
            "direction": "BUY",
            "source_reasons": ["trend_alignment"],
            "setup_type": "trend_follow",
            "session": "asia",
        },
        {
            "trade_id": "t-2",
            "status": "closed",
            "result": "win",
            "pnl_points": 1.4,
            "direction": "BUY",
            "source_reasons": ["trend_continuation"],
            "setup_type": "trend_follow",
            "session": "london",
        },
    ]

    result = run_autonomous_behavior_layer(
        memory_root=tmp_path / "memory",
        trade_outcomes=trade_outcomes,
        market_state={
            "structure_state": "trend_up",
            "volatility_ratio": 1.1,
            "spread_ratio": 1.0,
            "slippage_ratio": 1.0,
            "stale_price_data": False,
            "mt5_ready": True,
            "recent_setup_confidence": 0.82,
            "base_signal_confidence": 0.75,
            "base_risk_size": 1.0,
        },
        feature_contributors={"market_regime": 0.4, "session_behavior": 0.2},
        mutation_candidates=[
            {
                "candidate_id": "mut-strong",
                "mutation_score": 1.2,
                "replay_validation": {"required": True, "passed": True},
            }
        ],
    )

    assert result["market_regime_classifier"]["regime"] == "trend"
    assert result["behavior_adjustment_engine"]["trading_enabled"] is True
    assert result["environment_anomaly_detection"]["trigger_pause"] is False
    assert result["capital_survival_engine"]["resume_only_after_stable_conditions"] is True
    assert result["continuous_survival_loop"]["decision"] == "resume"
    assert result["strategy_comparison_engine"]["promoted_strategies"][0]["candidate_id"] == "mut-strong"
    assert result["internal_ranking_systems"]["setup_performance"][0]["name"] == "trend_follow"
