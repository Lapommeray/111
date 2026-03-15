from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExecutionState:
    symbol: str
    mode: str
    replay_source: str
    mt5_attempted: bool
    data_source: str
    ready: bool
    reasons: list[str]
    controlled_mt5_readiness: dict[str, Any] | None = None
    live_execution_blocked: bool = True
    mt5_execution_gate: str = "blocked"
    mt5_execution_refused: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "mode": self.mode,
            "replay_source": self.replay_source,
            "mt5_attempted": self.mt5_attempted,
            "data_source": self.data_source,
            "ready": self.ready,
            "reasons": self.reasons,
            "controlled_mt5_readiness": dict(self.controlled_mt5_readiness or {}),
            "live_execution_blocked": self.live_execution_blocked,
            "mt5_execution_gate": self.mt5_execution_gate,
            "mt5_execution_refused": self.mt5_execution_refused,
        }
