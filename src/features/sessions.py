from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.utils import now_session


def compute_session_state(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify current trading session from last bar timestamp."""
    if not bars:
        return {
            "module": "sessions",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence_delta": 0.0,
            "reasons": ["no_bars"],
        }

    ts = int(bars[-1]["time"])
    hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
    session = now_session(hour)

    confidence_delta = 0.0
    reasons = [f"session={session}"]
    if session in {"london", "new_york"}:
        confidence_delta = 0.03
        reasons.append("major_session")
    elif session == "off_hours":
        confidence_delta = -0.04
        reasons.append("off_hours")

    return {
        "module": "sessions",
        "state": session,
        "direction_vote": "neutral",
        "confidence_delta": confidence_delta,
        "reasons": reasons,
        "metrics": {"hour_utc": hour},
    }
