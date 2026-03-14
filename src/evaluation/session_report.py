from __future__ import annotations

from typing import Any


def build_session_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize action/blocking behavior by computed session state."""
    sessions: dict[str, dict[str, int]] = {}

    for record in records:
        signal = record.get("signal", {})
        action = str(signal.get("action", "WAIT"))
        blocked = bool(signal.get("blocked", False))

        session = (
            signal.get("advanced_modules", {})
            .get("module_results", {})
            .get("sessions", {})
            .get("payload", {})
            .get("state", "unknown")
        )
        session_key = str(session)

        stats = sessions.setdefault(
            session_key,
            {"samples": 0, "blocked": 0, "buy": 0, "sell": 0, "wait": 0},
        )

        stats["samples"] += 1
        if blocked:
            stats["blocked"] += 1

        if action == "BUY":
            stats["buy"] += 1
        elif action == "SELL":
            stats["sell"] += 1
        else:
            stats["wait"] += 1

    return {"sessions": sessions}
