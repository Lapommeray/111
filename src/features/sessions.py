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


def track_session_behavior(
    bars: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    lookback: int = 30,
) -> dict[str, Any]:
    """Track major-session behavior with volatility profile and session win-rate learning."""
    if not bars:
        return {
            "module": "session_behavior",
            "state": "insufficient_data",
            "direction_vote": "neutral",
            "confidence": 0.0,
            "confidence_level": "low",
            "confidence_delta": 0.0,
            "reasons": ["no_bars"],
            "metrics": {"session_stats": {}},
        }

    ts = int(bars[-1]["time"])
    current_hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
    current_session = now_session(current_hour)
    recent_bars = bars[-lookback:] if len(bars) >= lookback else bars
    ranges = [float(b["high"]) - float(b["low"]) for b in recent_bars]
    avg_range = (sum(ranges) / len(ranges)) if ranges else 0.0

    session_stats: dict[str, dict[str, float]] = {}
    for item in outcomes:
        if str(item.get("status", "")).lower() != "closed":
            continue
        stamp = str(item.get("timestamp", ""))
        try:
            outcome_hour = datetime.fromisoformat(stamp).hour
        except ValueError:
            continue
        session = now_session(outcome_hour)
        bucket = session_stats.setdefault(session, {"samples": 0.0, "wins": 0.0})
        bucket["samples"] += 1.0
        if str(item.get("result", "")).lower() == "win":
            bucket["wins"] += 1.0

    for session, bucket in session_stats.items():
        samples = bucket["samples"]
        bucket["win_rate"] = round((bucket["wins"] / samples), 4) if samples else 0.5

    current_stats = session_stats.get(current_session, {"samples": 0.0, "wins": 0.0, "win_rate": 0.5})
    win_rate = float(current_stats.get("win_rate", 0.5))
    confidence = round(max(0.2, min(0.9, 0.35 + (win_rate * 0.5))), 4)
    reasons = [
        f"session={current_session}",
        f"session_samples={int(current_stats.get('samples', 0.0))}",
        f"session_win_rate={round(win_rate, 4)}",
    ]

    if current_session in {"london", "new_york"} and avg_range > 0:
        confidence_delta = 0.03 if win_rate >= 0.5 else -0.01
    elif current_session == "off_hours":
        confidence_delta = -0.04
    else:
        confidence_delta = 0.0

    if float(current_stats.get("samples", 0.0)) < 2:
        reasons.append("weak_pattern_pruned")
        confidence_delta = min(confidence_delta, 0.0)

    return {
        "module": "session_behavior",
        "state": current_session,
        "direction_vote": "neutral",
        "confidence": confidence,
        "confidence_level": "high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
        "confidence_delta": round(confidence_delta, 4),
        "reasons": reasons,
        "metrics": {
            "hour_utc": current_hour,
            "avg_range": round(avg_range, 4),
            "session_stats": session_stats,
        },
    }
