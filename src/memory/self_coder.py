from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.memory.pattern_store import PatternStore


@dataclass(frozen=True)
class SelfCoderConfig:
    min_examples: int = 3
    min_win_rate: float = 0.60


class SelfCoder:
    """Generates deterministic rules only from stored, closed trade outcomes."""

    def __init__(self, store: PatternStore, config: SelfCoderConfig | None = None) -> None:
        self.store = store
        self.config = config or SelfCoderConfig()

    def generate_rules_from_outcomes(self) -> list[dict[str, Any]]:
        outcomes = self.store.load("trade_outcomes")
        closed = [o for o in outcomes if o.get("status") == "closed" and o.get("direction") in {"BUY", "SELL"}]

        grouped: dict[str, list[dict[str, Any]]] = {"BUY": [], "SELL": []}
        for row in closed:
            grouped[row["direction"]].append(row)

        rules: list[dict[str, Any]] = []
        for direction, rows in grouped.items():
            if len(rows) < self.config.min_examples:
                continue

            wins = [r for r in rows if r.get("result") == "win"]
            win_rate = len(wins) / len(rows)
            avg_confidence = sum(float(r.get("confidence", 0.0)) for r in rows) / len(rows)
            avg_win_pnl = (
                sum(float(r.get("pnl_points", 0.0)) for r in wins) / len(wins) if wins else 0.0
            )

            if win_rate < self.config.min_win_rate:
                continue

            evidence_ids = [r["trade_id"] for r in rows]
            rule = {
                "rule_id": f"rule_{direction.lower()}_{len(evidence_ids)}",
                "symbol": "XAUUSD",
                "direction": direction,
                "status": "active",
                "description": (
                    f"Promote {direction} only when confidence >= {round(avg_confidence, 3)} "
                    f"based on {len(rows)} closed outcomes."
                ),
                "conditions": {
                    "min_confidence": round(avg_confidence, 3),
                    "min_win_rate": round(win_rate, 3),
                },
                "evidence": {
                    "trade_ids": evidence_ids,
                    "sample_size": len(rows),
                    "wins": len(wins),
                    "avg_win_pnl_points": round(avg_win_pnl, 3),
                },
            }
            rules.append(rule)

        self.store.save_generated_rules(rules)
        return rules
