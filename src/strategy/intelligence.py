from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.utils import clamp, read_json_safe, write_json_atomic


def _feature_score(feature_payload: dict[str, Any]) -> float:
    confidence_delta = float(feature_payload.get("confidence_delta", 0.0))
    blocked = bool(feature_payload.get("blocked", False))
    direction_vote = str(feature_payload.get("direction_vote", "neutral")).lower()
    directional_bias = 0.04 if direction_vote in {"buy", "sell"} else 0.0
    score = 0.5 + confidence_delta + directional_bias - (0.25 if blocked else 0.0)
    return round(clamp(score, 0.0, 1.0), 4)


def _closed_outcomes(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in outcomes if str(item.get("status", "")).lower() == "closed"]


def score_signal_intelligence(
    *,
    memory_root: str,
    symbol: str,
    decision: str,
    base_confidence: float,
    module_results: dict[str, dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    strategy_root = Path(memory_root) / "strategy_intelligence"
    strategy_root.mkdir(parents=True, exist_ok=True)
    quality_path = strategy_root / "signal_quality_registry.json"
    feature_path = strategy_root / "signal_feature_scores.json"
    confidence_path = strategy_root / "strategy_confidence_state.json"

    contributors = {
        name: _feature_score(payload)
        for name, payload in sorted(module_results.items())
        if isinstance(payload, dict)
    }
    signal_score = round(sum(contributors.values()) / len(contributors), 4) if contributors else 0.0

    directional_votes = [
        str(payload.get("direction_vote", "neutral")).lower()
        for payload in module_results.values()
        if isinstance(payload, dict)
    ]
    confirmation_count = sum(1 for vote in directional_votes if vote == str(decision).lower())
    confirmation_ratio = round(
        confirmation_count / max(1, len(directional_votes)),
        4,
    )

    closed = _closed_outcomes(outcomes)
    wins = sum(1 for item in closed if str(item.get("result", "")).lower() == "win")
    win_rate = round(wins / len(closed), 4) if closed else 0.5
    adaptive_weight = round(clamp(0.5 + ((win_rate - 0.5) * 0.6), 0.2, 0.8), 4)
    confidence = round(
        clamp(
            (base_confidence * adaptive_weight)
            + (signal_score * (1.0 - adaptive_weight) * 0.7)
            + (confirmation_ratio * 0.3),
            0.0,
            1.0,
        ),
        4,
    )

    signal_key_payload = {
        "symbol": symbol,
        "decision": decision,
        "signal_score": signal_score,
        "confidence": confidence,
        "confirmation_ratio": confirmation_ratio,
        "contributors": contributors,
    }
    signal_id = sha256(json.dumps(signal_key_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    quality_registry = read_json_safe(quality_path, default={"signals": []})
    if not isinstance(quality_registry, dict):
        quality_registry = {"signals": []}
    historical_signals = quality_registry.get("signals", [])
    if not isinstance(historical_signals, list):
        historical_signals = []
    filtered_signals = [s for s in historical_signals if str(s.get("signal_id", "")) != signal_id]
    filtered_signals.append(
        {
            "signal_id": signal_id,
            "symbol": symbol,
            "decision": decision,
            "signal_score": signal_score,
            "confidence": confidence,
            "confirmation_ratio": confirmation_ratio,
            "feature_contributors": contributors,
            "outcome_attribution": {
                "closed_outcomes": len(closed),
                "win_rate": win_rate,
            },
        }
    )
    write_json_atomic(quality_path, {"signals": filtered_signals[-200:]})

    feature_state = read_json_safe(feature_path, default={"feature_scores": {}})
    if not isinstance(feature_state, dict):
        feature_state = {"feature_scores": {}}
    historical_feature_scores = feature_state.get("feature_scores", {})
    if not isinstance(historical_feature_scores, dict):
        historical_feature_scores = {}
    for feature_name, feature_score in contributors.items():
        previous = historical_feature_scores.get(feature_name, {"running_score": feature_score, "samples": 0})
        previous_score = float(previous.get("running_score", feature_score))
        previous_samples = int(previous.get("samples", 0))
        updated_samples = previous_samples + 1
        running_score = round(((previous_score * previous_samples) + feature_score) / updated_samples, 4)
        historical_feature_scores[feature_name] = {
            "running_score": running_score,
            "samples": updated_samples,
        }
    write_json_atomic(feature_path, {"feature_scores": historical_feature_scores})

    confidence_state = {
        "symbol": symbol,
        "adaptive_weight": adaptive_weight,
        "win_rate": win_rate,
        "confirmation_ratio": confirmation_ratio,
        "latest_signal_id": signal_id,
        "latest_signal_score": signal_score,
        "latest_confidence": confidence,
    }
    write_json_atomic(confidence_path, confidence_state)

    return {
        "signal_id": signal_id,
        "signal_score": signal_score,
        "confidence": confidence,
        "feature_contributors": contributors,
        "paths": {
            "signal_quality_registry": str(quality_path),
            "signal_feature_scores": str(feature_path),
            "strategy_confidence_state": str(confidence_path),
        },
    }
