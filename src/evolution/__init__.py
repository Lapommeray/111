from src.evolution.architecture_guard import ArchitectureGuard
from src.evolution.code_generator import CodeGenerator
from src.evolution.duplication_audit import DuplicationAudit
from src.evolution.evolution_registry import EvolutionRegistry
from src.evolution.gap_discovery import GapDiscovery
from src.evolution.promoter import Promoter
from src.evolution.self_inspector import SelfInspector
from src.evolution.verifier import Verifier
from src.evolution.knowledge_expansion_orchestrator import (
    KnowledgeExpansionOrchestrator,
    run_knowledge_expansion_phase_a,
)
from src.evolution.experimental_module_spec_flow import run_knowledge_expansion_phase_b
from src.evolution.experimental_module_spec_flow import (
    generate_sandbox_judgments,
    load_sandbox_module_artifacts,
    run_knowledge_expansion_phase_c,
    run_knowledge_expansion_phase_d,
)

__all__ = [
    "ArchitectureGuard",
    "CodeGenerator",
    "DuplicationAudit",
    "EvolutionRegistry",
    "GapDiscovery",
    "Promoter",
    "SelfInspector",
    "Verifier",
    "KnowledgeExpansionOrchestrator",
    "run_knowledge_expansion_phase_a",
    "run_knowledge_expansion_phase_b",
    "run_knowledge_expansion_phase_c",
    "run_knowledge_expansion_phase_d",
    "load_sandbox_module_artifacts",
    "generate_sandbox_judgments",
]
