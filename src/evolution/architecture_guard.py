from __future__ import annotations

from pathlib import Path
from typing import Any


class ArchitectureGuard:
    """Enforces explicit project golden rules for generated proposals."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def evaluate(self, proposal: dict[str, Any], symbol: str) -> dict[str, Any]:
        reasons: list[str] = []
        allowed_roots = ("src/", "config/", "memory/", "docs/")
        target_file = str(proposal.get("target_file", ""))
        content = str(proposal.get("content", "")).lower()

        if symbol.upper() != "XAUUSD":
            reasons.append("symbol_must_be_xauusd")

        if not target_file.startswith(allowed_roots):
            reasons.append("target_outside_allowed_roots")

        disallowed_strategy_targets = (
            "src/features/",
            "src/filters/",
            "src/scoring/",
        )
        if target_file.startswith(disallowed_strategy_targets):
            reasons.append("strategy_logic_target_not_allowed_for_evolution_proposal")

        blocked_markers = (
            "hidden",
            "secret",
            "self-modifying",
            "auto-apply",
            "silent mutation",
        )
        for marker in blocked_markers:
            if marker in content:
                reasons.append(f"blocked_marker:{marker}")

        passed = len(reasons) == 0
        return {
            "passed": passed,
            "reasons": reasons if reasons else ["architecture_guard_passed"],
        }
