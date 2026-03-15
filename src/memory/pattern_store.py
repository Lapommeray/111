from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class PatternStoreConfig:
    root: str = "memory"


class PatternStore:
    """JSON-backed storage for snapshots, setup memory, outcomes, and generated rules."""

    def __init__(self, config: PatternStoreConfig | None = None) -> None:
        self.config = config or PatternStoreConfig()
        self.root = Path(self.config.root)
        self.files = {
            "pattern_memory": self.root / "pattern_memory.json",
            "blocked_setups": self.root / "blocked_setups.json",
            "promoted_setups": self.root / "promoted_setups.json",
            "trade_outcomes": self.root / "trade_outcomes.json",
            "generated_rules": self.root / "generated_rules.json",
        }
        self._ensure_files()

    def _ensure_files(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for key, path in self.files.items():
            if not path.exists():
                self._write(path, self._seed_for(key))

    def _seed_for(self, name: str) -> Any:
        seeds: dict[str, Any] = {
            "pattern_memory": {"patterns": []},
            "blocked_setups": [],
            "promoted_setups": [],
            "trade_outcomes": [],
            "generated_rules": {"rules": []},
        }
        return seeds[name]

    def load(self, name: str) -> Any:
        if name not in self.files:
            raise KeyError(f"Unknown memory file key: {name}")

        path = self.files[name]
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            seed = self._seed_for(name)
            self._write(path, seed)
            return seed
        except json.JSONDecodeError:
            self._backup_corrupt_file(path)
            seed = self._seed_for(name)
            self._write(path, seed)
            return seed

    def save(self, name: str, value: Any) -> None:
        if name not in self.files:
            raise KeyError(f"Unknown memory file key: {name}")
        self._write(self.files[name], value)

    def record_snapshot(self, snapshot: dict[str, Any]) -> str:
        snapshot_id = self._new_id("snap")
        payload = self.load("pattern_memory")
        payload.setdefault("patterns", []).append(
            {
                "snapshot_id": snapshot_id,
                "timestamp": self._now_iso(),
                **snapshot,
            }
        )
        self.save("pattern_memory", payload)
        return snapshot_id

    def record_blocked(self, blocked_entry: dict[str, Any]) -> None:
        items = self.load("blocked_setups")
        items.append({"timestamp": self._now_iso(), **blocked_entry})
        self.save("blocked_setups", items)

    def record_promoted(self, promoted_entry: dict[str, Any]) -> str:
        trade_id = self._new_id("trade")
        items = self.load("promoted_setups")
        items.append({"trade_id": trade_id, "timestamp": self._now_iso(), **promoted_entry})
        self.save("promoted_setups", items)
        return trade_id

    def record_trade_outcome(self, outcome: dict[str, Any]) -> None:
        items = self.load("trade_outcomes")
        items.append({"timestamp": self._now_iso(), **outcome})
        self.save("trade_outcomes", items)

    def save_generated_rules(self, rules: list[dict[str, Any]]) -> None:
        payload = {"rules": rules, "updated_at": self._now_iso()}
        self.save("generated_rules", payload)

    def _backup_corrupt_file(self, path: Path) -> None:
        if not path.exists():
            return
        backup_path = path.with_name(f"{path.name}.corrupt.{self._new_id('bak')}")
        try:
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to back up corrupt memory file: {path}") from exc

    def _new_id(self, prefix: str) -> str:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return f"{prefix}_{ts}"

    def _now_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _write(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(value, fh, indent=2)
            tmp_path.replace(path)
        except OSError as exc:
            raise RuntimeError(f"Failed to write memory file: {path}") from exc
