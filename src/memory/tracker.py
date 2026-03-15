from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.memory.pattern_store import PatternStore


@dataclass(frozen=True)
class OutcomeTrackerConfig:
    lookahead_bars: int = 6
    min_move_points: float = 0.35


class OutcomeTracker:
    """Writes promoted trade outcomes from actual price movement in loaded bars."""

    def __init__(self, store: PatternStore, config: OutcomeTrackerConfig | None = None) -> None:
        self.store = store
        self.config = config or OutcomeTrackerConfig()

    def evaluate_and_record(
        self,
        trade_id: str,
        decision: str,
        bars: list[dict[str, Any]],
        confidence: float,
        reasons: list[str],
        trade_tags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if decision not in {"BUY", "SELL"}:
            outcome = {
                "trade_id": trade_id,
                "symbol": "XAUUSD",
                "direction": decision,
                "status": "skipped",
                "result": "n/a",
                "pnl_points": 0.0,
                "source_reasons": reasons,
                "confidence": confidence,
                "trade_tags": dict(trade_tags or {}),
            }
            self.store.record_trade_outcome(outcome)
            return outcome

        if len(bars) <= self.config.lookahead_bars + 1:
            outcome = {
                "trade_id": trade_id,
                "symbol": "XAUUSD",
                "direction": decision,
                "status": "pending",
                "result": "unknown",
                "pnl_points": 0.0,
                "source_reasons": reasons,
                "confidence": confidence,
                "trade_tags": dict(trade_tags or {}),
            }
            self.store.record_trade_outcome(outcome)
            return outcome

        entry_price = float(bars[-self.config.lookahead_bars - 1]["close"])
        evaluation_window = bars[-self.config.lookahead_bars :]
        exit_price = float(evaluation_window[-1]["close"])

        move = exit_price - entry_price
        pnl_points = move if decision == "BUY" else -move

        if pnl_points >= self.config.min_move_points:
            result = "win"
        elif pnl_points <= -self.config.min_move_points:
            result = "loss"
        else:
            result = "flat"

        outcome = {
            "trade_id": trade_id,
            "symbol": "XAUUSD",
            "direction": decision,
            "status": "closed",
            "result": result,
            "entry_price": round(entry_price, 3),
            "exit_price": round(exit_price, 3),
            "pnl_points": round(pnl_points, 3),
            "confidence": confidence,
            "source_reasons": reasons,
            "trade_tags": dict(trade_tags or {}),
        }
        self.store.record_trade_outcome(outcome)
        return outcome

    def summarize_recent_outcomes(self, limit: int = 50) -> dict[str, Any]:
        outcomes = self.store.load("trade_outcomes")[-limit:]
        closed = [o for o in outcomes if o.get("status") == "closed"]
        wins = sum(1 for o in closed if o.get("result") == "win")
        losses = sum(1 for o in closed if o.get("result") == "loss")
        flats = sum(1 for o in closed if o.get("result") == "flat")
        total = len(closed)

        return {
            "total_closed": total,
            "wins": wins,
            "losses": losses,
            "flats": flats,
            "win_rate": round((wins / total), 4) if total else 0.0,
        }
