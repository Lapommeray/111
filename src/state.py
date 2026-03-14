from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModuleResult:
    name: str
    role: str
    direction_vote: str = "neutral"
    confidence_delta: float = 0.0
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleHealth:
    name: str
    ready: bool
    status: str
    details: list[str] = field(default_factory=list)


@dataclass
class ConnectorHook:
    name: str
    source_module: str
    target_interface: str
    enabled: bool
    description: str


@dataclass
class EvolutionStatus:
    enabled: bool = False
    inspection_summary: dict[str, int] = field(default_factory=dict)
    gap_count: int = 0
    proposed_count: int = 0
    verified_count: int = 0
    rejected_count: int = 0


@dataclass
class PipelineState:
    symbol: str
    mode: str
    bars: list[dict[str, Any]]
    structure: dict[str, Any]
    liquidity: dict[str, Any]
    base_confidence: float
    base_direction: str
    module_results: dict[str, ModuleResult] = field(default_factory=dict)
    module_health: dict[str, ModuleHealth] = field(default_factory=dict)
    connector_hooks: dict[str, ConnectorHook] = field(default_factory=dict)
    evolution_status: EvolutionStatus = field(default_factory=EvolutionStatus)
    final_confidence: float = 0.0
    final_direction: str = "WAIT"
    blocked: bool = False
    blocked_reasons: list[str] = field(default_factory=list)

    def as_module_payload(self) -> dict[str, Any]:
        return {
            key: {
                "name": value.name,
                "role": value.role,
                "direction_vote": value.direction_vote,
                "confidence_delta": value.confidence_delta,
                "blocked": value.blocked,
                "reasons": value.reasons,
                "payload": value.payload,
            }
            for key, value in self.module_results.items()
        }

    def as_health_payload(self) -> dict[str, Any]:
        return {
            key: {
                "name": value.name,
                "ready": value.ready,
                "status": value.status,
                "details": value.details,
            }
            for key, value in self.module_health.items()
        }

    def as_connector_payload(self) -> dict[str, Any]:
        return {
            key: {
                "name": value.name,
                "source_module": value.source_module,
                "target_interface": value.target_interface,
                "enabled": value.enabled,
                "description": value.description,
            }
            for key, value in self.connector_hooks.items()
        }

    def as_evolution_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.evolution_status.enabled,
            "inspection_summary": self.evolution_status.inspection_summary,
            "gap_count": self.evolution_status.gap_count,
            "proposed_count": self.evolution_status.proposed_count,
            "verified_count": self.evolution_status.verified_count,
            "rejected_count": self.evolution_status.rejected_count,
        }
