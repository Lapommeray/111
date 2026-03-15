from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.utils import clamp, normalize_reasons, read_json_safe, write_json_atomic

_MAX_FEEDBACK_OUTCOMES = 200
_MAX_MUTATION_CANDIDATES = 200
_MIN_MUTATION_SCORE = 0.35
_FEEDBACK_RETENTION_DAYS = 30


def _evaluate_trade(outcome: dict[str, Any]) -> dict[str, Any]:
    result = str(outcome.get("result", "unknown")).lower()
    pnl_points = float(outcome.get("pnl_points", 0.0))
    quality = "positive" if result == "win" else "negative" if result == "loss" else "neutral"
    return {
        "trade_id": str(outcome.get("trade_id", "")),
        "result": result,
        "pnl_points": pnl_points,
        "quality": quality,
    }


def _attribute_features(
    *,
    feature_contributors: dict[str, float],
    trade_evaluation: dict[str, Any],
) -> dict[str, float]:
    direction = 1.0 if trade_evaluation.get("quality") == "positive" else -1.0 if trade_evaluation.get("quality") == "negative" else 0.0
    return {
        feature_name: round(clamp(float(score) * direction, -1.0, 1.0), 4)
        for feature_name, score in sorted(feature_contributors.items())
    }


def _mutation_score(*, evaluation: dict[str, Any], weak_features: list[str]) -> float:
    result = str(evaluation.get("result", "unknown")).lower()
    pnl_points = float(evaluation.get("pnl_points", 0.0))
    if result == "win":
        result_score = 1.0
    elif result == "flat":
        result_score = 0.5
    elif result == "loss":
        result_score = 0.0
    else:
        result_score = 0.3
    pnl_score = clamp((pnl_points + 2.0) / 4.0, 0.0, 1.0)
    weak_penalty = min(0.4, len(weak_features) * 0.1)
    return round(clamp((result_score * 0.6) + (pnl_score * 0.4) - weak_penalty, 0.0, 1.0), 4)


def _prune_trade_outcomes(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not outcomes:
        return []
    tail = outcomes[-20:]
    retained: list[dict[str, Any]] = []
    for outcome in outcomes:
        result = str(outcome.get("result", "")).lower()
        pnl_points = float(outcome.get("pnl_points", 0.0))
        usefulness = abs(pnl_points) + (0.4 if result in {"win", "loss"} else 0.0)
        if usefulness >= 0.45 or outcome in tail:
            retained.append(outcome)
    return retained[-_MAX_FEEDBACK_OUTCOMES:]


def _prune_mutation_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        governance = candidate.get("governance", {})
        if not isinstance(governance, dict):
            governance = {}
        promotion_state = str(governance.get("promotion_state", "pending")).lower()
        score = float(candidate.get("mutation_score", 0.0))
        if promotion_state == "quarantined":
            continue
        if score < _MIN_MUTATION_SCORE:
            continue
        retained.append(candidate)
    retained.sort(key=_candidate_rank, reverse=True)
    return retained[:_MAX_MUTATION_CANDIDATES]


def _candidate_rank(candidate: dict[str, Any]) -> tuple[float, str]:
    return float(candidate.get("mutation_score", 0.0)), str(candidate.get("candidate_id", ""))


def _cleanup_feedback_artifacts(feedback_root: Path, *, protected_files: set[str]) -> list[str]:
    deleted: list[str] = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_FEEDBACK_RETENTION_DAYS)
    for artifact in feedback_root.glob("*.json"):
        if artifact.name in protected_files:
            continue
        try:
            stat = artifact.stat()
        except OSError:
            continue
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if modified_at < cutoff or stat.st_size == 0:
            try:
                artifact.unlink()
                deleted.append(str(artifact))
            except OSError:
                continue
    return deleted


def process_live_trade_feedback(
    *,
    memory_root: Path,
    trade_outcomes: list[dict[str, Any]],
    feature_contributors: dict[str, float],
    replay_scope: str = "full_replay",
) -> dict[str, Any]:
    feedback_root = memory_root / "live_trade_feedback"
    feedback_root.mkdir(parents=True, exist_ok=True)
    outcomes_path = feedback_root / "trade_outcomes.json"
    attribution_path = feedback_root / "feature_attribution.json"
    candidates_path = feedback_root / "mutation_candidates.json"
    deleted_artifacts = _cleanup_feedback_artifacts(
        feedback_root,
        protected_files={outcomes_path.name, attribution_path.name, candidates_path.name},
    )

    closed = [outcome for outcome in trade_outcomes if str(outcome.get("status", "")).lower() == "closed"]
    latest = closed[-1] if closed else {}
    evaluation = _evaluate_trade(latest) if latest else {"trade_id": "", "quality": "neutral", "result": "unknown", "pnl_points": 0.0}
    attribution = _attribute_features(
        feature_contributors=feature_contributors,
        trade_evaluation=evaluation,
    )

    sorted_attribution = sorted(attribution.items(), key=lambda item: (item[1], item[0]))
    weak_features = [name for name, score in sorted_attribution if score < -0.2]
    candidate_payload = {
        "trade_id": evaluation.get("trade_id", ""),
        "weak_features": weak_features,
        "replay_scope": replay_scope,
    }
    candidate_id = sha256(json.dumps(candidate_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    replay_validation_passed = bool(weak_features) and str(evaluation.get("result", "")) != "loss"
    unsafe_mutation = str(evaluation.get("result", "")) == "loss" and bool(weak_features)
    promotion_state = "promoted" if replay_validation_passed else "quarantined" if unsafe_mutation else "pending"
    mutation_score = _mutation_score(evaluation=evaluation, weak_features=weak_features)
    mutation_candidate = {
        "candidate_id": candidate_id,
        "trade_id": evaluation.get("trade_id", ""),
        "mutation_type": "feature_weight_adjustment",
        "weak_features": weak_features,
        "mutation_score": mutation_score,
        "replay_validation": {
            "required": True,
            "scope": replay_scope,
            "passed": replay_validation_passed,
        },
        "governance": {
            "promotion_state": promotion_state,
            "quarantine_required": unsafe_mutation,
            "refusal_reasons": normalize_reasons(
                ["unsafe_mutation_detected"] if unsafe_mutation else ["replay_validation_pending"] if not replay_validation_passed else []
            ),
        },
    }

    write_json_atomic(outcomes_path, {"trade_outcomes": _prune_trade_outcomes(closed)})
    write_json_atomic(
        attribution_path,
        {
            "latest_trade_evaluation": evaluation,
            "feature_attribution": attribution,
        },
    )

    candidate_state = read_json_safe(candidates_path, default={"mutation_candidates": []})
    if not isinstance(candidate_state, dict):
        candidate_state = {"mutation_candidates": []}
    historical_candidates = candidate_state.get("mutation_candidates", [])
    if not isinstance(historical_candidates, list):
        historical_candidates = []
    historical_candidates = [c for c in historical_candidates if str(c.get("candidate_id", "")) != candidate_id]
    historical_candidates.append(mutation_candidate)
    write_json_atomic(candidates_path, {"mutation_candidates": _prune_mutation_candidates(historical_candidates)})

    return {
        "latest_trade_evaluation": evaluation,
        "feature_attribution": attribution,
        "mutation_candidate": mutation_candidate,
        "cleanup": {"deleted_artifacts": deleted_artifacts},
        "paths": {
            "trade_outcomes": str(outcomes_path),
            "feature_attribution": str(attribution_path),
            "mutation_candidates": str(candidates_path),
        },
    }
