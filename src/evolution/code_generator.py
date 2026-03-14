from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import write_json_atomic


class CodeGenerator:
    """Produces visible proposal artifacts only (no hidden self-modification)."""

    def __init__(self, artifact_root: Path) -> None:
        self.artifact_root = artifact_root
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def generate_proposal(self, gap: dict[str, Any]) -> dict[str, Any]:
        artifact_id = f"proposal_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        target_file = self._derive_target_file(gap)

        proposal = {
            "artifact_id": artifact_id,
            "kind": "code_proposal",
            "triggering_gap": gap,
            "target_file": target_file,
            "content": self._proposal_content(gap, target_file),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        artifact_path = self.artifact_root / f"{artifact_id}.json"
        write_json_atomic(artifact_path, proposal)

        return {
            "artifact_path": str(artifact_path),
            "proposal": proposal,
        }

    @staticmethod
    def _derive_target_file(gap: dict[str, Any]) -> str:
        reason = gap.get("reason", "")
        target = str(gap.get("target", ""))
        if reason == "missing_tests":
            return f"src/tests/test_{target}.py"
        if reason == "missing_hooks":
            return "config/connectors.json"
        if reason == "missing_state_contributions":
            return "src/pipeline.py"
        if reason == "missing_registrations":
            return "memory/generated_code_registry.json"
        if reason == "broken_arch_links":
            return "src/pipeline.py"
        return "docs/evolution_notes.md"

    @staticmethod
    def _proposal_content(gap: dict[str, Any], target_file: str) -> str:
        return (
            "# Evolution proposal artifact\n"
            f"# target_file: {target_file}\n"
            f"# gap_id: {gap.get('gap_id')}\n"
            f"# reason: {gap.get('reason')}\n"
            f"# target: {gap.get('target')}\n"
            "# This artifact is visible and requires manual application.\n"
        )
