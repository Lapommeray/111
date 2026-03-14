from __future__ import annotations

from typing import Any


class GapDiscovery:
    """Converts inspection findings into structured, prioritized gap records."""

    def discover(self, inspection_report: dict[str, Any]) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []

        mapping = {
            "missing_tests": "high",
            "missing_hooks": "medium",
            "missing_state_contributions": "high",
            "missing_registrations": "high",
            "dead_modules": "low",
            "broken_arch_links": "high",
        }

        for key, priority in mapping.items():
            findings = inspection_report.get(key, [])
            for index, finding in enumerate(findings, start=1):
                gaps.append(
                    {
                        "gap_id": f"{key}_{index}",
                        "reason": key,
                        "target": finding,
                        "priority": priority,
                    }
                )

        priority_rank = {"high": 0, "medium": 1, "low": 2}
        return sorted(gaps, key=lambda g: (priority_rank[g["priority"]], g["gap_id"]))
