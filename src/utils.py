from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def aggregate_direction(base_direction: str, votes: list[str]) -> str:
    normalized = [v.lower() for v in votes if v.lower() in {"buy", "sell", "wait", "neutral"}]
    normalized.append(base_direction.lower())
    counter = Counter(normalized)

    buy = counter.get("buy", 0)
    sell = counter.get("sell", 0)
    wait = counter.get("wait", 0) + counter.get("neutral", 0)

    if buy > sell and buy >= wait:
        return "BUY"
    if sell > buy and sell >= wait:
        return "SELL"
    return "WAIT"


def aggregate_confidence(base_confidence: float, deltas: list[float]) -> float:
    return round(clamp(base_confidence + sum(deltas), 0.0, 1.0), 4)


def timeframe_to_minutes(tf: str) -> int:
    mapping: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}
    return mapping[tf.upper()]


def now_session(hour_utc: int) -> str:
    if 0 <= hour_utc < 7:
        return "asia"
    if 7 <= hour_utc < 13:
        return "london"
    if 13 <= hour_utc < 21:
        return "new_york"
    return "off_hours"


def safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def ensure_required_keys(row: dict[str, Any], keys: list[str]) -> bool:
    return all(k in row for k in keys)


def module_ready(output: dict[str, Any]) -> tuple[bool, str, list[str]]:
    reasons = list(output.get("reasons", []))
    if str(output.get("state", "")).lower() == "insufficient_data":
        return False, "degraded", reasons or ["insufficient_data"]
    return True, "ready", reasons or ["healthy"]


def normalize_reasons(reasons: list[str]) -> list[str]:
    """Normalize and deduplicate reason strings while preserving first-seen order."""
    seen: set[str] = set()
    normalized: list[str] = []
    for reason in reasons:
        reason_text = str(reason).strip()
        if not reason_text or reason_text in seen:
            continue
        seen.add(reason_text)
        normalized.append(reason_text)
    return normalized


def read_json_safe(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def register_generated_artifact(
    registry_path: Path,
    artifact_type: str,
    artifact_path: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    data = read_json_safe(registry_path, default={"artifacts": []})
    if not isinstance(data, dict):
        data = {"artifacts": []}
    if not isinstance(data.get("artifacts"), list):
        data["artifacts"] = []

    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "artifact_type": artifact_type,
        "artifact_path": artifact_path,
        "metadata": metadata,
    }
    data.setdefault("artifacts", []).append(entry)
    write_json_atomic(registry_path, data)
    return entry
