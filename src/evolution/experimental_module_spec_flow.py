from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from src.learning.live_feedback import process_live_trade_feedback
from src.learning.self_evolving_indicator_layer import run_self_evolving_indicator_layer
from src.utils import read_json_safe, write_json_atomic

_SPREAD_RATIO_ON_GOVERNED_REFUSAL = 2.2
_SLIPPAGE_RATIO_ON_GOVERNED_ROLLBACK = 1.8
_DEFAULT_EVOLUTION_PARAMETERS = {
    "promotion_threshold": 0.6,
    "quarantine_strictness": 0.55,
    "mutation_rate": 0.5,
    "exploration_vs_stability_balance": 0.5,
}


def _safe_candidate_filename(candidate_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in candidate_id.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "candidate_unknown"


def generate_experimental_module_specs(
    validated_knowledge_registry_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = read_json_safe(validated_knowledge_registry_path, default={"validated_knowledge": []})
    if not isinstance(payload, dict):
        payload = {"validated_knowledge": []}

    validated_items = payload.get("validated_knowledge", [])
    if not isinstance(validated_items, list):
        validated_items = []

    deduplicated_by_candidate: dict[str, dict[str, Any]] = {}
    for item in validated_items:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_by_candidate[candidate_id] = item

    generated_paths: list[str] = []
    generated_at = datetime.now(tz=timezone.utc).isoformat()
    used_filenames: set[str] = set()
    for candidate_id, item in sorted(deduplicated_by_candidate.items(), key=lambda pair: pair[0]):
        evidence_history = item.get("evidence_history", [])
        if not isinstance(evidence_history, list):
            evidence_history = []

        entry = {
            "candidate_id": candidate_id,
            "truth_class": str(item.get("truth_class", "meta-intelligence")),
            "truth_class_rationale": str(
                item.get(
                    "truth_class_rationale",
                    "Derived from validated replay/governance knowledge entry.",
                )
            ),
            "usefulness_scope": str(item.get("usefulness_scope", "conditional")),
            "hypothesis_statement": str(item.get("statement", item.get("hypothesis_statement", ""))),
            "evidence_summary": {
                "evidence_points": len(evidence_history),
                "latest_evidence": evidence_history[-1] if evidence_history else {},
                "decision_reasons": item.get("decision_reasons", []),
            },
            "promotion_status": str(item.get("decision", "HOLD_FOR_MORE_DATA")),
            "spec_version": "1.0",
            "generated_at": generated_at,
        }

        base_name = _safe_candidate_filename(candidate_id)
        target_name = base_name
        if target_name in used_filenames:
            suffix = hashlib.blake2b(candidate_id.encode("utf-8"), digest_size=6).hexdigest()
            target_name = f"{base_name}_{suffix}"
        used_filenames.add(target_name)
        target_path = output_dir / f"{target_name}.json"
        write_json_atomic(target_path, entry)
        generated_paths.append(str(target_path))

    return {
        "experimental_module_specs_dir": str(output_dir),
        "experimental_spec_count": len(generated_paths),
        "experimental_spec_artifacts": generated_paths,
    }


def run_knowledge_expansion_phase_b(root: Path) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_experimental_module_specs(
        validated_knowledge_registry_path=knowledge_root / "validated_knowledge_registry.json",
        output_dir=knowledge_root / "experimental_module_specs",
    )


def generate_sandbox_module_artifacts(
    experimental_specs_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: list[str] = []
    default_generation_timestamp = datetime.now(tz=timezone.utc).isoformat()

    deduplicated_by_candidate: dict[str, tuple[Path, dict[str, Any]]] = {}
    for spec_path in sorted(experimental_specs_dir.glob("*.json")):
        payload = read_json_safe(spec_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_by_candidate[candidate_id] = (spec_path, payload)

    used_filenames: set[str] = set()
    for candidate_id, (spec_path, payload) in sorted(deduplicated_by_candidate.items(), key=lambda pair: pair[0]):
        module_name = f"sandbox_{_safe_candidate_filename(candidate_id)}"
        target_name = _safe_candidate_filename(candidate_id)
        if target_name in used_filenames:
            suffix = hashlib.blake2b(candidate_id.encode("utf-8"), digest_size=6).hexdigest()
            target_name = f"{target_name}_{suffix}"
        used_filenames.add(target_name)
        target_path = output_dir / f"{target_name}.json"
        existing_artifact = read_json_safe(target_path, default={})
        generation_timestamp = (
            str(existing_artifact.get("generation_timestamp", "")).strip()
            if isinstance(existing_artifact, dict)
            else ""
        ) or default_generation_timestamp
        artifact = {
            "candidate_id": candidate_id,
            "module_name": module_name,
            "truth_class": str(payload.get("truth_class", "meta-intelligence")),
            "hypothesis_statement": str(payload.get("hypothesis_statement", payload.get("statement", ""))),
            "evidence_summary": payload.get("evidence_summary", {}),
            "source_spec_path": str(spec_path),
            "generation_timestamp": generation_timestamp,
            "sandbox_status": "replay_only",
            "module_version": "1.0",
        }

        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))

    return {
        "sandbox_modules_dir": str(output_dir),
        "sandbox_module_count": len(generated_paths),
        "sandbox_module_artifacts": generated_paths,
    }


def load_sandbox_module_artifacts(sandbox_modules_dir: Path, mode: str) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "sandbox_enabled": False,
            "sandbox_module_count": 0,
            "sandbox_modules": [],
        }

    discovered: list[dict[str, Any]] = []
    for module_path in sorted(sandbox_modules_dir.glob("*.json")):
        payload = read_json_safe(module_path, default={})
        if isinstance(payload, dict):
            discovered.append(payload)

    return {
        "sandbox_enabled": True,
        "sandbox_module_count": len(discovered),
        "sandbox_modules": discovered,
    }


def run_knowledge_expansion_phase_c(root: Path) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_sandbox_module_artifacts(
        experimental_specs_dir=knowledge_root / "experimental_module_specs",
        output_dir=knowledge_root / "sandbox_modules",
    )


PHASE_D_REJECT = "reject"
PHASE_D_RETAIN_FOR_FURTHER_REPLAY = "retain_for_further_replay"
PHASE_D_PROMOTION_CANDIDATE = "promotion_candidate"
PHASE_D_DECISION_SEQUENCE = (
    PHASE_D_REJECT,
    PHASE_D_RETAIN_FOR_FURTHER_REPLAY,
    PHASE_D_PROMOTION_CANDIDATE,
)
PHASE_D_IMPROVEMENT_EPSILON = 0.05

PHASE_E_REJECTED = "rejected"
PHASE_E_RETAINED_FOR_FURTHER_REPLAY = "retained_for_further_replay"
PHASE_E_PROMOTION_CANDIDATE = "promotion_candidate"
PHASE_E_DECISION_SEQUENCE = (
    PHASE_E_REJECTED,
    PHASE_E_RETAINED_FOR_FURTHER_REPLAY,
    PHASE_E_PROMOTION_CANDIDATE,
)
PHASE_E_GOVERNOR_VERSION = "phase_e_governor_v1"
PHASE_F_BLOCKED = "blocked"
PHASE_F_MANUAL_REVIEW_REQUIRED = "manual_review_required"
PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW = "eligible_for_controlled_execution_review"
PHASE_F_DECISION_SEQUENCE = (
    PHASE_F_BLOCKED,
    PHASE_F_MANUAL_REVIEW_REQUIRED,
    PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW,
)
PHASE_F_GOVERNOR_VERSION = "phase_f_governor_v1"
PHASE_G_HOLD_NON_LIVE = "hold_non_live"
PHASE_G_PAPER_EXECUTION_ONLY = "paper_execution_only"
PHASE_G_CONTROLLED_REVIEW_SIGNAL = "controlled_review_signal"
PHASE_G_DECISION_SEQUENCE = (
    PHASE_G_HOLD_NON_LIVE,
    PHASE_G_PAPER_EXECUTION_ONLY,
    PHASE_G_CONTROLLED_REVIEW_SIGNAL,
)
PHASE_G_GOVERNOR_VERSION = "phase_g_governor_v1"
PHASE_H_BLOCKED_FAIL_SAFE = "blocked_fail_safe"
PHASE_H_BLOCKED_VENUE_UNHEALTHY = "blocked_venue_unhealthy"
PHASE_H_SUPERVISED_NON_LIVE = "supervised_non_live"
PHASE_H_DECISION_SEQUENCE = (
    PHASE_H_BLOCKED_FAIL_SAFE,
    PHASE_H_BLOCKED_VENUE_UNHEALTHY,
    PHASE_H_SUPERVISED_NON_LIVE,
)
PHASE_H_GOVERNOR_VERSION = "phase_h_governor_v1"
PHASE_I_CAPITAL_PRESERVATION_MODE = "capital_preservation_mode"
PHASE_I_CONSTRAINED_NON_LIVE = "constrained_non_live"
PHASE_I_ADAPTIVE_PAPER_ONLY = "adaptive_paper_only"
PHASE_I_DECISION_SEQUENCE = (
    PHASE_I_CAPITAL_PRESERVATION_MODE,
    PHASE_I_CONSTRAINED_NON_LIVE,
    PHASE_I_ADAPTIVE_PAPER_ONLY,
)
PHASE_I_GOVERNOR_VERSION = "phase_i_governor_v1"
PHASE_J_ROLLBACK_IMMEDIATE = "rollback_immediate"
PHASE_J_ROLLBACK_CONTROLLED_NON_LIVE = "rollback_controlled_non_live"
PHASE_J_MONITOR_CONTINUE_PAPER_ONLY = "monitor_continue_paper_only"
PHASE_J_DECISION_SEQUENCE = (
    PHASE_J_ROLLBACK_IMMEDIATE,
    PHASE_J_ROLLBACK_CONTROLLED_NON_LIVE,
    PHASE_J_MONITOR_CONTINUE_PAPER_ONLY,
)
PHASE_J_GOVERNOR_VERSION = "phase_j_governor_v1"
PHASE_K_MEMORY_VERSION = "phase_k_memory_v1"
PHASE_L_DISCOVERY_VERSION = "phase_l_discovery_v1"
PHASE_M_EXPANSION_VERSION = "phase_m_expansion_v1"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _summary_score(summary: Any) -> float:
    if not isinstance(summary, dict):
        return 0.0
    score_keys = (
        "score",
        "module_score",
        "baseline_score",
        "alignment_ratio",
        "confidence",
        "evidence_points",
    )
    for key in score_keys:
        if key in summary:
            return _to_float(summary.get(key))
    evidence_summary = summary.get("evidence_summary")
    if isinstance(evidence_summary, dict):
        return _summary_score(evidence_summary)
    return 0.0


def _phase_d_decision_from_delta(delta: float) -> tuple[str, str, str]:
    if delta > PHASE_D_IMPROVEMENT_EPSILON:
        return (
            PHASE_D_PROMOTION_CANDIDATE,
            "Sandbox module improved replay outcome versus baseline.",
            "promotion_candidate",
        )
    if delta < -PHASE_D_IMPROVEMENT_EPSILON:
        return (
            PHASE_D_REJECT,
            "Sandbox module regressed replay outcome versus baseline.",
            "not_eligible",
        )
    return (
        PHASE_D_RETAIN_FOR_FURTHER_REPLAY,
        "Sandbox module had no meaningful replay effect versus baseline.",
        "replay_only",
    )


def _phase_d_effect_from_delta(delta: float) -> str:
    if delta > PHASE_D_IMPROVEMENT_EPSILON:
        return "improved"
    if delta < -PHASE_D_IMPROVEMENT_EPSILON:
        return "regressed"
    return "no_meaningful_effect"


def generate_sandbox_judgments(
    sandbox_modules_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    baseline_summary: dict[str, Any] | None = None,
    replay_scope: str = "full_replay",
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "sandbox_enabled": False,
            "sandbox_module_count": 0,
            "sandbox_judgment_count": 0,
            "sandbox_judgments_dir": str(output_dir),
            "sandbox_judgments": [],
            "decision_classes": list(PHASE_D_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    baseline = baseline_summary if isinstance(baseline_summary, dict) else {}
    baseline_score = _summary_score(baseline)

    deduplicated_by_candidate: dict[str, dict[str, Any]] = {}
    for module_path in sorted(sandbox_modules_dir.glob("*.json")):
        payload = read_json_safe(module_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_by_candidate[candidate_id] = payload

    judgment_paths: list[str] = []
    default_judgment_timestamp = datetime.now(tz=timezone.utc).isoformat()
    used_filenames: set[str] = set()
    for candidate_id, module_payload in sorted(deduplicated_by_candidate.items(), key=lambda pair: pair[0]):
        module_name = str(module_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}"))
        module_score = _summary_score(module_payload)
        score_delta = module_score - baseline_score
        effect = _phase_d_effect_from_delta(score_delta)
        decision, decision_reason, promotion_status = _phase_d_decision_from_delta(score_delta)
        target_name = _safe_candidate_filename(candidate_id)
        if target_name in used_filenames:
            suffix = hashlib.blake2b(candidate_id.encode("utf-8"), digest_size=6).hexdigest()
            target_name = f"{target_name}_{suffix}"
        used_filenames.add(target_name)
        target_path = output_dir / f"{target_name}.json"
        existing_artifact = read_json_safe(target_path, default={})
        judgment_timestamp = (
            str(existing_artifact.get("judgment_timestamp", "")).strip()
            if isinstance(existing_artifact, dict)
            else ""
        ) or default_judgment_timestamp

        artifact = {
            "candidate_id": candidate_id,
            "module_name": module_name,
            "truth_class": str(module_payload.get("truth_class", "meta-intelligence")),
            "judgment_timestamp": judgment_timestamp,
            "replay_scope": replay_scope,
            "baseline_summary": {
                "score": baseline_score,
                "source": baseline,
            },
            "module_summary": {
                "score": module_score,
                "source": module_payload,
            },
            "comparison_summary": {
                "score_delta": round(score_delta, 6),
                "effect": effect,
            },
            "decision": decision,
            "decision_reason": decision_reason,
            "promotion_status": promotion_status,
        }

        write_json_atomic(target_path, artifact)
        judgment_paths.append(str(target_path))

    return {
        "sandbox_enabled": True,
        "sandbox_module_count": len(deduplicated_by_candidate),
        "sandbox_judgment_count": len(judgment_paths),
        "sandbox_judgments_dir": str(output_dir),
        "sandbox_judgments": judgment_paths,
        "decision_classes": list(PHASE_D_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_d(
    root: Path,
    *,
    mode: str,
    baseline_summary: dict[str, Any] | None = None,
    replay_scope: str = "full_replay",
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_sandbox_judgments(
        sandbox_modules_dir=knowledge_root / "sandbox_modules",
        output_dir=knowledge_root / "sandbox_judgments",
        mode=mode,
        baseline_summary=baseline_summary,
        replay_scope=replay_scope,
    )


def _phase_e_decision_from_judgment(judgment_payload: dict[str, Any]) -> tuple[str, str, str, bool]:
    phase_d_decision = str(judgment_payload.get("decision", "")).strip()
    phase_d_reason = str(judgment_payload.get("decision_reason", "")).strip()
    if phase_d_decision == PHASE_D_REJECT:
        return (
            PHASE_E_REJECTED,
            phase_d_reason or "Sandbox judgment rejected candidate for replay governance.",
            "rejected_non_live",
            False,
        )
    if phase_d_decision == PHASE_D_PROMOTION_CANDIDATE:
        return (
            PHASE_E_PROMOTION_CANDIDATE,
            phase_d_reason or "Sandbox judgment marked candidate for controlled promotion consideration.",
            "non_live_candidate",
            True,
        )
    return (
        PHASE_E_RETAINED_FOR_FURTHER_REPLAY,
        phase_d_reason or "Sandbox judgment retained candidate for further replay validation.",
        "replay_only",
        True,
    )


def generate_promotion_governance_artifacts(
    sandbox_judgments_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    registry_path: Path,
    governor_version: str = PHASE_E_GOVERNOR_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "governance_enabled": False,
            "governance_artifact_count": 0,
            "promotion_governance_dir": str(output_dir),
            "promotion_governance_artifacts": [],
            "promotion_registry_path": str(registry_path),
            "decision_classes": list(PHASE_E_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    deduplicated_judgments: dict[str, tuple[Path, dict[str, Any]]] = {}
    for judgment_path in sorted(sandbox_judgments_dir.glob("*.json")):
        payload = read_json_safe(judgment_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_judgments[candidate_id] = (judgment_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    for candidate_id, (judgment_path, judgment_payload) in sorted(deduplicated_judgments.items(), key=lambda pair: pair[0]):
        governance_decision, governance_reason, promotion_status, replay_revalidation_required = (
            _phase_e_decision_from_judgment(judgment_payload)
        )
        comparison_summary = judgment_payload.get("comparison_summary", {})
        judgment_summary = {
            "phase_d_decision": str(judgment_payload.get("decision", "")),
            "phase_d_effect": str(comparison_summary.get("effect", "")) if isinstance(comparison_summary, dict) else "",
            "phase_d_score_delta": (
                comparison_summary.get("score_delta", 0.0) if isinstance(comparison_summary, dict) else 0.0
            ),
        }
        artifact = {
            "candidate_id": candidate_id,
            "module_name": str(judgment_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}")),
            "truth_class": str(judgment_payload.get("truth_class", "meta-intelligence")),
            "governance_timestamp": str(
                judgment_payload.get("judgment_timestamp", datetime.now(tz=timezone.utc).isoformat())
            ),
            "judgment_summary": judgment_summary,
            "governance_decision": governance_decision,
            "governance_reason": governance_reason,
            "promotion_status": promotion_status,
            "replay_revalidation_required": replay_revalidation_required,
            "source_judgment_path": str(judgment_path),
            "governor_version": governor_version,
        }

        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"governance_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"governance_records": []}
    records = existing_registry.get("governance_records", [])
    if not isinstance(records, list):
        records = []

    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)

    registry_payload = {
        "governor_version": governor_version,
        "decision_classes": list(PHASE_E_DECISION_SEQUENCE),
        "governance_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "governance_enabled": True,
        "governance_artifact_count": len(generated_paths),
        "promotion_governance_dir": str(output_dir),
        "promotion_governance_artifacts": generated_paths,
        "promotion_registry_path": str(registry_path),
        "decision_classes": list(PHASE_E_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_e(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    promotion_governance_dir = knowledge_root / "promotion_governance"
    return generate_promotion_governance_artifacts(
        sandbox_judgments_dir=knowledge_root / "sandbox_judgments",
        output_dir=promotion_governance_dir,
        mode=mode,
        registry_path=promotion_governance_dir / "governed_promotion_registry.json",
    )


def _phase_f_execution_decision_from_governance(governance_payload: dict[str, Any]) -> tuple[str, str, str]:
    governance_decision = str(governance_payload.get("governance_decision", "")).strip()
    governance_reason = str(governance_payload.get("governance_reason", "")).strip()
    if governance_decision == PHASE_E_REJECTED:
        return (
            PHASE_F_BLOCKED,
            "blocked_non_live",
            governance_reason or "Promotion governance rejected candidate.",
        )
    if governance_decision == PHASE_E_PROMOTION_CANDIDATE:
        return (
            PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW,
            "pending_controlled_execution_review",
            governance_reason or "Candidate eligible for controlled execution review.",
        )
    return (
        PHASE_F_MANUAL_REVIEW_REQUIRED,
        "pending_manual_review",
        governance_reason or "Manual review required before controlled execution review.",
    )


def generate_execution_governance_artifacts(
    promotion_governance_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    registry_path: Path,
    governor_version: str = PHASE_F_GOVERNOR_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "execution_governance_enabled": False,
            "execution_governance_artifact_count": 0,
            "execution_governance_dir": str(output_dir),
            "execution_governance_artifacts": [],
            "controlled_execution_registry_path": str(registry_path),
            "decision_classes": list(PHASE_F_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    deduplicated_governance_records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for governance_path in sorted(promotion_governance_dir.glob("*.json")):
        payload = read_json_safe(governance_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_governance_records[candidate_id] = (governance_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    for candidate_id, (governance_path, governance_payload) in sorted(
        deduplicated_governance_records.items(),
        key=lambda pair: pair[0],
    ):
        execution_decision, execution_status, execution_reason = _phase_f_execution_decision_from_governance(
            governance_payload
        )
        execution_governance_timestamp = str(governance_payload.get("governance_timestamp", "")).strip()
        if not execution_governance_timestamp:
            execution_governance_timestamp = datetime.now(tz=timezone.utc).isoformat()
        artifact = {
            "candidate_id": candidate_id,
            "module_name": str(governance_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}")),
            "truth_class": str(governance_payload.get("truth_class", "meta-intelligence")),
            "governance_source_path": str(governance_path),
            "execution_governance_timestamp": execution_governance_timestamp,
            "governance_decision": str(governance_payload.get("governance_decision", "")),
            "execution_decision": execution_decision,
            "execution_reason": execution_reason,
            "execution_status": execution_status,
            "manual_approval_required": True,
            "live_activation_allowed": False,
            "risk_constraints": {
                "live_execution_blocked": True,
                "auto_live_activation": False,
                "controlled_execution_review_required": True,
            },
            "governor_version": governor_version,
        }

        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"execution_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"execution_records": []}
    records = existing_registry.get("execution_records", [])
    if not isinstance(records, list):
        records = []

    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)

    registry_payload = {
        "governor_version": governor_version,
        "decision_classes": list(PHASE_F_DECISION_SEQUENCE),
        "execution_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "execution_governance_enabled": True,
        "execution_governance_artifact_count": len(generated_paths),
        "execution_governance_dir": str(output_dir),
        "execution_governance_artifacts": generated_paths,
        "controlled_execution_registry_path": str(registry_path),
        "decision_classes": list(PHASE_F_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_f(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    execution_governance_dir = knowledge_root / "execution_governance"
    return generate_execution_governance_artifacts(
        promotion_governance_dir=knowledge_root / "promotion_governance",
        output_dir=execution_governance_dir,
        mode=mode,
        registry_path=execution_governance_dir / "controlled_execution_registry.json",
    )


def _phase_g_decision_from_inputs(
    execution_payload: dict[str, Any],
    market_state: dict[str, Any],
) -> tuple[str, str, str]:
    execution_decision = str(execution_payload.get("execution_decision", "")).strip()
    volatility = _to_float(market_state.get("volatility", 0.0))
    trend = str(market_state.get("trend", "neutral")).strip().lower()
    if execution_decision == PHASE_F_BLOCKED:
        return (
            PHASE_G_HOLD_NON_LIVE,
            "blocked_non_live",
            "Execution governance blocked candidate; remain non-live.",
        )
    if execution_decision == PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW and volatility <= 0.06:
        return (
            PHASE_G_CONTROLLED_REVIEW_SIGNAL,
            "pending_controlled_decision_review",
            f"Controlled review signal produced from recent market state (trend={trend}, volatility={volatility:.4f}).",
        )
    return (
        PHASE_G_PAPER_EXECUTION_ONLY,
        "paper_execution_non_live",
        "Candidate restricted to paper execution; controlled review conditions not satisfied.",
    )


def generate_realtime_decision_orchestrator_artifacts(
    execution_governance_dir: Path,
    market_data_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    market_state_memory_path: Path,
    registry_path: Path,
    governor_version: str = PHASE_G_GOVERNOR_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "decision_orchestration_enabled": False,
            "decision_artifact_count": 0,
            "decision_orchestrator_dir": str(output_dir),
            "decision_artifacts": [],
            "decision_registry_path": str(registry_path),
            "market_state_memory_path": str(market_state_memory_path),
            "decision_classes": list(PHASE_G_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    market_data_dir.mkdir(parents=True, exist_ok=True)

    existing_market_memory = read_json_safe(market_state_memory_path, default={"state_history": []})
    if not isinstance(existing_market_memory, dict):
        existing_market_memory = {"state_history": []}
    state_history = existing_market_memory.get("state_history", [])
    if not isinstance(state_history, list):
        state_history = []
    known_update_ids = {
        str(item.get("update_id", "")).strip()
        for item in state_history
        if isinstance(item, dict) and str(item.get("update_id", "")).strip()
    }

    market_state = existing_market_memory.get("latest_market_state", {})
    if not isinstance(market_state, dict):
        market_state = {}
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for market_path in sorted(market_data_dir.glob("*.json")):
        market_payload = read_json_safe(market_path, default={})
        if not isinstance(market_payload, dict):
            continue
        market_timestamp = str(market_payload.get("timestamp", "")).strip() or now_iso
        symbol = str(market_payload.get("symbol", "UNKNOWN")).strip() or "UNKNOWN"
        update_id = hashlib.blake2b(
            f"{market_path.name}|{market_timestamp}|{symbol}".encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        if update_id in known_update_ids:
            continue
        market_state = {
            "timestamp": market_timestamp,
            "symbol": symbol,
            "trend": str(market_payload.get("trend", "neutral")).strip().lower() or "neutral",
            "volatility": round(_to_float(market_payload.get("volatility", 0.0)), 6),
            "liquidity_state": str(market_payload.get("liquidity_state", "unknown")).strip() or "unknown",
        }
        state_history.append(
            {
                "update_id": update_id,
                "source_path": str(market_path),
                **market_state,
            }
        )
        known_update_ids.add(update_id)

    if not market_state:
        market_state = {
            "timestamp": now_iso,
            "symbol": "UNKNOWN",
            "trend": "neutral",
            "volatility": 0.0,
            "liquidity_state": "unknown",
        }
        fallback_id = hashlib.blake2b(f"default|{now_iso}".encode("utf-8"), digest_size=8).hexdigest()
        if fallback_id not in known_update_ids:
            state_history.append({"update_id": fallback_id, "source_path": "default", **market_state})

    market_state_memory_payload = {
        "governor_version": governor_version,
        "latest_market_state": market_state,
        "state_history": state_history,
    }
    write_json_atomic(market_state_memory_path, market_state_memory_payload)

    deduplicated_execution_records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for execution_path in sorted(execution_governance_dir.glob("*.json")):
        payload = read_json_safe(execution_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_execution_records[candidate_id] = (execution_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    for candidate_id, (execution_path, execution_payload) in sorted(
        deduplicated_execution_records.items(),
        key=lambda pair: pair[0],
    ):
        decision, decision_status, decision_reason = _phase_g_decision_from_inputs(execution_payload, market_state)
        artifact = {
            "candidate_id": candidate_id,
            "module_name": str(execution_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}")),
            "truth_class": str(execution_payload.get("truth_class", "meta-intelligence")),
            "execution_source_path": str(execution_path),
            "decision_timestamp": str(market_state.get("timestamp", now_iso)),
            "execution_decision": str(execution_payload.get("execution_decision", "")),
            "orchestrator_decision": decision,
            "decision_reason": decision_reason,
            "decision_status": decision_status,
            "market_state_snapshot": market_state,
            "market_state_memory_path": str(market_state_memory_path),
            "manual_approval_required": True,
            "live_activation_allowed": False,
            "risk_constraints": {
                "live_execution_blocked": True,
                "auto_live_activation": False,
                "controlled_execution_review_required": True,
                "paper_execution_only": decision != PHASE_G_CONTROLLED_REVIEW_SIGNAL,
            },
            "governor_version": governor_version,
        }
        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"decision_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"decision_records": []}
    records = existing_registry.get("decision_records", [])
    if not isinstance(records, list):
        records = []

    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)

    registry_payload = {
        "governor_version": governor_version,
        "decision_classes": list(PHASE_G_DECISION_SEQUENCE),
        "decision_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "decision_orchestration_enabled": True,
        "decision_artifact_count": len(generated_paths),
        "decision_orchestrator_dir": str(output_dir),
        "decision_artifacts": generated_paths,
        "decision_registry_path": str(registry_path),
        "market_state_memory_path": str(market_state_memory_path),
        "decision_classes": list(PHASE_G_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_g(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_realtime_decision_orchestrator_artifacts(
        execution_governance_dir=knowledge_root / "execution_governance",
        market_data_dir=knowledge_root / "market_data_feed",
        output_dir=knowledge_root / "decision_orchestrator",
        mode=mode,
        market_state_memory_path=knowledge_root / "market_state_memory.json",
        registry_path=(knowledge_root / "decision_orchestrator" / "controlled_decision_registry.json"),
    )


def _phase_h_supervision_decision(
    orchestrator_payload: dict[str, Any],
    interface_state: dict[str, Any],
) -> tuple[str, str, str, str]:
    fail_safe_triggered = bool(interface_state.get("fail_safe_triggered", False))
    venue_status = str(interface_state.get("venue_status", "unknown")).strip().lower()
    broker_connected = bool(interface_state.get("broker_connected", False))
    exchange_connected = bool(interface_state.get("exchange_connected", False))
    readiness = "not_ready"
    if broker_connected and exchange_connected and venue_status == "healthy" and not fail_safe_triggered:
        readiness = "ready_for_supervised_review"
    elif broker_connected and exchange_connected and venue_status in {"healthy", "degraded"} and not fail_safe_triggered:
        readiness = "restricted_supervised_review"

    if fail_safe_triggered:
        return (
            PHASE_H_BLOCKED_FAIL_SAFE,
            readiness,
            "fail_safe_triggered",
            "Fail-safe is triggered; broker/exchange execution remains blocked.",
        )
    if venue_status not in {"healthy", "degraded"}:
        return (
            PHASE_H_BLOCKED_VENUE_UNHEALTHY,
            readiness,
            f"venue_{venue_status or 'unknown'}",
            "Venue health is not acceptable for supervised review.",
        )
    _ = str(orchestrator_payload.get("orchestrator_decision", "")).strip()
    return (
        PHASE_H_SUPERVISED_NON_LIVE,
        readiness,
        "supervised_non_live",
        "Broker/exchange supervision satisfied for non-live controlled workflow.",
    )


def generate_broker_exchange_supervision_artifacts(
    decision_orchestrator_dir: Path,
    interface_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    interface_state_memory_path: Path,
    registry_path: Path,
    governor_version: str = PHASE_H_GOVERNOR_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "broker_exchange_supervision_enabled": False,
            "supervision_artifact_count": 0,
            "supervision_dir": str(output_dir),
            "supervision_artifacts": [],
            "supervision_registry_path": str(registry_path),
            "interface_state_memory_path": str(interface_state_memory_path),
            "decision_classes": list(PHASE_H_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    interface_dir.mkdir(parents=True, exist_ok=True)
    existing_memory = read_json_safe(interface_state_memory_path, default={"state_history": []})
    if not isinstance(existing_memory, dict):
        existing_memory = {"state_history": []}
    state_history = existing_memory.get("state_history", [])
    if not isinstance(state_history, list):
        state_history = []
    known_update_ids = {
        str(item.get("update_id", "")).strip()
        for item in state_history
        if isinstance(item, dict) and str(item.get("update_id", "")).strip()
    }

    interface_state = existing_memory.get("latest_interface_state", {})
    if not isinstance(interface_state, dict):
        interface_state = {}
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for interface_path in sorted(interface_dir.glob("*.json")):
        interface_payload = read_json_safe(interface_path, default={})
        if not isinstance(interface_payload, dict):
            continue
        timestamp = str(interface_payload.get("timestamp", "")).strip() or now_iso
        broker_name = str(interface_payload.get("broker_name", "unknown")).strip() or "unknown"
        exchange_name = str(interface_payload.get("exchange_name", "unknown")).strip() or "unknown"
        update_id = hashlib.blake2b(
            f"{interface_path.name}|{timestamp}|{broker_name}|{exchange_name}".encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        if update_id in known_update_ids:
            continue
        interface_state = {
            "timestamp": timestamp,
            "broker_name": broker_name,
            "exchange_name": exchange_name,
            "broker_connected": bool(interface_payload.get("broker_connected", False)),
            "exchange_connected": bool(interface_payload.get("exchange_connected", False)),
            "venue_status": str(interface_payload.get("venue_status", "unknown")).strip().lower() or "unknown",
            "latency_ms": round(_to_float(interface_payload.get("latency_ms", 0.0)), 3),
            "fail_safe_triggered": bool(interface_payload.get("fail_safe_triggered", False)),
        }
        state_history.append({"update_id": update_id, "source_path": str(interface_path), **interface_state})
        known_update_ids.add(update_id)

    if not interface_state:
        interface_state = {
            "timestamp": now_iso,
            "broker_name": "unknown",
            "exchange_name": "unknown",
            "broker_connected": False,
            "exchange_connected": False,
            "venue_status": "unknown",
            "latency_ms": 0.0,
            "fail_safe_triggered": True,
        }
        fallback_id = hashlib.blake2b(f"default|{now_iso}".encode("utf-8"), digest_size=8).hexdigest()
        if fallback_id not in known_update_ids:
            state_history.append({"update_id": fallback_id, "source_path": "default", **interface_state})

    memory_payload = {
        "governor_version": governor_version,
        "latest_interface_state": interface_state,
        "state_history": state_history,
    }
    write_json_atomic(interface_state_memory_path, memory_payload)

    deduplicated_orchestrator_records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for orchestrator_path in sorted(decision_orchestrator_dir.glob("*.json")):
        payload = read_json_safe(orchestrator_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_orchestrator_records[candidate_id] = (orchestrator_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    for candidate_id, (orchestrator_path, orchestrator_payload) in sorted(
        deduplicated_orchestrator_records.items(),
        key=lambda pair: pair[0],
    ):
        supervision_decision, readiness, fail_safe_status, supervision_reason = _phase_h_supervision_decision(
            orchestrator_payload,
            interface_state,
        )
        venue_health = str(interface_state.get("venue_status", "unknown")).strip().lower() or "unknown"
        artifact = {
            "candidate_id": candidate_id,
            "module_name": str(orchestrator_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}")),
            "truth_class": str(orchestrator_payload.get("truth_class", "meta-intelligence")),
            "orchestrator_source_path": str(orchestrator_path),
            "supervision_timestamp": str(interface_state.get("timestamp", now_iso)),
            "orchestrator_decision": str(orchestrator_payload.get("orchestrator_decision", "")),
            "supervision_decision": supervision_decision,
            "supervision_reason": supervision_reason,
            "execution_readiness": readiness,
            "venue_health": venue_health,
            "fail_safe_status": fail_safe_status,
            "interface_state_snapshot": interface_state,
            "interface_state_memory_path": str(interface_state_memory_path),
            "manual_approval_required": True,
            "live_activation_allowed": False,
            "risk_constraints": {
                "live_execution_blocked": True,
                "auto_live_activation": False,
                "broker_exchange_supervised_only": True,
                "fail_safe_required": True,
            },
            "governor_version": governor_version,
        }
        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"supervision_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"supervision_records": []}
    records = existing_registry.get("supervision_records", [])
    if not isinstance(records, list):
        records = []

    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)

    registry_payload = {
        "governor_version": governor_version,
        "decision_classes": list(PHASE_H_DECISION_SEQUENCE),
        "supervision_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "broker_exchange_supervision_enabled": True,
        "supervision_artifact_count": len(generated_paths),
        "supervision_dir": str(output_dir),
        "supervision_artifacts": generated_paths,
        "supervision_registry_path": str(registry_path),
        "interface_state_memory_path": str(interface_state_memory_path),
        "decision_classes": list(PHASE_H_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_h(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_broker_exchange_supervision_artifacts(
        decision_orchestrator_dir=knowledge_root / "decision_orchestrator",
        interface_dir=knowledge_root / "broker_exchange_interfaces",
        output_dir=knowledge_root / "execution_supervision",
        mode=mode,
        interface_state_memory_path=knowledge_root / "broker_exchange_state_memory.json",
        registry_path=(knowledge_root / "execution_supervision" / "broker_exchange_supervision_registry.json"),
    )


def _phase_i_portfolio_decision(
    supervision_payload: dict[str, Any],
    portfolio_state: dict[str, Any],
) -> tuple[str, str, str, str, str, str]:
    supervision_decision = str(supervision_payload.get("supervision_decision", "")).strip()
    fail_safe_status = str(supervision_payload.get("fail_safe_status", "")).strip()
    execution_readiness = str(supervision_payload.get("execution_readiness", "not_ready")).strip() or "not_ready"

    open_exposure_pct = max(0.0, _to_float(portfolio_state.get("open_exposure_pct", 0.0)))
    max_exposure_pct = max(0.0, _to_float(portfolio_state.get("max_exposure_pct", 0.35)))
    suggested_position_size_pct = max(0.0, _to_float(portfolio_state.get("suggested_position_size_pct", 0.0)))
    max_position_size_pct = max(0.0, _to_float(portfolio_state.get("max_position_size_pct", 0.03)))
    max_drawdown_pct = max(0.0, _to_float(portfolio_state.get("max_drawdown_pct", 8.0)))
    capital_budget_pct = max(0.0, _to_float(portfolio_state.get("capital_budget_pct", 0.25)))
    capital_allocated_pct = max(0.0, _to_float(portfolio_state.get("capital_allocated_pct", 0.0)))
    equity = max(0.0, _to_float(portfolio_state.get("equity", 0.0)))
    peak_equity = max(0.0, _to_float(portfolio_state.get("peak_equity", equity)))

    drawdown_pct = 0.0
    if peak_equity > 0.0 and equity <= peak_equity:
        drawdown_pct = ((peak_equity - equity) / peak_equity) * 100.0

    exposure_within_limits = open_exposure_pct <= max_exposure_pct
    position_sizing_ready = 0.0 < suggested_position_size_pct <= max_position_size_pct
    drawdown_within_limits = drawdown_pct <= max_drawdown_pct
    allocation_disciplined = capital_allocated_pct <= capital_budget_pct

    allocation_state = (
        "over_allocated"
        if capital_allocated_pct > capital_budget_pct
        else "budget_available"
        if capital_allocated_pct < capital_budget_pct
        else "at_budget"
    )
    exposure_state = "within_limit" if exposure_within_limits else "over_limit"
    sizing_state = "ready" if position_sizing_ready else "size_constrained"
    drawdown_state = "within_limit" if drawdown_within_limits else "drawdown_breached"

    if (
        supervision_decision != PHASE_H_SUPERVISED_NON_LIVE
        or fail_safe_status == "fail_safe_triggered"
        or not drawdown_within_limits
        or not allocation_disciplined
    ):
        return (
            PHASE_I_CAPITAL_PRESERVATION_MODE,
            execution_readiness,
            "defensive",
            "Capital preservation activated due to supervision, drawdown, or allocation guardrail breach.",
            allocation_state,
            drawdown_state,
        )
    if not exposure_within_limits or not position_sizing_ready:
        return (
            PHASE_I_CONSTRAINED_NON_LIVE,
            execution_readiness,
            "cautious",
            "Exposure or position-size constraints require constrained non-live allocation.",
            allocation_state,
            drawdown_state,
        )
    return (
        PHASE_I_ADAPTIVE_PAPER_ONLY,
        execution_readiness,
        "adaptive_balanced",
        "Portfolio constraints satisfied; adaptive allocation remains paper-only pending manual approval.",
        allocation_state,
        drawdown_state,
    )


def generate_adaptive_portfolio_risk_artifacts(
    supervision_dir: Path,
    portfolio_state_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    portfolio_state_memory_path: Path,
    registry_path: Path,
    governor_version: str = PHASE_I_GOVERNOR_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "adaptive_portfolio_enabled": False,
            "portfolio_artifact_count": 0,
            "portfolio_governance_dir": str(output_dir),
            "portfolio_artifacts": [],
            "portfolio_registry_path": str(registry_path),
            "portfolio_state_memory_path": str(portfolio_state_memory_path),
            "decision_classes": list(PHASE_I_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    portfolio_state_dir.mkdir(parents=True, exist_ok=True)
    existing_memory = read_json_safe(portfolio_state_memory_path, default={"state_history": []})
    if not isinstance(existing_memory, dict):
        existing_memory = {"state_history": []}
    state_history = existing_memory.get("state_history", [])
    if not isinstance(state_history, list):
        state_history = []
    known_update_ids = {
        str(item.get("update_id", "")).strip()
        for item in state_history
        if isinstance(item, dict) and str(item.get("update_id", "")).strip()
    }

    portfolio_state = existing_memory.get("latest_portfolio_state", {})
    if not isinstance(portfolio_state, dict):
        portfolio_state = {}
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for portfolio_path in sorted(portfolio_state_dir.glob("*.json")):
        portfolio_payload = read_json_safe(portfolio_path, default={})
        if not isinstance(portfolio_payload, dict):
            continue
        timestamp = str(portfolio_payload.get("timestamp", "")).strip() or now_iso
        account_id = str(portfolio_payload.get("account_id", "paper")).strip() or "paper"
        strategy_group = str(portfolio_payload.get("strategy_group", "sandbox")).strip() or "sandbox"
        update_id = hashlib.blake2b(
            f"{portfolio_path.name}|{timestamp}|{account_id}|{strategy_group}".encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        if update_id in known_update_ids:
            continue

        portfolio_state = {
            "timestamp": timestamp,
            "account_id": account_id,
            "strategy_group": strategy_group,
            "equity": round(max(0.0, _to_float(portfolio_payload.get("equity", 0.0))), 6),
            "peak_equity": round(
                max(
                    _to_float(portfolio_payload.get("equity", 0.0)),
                    _to_float(portfolio_payload.get("peak_equity", portfolio_payload.get("equity", 0.0))),
                ),
                6,
            ),
            "open_exposure_pct": round(max(0.0, _to_float(portfolio_payload.get("open_exposure_pct", 0.0))), 6),
            "max_exposure_pct": round(max(0.0, _to_float(portfolio_payload.get("max_exposure_pct", 0.35))), 6),
            "suggested_position_size_pct": round(
                max(0.0, _to_float(portfolio_payload.get("suggested_position_size_pct", 0.0))),
                6,
            ),
            "max_position_size_pct": round(
                max(0.0, _to_float(portfolio_payload.get("max_position_size_pct", 0.03))),
                6,
            ),
            "capital_budget_pct": round(max(0.0, _to_float(portfolio_payload.get("capital_budget_pct", 0.25))), 6),
            "capital_allocated_pct": round(
                max(0.0, _to_float(portfolio_payload.get("capital_allocated_pct", 0.0))),
                6,
            ),
            "max_drawdown_pct": round(max(0.0, _to_float(portfolio_payload.get("max_drawdown_pct", 8.0))), 6),
        }
        state_history.append({"update_id": update_id, "source_path": str(portfolio_path), **portfolio_state})
        known_update_ids.add(update_id)

    if not portfolio_state:
        portfolio_state = {
            "timestamp": now_iso,
            "account_id": "paper",
            "strategy_group": "sandbox",
            "equity": 0.0,
            "peak_equity": 0.0,
            "open_exposure_pct": 0.0,
            "max_exposure_pct": 0.35,
            "suggested_position_size_pct": 0.0,
            "max_position_size_pct": 0.03,
            "capital_budget_pct": 0.25,
            "capital_allocated_pct": 0.0,
            "max_drawdown_pct": 8.0,
        }
        fallback_id = hashlib.blake2b(f"default|{now_iso}".encode("utf-8"), digest_size=8).hexdigest()
        if fallback_id not in known_update_ids:
            state_history.append({"update_id": fallback_id, "source_path": "default", **portfolio_state})

    memory_payload = {
        "governor_version": governor_version,
        "latest_portfolio_state": portfolio_state,
        "state_history": state_history,
    }
    write_json_atomic(portfolio_state_memory_path, memory_payload)

    deduplicated_supervision_records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for supervision_path in sorted(supervision_dir.glob("*.json")):
        payload = read_json_safe(supervision_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_supervision_records[candidate_id] = (supervision_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    for candidate_id, (supervision_path, supervision_payload) in sorted(
        deduplicated_supervision_records.items(),
        key=lambda pair: pair[0],
    ):
        (
            portfolio_decision,
            execution_readiness,
            risk_state,
            decision_reason,
            allocation_state,
            drawdown_state,
        ) = _phase_i_portfolio_decision(
            supervision_payload,
            portfolio_state,
        )
        open_exposure_pct = max(0.0, _to_float(portfolio_state.get("open_exposure_pct", 0.0)))
        max_exposure_pct = max(0.0, _to_float(portfolio_state.get("max_exposure_pct", 0.35)))
        suggested_position_size_pct = max(0.0, _to_float(portfolio_state.get("suggested_position_size_pct", 0.0)))
        max_position_size_pct = max(0.0, _to_float(portfolio_state.get("max_position_size_pct", 0.03)))
        capital_budget_pct = max(0.0, _to_float(portfolio_state.get("capital_budget_pct", 0.25)))
        capital_allocated_pct = max(0.0, _to_float(portfolio_state.get("capital_allocated_pct", 0.0)))
        equity = max(0.0, _to_float(portfolio_state.get("equity", 0.0)))
        peak_equity = max(0.0, _to_float(portfolio_state.get("peak_equity", equity)))
        drawdown_pct = 0.0
        if peak_equity > 0.0 and equity <= peak_equity:
            drawdown_pct = ((peak_equity - equity) / peak_equity) * 100.0

        artifact = {
            "candidate_id": candidate_id,
            "module_name": str(supervision_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}")),
            "truth_class": str(supervision_payload.get("truth_class", "meta-intelligence")),
            "supervision_source_path": str(supervision_path),
            "portfolio_timestamp": str(portfolio_state.get("timestamp", now_iso)),
            "supervision_decision": str(supervision_payload.get("supervision_decision", "")),
            "portfolio_decision": portfolio_decision,
            "decision_reason": decision_reason,
            "execution_readiness": execution_readiness,
            "risk_state": risk_state,
            "allocation_state": allocation_state,
            "exposure_state": "within_limit" if open_exposure_pct <= max_exposure_pct else "over_limit",
            "sizing_state": (
                "ready" if 0.0 < suggested_position_size_pct <= max_position_size_pct else "size_constrained"
            ),
            "drawdown_state": drawdown_state,
            "portfolio_state_snapshot": portfolio_state,
            "portfolio_state_memory_path": str(portfolio_state_memory_path),
            "manual_approval_required": True,
            "live_activation_allowed": False,
            "risk_constraints": {
                "live_execution_blocked": True,
                "auto_live_activation": False,
                "paper_execution_only": True,
                "max_exposure_pct": max_exposure_pct,
                "max_position_size_pct": max_position_size_pct,
                "capital_budget_pct": capital_budget_pct,
                "max_drawdown_pct": max(0.0, _to_float(portfolio_state.get("max_drawdown_pct", 8.0))),
                "current_exposure_pct": open_exposure_pct,
                "current_position_size_pct": suggested_position_size_pct,
                "current_capital_allocated_pct": capital_allocated_pct,
                "drawdown_pct": round(drawdown_pct, 6),
            },
            "governor_version": governor_version,
        }
        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"portfolio_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"portfolio_records": []}
    records = existing_registry.get("portfolio_records", [])
    if not isinstance(records, list):
        records = []

    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)

    registry_payload = {
        "governor_version": governor_version,
        "decision_classes": list(PHASE_I_DECISION_SEQUENCE),
        "portfolio_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "adaptive_portfolio_enabled": True,
        "portfolio_artifact_count": len(generated_paths),
        "portfolio_governance_dir": str(output_dir),
        "portfolio_artifacts": generated_paths,
        "portfolio_registry_path": str(registry_path),
        "portfolio_state_memory_path": str(portfolio_state_memory_path),
        "decision_classes": list(PHASE_I_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_i(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_adaptive_portfolio_risk_artifacts(
        supervision_dir=knowledge_root / "execution_supervision",
        portfolio_state_dir=knowledge_root / "portfolio_risk_inputs",
        output_dir=knowledge_root / "adaptive_portfolio_governance",
        mode=mode,
        portfolio_state_memory_path=knowledge_root / "adaptive_portfolio_state_memory.json",
        registry_path=(knowledge_root / "adaptive_portfolio_governance" / "adaptive_portfolio_registry.json"),
    )


def _phase_j_incident_decision(
    portfolio_payload: dict[str, Any],
    health_state: dict[str, Any],
) -> tuple[str, str, str, str, str]:
    portfolio_decision = str(portfolio_payload.get("portfolio_decision", "")).strip()
    execution_readiness = str(portfolio_payload.get("execution_readiness", "not_ready")).strip() or "not_ready"
    health_score = max(0.0, min(1.0, _to_float(health_state.get("health_score", 1.0), 1.0)))
    failed_checks = max(0, int(_to_float(health_state.get("failed_checks", 0), 0.0)))
    unsafe_condition = bool(health_state.get("unsafe_condition", False))
    rollback_requested = bool(health_state.get("rollback_requested", False))
    incident_signals = health_state.get("incident_signals", [])
    if not isinstance(incident_signals, list):
        incident_signals = []

    if (
        rollback_requested
        or unsafe_condition
        or failed_checks >= 3
        or health_score < 0.4
        or portfolio_decision == PHASE_I_CAPITAL_PRESERVATION_MODE
    ):
        return (
            PHASE_J_ROLLBACK_IMMEDIATE,
            "critical",
            "rollback_required",
            execution_readiness,
            "Critical monitoring condition detected; immediate controlled rollback required while live execution remains blocked.",
        )
    if (
        failed_checks > 0
        or health_score < 0.75
        or bool(incident_signals)
        or portfolio_decision == PHASE_I_CONSTRAINED_NON_LIVE
    ):
        return (
            PHASE_J_ROLLBACK_CONTROLLED_NON_LIVE,
            "warning",
            "degraded_guarded",
            execution_readiness,
            "Degraded monitoring state detected; controlled non-live rollback and incident containment required.",
        )
    return (
        PHASE_J_MONITOR_CONTINUE_PAPER_ONLY,
        "normal",
        "stable_guarded",
        execution_readiness,
        "Health and incident checks are stable; continue paper-only monitoring with governance controls.",
    )


def generate_monitoring_rollback_incident_artifacts(
    portfolio_governance_dir: Path,
    health_state_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    health_state_memory_path: Path,
    registry_path: Path,
    governor_version: str = PHASE_J_GOVERNOR_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "incident_control_enabled": False,
            "incident_artifact_count": 0,
            "incident_control_dir": str(output_dir),
            "incident_artifacts": [],
            "incident_registry_path": str(registry_path),
            "health_state_memory_path": str(health_state_memory_path),
            "decision_classes": list(PHASE_J_DECISION_SEQUENCE),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    health_state_dir.mkdir(parents=True, exist_ok=True)

    existing_memory = read_json_safe(health_state_memory_path, default={"state_history": []})
    if not isinstance(existing_memory, dict):
        existing_memory = {"state_history": []}
    state_history = existing_memory.get("state_history", [])
    if not isinstance(state_history, list):
        state_history = []
    known_update_ids = {
        str(item.get("update_id", "")).strip()
        for item in state_history
        if isinstance(item, dict) and str(item.get("update_id", "")).strip()
    }

    health_state = existing_memory.get("latest_health_state", {})
    if not isinstance(health_state, dict):
        health_state = {}
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for health_path in sorted(health_state_dir.glob("*.json")):
        health_payload = read_json_safe(health_path, default={})
        if not isinstance(health_payload, dict):
            continue
        timestamp = str(health_payload.get("timestamp", "")).strip() or now_iso
        health_score = round(max(0.0, min(1.0, _to_float(health_payload.get("health_score", 1.0), 1.0))), 6)
        failed_checks = max(0, int(_to_float(health_payload.get("failed_checks", 0), 0.0)))
        rollback_requested = bool(health_payload.get("rollback_requested", False))
        update_id = hashlib.blake2b(
            f"{health_path.name}|{timestamp}|{health_score}|{failed_checks}|{rollback_requested}".encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        if update_id in known_update_ids:
            continue
        incident_signals = health_payload.get("incident_signals", [])
        if not isinstance(incident_signals, list):
            incident_signals = []
        incident_count = max(0, int(_to_float(health_payload.get("incident_count", len(incident_signals)), 0.0)))
        health_state = {
            "timestamp": timestamp,
            "health_score": health_score,
            "failed_checks": failed_checks,
            "unsafe_condition": bool(health_payload.get("unsafe_condition", False)),
            "rollback_requested": rollback_requested,
            "incident_signals": [str(signal) for signal in incident_signals],
            "incident_count": incident_count,
            "source_component": str(health_payload.get("source_component", "phase_j_monitor")).strip()
            or "phase_j_monitor",
        }
        state_history.append({"update_id": update_id, "source_path": str(health_path), **health_state})
        known_update_ids.add(update_id)

    if not health_state:
        health_state = {
            "timestamp": now_iso,
            "health_score": 1.0,
            "failed_checks": 0,
            "unsafe_condition": False,
            "rollback_requested": False,
            "incident_signals": [],
            "incident_count": 0,
            "source_component": "phase_j_monitor",
        }
        fallback_id = hashlib.blake2b(f"default|{now_iso}".encode("utf-8"), digest_size=8).hexdigest()
        if fallback_id not in known_update_ids:
            state_history.append({"update_id": fallback_id, "source_path": "default", **health_state})

    memory_payload = {
        "governor_version": governor_version,
        "latest_health_state": health_state,
        "state_history": state_history,
    }
    write_json_atomic(health_state_memory_path, memory_payload)

    deduplicated_portfolio_records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for portfolio_path in sorted(portfolio_governance_dir.glob("*.json")):
        payload = read_json_safe(portfolio_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_portfolio_records[candidate_id] = (portfolio_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    for candidate_id, (portfolio_path, portfolio_payload) in sorted(
        deduplicated_portfolio_records.items(),
        key=lambda pair: pair[0],
    ):
        incident_decision, incident_severity, rollback_status, execution_readiness, decision_reason = (
            _phase_j_incident_decision(portfolio_payload, health_state)
        )
        incident_id = hashlib.blake2b(
            (
                f"{candidate_id}|{health_state.get('timestamp', now_iso)}|"
                f"{incident_decision}|{incident_severity}|{rollback_status}"
            ).encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        artifact = {
            "candidate_id": candidate_id,
            "module_name": str(portfolio_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}")),
            "truth_class": str(portfolio_payload.get("truth_class", "meta-intelligence")),
            "portfolio_source_path": str(portfolio_path),
            "incident_timestamp": str(health_state.get("timestamp", now_iso)),
            "portfolio_decision": str(portfolio_payload.get("portfolio_decision", "")),
            "execution_readiness": execution_readiness,
            "incident_id": incident_id,
            "incident_severity": incident_severity,
            "incident_control_decision": incident_decision,
            "rollback_status": rollback_status,
            "decision_reason": decision_reason,
            "health_state_snapshot": health_state,
            "health_state_memory_path": str(health_state_memory_path),
            "manual_approval_required": True,
            "live_activation_allowed": False,
            "risk_constraints": {
                "live_execution_blocked": True,
                "auto_live_activation": False,
                "paper_execution_only": True,
                "rollback_allowed_non_live": True,
                "incident_severity": incident_severity,
            },
            "governor_version": governor_version,
        }
        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"incident_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"incident_records": []}
    records = existing_registry.get("incident_records", [])
    if not isinstance(records, list):
        records = []
    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)

    registry_payload = {
        "governor_version": governor_version,
        "decision_classes": list(PHASE_J_DECISION_SEQUENCE),
        "incident_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "incident_control_enabled": True,
        "incident_artifact_count": len(generated_paths),
        "incident_control_dir": str(output_dir),
        "incident_artifacts": generated_paths,
        "incident_registry_path": str(registry_path),
        "health_state_memory_path": str(health_state_memory_path),
        "decision_classes": list(PHASE_J_DECISION_SEQUENCE),
    }


def run_knowledge_expansion_phase_j(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_monitoring_rollback_incident_artifacts(
        portfolio_governance_dir=knowledge_root / "adaptive_portfolio_governance",
        health_state_dir=knowledge_root / "system_health_inputs",
        output_dir=knowledge_root / "incident_control_governance",
        mode=mode,
        health_state_memory_path=knowledge_root / "system_health_state_memory.json",
        registry_path=(knowledge_root / "incident_control_governance" / "incident_control_registry.json"),
    )


def generate_long_horizon_memory_artifacts(
    decision_orchestrator_dir: Path,
    portfolio_governance_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    memory_state_path: Path,
    registry_path: Path,
    memory_version: str = PHASE_K_MEMORY_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "long_horizon_memory_enabled": False,
            "long_horizon_memory_count": 0,
            "long_horizon_memory_dir": str(output_dir),
            "long_horizon_memory_artifacts": [],
            "long_horizon_memory_registry_path": str(registry_path),
            "long_horizon_memory_state_path": str(memory_state_path),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    decision_orchestrator_dir.mkdir(parents=True, exist_ok=True)
    portfolio_governance_dir.mkdir(parents=True, exist_ok=True)

    existing_state = read_json_safe(memory_state_path, default={"state_history": []})
    if not isinstance(existing_state, dict):
        existing_state = {"state_history": []}
    state_history = existing_state.get("state_history", [])
    if not isinstance(state_history, list):
        state_history = []
    known_update_ids = {
        str(item.get("update_id", "")).strip()
        for item in state_history
        if isinstance(item, dict) and str(item.get("update_id", "")).strip()
    }

    phase_g_by_candidate: dict[str, tuple[Path, dict[str, Any]]] = {}
    for decision_path in sorted(decision_orchestrator_dir.glob("*.json")):
        payload = read_json_safe(decision_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        phase_g_by_candidate[candidate_id] = (decision_path, payload)

    phase_i_by_candidate: dict[str, tuple[Path, dict[str, Any]]] = {}
    for portfolio_path in sorted(portfolio_governance_dir.glob("*.json")):
        payload = read_json_safe(portfolio_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        phase_i_by_candidate[candidate_id] = (portfolio_path, payload)

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for candidate_id in sorted(set(phase_g_by_candidate) | set(phase_i_by_candidate)):
        decision_path, decision_payload = phase_g_by_candidate.get(candidate_id, (Path(""), {}))
        portfolio_path, portfolio_payload = phase_i_by_candidate.get(candidate_id, (Path(""), {}))
        if not isinstance(decision_payload, dict):
            decision_payload = {}
        if not isinstance(portfolio_payload, dict):
            portfolio_payload = {}

        module_name = str(
            portfolio_payload.get(
                "module_name",
                decision_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}"),
            )
        )
        decision_timestamp = str(decision_payload.get("decision_timestamp", "")).strip()
        portfolio_timestamp = str(portfolio_payload.get("portfolio_timestamp", "")).strip()
        memory_timestamp = portfolio_timestamp or decision_timestamp or now_iso
        phase_g_decision = str(decision_payload.get("orchestrator_decision", "")).strip()
        phase_i_decision = str(portfolio_payload.get("portfolio_decision", "")).strip()
        performance_snapshot = portfolio_payload.get("portfolio_state_snapshot", {})
        if not isinstance(performance_snapshot, dict):
            performance_snapshot = {}
        historical_market_state_summary = decision_payload.get("market_state_snapshot", {})
        if not isinstance(historical_market_state_summary, dict):
            historical_market_state_summary = {}
        if not historical_market_state_summary:
            historical_market_state_summary = {
                "regime_state": str(decision_payload.get("regime_state", "unknown")),
                "volatility_state": str(decision_payload.get("volatility_state", "unknown")),
                "liquidity_state": str(decision_payload.get("liquidity_state", "unknown")),
                "session_state": str(decision_payload.get("session_state", "unknown")),
            }

        artifact = {
            "candidate_id": candidate_id,
            "module_name": module_name,
            "time_horizon_window": "long_horizon_90d",
            "historical_market_state_summary": historical_market_state_summary,
            "decision_outcome_history": {
                "phase_g_orchestrator_decision": phase_g_decision,
                "phase_i_portfolio_decision": phase_i_decision,
                "phase_g_execution_readiness": str(decision_payload.get("execution_readiness", "not_ready")),
                "phase_i_execution_readiness": str(portfolio_payload.get("execution_readiness", "not_ready")),
                "phase_i_risk_state": str(portfolio_payload.get("risk_state", "unknown")),
                "phase_i_drawdown_state": str(portfolio_payload.get("drawdown_state", "unknown")),
            },
            "performance_snapshot": {
                "equity": _to_float(performance_snapshot.get("equity", 0.0)),
                "peak_equity": _to_float(performance_snapshot.get("peak_equity", 0.0)),
                "open_exposure_pct": _to_float(performance_snapshot.get("open_exposure_pct", 0.0)),
                "capital_allocated_pct": _to_float(performance_snapshot.get("capital_allocated_pct", 0.0)),
                "max_drawdown_pct": _to_float(performance_snapshot.get("max_drawdown_pct", 8.0)),
                "risk_state": str(portfolio_payload.get("risk_state", "unknown")),
                "allocation_state": str(portfolio_payload.get("allocation_state", "unknown")),
            },
            "memory_timestamp": memory_timestamp,
            "memory_version": memory_version,
            "phase_g_source_path": str(decision_path) if str(decision_path) else "",
            "phase_i_source_path": str(portfolio_path) if str(portfolio_path) else "",
            "manual_approval_required": True,
            "live_activation_allowed": False,
            "risk_constraints": {
                "live_execution_blocked": True,
                "auto_live_activation": False,
                "paper_execution_only": True,
            },
        }
        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

        update_id = hashlib.blake2b(
            f"{candidate_id}|{memory_timestamp}|{phase_g_decision}|{phase_i_decision}".encode("utf-8"),
            digest_size=8,
        ).hexdigest()
        if update_id not in known_update_ids:
            state_history.append(
                {
                    "update_id": update_id,
                    "candidate_id": candidate_id,
                    "memory_timestamp": memory_timestamp,
                    "phase_g_decision": phase_g_decision,
                    "phase_i_decision": phase_i_decision,
                    "source_paths": {
                        "phase_g": str(decision_path) if str(decision_path) else "",
                        "phase_i": str(portfolio_path) if str(portfolio_path) else "",
                    },
                }
            )
            known_update_ids.add(update_id)

    state_payload = {
        "memory_version": memory_version,
        "latest_update_timestamp": generated_entries[next(reversed(sorted(generated_entries)))]["memory_timestamp"]
        if generated_entries
        else now_iso,
        "state_history": state_history,
    }
    write_json_atomic(memory_state_path, state_payload)

    existing_registry = read_json_safe(registry_path, default={"memory_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"memory_records": []}
    records = existing_registry.get("memory_records", [])
    if not isinstance(records, list):
        records = []
    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)
    registry_payload = {
        "memory_version": memory_version,
        "memory_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "long_horizon_memory_enabled": True,
        "long_horizon_memory_count": len(generated_paths),
        "long_horizon_memory_dir": str(output_dir),
        "long_horizon_memory_artifacts": generated_paths,
        "long_horizon_memory_registry_path": str(registry_path),
        "long_horizon_memory_state_path": str(memory_state_path),
    }


def run_knowledge_expansion_phase_k(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_long_horizon_memory_artifacts(
        decision_orchestrator_dir=knowledge_root / "decision_orchestrator",
        portfolio_governance_dir=knowledge_root / "adaptive_portfolio_governance",
        output_dir=knowledge_root / "long_horizon_memory",
        mode=mode,
        memory_state_path=knowledge_root / "long_horizon_state_memory.json",
        registry_path=(knowledge_root / "long_horizon_memory" / "long_horizon_memory_registry.json"),
    )


def generate_advanced_discovery_artifacts(
    validated_knowledge_registry_path: Path,
    output_dir: Path,
    *,
    mode: str,
    registry_path: Path,
    discovery_version: str = PHASE_L_DISCOVERY_VERSION,
) -> dict[str, Any]:
    if str(mode).lower() != "replay":
        return {
            "advanced_discovery_enabled": False,
            "advanced_discovery_count": 0,
            "advanced_discovery_dir": str(output_dir),
            "advanced_discovery_artifacts": [],
            "advanced_discovery_registry_path": str(registry_path),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = read_json_safe(validated_knowledge_registry_path, default={"validated_knowledge": []})
    if not isinstance(payload, dict):
        payload = {"validated_knowledge": []}
    validated_items = payload.get("validated_knowledge", [])
    if not isinstance(validated_items, list):
        validated_items = []

    deduplicated_by_candidate: dict[str, dict[str, Any]] = {}
    for item in validated_items:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_by_candidate[candidate_id] = item

    generated_paths: list[str] = []
    generated_entries: dict[str, dict[str, Any]] = {}
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for candidate_id, item in sorted(deduplicated_by_candidate.items(), key=lambda pair: pair[0]):
        statement = str(item.get("statement", item.get("hypothesis_statement", ""))).strip()
        truth_class = str(item.get("truth_class", "meta-intelligence")).strip() or "meta-intelligence"
        evidence_history = item.get("evidence_history", [])
        if not isinstance(evidence_history, list):
            evidence_history = []
        decision = str(item.get("decision", "HOLD_FOR_MORE_DATA")).strip() or "HOLD_FOR_MORE_DATA"
        decision_reasons = item.get("decision_reasons", [])
        if not isinstance(decision_reasons, list):
            decision_reasons = []
        support_ratio = min(1.0, round(len(evidence_history) / 5.0, 6))
        target_path = output_dir / f"{_safe_candidate_filename(candidate_id)}.json"
        existing_artifact = read_json_safe(target_path, default={})
        existing_discovery_timestamp = (
            str(existing_artifact.get("discovery_timestamp", "")).strip()
            if isinstance(existing_artifact, dict)
            else ""
        )
        discovery_timestamp = str(item.get("timestamp", "")).strip() or existing_discovery_timestamp or now_iso
        pattern_signature = hashlib.blake2b(
            f"{candidate_id}|{truth_class}|{statement}".encode("utf-8"),
            digest_size=12,
        ).hexdigest()
        artifact = {
            "candidate_id": candidate_id,
            "hypothesis_class": truth_class,
            "pattern_signature": pattern_signature,
            "statistical_summary": {
                "evidence_points": len(evidence_history),
                "support_ratio": support_ratio,
                "confidence_proxy": 0.5 + (0.5 * support_ratio),
            },
            "replay_validation_summary": {
                "replay_scope": "sandbox_only",
                "decision": decision,
                "decision_reasons": [str(reason) for reason in decision_reasons],
                "replay_governed": True,
            },
            "discovery_timestamp": discovery_timestamp,
            "discovery_version": discovery_version,
            "sandbox_status": "replay_only",
            "live_activation_allowed": False,
        }
        write_json_atomic(target_path, artifact)
        generated_paths.append(str(target_path))
        generated_entries[candidate_id] = artifact

    existing_registry = read_json_safe(registry_path, default={"discovery_records": []})
    if not isinstance(existing_registry, dict):
        existing_registry = {"discovery_records": []}
    records = existing_registry.get("discovery_records", [])
    if not isinstance(records, list):
        records = []
    registry_by_candidate: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        registry_by_candidate[candidate_id] = record
    registry_by_candidate.update(generated_entries)
    registry_payload = {
        "discovery_version": discovery_version,
        "discovery_records": [registry_by_candidate[cid] for cid in sorted(registry_by_candidate)],
    }
    write_json_atomic(registry_path, registry_payload)

    return {
        "advanced_discovery_enabled": True,
        "advanced_discovery_count": len(generated_paths),
        "advanced_discovery_dir": str(output_dir),
        "advanced_discovery_artifacts": generated_paths,
        "advanced_discovery_registry_path": str(registry_path),
    }


def run_knowledge_expansion_phase_l(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    return generate_advanced_discovery_artifacts(
        validated_knowledge_registry_path=knowledge_root / "validated_knowledge_registry.json",
        output_dir=knowledge_root / "advanced_discovery",
        mode=mode,
        registry_path=(knowledge_root / "advanced_discovery" / "advanced_discovery_registry.json"),
    )


def generate_autonomous_capability_expansion_artifacts(
    validated_knowledge_registry_path: Path,
    output_dir: Path,
    *,
    mode: str,
    registry_path: Path,
    governance_registry_path: Path,
    expansion_version: str = PHASE_M_EXPANSION_VERSION,
) -> dict[str, Any]:
    feature_dir = output_dir / "feature_modules"
    detector_dir = output_dir / "market_structure_detectors"
    adapter_dir = output_dir / "data_source_adapters"
    validation_dir = output_dir / "sandbox_validations"
    governance_dir = output_dir / "governance"

    if str(mode).lower() != "replay":
        return {
            "autonomous_capability_expansion_enabled": False,
            "feature_module_proposal_count": 0,
            "market_structure_detector_proposal_count": 0,
            "data_source_adapter_stub_count": 0,
            "sandbox_validation_count": 0,
            "governance_record_count": 0,
            "pruned_capability_count": 0,
            "feature_module_proposals": [],
            "market_structure_detector_proposals": [],
            "data_source_adapter_stubs": [],
            "sandbox_validations": [],
            "governance_records": [],
            "feature_module_dir": str(feature_dir),
            "market_structure_detector_dir": str(detector_dir),
            "data_source_adapter_dir": str(adapter_dir),
            "sandbox_validation_dir": str(validation_dir),
            "governance_dir": str(governance_dir),
            "autonomous_capability_registry_path": str(registry_path),
            "autonomous_capability_governance_registry_path": str(governance_registry_path),
        }

    feature_dir.mkdir(parents=True, exist_ok=True)
    detector_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)
    governance_dir.mkdir(parents=True, exist_ok=True)

    payload = read_json_safe(validated_knowledge_registry_path, default={"validated_knowledge": []})
    if not isinstance(payload, dict):
        payload = {"validated_knowledge": []}
    validated_items = payload.get("validated_knowledge", [])
    if not isinstance(validated_items, list):
        validated_items = []

    deduplicated_by_candidate: dict[str, dict[str, Any]] = {}
    for item in validated_items:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        deduplicated_by_candidate[candidate_id] = item

    feature_paths: list[str] = []
    detector_paths: list[str] = []
    adapter_paths: list[str] = []
    validation_paths: list[str] = []
    governance_paths: list[str] = []
    pruned_count = 0

    generated_capabilities: list[dict[str, Any]] = []
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for candidate_id, item in sorted(deduplicated_by_candidate.items(), key=lambda pair: pair[0]):
        candidate_slug = _safe_candidate_filename(candidate_id)
        truth_class = str(item.get("truth_class", "meta-intelligence")).strip() or "meta-intelligence"
        statement = str(item.get("statement", item.get("hypothesis_statement", ""))).strip()
        evidence_history = item.get("evidence_history", [])
        if not isinstance(evidence_history, list):
            evidence_history = []
        evidence_points = len(evidence_history)

        feature_path = feature_dir / f"{candidate_slug}.json"
        feature_payload = {
            "candidate_id": candidate_id,
            "capability_kind": "feature_module",
            "module_name": f"feature_module_{candidate_slug}",
            "truth_class": truth_class,
            "hypothesis_statement": statement,
            "evidence_points": evidence_points,
            "proposal_timestamp": now_iso,
            "expansion_version": expansion_version,
            "sandbox_status": "replay_only",
            "live_activation_allowed": False,
        }
        write_json_atomic(feature_path, feature_payload)
        feature_paths.append(str(feature_path))
        generated_capabilities.append(
            {
                "candidate_id": candidate_id,
                "capability_kind": "feature_module",
                "artifact_path": str(feature_path),
                "payload": feature_payload,
            }
        )

        detector_path = detector_dir / f"{candidate_slug}.json"
        detector_payload = {
            "candidate_id": candidate_id,
            "capability_kind": "market_structure_detector",
            "detector_name": f"detector_{candidate_slug}",
            "structure_focus": truth_class,
            "hypothesis_statement": statement,
            "evidence_points": evidence_points,
            "proposal_timestamp": now_iso,
            "expansion_version": expansion_version,
            "sandbox_status": "replay_only",
            "live_activation_allowed": False,
        }
        write_json_atomic(detector_path, detector_payload)
        detector_paths.append(str(detector_path))
        generated_capabilities.append(
            {
                "candidate_id": candidate_id,
                "capability_kind": "market_structure_detector",
                "artifact_path": str(detector_path),
                "payload": detector_payload,
            }
        )

        required_data_sources = item.get("required_data_sources", [])
        if not isinstance(required_data_sources, list):
            required_data_sources = []
        available_data_sources = item.get("available_data_sources", [])
        if not isinstance(available_data_sources, list):
            available_data_sources = []
        available_set = {str(source).strip() for source in available_data_sources if str(source).strip()}

        for source_name in sorted({str(source).strip() for source in required_data_sources if str(source).strip()}):
            if source_name in available_set:
                continue
            adapter_slug = _safe_candidate_filename(f"{candidate_id}_{source_name}")
            adapter_path = adapter_dir / f"{adapter_slug}.json"
            adapter_payload = {
                "candidate_id": candidate_id,
                "capability_kind": "data_source_adapter_stub",
                "adapter_name": f"adapter_{_safe_candidate_filename(source_name)}",
                "source_name": source_name,
                "adapter_status": "inactive_stub",
                "active": False,
                "external_data_access": False,
                "proposal_timestamp": now_iso,
                "expansion_version": expansion_version,
                "sandbox_status": "replay_only",
                "live_activation_allowed": False,
            }
            write_json_atomic(adapter_path, adapter_payload)
            adapter_paths.append(str(adapter_path))
            generated_capabilities.append(
                {
                    "candidate_id": candidate_id,
                    "capability_kind": "data_source_adapter_stub",
                    "artifact_path": str(adapter_path),
                    "payload": adapter_payload,
                }
            )

    registry_payload = {
        "expansion_version": expansion_version,
        "generated_capabilities": [
            {
                "candidate_id": item["candidate_id"],
                "capability_kind": item["capability_kind"],
                "artifact_path": item["artifact_path"],
            }
            for item in generated_capabilities
        ],
    }
    write_json_atomic(registry_path, registry_payload)

    governance_records: list[dict[str, Any]] = []
    for item in generated_capabilities:
        capability_payload = item["payload"]
        capability_kind = str(item["capability_kind"])
        candidate_id = str(item["candidate_id"])
        artifact_path = str(item["artifact_path"])
        capability_slug = _safe_candidate_filename(f"{candidate_id}_{capability_kind}")

        sandbox_enforced = (
            str(capability_payload.get("sandbox_status", "")).strip() == "replay_only"
            and not bool(capability_payload.get("live_activation_allowed", False))
        )
        inactive_stub_ok = True
        if capability_kind == "data_source_adapter_stub":
            inactive_stub_ok = (
                str(capability_payload.get("adapter_status", "")).strip() == "inactive_stub"
                and not bool(capability_payload.get("active", True))
                and not bool(capability_payload.get("external_data_access", True))
            )

        validation_passed = sandbox_enforced and inactive_stub_ok
        validation_payload = {
            "candidate_id": candidate_id,
            "capability_kind": capability_kind,
            "capability_path": artifact_path,
            "validation_timestamp": now_iso,
            "validation_scope": "sandbox_only",
            "checks": {
                "sandbox_enforced": sandbox_enforced,
                "inactive_stub_ok": inactive_stub_ok,
            },
            "validation_passed": validation_passed,
        }
        validation_path = validation_dir / f"{capability_slug}.json"
        write_json_atomic(validation_path, validation_payload)
        validation_paths.append(str(validation_path))

        evidence_points = int(capability_payload.get("evidence_points", 0))
        weak_capability = capability_kind != "data_source_adapter_stub" and evidence_points < 2
        if not validation_passed:
            governance_decision = "pruned_invalid_sandbox_state"
            governance_reason = "sandbox validation failed"
            pruned = True
        elif weak_capability:
            governance_decision = "pruned_weak_capability"
            governance_reason = "insufficient replay evidence for autonomous expansion"
            pruned = True
        elif capability_kind == "data_source_adapter_stub":
            governance_decision = "retained_inactive_stub"
            governance_reason = "stub kept inactive pending verified data-source access"
            pruned = False
        else:
            governance_decision = "retained_for_sandbox_replay"
            governance_reason = "eligible for additional sandbox replay only"
            pruned = False

        if pruned:
            pruned_count += 1
        governance_payload = {
            "candidate_id": candidate_id,
            "capability_kind": capability_kind,
            "capability_path": artifact_path,
            "sandbox_validation_path": str(validation_path),
            "governance_timestamp": now_iso,
            "governance_decision": governance_decision,
            "governance_reason": governance_reason,
            "pruned": pruned,
            "sandbox_status": "replay_only",
            "live_activation_allowed": False,
            "governor_version": expansion_version,
        }
        governance_path = governance_dir / f"{capability_slug}.json"
        write_json_atomic(governance_path, governance_payload)
        governance_paths.append(str(governance_path))
        governance_records.append(governance_payload)

    governance_registry = {
        "expansion_version": expansion_version,
        "governance_records": governance_records,
    }
    write_json_atomic(governance_registry_path, governance_registry)

    return {
        "autonomous_capability_expansion_enabled": True,
        "feature_module_proposal_count": len(feature_paths),
        "market_structure_detector_proposal_count": len(detector_paths),
        "data_source_adapter_stub_count": len(adapter_paths),
        "sandbox_validation_count": len(validation_paths),
        "governance_record_count": len(governance_paths),
        "pruned_capability_count": pruned_count,
        "feature_module_proposals": feature_paths,
        "market_structure_detector_proposals": detector_paths,
        "data_source_adapter_stubs": adapter_paths,
        "sandbox_validations": validation_paths,
        "governance_records": governance_paths,
        "feature_module_dir": str(feature_dir),
        "market_structure_detector_dir": str(detector_dir),
        "data_source_adapter_dir": str(adapter_dir),
        "sandbox_validation_dir": str(validation_dir),
        "governance_dir": str(governance_dir),
        "autonomous_capability_registry_path": str(registry_path),
        "autonomous_capability_governance_registry_path": str(governance_registry_path),
    }


def run_autonomous_capability_expansion_layer(
    root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    output_dir = knowledge_root / "autonomous_capability_expansion"
    return generate_autonomous_capability_expansion_artifacts(
        validated_knowledge_registry_path=knowledge_root / "validated_knowledge_registry.json",
        output_dir=output_dir,
        mode=mode,
        registry_path=output_dir / "autonomous_capability_registry.json",
        governance_registry_path=output_dir / "autonomous_capability_governance_registry.json",
    )


def _deterministic_payload_digest(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.blake2b(serialized.encode("utf-8"), digest_size=16).hexdigest()


def _artifact_digests(paths: list[str]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path_str in sorted(paths):
        artifact_path = Path(path_str)
        payload = read_json_safe(artifact_path, default={})
        digests[str(artifact_path)] = _deterministic_payload_digest(payload)
    return digests


def _load_registry_candidate_ids(registry_path: Path, records_key: str) -> set[str]:
    payload = read_json_safe(registry_path, default={})
    if not isinstance(payload, dict):
        return set()
    records = payload.get(records_key, [])
    if not isinstance(records, list):
        return set()
    candidate_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if candidate_id:
            candidate_ids.add(candidate_id)
    return candidate_ids


def _artifact_candidate_ids(artifact_paths: list[str]) -> set[str]:
    candidate_ids: set[str] = set()
    for artifact_path in artifact_paths:
        payload = read_json_safe(Path(artifact_path), default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if candidate_id:
            candidate_ids.add(candidate_id)
    return candidate_ids


def _artifact_integrity_report(paths: list[str]) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for path_str in sorted(paths):
        artifact_path = Path(path_str)
        raw_payload = artifact_path.read_text(encoding="utf-8") if artifact_path.exists() else ""
        parsed_payload = read_json_safe(artifact_path, default=None)
        parse_ok = isinstance(parsed_payload, dict)
        canonical_digest = _deterministic_payload_digest(parsed_payload if parse_ok else {})
        artifacts.append(
            {
                "artifact_path": str(artifact_path),
                "exists": artifact_path.exists(),
                "parse_ok": parse_ok,
                "canonical_digest": canonical_digest,
                "raw_digest": hashlib.blake2b(raw_payload.encode("utf-8"), digest_size=16).hexdigest(),
            }
        )
    return {
        "artifact_count": len(artifacts),
        "all_present": all(bool(item["exists"]) for item in artifacts),
        "all_parse_ok": all(bool(item["parse_ok"]) for item in artifacts),
        "artifacts": artifacts,
    }


def _is_cycle_artifact_stale(existing_cycle_payload: Any) -> tuple[bool, list[str]]:
    if not isinstance(existing_cycle_payload, dict):
        return False, []
    stale_reasons: list[str] = []
    phase_artifact_digests = existing_cycle_payload.get("phase_artifact_digests", {})
    if not isinstance(phase_artifact_digests, dict):
        return False, []
    for phase_name, digest_map in phase_artifact_digests.items():
        if not isinstance(digest_map, dict):
            continue
        for artifact_path, expected_digest in digest_map.items():
            path_obj = Path(str(artifact_path))
            if not path_obj.exists():
                stale_reasons.append(f"{phase_name}:missing:{artifact_path}")
                continue
            current_payload = read_json_safe(path_obj, default={})
            current_digest = _deterministic_payload_digest(current_payload)
            if current_digest != str(expected_digest):
                stale_reasons.append(f"{phase_name}:digest_mismatch:{artifact_path}")
    return (len(stale_reasons) > 0, stale_reasons)


def _refresh_stale_artifacts(
    stale_reasons: list[str],
    *,
    mode: str,
    root: Path,
    baseline_summary: dict[str, Any] | None,
    replay_scope: str,
) -> bool:
    if str(mode).lower() != "replay" or not stale_reasons:
        return False
    run_knowledge_expansion_phase_l(root, mode=mode)
    run_knowledge_expansion_phase_b(root)
    run_knowledge_expansion_phase_c(root)
    run_knowledge_expansion_phase_d(
        root,
        mode=mode,
        baseline_summary=baseline_summary,
        replay_scope=replay_scope,
    )
    run_knowledge_expansion_phase_e(root, mode=mode)
    run_knowledge_expansion_phase_f(root, mode=mode)
    run_knowledge_expansion_phase_g(root, mode=mode)
    run_knowledge_expansion_phase_h(root, mode=mode)
    run_knowledge_expansion_phase_i(root, mode=mode)
    run_knowledge_expansion_phase_j(root, mode=mode)
    run_knowledge_expansion_phase_k(root, mode=mode)
    return True


def _phase_result_artifact_paths(phase_name: str, phase_result: Any) -> list[str]:
    if not isinstance(phase_result, dict):
        return []
    artifact_key_by_phase = {
        "discovery": "advanced_discovery_artifacts",
        "experimental_specs": "experimental_spec_artifacts",
        "sandbox_generation": "sandbox_module_artifacts",
        "replay_judgment": "sandbox_judgments",
        "promotion_governance": "promotion_governance_artifacts",
        "execution_governance": "execution_governance_artifacts",
        "decision_orchestration": "decision_artifacts",
        "execution_supervision": "supervision_artifacts",
        "adaptive_portfolio": "portfolio_artifacts",
        "incident_control": "incident_artifacts",
        "long_horizon_memory": "long_horizon_memory_artifacts",
    }
    artifact_key = artifact_key_by_phase.get(phase_name, "")
    artifact_paths = phase_result.get(artifact_key, [])
    if not isinstance(artifact_paths, list):
        return []
    return [str(path) for path in artifact_paths]


def _phase_result_safe_to_resume(phase_name: str, phase_result: Any) -> bool:
    if not isinstance(phase_result, dict):
        return False
    count_key_by_phase = {
        "discovery": "advanced_discovery_count",
        "experimental_specs": "experimental_spec_count",
        "sandbox_generation": "sandbox_module_count",
        "replay_judgment": "sandbox_judgment_count",
        "promotion_governance": "governance_artifact_count",
        "execution_governance": "execution_governance_artifact_count",
        "decision_orchestration": "decision_artifact_count",
        "execution_supervision": "supervision_artifact_count",
        "adaptive_portfolio": "portfolio_artifact_count",
        "incident_control": "incident_artifact_count",
        "long_horizon_memory": "long_horizon_memory_count",
    }
    artifact_paths = _phase_result_artifact_paths(phase_name, phase_result)
    expected_count = int(phase_result.get(count_key_by_phase.get(phase_name, ""), 0))
    if expected_count != len(artifact_paths):
        return False
    for artifact_path in artifact_paths:
        artifact_file = Path(artifact_path)
        if not artifact_file.exists():
            return False
        payload = read_json_safe(artifact_file, default=None)
        if not isinstance(payload, dict):
            return False
    return True


def _candidate_artifact_payloads(paths: list[str]) -> dict[str, tuple[str, dict[str, Any]]]:
    candidate_payloads: dict[str, tuple[str, dict[str, Any]]] = {}
    for path_str in sorted(paths):
        artifact_path = Path(path_str)
        payload = read_json_safe(artifact_path, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        candidate_payloads[candidate_id] = (str(artifact_path), payload)
    return candidate_payloads


def _decision_chain_anomaly_report(
    replay_paths: list[str],
    promotion_paths: list[str],
    execution_paths: list[str],
) -> dict[str, Any]:
    replay_by_candidate = _candidate_artifact_payloads(replay_paths)
    promotion_by_candidate = _candidate_artifact_payloads(promotion_paths)
    execution_by_candidate = _candidate_artifact_payloads(execution_paths)
    expected_replay_to_promotion = {
        PHASE_D_REJECT: PHASE_E_REJECTED,
        PHASE_D_RETAIN_FOR_FURTHER_REPLAY: PHASE_E_RETAINED_FOR_FURTHER_REPLAY,
        PHASE_D_PROMOTION_CANDIDATE: PHASE_E_PROMOTION_CANDIDATE,
    }
    expected_promotion_to_execution = {
        PHASE_E_REJECTED: PHASE_F_BLOCKED,
        PHASE_E_RETAINED_FOR_FURTHER_REPLAY: PHASE_F_MANUAL_REVIEW_REQUIRED,
        PHASE_E_PROMOTION_CANDIDATE: PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW,
    }

    anomalies_by_candidate: dict[str, list[str]] = {}
    all_candidates = sorted(set(replay_by_candidate) | set(promotion_by_candidate) | set(execution_by_candidate))
    for candidate_id in all_candidates:
        anomalies: list[str] = []
        replay_record = replay_by_candidate.get(candidate_id)
        promotion_record = promotion_by_candidate.get(candidate_id)
        execution_record = execution_by_candidate.get(candidate_id)
        if replay_record is None:
            anomalies.append("missing_replay_judgment")
        if promotion_record is None:
            anomalies.append("missing_promotion_governance")
        if execution_record is None:
            anomalies.append("missing_execution_governance")
        if replay_record and promotion_record:
            replay_decision = str(replay_record[1].get("decision", "")).strip()
            promotion_decision = str(promotion_record[1].get("governance_decision", "")).strip()
            expected_promotion_decision = expected_replay_to_promotion.get(replay_decision, "")
            if expected_promotion_decision and promotion_decision != expected_promotion_decision:
                anomalies.append(
                    f"replay_to_promotion_decision_mismatch:{replay_decision}->{promotion_decision}"
                )
        if promotion_record and execution_record:
            promotion_decision = str(promotion_record[1].get("governance_decision", "")).strip()
            execution_decision = str(execution_record[1].get("execution_decision", "")).strip()
            expected_execution_decision = expected_promotion_to_execution.get(promotion_decision, "")
            if expected_execution_decision and execution_decision != expected_execution_decision:
                anomalies.append(
                    f"promotion_to_execution_decision_mismatch:{promotion_decision}->{execution_decision}"
                )
        if anomalies:
            anomalies_by_candidate[candidate_id] = anomalies

    return {
        "has_anomalies": bool(anomalies_by_candidate),
        "anomaly_count": sum(len(items) for items in anomalies_by_candidate.values()),
        "invalid_candidate_ids": sorted(anomalies_by_candidate),
        "candidate_anomalies": anomalies_by_candidate,
    }


def _replay_governance_traceability_report(
    replay_paths: list[str],
    promotion_paths: list[str],
    execution_paths: list[str],
) -> dict[str, Any]:
    replay_by_candidate = _candidate_artifact_payloads(replay_paths)
    promotion_by_candidate = _candidate_artifact_payloads(promotion_paths)
    execution_by_candidate = _candidate_artifact_payloads(execution_paths)

    issues_by_candidate: dict[str, list[str]] = {}
    all_candidates = sorted(set(replay_by_candidate) | set(promotion_by_candidate) | set(execution_by_candidate))
    for candidate_id in all_candidates:
        issues: list[str] = []
        replay_record = replay_by_candidate.get(candidate_id)
        promotion_record = promotion_by_candidate.get(candidate_id)
        execution_record = execution_by_candidate.get(candidate_id)
        if replay_record and promotion_record:
            replay_path, replay_payload = replay_record
            _, promotion_payload = promotion_record
            source_judgment_path = str(promotion_payload.get("source_judgment_path", "")).strip()
            if source_judgment_path != replay_path:
                issues.append("promotion_source_judgment_path_mismatch")
            source_payload = read_json_safe(Path(source_judgment_path), default={})
            if not isinstance(source_payload, dict):
                issues.append("promotion_source_judgment_path_unreadable")
            elif str(source_payload.get("candidate_id", "")).strip() != candidate_id:
                issues.append("promotion_source_candidate_mismatch")
            promotion_phase_d_decision = str(
                (promotion_payload.get("judgment_summary", {}) or {}).get("phase_d_decision", "")
            ).strip()
            replay_decision = str(replay_payload.get("decision", "")).strip()
            if promotion_phase_d_decision and replay_decision and promotion_phase_d_decision != replay_decision:
                issues.append("promotion_phase_d_decision_trace_mismatch")
        if promotion_record and execution_record:
            promotion_path, promotion_payload = promotion_record
            _, execution_payload = execution_record
            governance_source_path = str(execution_payload.get("governance_source_path", "")).strip()
            if governance_source_path != promotion_path:
                issues.append("execution_governance_source_path_mismatch")
            source_payload = read_json_safe(Path(governance_source_path), default={})
            if not isinstance(source_payload, dict):
                issues.append("execution_governance_source_unreadable")
            elif str(source_payload.get("candidate_id", "")).strip() != candidate_id:
                issues.append("execution_governance_source_candidate_mismatch")
            traced_governance_decision = str(execution_payload.get("governance_decision", "")).strip()
            expected_governance_decision = str(promotion_payload.get("governance_decision", "")).strip()
            if traced_governance_decision != expected_governance_decision:
                issues.append("execution_governance_decision_trace_mismatch")
        if issues:
            issues_by_candidate[candidate_id] = issues

    return {
        "has_issues": bool(issues_by_candidate),
        "issue_count": sum(len(items) for items in issues_by_candidate.values()),
        "invalid_candidate_ids": sorted(issues_by_candidate),
        "candidate_issues": issues_by_candidate,
    }


def _apply_governed_rollback_for_invalid_downstream_chain(
    *,
    execution_governance: dict[str, Any],
    invalid_candidate_ids: set[str],
    cycle_dir: Path,
    iteration_id: str,
    trigger_reasons: list[str],
) -> dict[str, Any]:
    if not invalid_candidate_ids:
        return {
            "triggered": False,
            "trigger_reasons": trigger_reasons,
            "invalid_candidate_ids": [],
            "rollback_report_path": "",
            "affected_execution_artifacts": [],
        }

    rollback_timestamp = datetime.now(tz=timezone.utc).isoformat()
    affected_execution_artifacts: list[str] = []
    for artifact_path in execution_governance.get("execution_governance_artifacts", []):
        path_obj = Path(str(artifact_path))
        payload = read_json_safe(path_obj, default={})
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if candidate_id not in invalid_candidate_ids:
            continue
        payload["execution_decision"] = PHASE_F_BLOCKED
        payload["execution_status"] = "blocked_non_live"
        payload["execution_reason"] = "Governed rollback blocked invalid downstream artifact chain."
        payload["manual_approval_required"] = True
        payload["live_activation_allowed"] = False
        payload["risk_constraints"] = {
            "live_execution_blocked": True,
            "auto_live_activation": False,
            "controlled_execution_review_required": True,
        }
        payload["governed_rollback"] = {
            "triggered": True,
            "rollback_timestamp": rollback_timestamp,
            "trigger_reasons": list(trigger_reasons),
        }
        write_json_atomic(path_obj, payload)
        affected_execution_artifacts.append(str(path_obj))

    registry_path = Path(str(execution_governance.get("controlled_execution_registry_path", "")))
    registry_payload = read_json_safe(registry_path, default={})
    if isinstance(registry_payload, dict):
        records = registry_payload.get("execution_records", [])
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, dict):
                    continue
                candidate_id = str(record.get("candidate_id", "")).strip()
                if candidate_id not in invalid_candidate_ids:
                    continue
                record["execution_decision"] = PHASE_F_BLOCKED
                record["execution_status"] = "blocked_non_live"
                record["execution_reason"] = "Governed rollback blocked invalid downstream artifact chain."
                record["manual_approval_required"] = True
                record["live_activation_allowed"] = False
                record["risk_constraints"] = {
                    "live_execution_blocked": True,
                    "auto_live_activation": False,
                    "controlled_execution_review_required": True,
                }
                record["governed_rollback"] = {
                    "triggered": True,
                    "rollback_timestamp": rollback_timestamp,
                    "trigger_reasons": list(trigger_reasons),
                }
            write_json_atomic(registry_path, registry_payload)

    rollback_report = {
        "iteration_id": iteration_id,
        "rollback_timestamp": rollback_timestamp,
        "trigger_reasons": list(trigger_reasons),
        "invalid_candidate_ids": sorted(invalid_candidate_ids),
        "affected_execution_artifacts": affected_execution_artifacts,
        "live_activation_allowed": False,
    }
    rollback_report_path = cycle_dir / f"governed_rollback_{iteration_id}.json"
    write_json_atomic(rollback_report_path, rollback_report)
    return {
        "triggered": True,
        "trigger_reasons": list(trigger_reasons),
        "invalid_candidate_ids": sorted(invalid_candidate_ids),
        "rollback_report_path": str(rollback_report_path),
        "affected_execution_artifacts": affected_execution_artifacts,
    }


def _candidate_payloads_from_validated_registry(registry_path: Path) -> dict[str, tuple[str, dict[str, Any]]]:
    payload = read_json_safe(registry_path, default={"validated_knowledge": []})
    if not isinstance(payload, dict):
        payload = {"validated_knowledge": []}
    records = payload.get("validated_knowledge", [])
    if not isinstance(records, list):
        records = []
    candidates: dict[str, tuple[str, dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_id = str(record.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        candidates[candidate_id] = (str(registry_path), record)
    return candidates


def _end_to_end_governance_chain_report(
    *,
    root: Path,
    phase_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    phase_payloads: dict[str, dict[str, tuple[str, dict[str, Any]]]] = {
        "phase_a": _candidate_payloads_from_validated_registry(knowledge_root / "validated_knowledge_registry.json"),
        "phase_b": _candidate_artifact_payloads(
            phase_results.get("experimental_specs", {}).get("experimental_spec_artifacts", [])
        ),
        "phase_c": _candidate_artifact_payloads(
            phase_results.get("sandbox_generation", {}).get("sandbox_module_artifacts", [])
        ),
        "phase_d": _candidate_artifact_payloads(phase_results.get("replay_judgment", {}).get("sandbox_judgments", [])),
        "phase_e": _candidate_artifact_payloads(
            phase_results.get("promotion_governance", {}).get("promotion_governance_artifacts", [])
        ),
        "phase_f": _candidate_artifact_payloads(
            phase_results.get("execution_governance", {}).get("execution_governance_artifacts", [])
        ),
        "phase_g": _candidate_artifact_payloads(
            phase_results.get("decision_orchestration", {}).get("decision_artifacts", [])
        ),
        "phase_h": _candidate_artifact_payloads(
            phase_results.get("execution_supervision", {}).get("supervision_artifacts", [])
        ),
        "phase_i": _candidate_artifact_payloads(phase_results.get("adaptive_portfolio", {}).get("portfolio_artifacts", [])),
        "phase_j": _candidate_artifact_payloads(phase_results.get("incident_control", {}).get("incident_artifacts", [])),
        "phase_k": _candidate_artifact_payloads(
            phase_results.get("long_horizon_memory", {}).get("long_horizon_memory_artifacts", [])
        ),
        "phase_l": _candidate_artifact_payloads(phase_results.get("discovery", {}).get("advanced_discovery_artifacts", [])),
    }

    phase_sequence = [
        "phase_a",
        "phase_b",
        "phase_c",
        "phase_d",
        "phase_e",
        "phase_f",
        "phase_g",
        "phase_h",
        "phase_i",
        "phase_j",
        "phase_k",
        "phase_l",
    ]
    phase_candidate_counts = {
        phase_name: len(phase_payloads.get(phase_name, {}))
        for phase_name in phase_sequence
    }
    phase_set_flow_checks: dict[str, bool] = {}
    issues: list[str] = []
    invalid_candidate_ids: set[str] = set()
    for upstream_phase, downstream_phase in zip(phase_sequence, phase_sequence[1:]):
        upstream_candidates = set(phase_payloads.get(upstream_phase, {}))
        downstream_candidates = set(phase_payloads.get(downstream_phase, {}))
        check_key = f"{upstream_phase}_to_{downstream_phase}_downstream_subset"
        phase_set_flow_checks[check_key] = downstream_candidates.issubset(upstream_candidates)
        if not phase_set_flow_checks[check_key]:
            issues.append(f"{check_key}_failed")
            invalid_candidate_ids.update(sorted(downstream_candidates - upstream_candidates))

    traceability_checks = {
        "phase_c_source_spec_paths_valid": True,
        "phase_d_source_spec_paths_valid": True,
        "phase_e_source_judgment_paths_valid": True,
        "phase_f_governance_source_paths_valid": True,
        "phase_g_execution_source_paths_valid": True,
        "phase_h_orchestrator_source_paths_valid": True,
        "phase_i_supervision_source_paths_valid": True,
        "phase_j_portfolio_source_paths_valid": True,
        "phase_k_phase_g_source_paths_valid": True,
        "phase_k_phase_i_source_paths_valid": True,
    }

    def _record_trace_issue(
        check_key: str,
        candidate_id: str,
        reason: str,
    ) -> None:
        traceability_checks[check_key] = False
        invalid_candidate_ids.add(candidate_id)
        issues.append(f"{check_key}:{candidate_id}:{reason}")

    phase_b_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_b"].items()}
    phase_d_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_d"].items()}
    phase_e_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_e"].items()}
    phase_f_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_f"].items()}
    phase_g_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_g"].items()}
    phase_h_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_h"].items()}
    phase_i_paths = {candidate_id: payload[0] for candidate_id, payload in phase_payloads["phase_i"].items()}

    for candidate_id, (_, payload) in phase_payloads["phase_c"].items():
        source_path = str(payload.get("source_spec_path", "")).strip()
        if source_path != phase_b_paths.get(candidate_id, ""):
            _record_trace_issue("phase_c_source_spec_paths_valid", candidate_id, "source_spec_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_d"].items():
        module_source = payload.get("module_summary", {})
        source_payload = module_source.get("source", {}) if isinstance(module_source, dict) else {}
        source_path = str(source_payload.get("source_spec_path", "")).strip() if isinstance(source_payload, dict) else ""
        if source_path != phase_b_paths.get(candidate_id, ""):
            _record_trace_issue("phase_d_source_spec_paths_valid", candidate_id, "module_summary_source_spec_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_e"].items():
        source_path = str(payload.get("source_judgment_path", "")).strip()
        if source_path != phase_d_paths.get(candidate_id, ""):
            _record_trace_issue("phase_e_source_judgment_paths_valid", candidate_id, "source_judgment_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_f"].items():
        source_path = str(payload.get("governance_source_path", "")).strip()
        if source_path != phase_e_paths.get(candidate_id, ""):
            _record_trace_issue("phase_f_governance_source_paths_valid", candidate_id, "governance_source_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_g"].items():
        source_path = str(payload.get("execution_source_path", "")).strip()
        if source_path != phase_f_paths.get(candidate_id, ""):
            _record_trace_issue("phase_g_execution_source_paths_valid", candidate_id, "execution_source_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_h"].items():
        source_path = str(payload.get("orchestrator_source_path", "")).strip()
        if source_path != phase_g_paths.get(candidate_id, ""):
            _record_trace_issue("phase_h_orchestrator_source_paths_valid", candidate_id, "orchestrator_source_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_i"].items():
        source_path = str(payload.get("supervision_source_path", "")).strip()
        if source_path != phase_h_paths.get(candidate_id, ""):
            _record_trace_issue("phase_i_supervision_source_paths_valid", candidate_id, "supervision_source_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_j"].items():
        source_path = str(payload.get("portfolio_source_path", "")).strip()
        if source_path != phase_i_paths.get(candidate_id, ""):
            _record_trace_issue("phase_j_portfolio_source_paths_valid", candidate_id, "portfolio_source_path_mismatch")
    for candidate_id, (_, payload) in phase_payloads["phase_k"].items():
        source_g_path = str(payload.get("phase_g_source_path", "")).strip()
        source_i_path = str(payload.get("phase_i_source_path", "")).strip()
        if source_g_path != phase_g_paths.get(candidate_id, ""):
            _record_trace_issue("phase_k_phase_g_source_paths_valid", candidate_id, "phase_g_source_path_mismatch")
        if source_i_path != phase_i_paths.get(candidate_id, ""):
            _record_trace_issue("phase_k_phase_i_source_paths_valid", candidate_id, "phase_i_source_path_mismatch")

    all_checks_passed = all(phase_set_flow_checks.values()) and all(traceability_checks.values())
    return {
        "phase_sequence": phase_sequence,
        "phase_candidate_counts": phase_candidate_counts,
        "phase_set_flow_checks": phase_set_flow_checks,
        "traceability_checks": traceability_checks,
        "issues": sorted(issues),
        "invalid_candidate_ids": sorted(invalid_candidate_ids),
        "all_checks_passed": all_checks_passed,
    }


def _quarantine_invalid_artifacts(
    *,
    cycle_dir: Path,
    iteration_id: str,
    artifact_integrity: dict[str, Any],
    end_to_end_governance_chain: dict[str, Any],
) -> dict[str, Any]:
    quarantine_dir = cycle_dir / "quarantine" / iteration_id
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_records: list[dict[str, Any]] = []

    for phase_name, phase_report in artifact_integrity.items():
        if phase_name == "all_checks_passed" or not isinstance(phase_report, dict):
            continue
        artifacts = phase_report.get("artifacts", [])
        if not isinstance(artifacts, list):
            continue
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            if bool(artifact.get("exists", False)) and bool(artifact.get("parse_ok", False)):
                continue
            artifact_path = str(artifact.get("artifact_path", "")).strip()
            quarantine_records.append(
                {
                    "phase": phase_name,
                    "reason": "artifact_missing_or_unparseable",
                    "artifact_path": artifact_path,
                    "exists": bool(artifact.get("exists", False)),
                    "parse_ok": bool(artifact.get("parse_ok", False)),
                    "raw_digest": str(artifact.get("raw_digest", "")),
                    "canonical_digest": str(artifact.get("canonical_digest", "")),
                }
            )

    for issue in end_to_end_governance_chain.get("issues", []):
        issue_text = str(issue)
        if ":" not in issue_text:
            continue
        issue_parts = issue_text.split(":")
        if len(issue_parts) < 3:
            continue
        check_key, candidate_id, *reason_parts = issue_parts
        reason = ":".join(reason_parts)
        quarantine_records.append(
            {
                "phase": "chain_verification",
                "reason": f"{check_key}:{reason}",
                "candidate_id": candidate_id,
                "artifact_path": "",
                "exists": False,
                "parse_ok": False,
            }
        )

    unique_records: dict[str, dict[str, Any]] = {}
    for record in quarantine_records:
        record_key = _deterministic_payload_digest(record)
        unique_records[record_key] = record
    ordered_records = [unique_records[key] for key in sorted(unique_records)]
    quarantine_payload = {
        "iteration_id": iteration_id,
        "quarantined_record_count": len(ordered_records),
        "quarantined_records": ordered_records,
    }
    quarantine_report_path = quarantine_dir / "quarantine_report.json"
    write_json_atomic(quarantine_report_path, quarantine_payload)
    return {
        "quarantine_required": bool(ordered_records),
        "quarantined_record_count": len(ordered_records),
        "quarantine_report_path": str(quarantine_report_path),
        "quarantine_records": ordered_records,
    }


def _governed_refusal_state(
    *,
    end_to_end_governance_chain: dict[str, Any],
    invalid_artifact_quarantine: dict[str, Any],
    governed_rollback: dict[str, Any],
) -> dict[str, Any]:
    refusal_reasons: list[str] = []
    if not bool(end_to_end_governance_chain.get("all_checks_passed", False)):
        refusal_reasons.append("end_to_end_chain_verification_failed")
    if bool(invalid_artifact_quarantine.get("quarantine_required", False)):
        refusal_reasons.append("invalid_artifact_quarantine_required")
    if bool(governed_rollback.get("triggered", False)):
        refusal_reasons.append("downstream_rollback_triggered")

    refusal_state = "continue_governed_non_live"
    if refusal_reasons:
        if len(refusal_reasons) > 1:
            refusal_state = "refuse_cycle_continuation_multiple_unsafe_conditions"
        elif refusal_reasons[0] == "end_to_end_chain_verification_failed":
            refusal_state = "refuse_cycle_continuation_chain_verification_failed"
        elif refusal_reasons[0] == "invalid_artifact_quarantine_required":
            refusal_state = "refuse_cycle_continuation_quarantine_required"
        else:
            refusal_state = "refuse_cycle_continuation_rollback_required"
    return {
        "refused": bool(refusal_reasons),
        "refusal_state": refusal_state,
        "refusal_reasons": refusal_reasons,
        "safe_to_continue": not bool(refusal_reasons),
    }


def _clamp_parameter(value: Any) -> float:
    return round(max(0.05, min(0.95, _to_float(value, default=0.5))), 4)


def _evolution_regime_context(
    *,
    baseline_summary: dict[str, Any] | None,
    replay_paths: list[str],
    replay_scope: str,
) -> dict[str, Any]:
    baseline = baseline_summary if isinstance(baseline_summary, dict) else {}
    volatility_ratio = _to_float(baseline.get("volatility_ratio", 1.0), default=1.0)
    if volatility_ratio <= 0.9:
        volatility_regime = "low_volatility"
    elif volatility_ratio >= 1.2:
        volatility_regime = "high_volatility"
    else:
        volatility_regime = "medium_volatility"
    replay_by_candidate = _candidate_artifact_payloads(replay_paths)
    weak_module_cluster_size = sum(
        1
        for _, payload in replay_by_candidate.values()
        if str(payload.get("decision", "")).strip() != PHASE_D_PROMOTION_CANDIDATE
    )
    return {
        "volatility_ratio": volatility_ratio,
        "volatility_regime": volatility_regime,
        "structure_state": str(baseline.get("structure_state", "range")),
        "confidence": round(_to_float(baseline.get("confidence", 0.5), default=0.5), 4),
        "replay_scope": replay_scope,
        "weak_module_cluster_size": weak_module_cluster_size,
        "weak_module_cluster_detected": weak_module_cluster_size >= 1,
    }


def _evolution_parameter_performance(
    *,
    regime_context: dict[str, Any],
    replay_paths: list[str],
    promotion_paths: list[str],
    execution_paths: list[str],
    governed_rollback: dict[str, Any],
    live_learning_feedback: dict[str, Any],
) -> dict[str, Any]:
    replay_by_candidate = _candidate_artifact_payloads(replay_paths)
    promotion_by_candidate = _candidate_artifact_payloads(promotion_paths)
    execution_by_candidate = _candidate_artifact_payloads(execution_paths)
    promoted_ids: set[str] = set()
    quarantined_ids: set[str] = set()
    quarantined_later_would_work_ids: set[str] = set()
    promoted_later_failed_ids: set[str] = set()
    rollback_ids = {
        str(item).strip()
        for item in governed_rollback.get("invalid_candidate_ids", [])
        if str(item).strip()
    }
    for candidate_id in sorted(set(replay_by_candidate) | set(promotion_by_candidate)):
        replay_payload = replay_by_candidate.get(candidate_id, ("", {}))[1]
        promotion_payload = promotion_by_candidate.get(candidate_id, ("", {}))[1]
        execution_payload = execution_by_candidate.get(candidate_id, ("", {}))[1]
        governance_decision = str(promotion_payload.get("governance_decision", "")).strip()
        replay_decision = str(replay_payload.get("decision", "")).strip()
        execution_decision = str(execution_payload.get("execution_decision", "")).strip()
        if governance_decision == PHASE_E_PROMOTION_CANDIDATE:
            promoted_ids.add(candidate_id)
            if execution_decision and execution_decision != PHASE_F_ELIGIBLE_FOR_CONTROLLED_EXECUTION_REVIEW:
                promoted_later_failed_ids.add(candidate_id)
            if candidate_id in rollback_ids:
                promoted_later_failed_ids.add(candidate_id)
        elif governance_decision in {PHASE_E_REJECTED, PHASE_E_RETAINED_FOR_FURTHER_REPLAY}:
            quarantined_ids.add(candidate_id)
            if replay_decision == PHASE_D_PROMOTION_CANDIDATE:
                quarantined_later_would_work_ids.add(candidate_id)
    mutation_candidate = live_learning_feedback.get("mutation_candidate", {})
    if not isinstance(mutation_candidate, dict):
        mutation_candidate = {}
    mutation_score = _to_float(mutation_candidate.get("mutation_score", 0.0), default=0.0)
    promotion_state = str((mutation_candidate.get("governance", {}) or {}).get("promotion_state", "pending")).lower()
    mutation_usefulness = mutation_score if promotion_state == "promoted" else 0.0
    mutation_noise = (1.0 - mutation_score) if promotion_state in {"quarantined", "pending"} else 0.0
    promoted_total = len(promoted_ids)
    quarantined_total = len(quarantined_ids)
    promoted_later_failed = len(promoted_later_failed_ids)
    quarantined_later_would_work = len(quarantined_later_would_work_ids)
    promotion_precision = round(
        (promoted_total - promoted_later_failed) / promoted_total,
        4,
    ) if promoted_total else 1.0
    quarantine_precision = round(
        (quarantined_total - quarantined_later_would_work) / quarantined_total,
        4,
    ) if quarantined_total else 1.0
    regime = str(regime_context.get("volatility_regime", "unknown"))
    return {
        "promoted_modules_total": promoted_total,
        "promoted_modules_later_failed": promoted_later_failed,
        "promoted_modules_later_failed_ids": sorted(promoted_later_failed_ids),
        "quarantined_modules_total": quarantined_total,
        "quarantined_modules_later_would_work": quarantined_later_would_work,
        "quarantined_modules_later_would_work_ids": sorted(quarantined_later_would_work_ids),
        "mutation_usefulness": round(mutation_usefulness, 4),
        "mutation_noise": round(mutation_noise, 4),
        "promotion_precision_by_regime": {regime: promotion_precision},
        "quarantine_precision_by_regime": {regime: quarantine_precision},
        "replay_evaluated": True,
        "governed": True,
    }


def _adapt_evolution_parameters(
    *,
    previous_state: dict[str, Any],
    regime_context: dict[str, Any],
    performance: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    next_state = {
        key: _clamp_parameter(previous_state.get(key, default_value))
        for key, default_value in _DEFAULT_EVOLUTION_PARAMETERS.items()
    }
    changes: list[dict[str, Any]] = []
    reasons: list[str] = []

    def _apply(name: str, delta: float, reason: str) -> None:
        before = _clamp_parameter(next_state.get(name))
        after = _clamp_parameter(before + delta)
        if after == before:
            return
        next_state[name] = after
        reasons.append(reason)
        changes.append(
            {
                "parameter": name,
                "previous": before,
                "updated": after,
                "delta": round(after - before, 4),
                "reason": reason,
                "replay_evaluated": True,
                "governed": True,
            }
        )

    volatility_regime = str(regime_context.get("volatility_regime", "medium_volatility"))
    if volatility_regime == "low_volatility":
        _apply(
            "promotion_threshold",
            0.05,
            "strict promotion works better in low volatility",
        )
        _apply(
            "exploration_vs_stability_balance",
            -0.05,
            "low volatility favors stability over exploration",
        )
    elif volatility_regime == "high_volatility":
        _apply(
            "mutation_rate",
            0.1,
            "faster mutation works better in high volatility",
        )
        _apply(
            "exploration_vs_stability_balance",
            0.08,
            "high volatility favors exploration for adaptation",
        )

    if bool(regime_context.get("weak_module_cluster_detected", False)):
        _apply(
            "quarantine_strictness",
            0.1,
            "quarantine should tighten after weak-module clusters",
        )

    if int(performance.get("promoted_modules_later_failed", 0)) > 0:
        _apply(
            "promotion_threshold",
            0.05,
            "promoted modules later failed under replay-governed execution",
        )
    if int(performance.get("quarantined_modules_later_would_work", 0)) > 0:
        _apply(
            "quarantine_strictness",
            -0.05,
            "quarantined modules later showed replay potential",
        )

    mutation_noise = _to_float(performance.get("mutation_noise", 0.0), default=0.0)
    mutation_usefulness = _to_float(performance.get("mutation_usefulness", 0.0), default=0.0)
    if mutation_noise > mutation_usefulness:
        _apply(
            "mutation_rate",
            -0.05,
            "mutation usefulness is below noise under replay evaluation",
        )
    elif mutation_usefulness > mutation_noise:
        _apply(
            "mutation_rate",
            0.03,
            "mutation usefulness exceeds noise under replay evaluation",
        )

    return next_state, changes, sorted(set(reasons))


def _update_evolution_parameter_control(
    *,
    cycle_dir: Path,
    iteration_id: str,
    baseline_summary: dict[str, Any] | None,
    replay_scope: str,
    replay_paths: list[str],
    promotion_paths: list[str],
    execution_paths: list[str],
    live_learning_feedback: dict[str, Any],
    governed_rollback: dict[str, Any],
    governed_refusal: dict[str, Any],
) -> dict[str, Any]:
    control_dir = cycle_dir / "evolution_parameter_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    registry_path = control_dir / "evolution_parameter_control_registry.json"
    registry_payload = read_json_safe(registry_path, default={"iterations": []})
    if not isinstance(registry_payload, dict):
        registry_payload = {"iterations": []}
    iterations = registry_payload.get("iterations", [])
    if not isinstance(iterations, list):
        iterations = []
    previous_state = dict(_DEFAULT_EVOLUTION_PARAMETERS)
    latest_iteration = None
    for item in iterations:
        if not isinstance(item, dict):
            continue
        item_iteration = str(item.get("iteration_id", "")).strip()
        if not item_iteration:
            continue
        if item_iteration == iteration_id:
            continue
        if latest_iteration is None or item_iteration > latest_iteration:
            latest_iteration = item_iteration
            item_state = item.get("parameter_state", {})
            if isinstance(item_state, dict):
                previous_state = {
                    key: _clamp_parameter(item_state.get(key, default_value))
                    for key, default_value in _DEFAULT_EVOLUTION_PARAMETERS.items()
                }

    regime_context = _evolution_regime_context(
        baseline_summary=baseline_summary,
        replay_paths=replay_paths,
        replay_scope=replay_scope,
    )
    performance = _evolution_parameter_performance(
        regime_context=regime_context,
        replay_paths=replay_paths,
        promotion_paths=promotion_paths,
        execution_paths=execution_paths,
        governed_rollback=governed_rollback,
        live_learning_feedback=live_learning_feedback,
    )
    next_state, changes, reasons = _adapt_evolution_parameters(
        previous_state=previous_state,
        regime_context=regime_context,
        performance=performance,
    )
    governance_context = {
        "governed_refusal": governed_refusal,
        "governed_rollback": governed_rollback,
        "replay_evaluated": True,
        "governed": True,
    }
    iteration_record = {
        "iteration_id": iteration_id,
        "regime_context": regime_context,
        "performance": performance,
        "parameter_state": next_state,
        "parameter_changes": changes,
        "adaptation_reasons": reasons,
        "governance_context": governance_context,
    }
    iterations_by_id: dict[str, dict[str, Any]] = {}
    for item in iterations:
        if not isinstance(item, dict):
            continue
        item_iteration = str(item.get("iteration_id", "")).strip()
        if not item_iteration:
            continue
        iterations_by_id[item_iteration] = item
    iterations_by_id[iteration_id] = iteration_record
    ordered_iterations = [iterations_by_id[key] for key in sorted(iterations_by_id)]
    updated_registry_payload = {"iterations": ordered_iterations}
    write_json_atomic(registry_path, updated_registry_payload)

    by_regime: dict[str, dict[str, Any]] = {}
    for item in ordered_iterations:
        regime = str((item.get("regime_context", {}) or {}).get("volatility_regime", "unknown"))
        regime_bucket = by_regime.setdefault(
            regime,
            {
                "iterations": 0,
                "promoted_modules_total": 0,
                "promoted_modules_later_failed": 0,
                "quarantined_modules_total": 0,
                "quarantined_modules_later_would_work": 0,
            },
        )
        perf = item.get("performance", {})
        if not isinstance(perf, dict):
            perf = {}
        regime_bucket["iterations"] += 1
        regime_bucket["promoted_modules_total"] += int(perf.get("promoted_modules_total", 0))
        regime_bucket["promoted_modules_later_failed"] += int(perf.get("promoted_modules_later_failed", 0))
        regime_bucket["quarantined_modules_total"] += int(perf.get("quarantined_modules_total", 0))
        regime_bucket["quarantined_modules_later_would_work"] += int(perf.get("quarantined_modules_later_would_work", 0))
    for regime, item in by_regime.items():
        promoted_total = int(item.get("promoted_modules_total", 0))
        failed_promotions = int(item.get("promoted_modules_later_failed", 0))
        quarantined_total = int(item.get("quarantined_modules_total", 0))
        quarantined_misses = int(item.get("quarantined_modules_later_would_work", 0))
        item["promotion_precision"] = round(
            (promoted_total - failed_promotions) / promoted_total,
            4,
        ) if promoted_total else 1.0
        item["quarantine_precision"] = round(
            (quarantined_total - quarantined_misses) / quarantined_total,
            4,
        ) if quarantined_total else 1.0
        item["regime"] = regime
        item["replay_evaluated"] = True
        item["governed"] = True
    parameter_performance_by_regime = {
        "iteration_id": iteration_id,
        "by_regime": {key: by_regime[key] for key in sorted(by_regime)},
    }

    state_path = control_dir / f"parameter_state_{iteration_id}.json"
    changes_path = control_dir / f"parameter_changes_{iteration_id}.json"
    adaptation_reasons_path = control_dir / f"adaptation_reasons_{iteration_id}.json"
    performance_by_regime_path = control_dir / "parameter_performance_by_regime.json"
    state_payload = {
        "iteration_id": iteration_id,
        "parameter_state": next_state,
        "previous_parameter_state": previous_state,
        "regime_context": regime_context,
        "replay_evaluated": True,
        "governed": True,
    }
    changes_payload = {
        "iteration_id": iteration_id,
        "parameter_changes": changes,
        "replay_evaluated": True,
        "governed": True,
    }
    reasons_payload = {
        "iteration_id": iteration_id,
        "adaptation_reasons": reasons,
        "governance_context": governance_context,
    }
    write_json_atomic(state_path, state_payload)
    write_json_atomic(changes_path, changes_payload)
    write_json_atomic(adaptation_reasons_path, reasons_payload)
    write_json_atomic(performance_by_regime_path, parameter_performance_by_regime)
    return {
        "parameter_state": next_state,
        "parameter_changes": changes,
        "adaptation_reasons": reasons,
        "performance": performance,
        "regime_context": regime_context,
        "parameter_state_path": str(state_path),
        "parameter_changes_path": str(changes_path),
        "adaptation_reasons_path": str(adaptation_reasons_path),
        "parameter_performance_by_regime_path": str(performance_by_regime_path),
        "registry_path": str(registry_path),
    }


def _write_cycle_self_audit_artifact(
    *,
    cycle_dir: Path,
    iteration_id: str,
    cycle_payload: dict[str, Any],
) -> dict[str, Any]:
    deterministic_scope = {
        "iteration_id": str(cycle_payload.get("iteration_id", "")),
        "mode": str(cycle_payload.get("mode", "")),
        "replay_scope": str(cycle_payload.get("replay_scope", "")),
        "phase_artifact_digests": cycle_payload.get("phase_artifact_digests", {}),
        "phase_registry_consistency": cycle_payload.get("phase_registry_consistency", {}),
        "end_to_end_governance_chain": cycle_payload.get("end_to_end_governance_chain", {}),
        "cross_phase_anomaly_detection": cycle_payload.get("cross_phase_anomaly_detection", {}),
        "replay_governance_traceability": cycle_payload.get("replay_governance_traceability", {}),
        "governed_rollback": cycle_payload.get("governed_rollback", {}),
        "invalid_artifact_quarantine": cycle_payload.get("invalid_artifact_quarantine", {}),
        "governed_refusal": cycle_payload.get("governed_refusal", {}),
        "live_activation_blocked": bool(cycle_payload.get("live_activation_blocked", True)),
    }
    self_audit_signature = _deterministic_payload_digest(deterministic_scope)
    self_audit_payload = {
        "iteration_id": iteration_id,
        "self_audit_version": "governed_cycle_self_audit_v1",
        "deterministic_scope": deterministic_scope,
        "self_audit_signature": self_audit_signature,
    }
    self_audit_path = cycle_dir / f"self_audit_{iteration_id}.json"
    write_json_atomic(self_audit_path, self_audit_payload)
    return {
        "self_audit_path": str(self_audit_path),
        "self_audit_signature": self_audit_signature,
    }


def run_continuous_governed_improvement_cycle(
    root: Path,
    *,
    mode: str,
    baseline_summary: dict[str, Any] | None = None,
    replay_scope: str = "full_replay",
    iteration_id: str = "default",
) -> dict[str, Any]:
    knowledge_root = root / "memory" / "knowledge_expansion"
    cycle_dir = knowledge_root / "continuous_governed_improvement"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    normalized_iteration_id = _safe_candidate_filename(iteration_id)
    cycle_artifact_path = cycle_dir / f"cycle_{normalized_iteration_id}.json"
    cycle_state_path = cycle_dir / f"cycle_state_{normalized_iteration_id}.json"

    previous_state_payload = read_json_safe(cycle_state_path, default={})
    recovering_interrupted_cycle = (
        isinstance(previous_state_payload, dict)
        and str(previous_state_payload.get("status", "")).strip().lower() == "in_progress"
    )
    existing_cycle_payload = read_json_safe(cycle_artifact_path, default={})
    stale_detected, stale_reasons = _is_cycle_artifact_stale(existing_cycle_payload)
    stale_refreshed = _refresh_stale_artifacts(
        stale_reasons,
        mode=mode,
        root=root,
        baseline_summary=baseline_summary,
        replay_scope=replay_scope,
    )
    previous_phase_results = {}
    if recovering_interrupted_cycle and isinstance(previous_state_payload, dict):
        candidate_previous_results = previous_state_payload.get("phase_results", {})
        if isinstance(candidate_previous_results, dict):
            previous_phase_results = candidate_previous_results

    phase_results: dict[str, dict[str, Any]] = {}
    phase_status: dict[str, str] = {}
    resumed_phases: list[str] = []
    rerun_from_phase = ""
    force_rerun_downstream = False

    def _persist_in_progress_state() -> None:
        write_json_atomic(
            cycle_state_path,
            {
                "iteration_id": normalized_iteration_id,
                "status": "in_progress",
                "recovery": {
                    "interrupted_cycle_recovered": recovering_interrupted_cycle,
                    "partial_resume_applied": bool(resumed_phases),
                    "resumed_phases": list(resumed_phases),
                    "rerun_from_phase": rerun_from_phase,
                },
                "stale_detection": {
                    "detected": stale_detected,
                    "reasons": stale_reasons,
                    "safe_refresh_applied": stale_refreshed,
                },
                "phase_status": dict(phase_status),
                "phase_results": phase_results,
            },
        )

    phase_plan: list[tuple[str, Any]] = [
        ("discovery", lambda: run_knowledge_expansion_phase_l(root, mode=mode)),
        ("experimental_specs", lambda: run_knowledge_expansion_phase_b(root)),
        ("sandbox_generation", lambda: run_knowledge_expansion_phase_c(root)),
        (
            "replay_judgment",
            lambda: run_knowledge_expansion_phase_d(
                root,
                mode=mode,
                baseline_summary=baseline_summary,
                replay_scope=replay_scope,
            ),
        ),
        ("promotion_governance", lambda: run_knowledge_expansion_phase_e(root, mode=mode)),
        ("execution_governance", lambda: run_knowledge_expansion_phase_f(root, mode=mode)),
        ("decision_orchestration", lambda: run_knowledge_expansion_phase_g(root, mode=mode)),
        ("execution_supervision", lambda: run_knowledge_expansion_phase_h(root, mode=mode)),
        ("adaptive_portfolio", lambda: run_knowledge_expansion_phase_i(root, mode=mode)),
        ("incident_control", lambda: run_knowledge_expansion_phase_j(root, mode=mode)),
        ("long_horizon_memory", lambda: run_knowledge_expansion_phase_k(root, mode=mode)),
    ]

    for phase_name, runner in phase_plan:
        previous_phase_result = previous_phase_results.get(phase_name)
        if (
            recovering_interrupted_cycle
            and not force_rerun_downstream
            and _phase_result_safe_to_resume(phase_name, previous_phase_result)
        ):
            phase_results[phase_name] = previous_phase_result
            phase_status[phase_name] = "resumed"
            resumed_phases.append(phase_name)
            _persist_in_progress_state()
            continue

        if recovering_interrupted_cycle and not rerun_from_phase:
            rerun_from_phase = phase_name
        force_rerun_downstream = force_rerun_downstream or recovering_interrupted_cycle
        phase_results[phase_name] = runner()
        phase_status[phase_name] = "completed"
        _persist_in_progress_state()

    discovery = phase_results["discovery"]
    experimental_specs = phase_results["experimental_specs"]
    sandbox = phase_results["sandbox_generation"]
    replay_judgment = phase_results["replay_judgment"]
    promotion_governance = phase_results["promotion_governance"]
    execution_governance = phase_results["execution_governance"]
    decision_orchestration = phase_results["decision_orchestration"]
    execution_supervision = phase_results["execution_supervision"]
    adaptive_portfolio = phase_results["adaptive_portfolio"]
    incident_control = phase_results["incident_control"]
    long_horizon_memory = phase_results["long_horizon_memory"]

    replay_candidate_ids = _artifact_candidate_ids(replay_judgment.get("sandbox_judgments", []))
    promotion_candidate_ids = _artifact_candidate_ids(promotion_governance.get("promotion_governance_artifacts", []))
    execution_candidate_ids = _artifact_candidate_ids(
        execution_governance.get("execution_governance_artifacts", [])
    )
    promotion_registry_path = Path(str(promotion_governance.get("promotion_registry_path", "")))
    execution_registry_path = Path(str(execution_governance.get("controlled_execution_registry_path", "")))
    promotion_registry_candidates = _load_registry_candidate_ids(
        promotion_registry_path,
        "governance_records",
    )
    execution_registry_candidates = _load_registry_candidate_ids(
        execution_registry_path,
        "execution_records",
    )
    phase_registry_consistency = {
        "replay_to_promotion_artifacts_match": replay_candidate_ids == promotion_candidate_ids,
        "promotion_to_execution_artifacts_match": promotion_candidate_ids == execution_candidate_ids,
        "promotion_artifacts_in_registry": promotion_candidate_ids.issubset(promotion_registry_candidates),
        "execution_artifacts_in_registry": execution_candidate_ids.issubset(execution_registry_candidates),
        "candidate_counts": {
            "replay_judgment": len(replay_candidate_ids),
            "promotion_governance": len(promotion_candidate_ids),
            "execution_governance": len(execution_candidate_ids),
        },
    }
    phase_registry_consistency["all_checks_passed"] = all(
        bool(value)
        for key, value in phase_registry_consistency.items()
        if key not in {"candidate_counts"}
    )

    cross_phase_anomaly_detection = _decision_chain_anomaly_report(
        replay_judgment.get("sandbox_judgments", []),
        promotion_governance.get("promotion_governance_artifacts", []),
        execution_governance.get("execution_governance_artifacts", []),
    )
    replay_governance_traceability = _replay_governance_traceability_report(
        replay_judgment.get("sandbox_judgments", []),
        promotion_governance.get("promotion_governance_artifacts", []),
        execution_governance.get("execution_governance_artifacts", []),
    )
    rollback_trigger_reasons: list[str] = []
    if cross_phase_anomaly_detection.get("has_anomalies", False):
        rollback_trigger_reasons.append("cross_phase_decision_chain_anomaly_detected")
    if replay_governance_traceability.get("has_issues", False):
        rollback_trigger_reasons.append("replay_to_governance_traceability_failed")
    if not phase_registry_consistency.get("all_checks_passed", False):
        rollback_trigger_reasons.append("cross_phase_registry_consistency_failed")

    rollback_candidates = set(cross_phase_anomaly_detection.get("invalid_candidate_ids", []))
    rollback_candidates.update(replay_governance_traceability.get("invalid_candidate_ids", []))
    end_to_end_governance_chain = _end_to_end_governance_chain_report(root=root, phase_results=phase_results)
    if not end_to_end_governance_chain.get("all_checks_passed", False):
        rollback_trigger_reasons.append("end_to_end_governance_chain_failed")
    rollback_candidates.update(end_to_end_governance_chain.get("invalid_candidate_ids", []))
    governed_rollback = _apply_governed_rollback_for_invalid_downstream_chain(
        execution_governance=execution_governance,
        invalid_candidate_ids=rollback_candidates if rollback_trigger_reasons else set(),
        cycle_dir=cycle_dir,
        iteration_id=normalized_iteration_id,
        trigger_reasons=rollback_trigger_reasons,
    )

    artifact_integrity = {
        "discovery": _artifact_integrity_report(discovery.get("advanced_discovery_artifacts", [])),
        "sandbox_generation": _artifact_integrity_report(sandbox.get("sandbox_module_artifacts", [])),
        "replay_judgment": _artifact_integrity_report(replay_judgment.get("sandbox_judgments", [])),
        "promotion_governance": _artifact_integrity_report(
            promotion_governance.get("promotion_governance_artifacts", [])
        ),
        "execution_governance": _artifact_integrity_report(
            execution_governance.get("execution_governance_artifacts", [])
        ),
        "decision_orchestration": _artifact_integrity_report(
            decision_orchestration.get("decision_artifacts", [])
        ),
        "execution_supervision": _artifact_integrity_report(
            execution_supervision.get("supervision_artifacts", [])
        ),
        "adaptive_portfolio": _artifact_integrity_report(adaptive_portfolio.get("portfolio_artifacts", [])),
        "incident_control": _artifact_integrity_report(incident_control.get("incident_artifacts", [])),
        "long_horizon_memory": _artifact_integrity_report(
            long_horizon_memory.get("long_horizon_memory_artifacts", [])
        ),
    }
    artifact_integrity["all_checks_passed"] = all(
        bool(item.get("all_present", False)) and bool(item.get("all_parse_ok", False))
        for phase_name, item in artifact_integrity.items()
        if phase_name != "all_checks_passed" and isinstance(item, dict)
    )

    phase_artifact_digests = {
        "discovery": _artifact_digests(discovery.get("advanced_discovery_artifacts", [])),
        "sandbox_generation": _artifact_digests(sandbox.get("sandbox_module_artifacts", [])),
        "replay_judgment": _artifact_digests(replay_judgment.get("sandbox_judgments", [])),
        "promotion_governance": _artifact_digests(
            promotion_governance.get("promotion_governance_artifacts", [])
        ),
        "execution_governance": _artifact_digests(
            execution_governance.get("execution_governance_artifacts", [])
        ),
        "decision_orchestration": _artifact_digests(decision_orchestration.get("decision_artifacts", [])),
        "execution_supervision": _artifact_digests(execution_supervision.get("supervision_artifacts", [])),
        "adaptive_portfolio": _artifact_digests(adaptive_portfolio.get("portfolio_artifacts", [])),
        "incident_control": _artifact_digests(incident_control.get("incident_artifacts", [])),
        "long_horizon_memory": _artifact_digests(long_horizon_memory.get("long_horizon_memory_artifacts", [])),
    }
    cycle_signature = _deterministic_payload_digest(
        {
            "iteration_id": normalized_iteration_id,
            "mode": str(mode).lower(),
            "replay_scope": replay_scope,
            "phase_artifact_digests": phase_artifact_digests,
            "artifact_integrity": artifact_integrity,
            "phase_registry_consistency": phase_registry_consistency,
        }
    )

    live_flags: list[bool] = []
    for artifact_path in execution_governance.get("execution_governance_artifacts", []):
        artifact_payload = read_json_safe(Path(artifact_path), default={})
        if isinstance(artifact_payload, dict):
            live_flags.append(bool(artifact_payload.get("live_activation_allowed", False)))
    live_activation_blocked = not any(live_flags)
    if governed_rollback.get("triggered", False):
        live_activation_blocked = True
    invalid_artifact_quarantine = _quarantine_invalid_artifacts(
        cycle_dir=cycle_dir,
        iteration_id=normalized_iteration_id,
        artifact_integrity=artifact_integrity,
        end_to_end_governance_chain=end_to_end_governance_chain,
    )
    governed_refusal = _governed_refusal_state(
        end_to_end_governance_chain=end_to_end_governance_chain,
        invalid_artifact_quarantine=invalid_artifact_quarantine,
        governed_rollback=governed_rollback,
    )
    if governed_refusal.get("refused", False):
        live_activation_blocked = True
    feedback_outcomes = read_json_safe(root / "memory" / "trade_outcomes.json", default=[])
    if not isinstance(feedback_outcomes, list):
        feedback_outcomes = []
    live_learning_feedback = process_live_trade_feedback(
        memory_root=root / "memory",
        trade_outcomes=feedback_outcomes,
        feature_contributors={},
        replay_scope=replay_scope,
    )
    evolution_parameter_control = _update_evolution_parameter_control(
        cycle_dir=cycle_dir,
        iteration_id=normalized_iteration_id,
        baseline_summary=baseline_summary,
        replay_scope=replay_scope,
        replay_paths=replay_judgment.get("sandbox_judgments", []),
        promotion_paths=promotion_governance.get("promotion_governance_artifacts", []),
        execution_paths=execution_governance.get("execution_governance_artifacts", []),
        live_learning_feedback=live_learning_feedback,
        governed_rollback=governed_rollback,
        governed_refusal=governed_refusal,
    )
    mutation_candidates_path = Path(str(live_learning_feedback.get("paths", {}).get("mutation_candidates", "")))
    mutation_candidate_payload = read_json_safe(mutation_candidates_path, default={"mutation_candidates": []})
    if not isinstance(mutation_candidate_payload, dict):
        mutation_candidate_payload = {"mutation_candidates": []}
    mutation_candidates = mutation_candidate_payload.get("mutation_candidates", [])
    if not isinstance(mutation_candidates, list):
        mutation_candidates = []
    self_evolving_indicator = run_self_evolving_indicator_layer(
        memory_root=root / "memory",
        trade_outcomes=feedback_outcomes,
        market_state={
            "structure_state": str(baseline_summary.get("structure_state", "range")) if isinstance(baseline_summary, dict) else "range",
            "volatility_ratio": _to_float(
                baseline_summary.get("volatility_ratio", 1.0) if isinstance(baseline_summary, dict) else 1.0,
                default=1.0,
            ),
            "spread_ratio": 1.0 if not governed_refusal.get("refused", False) else _SPREAD_RATIO_ON_GOVERNED_REFUSAL,
            "slippage_ratio": (
                1.0 if not governed_rollback.get("triggered", False) else _SLIPPAGE_RATIO_ON_GOVERNED_ROLLBACK
            ),
            "stale_price_data": not bool(artifact_integrity.get("all_checks_passed", False)),
            "mt5_ready": not bool(governed_refusal.get("refused", False)),
            "recent_setup_confidence": _to_float(
                baseline_summary.get("confidence", 0.5) if isinstance(baseline_summary, dict) else 0.5,
                default=0.5,
            ),
            "base_signal_confidence": _to_float(
                baseline_summary.get("confidence", 0.5) if isinstance(baseline_summary, dict) else 0.5,
                default=0.5,
            ),
            "base_risk_size": 1.0,
        },
        feature_contributors={},
        mutation_candidates=mutation_candidates,
        replay_scope=replay_scope,
    )
    autonomous_behavior = self_evolving_indicator.get("autonomous_behavior_layer", {})
    if not isinstance(autonomous_behavior, dict):
        autonomous_behavior = {}
    if autonomous_behavior.get("continuous_survival_loop", {}).get("decision") == "pause":
        live_activation_blocked = True

    cycle_payload = {
        "iteration_id": normalized_iteration_id,
        "mode": str(mode).lower(),
        "replay_scope": replay_scope,
        "cycle_signature": cycle_signature,
        "live_activation_blocked": live_activation_blocked,
        "phase_artifact_digests": phase_artifact_digests,
        "artifact_integrity": artifact_integrity,
        "phase_registry_consistency": phase_registry_consistency,
        "end_to_end_governance_chain": end_to_end_governance_chain,
        "cross_phase_anomaly_detection": cross_phase_anomaly_detection,
        "replay_governance_traceability": replay_governance_traceability,
        "governed_rollback": governed_rollback,
        "invalid_artifact_quarantine": invalid_artifact_quarantine,
        "governed_refusal": governed_refusal,
        "live_learning_feedback": live_learning_feedback,
        "evolution_parameter_control": evolution_parameter_control,
        "autonomous_behavior_layer": autonomous_behavior,
        "self_evolving_indicator_layer": self_evolving_indicator,
        "cycle_recovery": {
            "interrupted_cycle_recovered": recovering_interrupted_cycle,
            "stale_artifacts_detected": stale_detected,
            "safe_refresh_applied": stale_refreshed,
            "partial_resume_applied": bool(resumed_phases),
            "resumed_phases": resumed_phases,
            "rerun_from_phase": rerun_from_phase,
        },
        "stale_artifact_reasons": stale_reasons,
        "phase_counts": {
            "discovery": int(discovery.get("advanced_discovery_count", 0)),
            "sandbox_generation": int(sandbox.get("sandbox_module_count", 0)),
            "replay_judgment": int(replay_judgment.get("sandbox_judgment_count", 0)),
            "promotion_governance": int(promotion_governance.get("governance_artifact_count", 0)),
            "execution_governance": int(execution_governance.get("execution_governance_artifact_count", 0)),
            "decision_orchestration": int(decision_orchestration.get("decision_artifact_count", 0)),
            "execution_supervision": int(execution_supervision.get("supervision_artifact_count", 0)),
            "adaptive_portfolio": int(adaptive_portfolio.get("portfolio_artifact_count", 0)),
            "incident_control": int(incident_control.get("incident_artifact_count", 0)),
            "long_horizon_memory": int(long_horizon_memory.get("long_horizon_memory_count", 0)),
        },
        "registry_paths": {
            "advanced_discovery": str(discovery.get("advanced_discovery_registry_path", "")),
            "promotion_governance": str(promotion_governance.get("promotion_registry_path", "")),
            "execution_governance": str(execution_governance.get("controlled_execution_registry_path", "")),
            "decision_orchestration": str(decision_orchestration.get("decision_registry_path", "")),
            "execution_supervision": str(execution_supervision.get("supervision_registry_path", "")),
            "adaptive_portfolio": str(adaptive_portfolio.get("portfolio_registry_path", "")),
            "incident_control": str(incident_control.get("incident_registry_path", "")),
            "long_horizon_memory": str(long_horizon_memory.get("long_horizon_memory_registry_path", "")),
        },
    }
    self_audit_artifact = _write_cycle_self_audit_artifact(
        cycle_dir=cycle_dir,
        iteration_id=normalized_iteration_id,
        cycle_payload=cycle_payload,
    )
    cycle_payload["self_audit_artifact"] = self_audit_artifact

    write_json_atomic(cycle_artifact_path, cycle_payload)

    registry_path = cycle_dir / "continuous_governed_improvement_registry.json"
    registry_payload = read_json_safe(registry_path, default={"cycles": []})
    if not isinstance(registry_payload, dict):
        registry_payload = {"cycles": []}
    cycles = registry_payload.get("cycles", [])
    if not isinstance(cycles, list):
        cycles = []
    cycles_by_iteration: dict[str, dict[str, Any]] = {}
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        existing_iteration_id = str(cycle.get("iteration_id", "")).strip()
        if not existing_iteration_id:
            continue
        cycles_by_iteration[existing_iteration_id] = cycle
    cycles_by_iteration[normalized_iteration_id] = {
        "iteration_id": normalized_iteration_id,
        "cycle_signature": cycle_signature,
        "cycle_artifact_path": str(cycle_artifact_path),
        "live_activation_blocked": live_activation_blocked,
    }
    registry_payload = {
        "cycles": [cycles_by_iteration[cycle_id] for cycle_id in sorted(cycles_by_iteration)],
    }
    write_json_atomic(registry_path, registry_payload)
    write_json_atomic(
        cycle_state_path,
        {
            "iteration_id": normalized_iteration_id,
            "status": (
                "refused_unsafe_continuation"
                if bool(governed_refusal.get("refused", False))
                else "completed"
            ),
            "cycle_signature": cycle_signature,
            "recovery": {"interrupted_cycle_recovered": recovering_interrupted_cycle},
            "stale_detection": {
                "detected": stale_detected,
                "reasons": stale_reasons,
                "safe_refresh_applied": stale_refreshed,
            },
            "partial_resume": {
                "applied": bool(resumed_phases),
                "resumed_phases": resumed_phases,
                "rerun_from_phase": rerun_from_phase,
            },
            "governed_rollback": governed_rollback,
            "governed_refusal": governed_refusal,
            "self_audit_artifact": self_audit_artifact,
            "phase_status": phase_status,
            "phase_results": phase_results,
            "live_activation_blocked": live_activation_blocked,
        },
    )

    return {
        "continuous_governed_improvement_enabled": str(mode).lower() == "replay",
        "iteration_id": normalized_iteration_id,
        "cycle_signature": cycle_signature,
        "cycle_artifact_path": str(cycle_artifact_path),
        "cycle_registry_path": str(registry_path),
        "cycle_state_path": str(cycle_state_path),
        "live_activation_blocked": live_activation_blocked,
        "artifact_integrity": artifact_integrity,
        "phase_registry_consistency": phase_registry_consistency,
        "end_to_end_governance_chain": end_to_end_governance_chain,
        "cross_phase_anomaly_detection": cross_phase_anomaly_detection,
        "replay_governance_traceability": replay_governance_traceability,
        "governed_rollback": governed_rollback,
        "invalid_artifact_quarantine": invalid_artifact_quarantine,
        "governed_refusal": governed_refusal,
        "live_learning_feedback": live_learning_feedback,
        "evolution_parameter_control": evolution_parameter_control,
        "autonomous_behavior_layer": autonomous_behavior,
        "self_evolving_indicator_layer": self_evolving_indicator,
        "self_audit_artifact": self_audit_artifact,
        "cycle_recovery": cycle_payload["cycle_recovery"],
        "phase_results": phase_results,
    }
