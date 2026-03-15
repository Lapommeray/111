from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Callable

from src.evaluation.blocker_effect_report import build_blocker_effect_report
from src.evaluation.module_contribution_report import build_module_contribution_report
from src.evaluation.session_report import build_session_report


PipelineRunner = Callable[[Any], dict[str, Any]]
ConfigFactory = Callable[..., Any]


def evaluate_replay(
    pipeline_runner: PipelineRunner,
    config_factory: ConfigFactory,
    *,
    symbol: str,
    timeframe: str,
    bars: int,
    replay_csv_path: str,
    sample_path: str,
    memory_root: str,
    generated_registry_path: str,
    meta_adaptive_profile_path: str,
    evolution_enabled: bool,
    evolution_registry_path: str,
    evolution_artifact_root: str,
    evolution_max_proposals: int,
    compact_output: bool,
    evaluation_steps: int,
    evaluation_stride: int,
    knowledge_expansion_enabled: bool = False,
    knowledge_expansion_root: str = "memory/knowledge_expansion",
    knowledge_candidate_limit: int = 6,
) -> dict[str, Any]:
    """Run replay evaluation using the existing replay pipeline path only."""
    rows = _load_rows(Path(replay_csv_path))
    if len(rows) < bars:
        raise ValueError("Replay evaluation requires at least `bars` rows.")

    start_index = bars
    max_steps_available = max(0, ((len(rows) - start_index) // max(1, evaluation_stride)) + 1)
    steps = min(evaluation_steps, max_steps_available)

    records: list[dict[str, Any]] = []

    for step in range(steps):
        end = start_index + (step * evaluation_stride)
        window = rows[:end]
        temp_csv = Path(memory_root) / f"evaluation_window_{step + 1}.csv"
        _write_rows(temp_csv, window)

        cfg = config_factory(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            sample_path=sample_path,
            memory_root=memory_root,
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(temp_csv),
            generated_registry_path=generated_registry_path,
            meta_adaptive_profile_path=meta_adaptive_profile_path,
            evolution_enabled=evolution_enabled,
            evolution_registry_path=evolution_registry_path,
            evolution_artifact_root=evolution_artifact_root,
            evolution_max_proposals=evolution_max_proposals,
            compact_output=False,
        )
        result = pipeline_runner(cfg)
        result["evaluation_step"] = step + 1
        records.append(result)

    signal_counts = {
        "total": len(records),
        "blocked": sum(1 for r in records if bool(r.get("signal", {}).get("blocked", False))),
    }
    action_distribution = _action_distribution(records)
    confidence_distribution = _confidence_distribution(records)

    return {
        "symbol": symbol,
        "mode": "replay_evaluation",
        "steps": len(records),
        "signal_counts": signal_counts,
        "action_distribution": action_distribution,
        "confidence_distribution": confidence_distribution,
        "blocker_effect_report": build_blocker_effect_report(records),
        "module_contribution_report": build_module_contribution_report(records),
        "session_report": build_session_report(records),
        "records": records,
        "knowledge_expansion_config": {
            "enabled": knowledge_expansion_enabled,
            "root": knowledge_expansion_root,
            "candidate_limit": knowledge_candidate_limit,
        },
    }


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Replay CSV not found for evaluation: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Cannot write empty evaluation window.")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _action_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    dist = {"BUY": 0, "SELL": 0, "WAIT": 0}
    for record in records:
        action = str(record.get("signal", {}).get("action", "WAIT"))
        if action not in dist:
            action = "WAIT"
        dist[action] += 1
    return dist


def _confidence_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    bins = {"low": 0, "medium": 0, "high": 0}
    for record in records:
        confidence = float(record.get("signal", {}).get("confidence", 0.0))
        if confidence < 0.5:
            bins["low"] += 1
        elif confidence < 0.75:
            bins["medium"] += 1
        else:
            bins["high"] += 1
    return bins
