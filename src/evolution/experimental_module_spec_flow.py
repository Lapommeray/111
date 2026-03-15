from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from src.utils import read_json_safe, write_json_atomic


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
    return True


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
    write_json_atomic(
        cycle_state_path,
        {
            "iteration_id": normalized_iteration_id,
            "status": "in_progress",
            "recovery": {"interrupted_cycle_recovered": recovering_interrupted_cycle},
            "stale_detection": {
                "detected": stale_detected,
                "reasons": stale_reasons,
                "safe_refresh_applied": stale_refreshed,
            },
        },
    )

    discovery = run_knowledge_expansion_phase_l(root, mode=mode)
    experimental_specs = run_knowledge_expansion_phase_b(root)
    sandbox = run_knowledge_expansion_phase_c(root)
    replay_judgment = run_knowledge_expansion_phase_d(
        root,
        mode=mode,
        baseline_summary=baseline_summary,
        replay_scope=replay_scope,
    )
    promotion_governance = run_knowledge_expansion_phase_e(root, mode=mode)
    execution_governance = run_knowledge_expansion_phase_f(root, mode=mode)

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

    cycle_payload = {
        "iteration_id": normalized_iteration_id,
        "mode": str(mode).lower(),
        "replay_scope": replay_scope,
        "cycle_signature": cycle_signature,
        "live_activation_blocked": live_activation_blocked,
        "phase_artifact_digests": phase_artifact_digests,
        "artifact_integrity": artifact_integrity,
        "phase_registry_consistency": phase_registry_consistency,
        "cycle_recovery": {
            "interrupted_cycle_recovered": recovering_interrupted_cycle,
            "stale_artifacts_detected": stale_detected,
            "safe_refresh_applied": stale_refreshed,
        },
        "stale_artifact_reasons": stale_reasons,
        "phase_counts": {
            "discovery": int(discovery.get("advanced_discovery_count", 0)),
            "sandbox_generation": int(sandbox.get("sandbox_module_count", 0)),
            "replay_judgment": int(replay_judgment.get("sandbox_judgment_count", 0)),
            "promotion_governance": int(promotion_governance.get("governance_artifact_count", 0)),
            "execution_governance": int(execution_governance.get("execution_governance_artifact_count", 0)),
        },
        "registry_paths": {
            "advanced_discovery": str(discovery.get("advanced_discovery_registry_path", "")),
            "promotion_governance": str(promotion_governance.get("promotion_registry_path", "")),
            "execution_governance": str(execution_governance.get("controlled_execution_registry_path", "")),
        },
    }

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
            "status": "completed",
            "cycle_signature": cycle_signature,
            "recovery": {"interrupted_cycle_recovered": recovering_interrupted_cycle},
            "stale_detection": {
                "detected": stale_detected,
                "reasons": stale_reasons,
                "safe_refresh_applied": stale_refreshed,
            },
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
        "cycle_recovery": cycle_payload["cycle_recovery"],
        "phase_results": {
            "discovery": discovery,
            "experimental_specs": experimental_specs,
            "sandbox_generation": sandbox,
            "replay_judgment": replay_judgment,
            "promotion_governance": promotion_governance,
            "execution_governance": execution_governance,
        },
    }
