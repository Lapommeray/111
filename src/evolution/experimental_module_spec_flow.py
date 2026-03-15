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
