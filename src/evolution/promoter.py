from __future__ import annotations

from typing import Any

from src.evolution.evolution_registry import EvolutionRegistry


class Promoter:
    """Applies lifecycle transitions for generated evolution artifacts."""

    def __init__(self, registry: EvolutionRegistry) -> None:
        self.registry = registry

    def decide_status(
        self,
        entry_id: str,
        verification: dict[str, Any],
        duplicate_check: dict[str, Any],
        architecture_check: dict[str, Any],
        auto_promote: bool = False,
    ) -> dict[str, Any]:
        if duplicate_check.get("is_duplicate", False):
            return self.registry.update_status(
                entry_id,
                "rejected",
                extra={"rejection_reason": "duplicate_logic_detected"},
            )

        if not architecture_check.get("passed", False):
            return self.registry.update_status(
                entry_id,
                "rejected",
                extra={"rejection_reason": "architecture_guard_failed"},
            )

        if not verification.get("passed", False):
            return self.registry.update_status(
                entry_id,
                "rejected",
                extra={"rejection_reason": "verification_failed"},
            )

        verified = self.registry.update_status(entry_id, "verified")
        if auto_promote:
            return self.promote(entry_id)
        return verified

    def promote(self, entry_id: str) -> dict[str, Any]:
        """Mark a verified proposal as promoted for manual merge/application."""
        return self.registry.update_status(
            entry_id,
            "promoted",
            extra={"promotion_note": "manual_promotion_recorded"},
        )

    def archive(self, entry_id: str, reason: str = "superseded") -> dict[str, Any]:
        """Archive a proposal after promotion/rejection when no longer active."""
        return self.registry.update_status(entry_id, "archived", extra={"archive_reason": reason})
