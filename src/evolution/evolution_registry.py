from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import read_json_safe, write_json_atomic


class EvolutionRegistry:
    """Permanent traceable lifecycle registry for evolution artifacts."""

    ALLOWED_STATUSES = {"proposed", "verified", "promoted", "rejected", "archived"}

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            write_json_atomic(self.path, {"entries": []})

    def load(self) -> dict[str, Any]:
        data = read_json_safe(self.path, default={"entries": []})
        if not isinstance(data, dict):
            return {"entries": []}
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            return {"entries": []}
        return {"entries": entries}

    def append_entry(
        self,
        gap: dict[str, Any],
        artifact_path: str,
        artifact_type: str,
        status: str,
        validation: dict[str, Any],
        duplicate_check: dict[str, Any],
    ) -> dict[str, Any]:
        if status not in self.ALLOWED_STATUSES:
            raise ValueError(f"Invalid evolution status: {status}")

        now = datetime.now(tz=timezone.utc).isoformat()
        data = self.load()
        entry = {
            "entry_id": f"evo_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "timestamp": now,
            "gap_id": gap.get("gap_id", "unknown_gap"),
            "triggering_gap": gap,
            "artifact_path": artifact_path,
            "artifact_type": artifact_type,
            "status": status,
            "validation": validation,
            "duplicate_check": duplicate_check,
            "status_history": [{"status": status, "timestamp": now}],
        }
        data["entries"].append(entry)
        write_json_atomic(self.path, data)
        return entry

    def update_status(self, entry_id: str, status: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        if status not in self.ALLOWED_STATUSES:
            raise ValueError(f"Invalid evolution status: {status}")

        data = self.load()
        updated: dict[str, Any] | None = None
        for entry in data["entries"]:
            if entry.get("entry_id") == entry_id:
                updated_at = datetime.now(tz=timezone.utc).isoformat()
                entry["status"] = status
                entry["status_updated_at"] = updated_at
                history = entry.setdefault("status_history", [])
                if isinstance(history, list):
                    history.append({"status": status, "timestamp": updated_at})
                if extra:
                    entry.update(extra)
                updated = entry
                break

        if updated is None:
            raise ValueError(f"Entry id not found in evolution registry: {entry_id}")

        write_json_atomic(self.path, data)
        return updated

    def latest(self, limit: int = 25) -> list[dict[str, Any]]:
        return self.load()["entries"][-limit:]

    def count_by_status(self) -> dict[str, int]:
        counts = {status: 0 for status in self.ALLOWED_STATUSES}
        for entry in self.load()["entries"]:
            status = str(entry.get("status", ""))
            if status in counts:
                counts[status] += 1
        return counts
