from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class MetaAdaptiveConfig:
    profile_path: str = "memory/meta_adaptive_profile.json"


class MetaAdaptiveAI:
    """Internal-data-only adaptive profile updater (no external/hidden intelligence)."""

    def __init__(self, config: MetaAdaptiveConfig | None = None) -> None:
        self.config = config or MetaAdaptiveConfig()
        self.path = Path(self.config.profile_path)
        self._ensure_seed()

    def _ensure_seed(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(
                    {
                        "symbol": "XAUUSD",
                        "samples": 0,
                        "win_rate": 0.0,
                        "preferred_direction": "WAIT",
                        "confidence_bias": 0.0,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    def load_profile(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def update_from_internal_memory(self, trade_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
        relevant = [o for o in trade_outcomes if str(o.get("symbol", "")).upper() == "XAUUSD"]
        closed = [o for o in relevant if o.get("status") == "closed"]
        wins = [o for o in closed if o.get("result") == "win"]

        buy_closed = [o for o in closed if str(o.get("direction", "")).upper() == "BUY"]
        sell_closed = [o for o in closed if str(o.get("direction", "")).upper() == "SELL"]

        buy_wins = sum(1 for o in buy_closed if o.get("result") == "win")
        sell_wins = sum(1 for o in sell_closed if o.get("result") == "win")

        if buy_wins > sell_wins:
            preferred = "BUY"
        elif sell_wins > buy_wins:
            preferred = "SELL"
        else:
            preferred = "WAIT"

        win_rate = (len(wins) / len(closed)) if closed else 0.0
        confidence_bias = round((win_rate - 0.5) * 0.2, 4)

        profile = {
            "symbol": "XAUUSD",
            "samples": len(closed),
            "win_rate": round(win_rate, 4),
            "preferred_direction": preferred,
            "confidence_bias": confidence_bias,
        }
        self.path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile

    def profile_as_module_output(self, profile: dict[str, Any], current_direction: str) -> dict[str, Any]:
        preferred = str(profile.get("preferred_direction", "WAIT"))
        bias = float(profile.get("confidence_bias", 0.0))

        if preferred == current_direction and preferred in {"BUY", "SELL"}:
            delta = max(0.0, bias)
            vote = preferred.lower()
        elif preferred in {"BUY", "SELL"} and current_direction in {"BUY", "SELL"} and preferred != current_direction:
            delta = min(0.0, -abs(bias))
            vote = "neutral"
        else:
            delta = 0.0
            vote = "neutral"

        return {
            "module": "meta_adaptive_ai",
            "state": "computed",
            "direction_vote": vote,
            "confidence_delta": round(delta, 4),
            "reasons": [
                f"samples={profile.get('samples', 0)}",
                f"win_rate={profile.get('win_rate', 0.0)}",
                f"preferred_direction={preferred}",
            ],
        }
