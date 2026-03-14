from __future__ import annotations

import json
from pathlib import Path

from run import RuntimeConfig, ensure_sample_data, run_pipeline, validate_runtime_config
from src.memory.pattern_store import PatternStore, PatternStoreConfig


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
