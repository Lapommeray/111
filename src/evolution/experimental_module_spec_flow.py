from __future__ import annotations

from datetime import datetime, timezone
import hashlib
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
    generation_timestamp = datetime.now(tz=timezone.utc).isoformat()

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

        target_name = _safe_candidate_filename(candidate_id)
        if target_name in used_filenames:
            suffix = hashlib.blake2b(candidate_id.encode("utf-8"), digest_size=6).hexdigest()
            target_name = f"{target_name}_{suffix}"
        used_filenames.add(target_name)
        target_path = output_dir / f"{target_name}.json"
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
    judgment_timestamp = datetime.now(tz=timezone.utc).isoformat()
    used_filenames: set[str] = set()
    for candidate_id, module_payload in sorted(deduplicated_by_candidate.items(), key=lambda pair: pair[0]):
        module_name = str(module_payload.get("module_name", f"sandbox_{_safe_candidate_filename(candidate_id)}"))
        module_score = _summary_score(module_payload)
        score_delta = module_score - baseline_score
        effect = _phase_d_effect_from_delta(score_delta)
        decision, decision_reason, promotion_status = _phase_d_decision_from_delta(score_delta)

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

        target_name = _safe_candidate_filename(candidate_id)
        if target_name in used_filenames:
            suffix = hashlib.blake2b(candidate_id.encode("utf-8"), digest_size=6).hexdigest()
            target_name = f"{target_name}_{suffix}"
        used_filenames.add(target_name)
        target_path = output_dir / f"{target_name}.json"
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
