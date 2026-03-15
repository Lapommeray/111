from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evaluation.replay_evaluator import evaluate_replay
from src.evolution.architecture_guard import ArchitectureGuard
from src.evolution.code_generator import CodeGenerator
from src.evolution.duplication_audit import DuplicationAudit
from src.evolution.evolution_registry import EvolutionRegistry
from src.evolution.gap_discovery import GapDiscovery
from src.evolution.promoter import Promoter
from src.evolution.self_inspector import SelfInspector
from src.evolution.verifier import Verifier
from src.evolution.knowledge_expansion_orchestrator import run_knowledge_expansion_phase_a
from src.features.liquidity import assess_liquidity_state
from src.features.market_structure import classify_market_structure
from src.filters.loss_blocker import LossBlocker
from src.indicator.chart_objects import build_chart_objects
from src.indicator.indicator_output import build_indicator_output, build_status_panel
from src.indicator.signal_model import build_signal_output
from src.memory.pattern_store import PatternStore, PatternStoreConfig
from src.memory.self_coder import SelfCoder
from src.memory.tracker import OutcomeTracker
from src.mt5.adapter import MT5Adapter, MT5Config
from src.mt5.execution_state import ExecutionState
from src.mt5.symbol_guard import SymbolGuard
from src.pipeline import OversoulDirector, run_advanced_modules, state_to_dict
from src.scoring.confidence_score import compute_confidence
from src.utils import normalize_reasons, register_generated_artifact


SUPPORTED_TIMEFRAMES = {"M1", "M5", "M15", "H1", "H4"}


@dataclass(frozen=True)
class RuntimeConfig:
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    bars: int = 220
    sample_path: str = "data/samples/xauusd.csv"
    memory_root: str = "memory"
    mode: str = "live"
    replay_source: str = "csv"
    replay_csv_path: str = "data/samples/xauusd.csv"
    generated_registry_path: str = "memory/generated_code_registry.json"
    meta_adaptive_profile_path: str = "memory/meta_adaptive_profile.json"
    evolution_enabled: bool = True
    evolution_registry_path: str = "memory/evolution_registry.json"
    evolution_artifact_root: str = "memory/evolution_artifacts"
    evolution_max_proposals: int = 3
    compact_output: bool = False
    evaluation_steps: int = 30
    evaluation_stride: int = 5
    evaluation_output_path: str = "memory/replay_evaluation_report.json"
    knowledge_expansion_enabled: bool = False
    knowledge_expansion_root: str = "memory/knowledge_expansion"
    knowledge_candidate_limit: int = 6


def ensure_sample_data(path: Path) -> None:
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    base = 2030.0
    for i in range(1, 321):
        if i < 120:
            drift = i * 0.12
        elif i < 220:
            drift = (120 * 0.12) - ((i - 120) * 0.07)
        else:
            drift = (120 * 0.12) - (100 * 0.07) + ((i - 220) * 0.1)

        close = base + drift
        rows.append(
            {
                "time": 1700000000 + i * 60,
                "open": round(close - 0.25, 2),
                "high": round(close + 0.5, 2),
                "low": round(close - 0.55, 2),
                "close": round(close, 2),
                "tick_volume": 120 + (i % 40),
            }
        )

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        writer.writerows(rows)


def load_runtime_config(path: Path) -> RuntimeConfig:
    if not path.exists():
        return RuntimeConfig()
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return RuntimeConfig(
        symbol=str(data.get("symbol", "XAUUSD")),
        timeframe=str(data.get("timeframe", "M5")),
        bars=int(data.get("bars", 220)),
        sample_path=str(data.get("sample_path", "data/samples/xauusd.csv")),
        memory_root=str(data.get("memory_root", "memory")),
        mode=str(data.get("mode", "live")),
        replay_source=str(data.get("replay_source", "csv")),
        replay_csv_path=str(data.get("replay_csv_path", "data/samples/xauusd.csv")),
        generated_registry_path=str(
            data.get("generated_registry_path", "memory/generated_code_registry.json")
        ),
        meta_adaptive_profile_path=str(
            data.get("meta_adaptive_profile_path", "memory/meta_adaptive_profile.json")
        ),
        evolution_enabled=bool(data.get("evolution_enabled", True)),
        evolution_registry_path=str(data.get("evolution_registry_path", "memory/evolution_registry.json")),
        evolution_artifact_root=str(data.get("evolution_artifact_root", "memory/evolution_artifacts")),
        evolution_max_proposals=int(data.get("evolution_max_proposals", 3)),
        compact_output=bool(data.get("compact_output", False)),
        evaluation_steps=int(data.get("evaluation_steps", 30)),
        evaluation_stride=int(data.get("evaluation_stride", 5)),
        evaluation_output_path=str(data.get("evaluation_output_path", "memory/replay_evaluation_report.json")),
        knowledge_expansion_enabled=bool(data.get("knowledge_expansion_enabled", False)),
        knowledge_expansion_root=str(data.get("knowledge_expansion_root", "memory/knowledge_expansion")),
        knowledge_candidate_limit=int(data.get("knowledge_candidate_limit", 6)),
    )


def validate_runtime_config(config: RuntimeConfig) -> None:
    guard_result = SymbolGuard().validate(config.symbol)
    if not guard_result["ready"]:
        raise ValueError("Only XAUUSD is supported in this project stage.")

    if config.timeframe.upper() not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {config.timeframe}")
    if config.bars <= 20:
        raise ValueError("bars must be > 20 for feature calculations")

    Path(config.sample_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.memory_root).mkdir(parents=True, exist_ok=True)
    Path(config.generated_registry_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.meta_adaptive_profile_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.evolution_registry_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.evolution_artifact_root).mkdir(parents=True, exist_ok=True)
    Path(config.evaluation_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.knowledge_expansion_root).mkdir(parents=True, exist_ok=True)

    if config.evaluation_steps <= 0:
        raise ValueError("evaluation_steps must be > 0")
    if config.evaluation_stride <= 0:
        raise ValueError("evaluation_stride must be > 0")


def load_bars_from_csv(csv_path: Path, bars: int) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Replay CSV not found: {csv_path}")
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                {
                    "time": int(row["time"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "tick_volume": float(row.get("tick_volume", 0.0)),
                }
            )
    if not rows:
        raise ValueError(f"Replay CSV is empty: {csv_path}")
    return rows[-bars:]


def load_bars_from_memory(store: PatternStore, bars: int) -> list[dict[str, Any]]:
    payload = store.load("pattern_memory")
    patterns = payload.get("patterns", [])
    if not patterns:
        raise ValueError("No pattern snapshots available for memory replay.")
    snapshot_bars = patterns[-1].get("bars")
    if not snapshot_bars:
        raise ValueError("Latest snapshot has no stored bars for replay.")
    return snapshot_bars[-bars:]


def run_evolution_kernel(config: RuntimeConfig) -> dict[str, Any]:
    if not config.evolution_enabled:
        return {
            "enabled": False,
            "inspection": {},
            "gaps": [],
            "lifecycle": [],
            "status_counts": {
                "proposed": 0,
                "verified": 0,
                "promoted": 0,
                "rejected": 0,
                "archived": 0,
            },
        }

    project_root = Path.cwd()
    generated_registry_path = Path(config.generated_registry_path)
    evolution_registry = EvolutionRegistry(Path(config.evolution_registry_path))

    inspector = SelfInspector(
        project_root=project_root,
        generated_registry_path=generated_registry_path,
        evolution_registry_path=Path(config.evolution_registry_path),
    )
    inspection = inspector.inspect()
    gaps = GapDiscovery().discover(inspection)

    generator = CodeGenerator(Path(config.evolution_artifact_root))
    verifier = Verifier()
    guard = ArchitectureGuard(project_root)
    duplication = DuplicationAudit(project_root)
    promoter = Promoter(evolution_registry)

    lifecycle: list[dict[str, Any]] = []
    for gap in gaps[: config.evolution_max_proposals]:
        generated = generator.generate_proposal(gap)
        artifact_path = Path(generated["artifact_path"])
        proposal = generated["proposal"]

        duplicate_check = duplication.check_proposal(
            artifact_path=artifact_path,
            proposal=proposal,
            existing_registry_entries=evolution_registry.latest(limit=1000),
        )
        validation = verifier.verify(artifact_path, proposal)
        architecture_check = guard.evaluate(proposal, symbol=config.symbol)

        entry = evolution_registry.append_entry(
            gap=gap,
            artifact_path=str(artifact_path),
            artifact_type="code_proposal",
            status="proposed",
            validation=validation,
            duplicate_check={**duplicate_check, "architecture_check": architecture_check},
        )
        promoted = promoter.decide_status(
            entry_id=entry["entry_id"],
            verification=validation,
            duplicate_check=duplicate_check,
            architecture_check=architecture_check,
        )
        lifecycle.append(promoted)

        register_generated_artifact(
            registry_path=generated_registry_path,
            artifact_type="evolution_proposal",
            artifact_path=str(artifact_path),
            metadata={
                "gap_id": gap["gap_id"],
                "validation_passed": validation["passed"],
                "final_status": promoted["status"],
                "symbol": config.symbol,
            },
        )

    return {
        "enabled": True,
        "inspection": inspection,
        "gaps": gaps,
        "lifecycle": lifecycle,
        "status_counts": evolution_registry.count_by_status(),
    }


def _build_compact_signal_payload(signal_payload: dict[str, Any]) -> dict[str, Any]:
    """Return reduced-detail signal payload for downstream consumers when configured."""
    compact = {
        "symbol": signal_payload.get("symbol", "XAUUSD"),
        "action": signal_payload.get("action", "WAIT"),
        "confidence": signal_payload.get("confidence", 0.0),
        "reasons": signal_payload.get("reasons", []),
        "blocked": signal_payload.get("blocked", False),
        "setup_classification": signal_payload.get("setup_classification", "observe"),
        "blocker_reasons": signal_payload.get("blocker_reasons", []),
        "memory_context": signal_payload.get("memory_context", {}),
        "rule_context": signal_payload.get("rule_context", {}),
        "schema_version": signal_payload.get("schema_version", "phase3.v1"),
        "consumer_hints": signal_payload.get("consumer_hints", {}),
        "advanced_modules": {
            "final_direction": signal_payload.get("advanced_modules", {}).get("final_direction", "WAIT"),
            "final_confidence": signal_payload.get("advanced_modules", {}).get("final_confidence", 0.0),
            "module_count": len(signal_payload.get("advanced_modules", {}).get("module_results", {})),
            "ready_count": sum(
                1
                for h in signal_payload.get("advanced_modules", {}).get("module_health", {}).values()
                if bool(h.get("ready", False))
            ),
        },
        "generated_code_visibility": signal_payload.get("generated_code_visibility", {}),
        "evolution_kernel": {
            "enabled": signal_payload.get("evolution_kernel", {}).get("enabled", False),
            "gap_count": signal_payload.get("evolution_kernel", {}).get("gap_count", 0),
        },
    }
    return compact


def run_pipeline(config: RuntimeConfig) -> dict[str, Any]:
    validate_runtime_config(config)
    sample_path = Path(config.sample_path)
    ensure_sample_data(sample_path)

    store = PatternStore(PatternStoreConfig(root=config.memory_root))

    if config.mode == "replay":
        if config.replay_source == "csv":
            bars = load_bars_from_csv(Path(config.replay_csv_path), config.bars)
            data_source = "replay_csv"
        elif config.replay_source == "memory":
            bars = load_bars_from_memory(store, config.bars)
            data_source = "replay_memory"
        else:
            raise ValueError(f"Unsupported replay_source: {config.replay_source}")
        mt5_attempted = False
    else:
        bars = MT5Adapter(
            MT5Config(
                symbol=config.symbol,
                timeframe=config.timeframe,
                bars=config.bars,
                csv_fallback_path=str(sample_path),
            )
        ).get_bars()
        data_source = "mt5_or_csv_fallback"
        mt5_attempted = True

    execution_state = ExecutionState(
        symbol=config.symbol,
        mode=config.mode,
        replay_source=config.replay_source,
        mt5_attempted=mt5_attempted,
        data_source=data_source,
        ready=True,
        reasons=["validated", f"data_source={data_source}"],
    )

    structure = classify_market_structure(bars)
    liquidity = assess_liquidity_state(bars)
    score = compute_confidence(structure, liquidity)

    blocked_setups = store.load("blocked_setups")
    trade_outcomes = store.load("trade_outcomes")

    director = OversoulDirector()
    advanced_state = run_advanced_modules(
        director=director,
        bars=bars,
        base_direction=score["direction"],
        structure=structure,
        liquidity=liquidity,
        base_confidence=score["confidence"],
        blocked_setups=blocked_setups,
        trade_outcomes=trade_outcomes,
        symbol=config.symbol,
        mode=config.mode,
    )

    blocker = LossBlocker(min_confidence=0.6, max_spread_points=60.0)
    spread_points = float(
        advanced_state.module_results.get("spread_state", {}).payload.get("spread_points", 25.0)
    )
    block = blocker.evaluate(
        confidence=advanced_state.final_confidence,
        structure=structure,
        liquidity=liquidity,
        spread_points=spread_points,
    )

    combined_blocked = block["blocked"] or advanced_state.blocked
    combined_reasons = normalize_reasons(block["reasons"] + advanced_state.blocked_reasons)

    snapshot_id = store.record_snapshot(
        {
            "symbol": config.symbol,
            "mode": config.mode,
            "execution_state": execution_state.to_dict(),
            "structure": structure,
            "liquidity": liquidity,
            "base_confidence": score,
            "advanced_state": state_to_dict(advanced_state),
            "bars": bars,
        }
    )

    decision = advanced_state.final_direction
    reasons = (
        combined_reasons if combined_blocked else [f"advanced_direction={decision}"] + score["reasons"]
    )

    if combined_blocked:
        decision = "WAIT"
        store.record_blocked(
            {
                "symbol": config.symbol,
                "snapshot_id": snapshot_id,
                "direction": advanced_state.final_direction,
                "reasons": reasons,
            }
        )
        trade_id = f"blocked_{snapshot_id}"
    else:
        trade_id = store.record_promoted(
            {
                "symbol": config.symbol,
                "snapshot_id": snapshot_id,
                "direction": decision,
                "confidence": advanced_state.final_confidence,
                "reasons": reasons,
            }
        )

    tracker = OutcomeTracker(store)
    outcome = tracker.evaluate_and_record(
        trade_id=trade_id,
        decision=decision,
        bars=bars,
        confidence=advanced_state.final_confidence,
        reasons=reasons,
    )

    generated_rules = SelfCoder(store).generate_rules_from_outcomes()
    summary = tracker.summarize_recent_outcomes(limit=100)

    rules_registry_entry = register_generated_artifact(
        registry_path=Path(config.generated_registry_path),
        artifact_type="generated_rules",
        artifact_path=str(Path(config.memory_root) / "generated_rules.json"),
        metadata={
            "symbol": config.symbol,
            "mode": config.mode,
            "rule_count": len(generated_rules),
            "snapshot_id": snapshot_id,
        },
    )
    profile_registry_entry = register_generated_artifact(
        registry_path=Path(config.generated_registry_path),
        artifact_type="meta_adaptive_profile",
        artifact_path=config.meta_adaptive_profile_path,
        metadata={"symbol": config.symbol, "mode": config.mode, "snapshot_id": snapshot_id},
    )

    evolution_result = run_evolution_kernel(config)

    memory_context = {
        "latest_snapshot_id": snapshot_id,
        "last_blocked_count": len(store.load("blocked_setups")),
        "last_promoted_count": len(store.load("promoted_setups")),
        "latest_trade_outcome": outcome,
    }

    signal = build_signal_output(
        symbol=config.symbol,
        action=decision,
        confidence=advanced_state.final_confidence,
        reasons=reasons,
        block_result={"blocked": combined_blocked, "reasons": combined_reasons},
        structure=structure,
        liquidity=liquidity,
        memory_context=memory_context,
        generated_rules=generated_rules,
    )

    signal_payload = signal.to_dict()
    signal_payload["advanced_modules"] = {
        "director_module_map": director.as_dict(),
        "discovered_modules": director.discovered_as_dict(),
        "module_results": advanced_state.as_module_payload(),
        "module_health": advanced_state.as_health_payload(),
        "connector_hooks": advanced_state.as_connector_payload(),
        "final_direction": advanced_state.final_direction,
        "final_confidence": advanced_state.final_confidence,
    }
    signal_payload["generated_code_visibility"] = {
        "registry_path": config.generated_registry_path,
        "latest_entries": [rules_registry_entry, profile_registry_entry],
    }
    signal_payload["evolution_kernel"] = {
        "enabled": evolution_result["enabled"],
        "inspection": evolution_result["inspection"],
        "gap_count": len(evolution_result["gaps"]),
        "lifecycle": evolution_result["lifecycle"],
    }

    if config.compact_output:
        signal_payload = _build_compact_signal_payload(signal_payload)

    chart_objects = build_chart_objects(
        symbol=config.symbol,
        structure=structure,
        liquidity=liquidity,
        signal_payload=signal_payload,
    )

    status_panel = build_status_panel(
        structure=structure,
        liquidity=liquidity,
        signal_payload=signal_payload,
        memory_result={"latest_trade_outcome": outcome, "outcome_summary": summary},
        rule_result={
            "generated_rule_count": len(generated_rules),
            "matching_rule_ids": signal_payload["rule_context"]["matching_rule_ids"],
        },
    )
    status_panel["advanced_module_result"] = {
        "blocked": advanced_state.blocked,
        "blocked_reasons": advanced_state.blocked_reasons,
        "module_count": len(advanced_state.module_results),
        "ready_count": sum(1 for h in advanced_state.module_health.values() if h.ready),
    }
    status_counts = evolution_result.get("status_counts", {})
    status_panel["evolution_result"] = {
        "enabled": evolution_result["enabled"],
        "gaps_found": len(evolution_result["gaps"]),
        "proposals_processed": len(evolution_result["lifecycle"]),
        "proposed": int(status_counts.get("proposed", 0)),
        "verified": int(status_counts.get("verified", 0)),
        "promoted": int(status_counts.get("promoted", 0)),
        "rejected": int(status_counts.get("rejected", 0)),
        "archived": int(status_counts.get("archived", 0)),
    }
    status_panel["execution_state"] = execution_state.to_dict()

    return build_indicator_output(
        symbol=config.symbol,
        signal_payload=signal_payload,
        chart_objects=chart_objects,
        status_panel=status_panel,
    )



def run_replay_evaluation(config: RuntimeConfig) -> dict[str, Any]:
    """Run replay evaluation using the existing replay pipeline path."""
    validate_runtime_config(config)
    ensure_sample_data(Path(config.sample_path))

    report = evaluate_replay(
        pipeline_runner=run_pipeline,
        config_factory=RuntimeConfig,
        symbol=config.symbol,
        timeframe=config.timeframe,
        bars=config.bars,
        replay_csv_path=config.replay_csv_path,
        sample_path=config.sample_path,
        memory_root=config.memory_root,
        generated_registry_path=config.generated_registry_path,
        meta_adaptive_profile_path=config.meta_adaptive_profile_path,
        evolution_enabled=config.evolution_enabled,
        evolution_registry_path=config.evolution_registry_path,
        evolution_artifact_root=config.evolution_artifact_root,
        evolution_max_proposals=config.evolution_max_proposals,
        compact_output=config.compact_output,
        evaluation_steps=config.evaluation_steps,
        evaluation_stride=config.evaluation_stride,
        knowledge_expansion_enabled=config.knowledge_expansion_enabled,
        knowledge_expansion_root=config.knowledge_expansion_root,
        knowledge_candidate_limit=config.knowledge_candidate_limit,
    )

    if config.knowledge_expansion_enabled:
        report["knowledge_expansion_phase_a"] = run_knowledge_expansion_phase_a(
            replay_report=report,
            root=Path(config.knowledge_expansion_root),
            candidate_limit=config.knowledge_candidate_limit,
        )

    )

    Path(config.evaluation_output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XAUUSD indicator runner")
    parser.add_argument("--config", default="config/settings.json")
    parser.add_argument("--mode", choices=["live", "replay"], default=None)
    parser.add_argument("--replay-source", choices=["csv", "memory"], default=None)
    parser.add_argument("--replay-csv", default=None)
    parser.add_argument("--evolution-enabled", choices=["true", "false"], default=None)
    parser.add_argument("--compact-output", choices=["true", "false"], default=None)
    parser.add_argument("--evaluate-replay", choices=["true", "false"], default=None)
    parser.add_argument("--evaluation-steps", type=int, default=None)
    parser.add_argument("--evaluation-stride", type=int, default=None)
    parser.add_argument("--knowledge-expansion-enabled", choices=["true", "false"], default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_runtime_config(Path(args.config))
    if args.mode is not None:
        config = RuntimeConfig(**{**config.__dict__, "mode": args.mode})
    if args.replay_source is not None:
        config = RuntimeConfig(**{**config.__dict__, "replay_source": args.replay_source})
    if args.replay_csv is not None:
        config = RuntimeConfig(**{**config.__dict__, "replay_csv_path": args.replay_csv})
    if args.evolution_enabled is not None:
        config = RuntimeConfig(
            **{**config.__dict__, "evolution_enabled": args.evolution_enabled.lower() == "true"}
        )
    if args.compact_output is not None:
        config = RuntimeConfig(
            **{**config.__dict__, "compact_output": args.compact_output.lower() == "true"}
        )
    if args.evaluation_steps is not None:
        config = RuntimeConfig(**{**config.__dict__, "evaluation_steps": int(args.evaluation_steps)})
    if args.evaluation_stride is not None:
        config = RuntimeConfig(**{**config.__dict__, "evaluation_stride": int(args.evaluation_stride)})
    if args.knowledge_expansion_enabled is not None:
        config = RuntimeConfig(
            **{
                **config.__dict__,
                "knowledge_expansion_enabled": args.knowledge_expansion_enabled.lower() == "true",
            }
        )

    evaluate_replay_mode = args.evaluate_replay is not None and args.evaluate_replay.lower() == "true"
    if evaluate_replay_mode:
        print(run_replay_evaluation(config))
    else:
        print(run_pipeline(config))


if __name__ == "__main__":
    main()
