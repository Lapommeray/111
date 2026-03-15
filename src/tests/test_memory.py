from __future__ import annotations

import csv
import json
from pathlib import Path

from run import (
    RuntimeConfig,
    _run_controlled_mt5_live_execution,
    ensure_sample_data,
    load_runtime_config,
    run_pipeline,
    validate_runtime_config,
)
from src.memory.pattern_store import PatternStore, PatternStoreConfig


def _write_stale_csv(path: Path, rows: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        old_start = 1700000000
        for i in range(rows):
            writer.writerow(
                {
                    "time": old_start + (i * 60),
                    "open": 2000.0,
                    "high": 2000.5,
                    "low": 1999.5,
                    "close": 2000.1,
                    "tick_volume": 100 + i,
                }
            )


def _write_fresh_csv(path: Path, rows: int = 20, *, base_timestamp: int = 4_000_000_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        for i in range(rows):
            writer.writerow(
                {
                    "time": base_timestamp - ((rows - i) * 60),
                    "open": 2010.0,
                    "high": 2010.5,
                    "low": 2009.5,
                    "close": 2010.1,
                    "tick_volume": 120 + i,
                }
            )


def test_import_and_path_safety() -> None:
    imported = __import__("src.indicator.signal_model", fromlist=["build_signal_output"])
    assert hasattr(imported, "build_signal_output")


def test_pattern_store_seed_files_created(tmp_path: Path) -> None:
    store = PatternStore(PatternStoreConfig(root=str(tmp_path / "memory")))
    for name, path in store.files.items():
        assert path.exists(), f"missing seed file for {name}"


def test_pattern_store_recovers_from_corrupt_json(tmp_path: Path) -> None:
    mem_root = tmp_path / "memory"
    store = PatternStore(PatternStoreConfig(root=str(mem_root)))
    corrupt_path = store.files["blocked_setups"]
    corrupt_path.write_text("{broken-json", encoding="utf-8")

    recovered = store.load("blocked_setups")
    assert recovered == []


def test_pattern_store_backups_corrupt_file_before_reseed(tmp_path: Path) -> None:
    mem_root = tmp_path / "memory"
    store = PatternStore(PatternStoreConfig(root=str(mem_root)))
    corrupt_path = store.files["trade_outcomes"]
    corrupt_path.write_text("{bad-json", encoding="utf-8")

    recovered = store.load("trade_outcomes")
    assert recovered == []

    backups = list(mem_root.glob("trade_outcomes.json.corrupt.*"))
    assert backups, "Expected at least one corrupt backup file"
    assert backups[0].read_text(encoding="utf-8") == "{bad-json"


def test_memory_lifecycle_writes_snapshot_and_outcomes(tmp_path: Path) -> None:
    mem_root = tmp_path / "memory"
    store = PatternStore(PatternStoreConfig(root=str(mem_root)))

    snapshot_id = store.record_snapshot({"symbol": "XAUUSD", "bars": []})
    store.record_blocked({"symbol": "XAUUSD", "snapshot_id": snapshot_id, "reasons": ["test"]})
    trade_id = store.record_promoted({"symbol": "XAUUSD", "snapshot_id": snapshot_id, "direction": "BUY"})
    store.record_trade_outcome({"trade_id": trade_id, "symbol": "XAUUSD", "result": "win", "status": "closed"})

    assert store.load("pattern_memory")["patterns"]
    assert store.load("blocked_setups")
    assert store.load("promoted_setups")
    assert store.load("trade_outcomes")


def test_run_pipeline_first_run_live_and_replay_csv(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    live_config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=120,
        sample_path=str(sample_path),
        memory_root=str(tmp_path / "memory_live"),
        mode="live",
        replay_source="csv",
        replay_csv_path=str(sample_path),
    )
    live_output = run_pipeline(live_config)

    replay_config = RuntimeConfig(
        symbol="XAUUSD",
        timeframe="M5",
        bars=120,
        sample_path=str(sample_path),
        memory_root=str(tmp_path / "memory_replay"),
        mode="replay",
        replay_source="csv",
        replay_csv_path=str(sample_path),
    )
    replay_output = run_pipeline(replay_config)

    assert live_output["schema_version"] == replay_output["schema_version"] == "phase3.output.v1"
    assert set(live_output.keys()) == set(replay_output.keys())
    assert live_output["symbol"] == replay_output["symbol"] == "XAUUSD"


def test_market_structure_detectors_are_persisted_in_snapshot_memory(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    memory_root = tmp_path / "memory"

    run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    snapshot_payload = json.loads((memory_root / "pattern_memory.json").read_text(encoding="utf-8"))
    latest = snapshot_payload["patterns"][-1]
    modules = latest["advanced_state"]["module_results"]
    for detector_name in (
        "liquidity_sweep",
        "compression_expansion",
        "session_behavior",
        "market_regime",
        "execution_quality",
    ):
        assert detector_name in modules
        payload = modules[detector_name]["payload"]
        assert "confidence" in payload
        assert "confidence_level" in payload


def test_run_pipeline_compact_output_mode(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(tmp_path / "memory"),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
            compact_output=True,
        )
    )

    signal = output["signal"]
    assert signal["symbol"] == "XAUUSD"
    assert "module_results" not in signal.get("advanced_modules", {})
    assert "gap_count" in signal.get("evolution_kernel", {})


def test_status_panel_exposes_evolution_promoted_archived_counts(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(tmp_path / "memory"),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    evo = output["status_panel"]["evolution_result"]
    assert "promoted" in evo
    assert "archived" in evo


def test_replay_from_memory_uses_stored_bars(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)

    memory_root = tmp_path / "memory"
    live_output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="live",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )
    assert live_output["symbol"] == "XAUUSD"

    replay_output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="memory",
            replay_csv_path=str(sample_path),
        )
    )
    assert replay_output["symbol"] == "XAUUSD"


def test_run_pipeline_persists_controlled_mt5_readiness_state(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    memory_root = tmp_path / "memory"

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    execution_state = output["status_panel"]["execution_state"]
    readiness = execution_state["controlled_mt5_readiness"]
    assert execution_state["live_execution_blocked"] is True
    assert execution_state["mt5_execution_refused"] is True
    assert execution_state["mt5_quarantined"] is False
    assert readiness["live_execution_blocked"] is True
    assert readiness["order_execution_enabled"] is False
    assert readiness["fail_safe_blocked_state"] is True
    assert readiness["ready_for_controlled_usage"] is False
    assert readiness["execution_gate"] == "non_live_enforced"
    assert readiness["readiness_chain_verification"]["all_checks_passed"] is False
    assert readiness["quarantine_state"]["quarantine_required"] is False
    artifact_path = Path(readiness["artifact_path"])
    assert artifact_path.exists()
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["live_execution_blocked"] is True


def test_live_mode_refuses_unsafe_mt5_readiness_and_rolls_back_to_wait(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    memory_root = tmp_path / "memory_live_refusal"

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="live",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    execution_state = output["status_panel"]["execution_state"]
    readiness = execution_state["controlled_mt5_readiness"]
    assert output["signal"]["action"] == "WAIT"
    assert execution_state["ready"] is False
    assert execution_state["mt5_execution_refused"] is True
    assert execution_state["mt5_quarantined"] is True
    assert execution_state["mt5_execution_gate"] == "quarantined_invalid_readiness"
    assert readiness["execution_refused"] is True
    assert readiness["rollback_applied"] is True
    assert readiness["quarantine_state"]["quarantine_required"] is True
    assert readiness["readiness_chain_verification"]["all_checks_passed"] is False
    assert "mt5_execution_refused_unsafe_readiness" in output["signal"]["reasons"]


def test_mt5_pack3_self_audit_artifacts_are_deterministic(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    _write_fresh_csv(sample_path, rows=30)
    memory_root = tmp_path / "memory_pack3_audit"

    first = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )
    second = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    first_readiness = first["status_panel"]["execution_state"]["controlled_mt5_readiness"]
    second_readiness = second["status_panel"]["execution_state"]["controlled_mt5_readiness"]
    assert (
        first_readiness["self_audit_report"]["audit_id"]
        == second_readiness["self_audit_report"]["audit_id"]
    )
    assert Path(first_readiness["readiness_chain_verification"]["artifact_path"]).exists()
    assert Path(first_readiness["self_audit_report"]["artifact_path"]).exists()
    assert Path(first_readiness["quarantine_state"]["artifact_path"]).exists()
    assert Path(first_readiness["resume_state"]["artifact_path"]).exists()


def test_mt5_pack3_safe_resume_after_readiness_interruption(tmp_path: Path) -> None:
    stale_path = tmp_path / "samples" / "xauusd_stale.csv"
    fresh_path = tmp_path / "samples" / "xauusd_fresh.csv"
    _write_stale_csv(stale_path, rows=30)
    _write_fresh_csv(fresh_path, rows=30)
    memory_root = tmp_path / "memory_pack3_resume"

    interrupted = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(stale_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(stale_path),
        )
    )
    interrupted_state = interrupted["status_panel"]["execution_state"]["controlled_mt5_readiness"]
    assert interrupted_state["readiness_chain_verification"]["all_checks_passed"] is False
    assert interrupted_state["resume_state"]["status"] == "interrupted"

    resumed = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(fresh_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(fresh_path),
        )
    )
    resumed_execution_state = resumed["status_panel"]["execution_state"]
    resumed_state = resumed_execution_state["controlled_mt5_readiness"]
    assert resumed_state["readiness_chain_verification"]["all_checks_passed"] is True
    assert resumed_state["resume_state"]["safe_resume_applied"] is True
    assert resumed_state["resume_state"]["status"] == "resumed_safe"
    assert resumed_execution_state["mt5_safe_resume_state"] == "resumed_safe"


def test_run_pipeline_persists_controlled_mt5_execution_artifacts(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    memory_root = tmp_path / "memory_execution_artifacts"

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    execution_state = output["status_panel"]["execution_state"]
    controlled_execution = execution_state["mt5_controlled_execution"]
    assert controlled_execution["entry_decision"]["mode"] == "replay"
    assert controlled_execution["order_result"]["status"] in {"refused", "failed", "rejected"}
    assert controlled_execution["rejection_reason"] == "non_live_mode"
    assert Path(controlled_execution["execution_artifact_path"]).exists()
    assert Path(controlled_execution["execution_state_path"]).exists()
    assert Path(controlled_execution["execution_history_path"]).exists()
    assert "trade_tags" in controlled_execution
    assert "session" in controlled_execution["trade_tags"]


def test_run_pipeline_persists_macro_state_and_trade_tags(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples" / "xauusd.csv"
    ensure_sample_data(sample_path)
    memory_root = tmp_path / "memory_macro"

    output = run_pipeline(
        RuntimeConfig(
            symbol="XAUUSD",
            timeframe="M5",
            bars=120,
            sample_path=str(sample_path),
            memory_root=str(memory_root),
            mode="replay",
            replay_source="csv",
            replay_csv_path=str(sample_path),
        )
    )

    execution_state = output["status_panel"]["execution_state"]
    signal = output["signal"]
    assert "macro_state" in signal
    assert "trade_tags" in signal
    assert execution_state["macro_state"]["macro_states"]["dxy_state"] == "unavailable"
    outcomes = json.loads((memory_root / "trade_outcomes.json").read_text(encoding="utf-8"))
    assert outcomes[-1]["trade_tags"]["session"] in {"asia", "london", "new_york", "off_hours"}


def test_controlled_mt5_execution_requires_explicit_live_gate(tmp_path: Path) -> None:
    controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(
        memory_root=str(tmp_path / "memory_gate"),
        mode="live",
        symbol="XAUUSD",
        decision="BUY",
        confidence=0.8,
        bars=[{"close": 2000.0}],
        live_execution_enabled=False,
        live_order_volume=0.01,
        controlled_mt5_readiness={
            "ready_for_controlled_usage": True,
            "symbol_validity": True,
            "account_trading_permission": True,
            "account_readiness": True,
            "data_freshness": True,
            "tick_data_freshness": True,
            "fail_safe_blocked_reasons": [],
        },
        readiness_chain={"all_checks_passed": True},
        quarantine_state={"quarantine_required": False},
        risk_state_valid=True,
        fail_safe_state_clear=True,
    )

    assert controlled_execution["order_result"]["status"] == "refused"
    assert "pretrade_check_failed:live_execution_enabled" in controlled_execution["rollback_refusal_reasons"]
    assert controlled_execution["mistake_failure_classification"] == "explicit_gate_disabled"


def test_controlled_mt5_execution_auto_stop_after_repeated_failures(tmp_path: Path) -> None:
    memory_root = str(tmp_path / "memory_auto_stop")
    base_kwargs = {
        "memory_root": memory_root,
        "mode": "live",
        "symbol": "XAUUSD",
        "decision": "BUY",
        "confidence": 0.9,
        "bars": [{"close": 2100.0}],
        "live_execution_enabled": True,
        "live_order_volume": 0.01,
        "controlled_mt5_readiness": {
            "ready_for_controlled_usage": True,
            "symbol_validity": True,
            "account_trading_permission": True,
            "account_readiness": True,
            "data_freshness": True,
            "tick_data_freshness": True,
            "fail_safe_blocked_reasons": [],
        },
        "readiness_chain": {"all_checks_passed": True},
        "quarantine_state": {"quarantine_required": False},
        "risk_state_valid": True,
        "fail_safe_state_clear": True,
    }

    for _ in range(3):
        _run_controlled_mt5_live_execution(**base_kwargs)
    fourth_execution, state, _ = _run_controlled_mt5_live_execution(**base_kwargs)

    assert state["auto_stop_active"] is True
    assert fourth_execution["auto_stop_active"] is True
    assert "pretrade_check_failed:auto_stop_inactive" in fourth_execution["rollback_refusal_reasons"]


def test_config_validation_xauusd_first_and_timeframe() -> None:
    validate_runtime_config(RuntimeConfig(symbol="XAUUSD", timeframe="M5"))

    try:
        validate_runtime_config(RuntimeConfig(symbol="EURUSD", timeframe="M5"))
        assert False, "Expected ValueError for non-XAUUSD"
    except ValueError as exc:
        assert "XAUUSD" in str(exc)

    try:
        validate_runtime_config(RuntimeConfig(symbol="XAUUSD", timeframe="D1"))
        assert False, "Expected ValueError for unsupported timeframe"
    except ValueError as exc:
        assert "Unsupported timeframe" in str(exc)

    try:
        validate_runtime_config(RuntimeConfig(symbol="XAUUSD", timeframe="M5", live_order_volume=0))
        assert False, "Expected ValueError for invalid live order volume"
    except ValueError as exc:
        assert "live_order_volume" in str(exc)


def test_runtime_config_defaults_live_execution_enabled_true_when_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps(
            {
                "symbol": "XAUUSD",
                "timeframe": "M5",
                "bars": 220,
                "sample_path": "data/samples/xauusd.csv",
                "memory_root": "memory",
                "mode": "live",
            }
        ),
        encoding="utf-8",
    )
    loaded = load_runtime_config(config_path)
    assert loaded.live_execution_enabled is True
    assert RuntimeConfig().live_execution_enabled is True


def test_json_seed_file_shapes_are_safe() -> None:
    expected = {
        "memory/pattern_memory.json": "dict_patterns",
        "memory/blocked_setups.json": "list",
        "memory/promoted_setups.json": "list",
        "memory/trade_outcomes.json": "list",
        "memory/generated_rules.json": "dict_rules",
    }

    for path, kind in expected.items():
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if kind == "list":
            assert isinstance(payload, list)
        elif kind == "dict_patterns":
            assert isinstance(payload, dict) and "patterns" in payload
        else:
            assert isinstance(payload, dict) and "rules" in payload
