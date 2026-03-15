from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.mt5.adapter import MT5Adapter, MT5Config
from src.mt5.execution_state import ExecutionState
from src.mt5.symbol_guard import SymbolGuard


def _write_sample_csv(path: Path, rows: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base_timestamp = 4_000_000_000
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        for i in range(rows):
            base = 2000 + i * 0.1
            age_seconds = (rows - i) * 60
            writer.writerow(
                {
                    "time": base_timestamp - age_seconds,
                    "open": round(base, 2),
                    "high": round(base + 0.3, 2),
                    "low": round(base - 0.3, 2),
                    "close": round(base + 0.05, 2),
                    "tick_volume": 100 + i,
                }
            )


def test_symbol_guard_enforces_xauusd_first() -> None:
    guard = SymbolGuard()
    assert guard.validate("XAUUSD")["ready"] is True
    mt5_validation = guard.validate_for_mt5("XAUUSD")
    assert mt5_validation["symbol_validity"] is True
    assert mt5_validation["symbol_status"] == "ready"
    blocked = guard.validate("EURUSD")
    assert blocked["ready"] is False
    assert "symbol_not_allowed:EURUSD" in blocked["reasons"]


def test_mt5_adapter_restricts_non_xauusd() -> None:
    adapter = MT5Adapter(MT5Config(symbol="EURUSD", csv_fallback_path="missing.csv"))
    with pytest.raises(ValueError, match="restricted to XAUUSD"):
        adapter.get_bars()


def test_mt5_adapter_uses_csv_fallback_when_available(tmp_path: Path) -> None:
    csv_path = tmp_path / "samples" / "xauusd.csv"
    _write_sample_csv(csv_path, rows=15)

    adapter = MT5Adapter(MT5Config(symbol="XAUUSD", bars=10, csv_fallback_path=str(csv_path)))
    bars = adapter.get_bars()
    readiness = adapter.get_controlled_readiness_state()

    assert len(bars) == 10
    assert set(bars[0].keys()) == {"time", "open", "high", "low", "close", "tick_volume"}
    assert readiness["data_source"] == "csv_fallback"
    assert readiness["symbol_validity"] is True
    assert readiness["terminal_connectivity"] is False
    assert readiness["account_trading_permission"] is False
    assert readiness["data_freshness"] is True
    assert readiness["fail_safe_blocked_state"] is True
    assert readiness["live_execution_blocked"] is True
    assert readiness["order_execution_enabled"] is False
    assert readiness["ready_for_controlled_usage"] is False
    assert readiness["terminal_connection_stable"] is False
    assert readiness["symbol_subscription_ready"] is True
    assert readiness["account_readiness"] is False
    assert readiness["tick_data_freshness"] is True
    assert "terminal_connection_unstable" in readiness["fail_safe_blocked_reasons"]
    assert "account_not_ready" in readiness["fail_safe_blocked_reasons"]
    assert readiness["execution_gate"] == "refused_unsafe_readiness"
    assert readiness["execution_refused"] is True


def test_mt5_adapter_marks_stale_csv_data_as_not_fresh(tmp_path: Path) -> None:
    csv_path = tmp_path / "samples" / "xauusd_stale.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        old_start = 1700000000
        for i in range(12):
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

    adapter = MT5Adapter(
        MT5Config(
            symbol="XAUUSD",
            bars=10,
            csv_fallback_path=str(csv_path),
            max_data_age_seconds=300,
        )
    )
    _ = adapter.get_bars()
    readiness = adapter.get_controlled_readiness_state()
    assert readiness["data_freshness"] is False
    assert readiness["tick_data_freshness"] is False
    assert "data_stale_or_missing" in readiness["reason_codes"]
    assert "tick_data_stale" in readiness["fail_safe_blocked_reasons"]


def test_execution_state_to_dict_shape() -> None:
    state = ExecutionState(
        symbol="XAUUSD",
        mode="replay",
        replay_source="csv",
        mt5_attempted=False,
        data_source="replay_csv",
        ready=True,
        reasons=["validated"],
        controlled_mt5_readiness={"live_execution_blocked": True},
        live_execution_blocked=True,
        mt5_execution_gate="non_live_enforced",
        mt5_execution_refused=True,
        mt5_chain_verified=True,
        mt5_quarantined=False,
        mt5_safe_resume_state="stable",
    )
    payload = state.to_dict()
    assert payload["symbol"] == "XAUUSD"
    assert payload["mode"] == "replay"
    assert payload["ready"] is True
    assert payload["reasons"] == ["validated"]
    assert payload["controlled_mt5_readiness"]["live_execution_blocked"] is True
    assert payload["live_execution_blocked"] is True
    assert payload["mt5_execution_gate"] == "non_live_enforced"
    assert payload["mt5_execution_refused"] is True
    assert payload["mt5_chain_verified"] is True
    assert payload["mt5_quarantined"] is False
    assert payload["mt5_safe_resume_state"] == "stable"
