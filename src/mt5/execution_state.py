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

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "mode": self.mode,
            "replay_source": self.replay_source,
            "mt5_attempted": self.mt5_attempted,
            "data_source": self.data_source,
            "ready": self.ready,
            "reasons": self.reasons,
        }
