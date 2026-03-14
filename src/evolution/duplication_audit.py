from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any


class DuplicationAudit:
    """Prevents repeated generated logic under new names."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def check_proposal(
        self,
        artifact_path: Path,
        proposal: dict[str, Any],
        existing_registry_entries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        content = proposal.get("content", "")
        content_hash = sha256(content.encode("utf-8")).hexdigest()

        duplicate_hash = any(
            str(entry.get("duplicate_check", {}).get("content_hash", "")) == content_hash
            for entry in existing_registry_entries
        )

        duplicate_target = False
        target_file = str(proposal.get("target_file", ""))
        if target_file:
            target_path = self.project_root / target_file
            duplicate_target = target_path.exists() and target_path.read_text(encoding="utf-8") == content

        return {
            "is_duplicate": duplicate_hash or duplicate_target,
            "duplicate_by_hash": duplicate_hash,
            "duplicate_by_target_match": duplicate_target,
            "content_hash": content_hash,
        }
