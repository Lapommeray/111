from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.mt5.adapter import MT5Adapter, MT5Config
from src.mt5.execution_state import ExecutionState
from src.mt5.symbol_guard import SymbolGuard


def _write_sample_csv(path: Path, rows: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["time", "open", "high", "low", "close", "tick_volume"],
        )
        writer.writeheader()
        for i in range(rows):
            base = 2000 + i * 0.1
            writer.writerow(
                {
                    "time": 1700000000 + i * 60,
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

    assert len(bars) == 10
    assert set(bars[0].keys()) == {"time", "open", "high", "low", "close", "tick_volume"}


def test_execution_state_to_dict_shape() -> None:
    state = ExecutionState(
        symbol="XAUUSD",
        mode="replay",
        replay_source="csv",
        mt5_attempted=False,
        data_source="replay_csv",
        ready=True,
        reasons=["validated"],
    )
    payload = state.to_dict()
    assert payload["symbol"] == "XAUUSD"
    assert payload["mode"] == "replay"
    assert payload["ready"] is True
    assert payload["reasons"] == ["validated"]
