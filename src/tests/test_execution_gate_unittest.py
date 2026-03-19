from __future__ import annotations

import unittest
import tempfile
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

from run import RuntimeConfig, _run_controlled_mt5_live_execution, ensure_sample_data, run_pipeline
from src.mt5.adapter import MT5Adapter, MT5Config


class _AcceptedResult:
    retcode = 100
    order = 42


class _PartialResult:
    retcode = 101
    order = 43


class _RequoteResult:
    retcode = 102
    order = 44


class _MT5AcceptedStub:
    TRADE_RETCODE_DONE = 100

    def initialize(self) -> bool:
        return True

    def order_send(self, _request: dict[str, object]) -> object:
        return _AcceptedResult()

    def shutdown(self) -> None:
        return None


class _MT5PartialStub:
    TRADE_RETCODE_DONE = 100
    TRADE_RETCODE_DONE_PARTIAL = 101

    def initialize(self) -> bool:
        return True

    def order_send(self, _request: dict[str, object]) -> object:
        return _PartialResult()

    def shutdown(self) -> None:
        return None


class _MT5RequoteStub:
    TRADE_RETCODE_DONE = 100
    TRADE_RETCODE_REQUOTE = 102

    def initialize(self) -> bool:
        return True

    def order_send(self, _request: dict[str, object]) -> object:
        return _RequoteResult()

    def shutdown(self) -> None:
        return None


class _MT5Info:
    visible = True


class _MT5Account:
    trade_allowed = True
    login = 12345


class _AcceptedPipelineResult:
    retcode = 100
    order = 77


class _MT5LivePipelineStub:
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TRADE_RETCODE_DONE = 100

    def initialize(self) -> bool:
        return True

    def symbol_info(self, _symbol: str) -> object:
        return _MT5Info()

    def account_info(self) -> object:
        return _MT5Account()

    def copy_rates_from_pos(self, _symbol: str, _tf: int, _start: int, count: int) -> list[dict[str, float]]:
        now_ts = int(time.time())
        return [
            {
                "time": now_ts - ((count - i) * 60),
                "open": 2100.0,
                "high": 2100.5,
                "low": 2099.5,
                "close": 2100.2,
                "tick_volume": 130.0,
            }
            for i in range(count)
        ]

    def order_send(self, _request: dict[str, object]) -> object:
        return _AcceptedPipelineResult()

    def shutdown(self) -> None:
        return None


def _base_kwargs(memory_root: str) -> dict[str, object]:
    return {
        "memory_root": memory_root,
        "mode": "live",
        "symbol": "XAUUSD",
        "decision": "BUY",
        "confidence": 0.9,
        "bars": [{"close": 2100.0, "time": 1_700_000_000}],
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


class TestExecutionGateSemantics(unittest.TestCase):
    def _mkdtemp(self, prefix: str) -> str:
        path = tempfile.mkdtemp(prefix=prefix)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def test_blocked_default_readiness_refuses_execution(self) -> None:
        kwargs = _base_kwargs(self._mkdtemp(prefix="execution_gate_blocked_"))
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "refused")
        self.assertIn(
            "pretrade_check_failed:readiness_allows_live_order",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_explicit_live_authorized_readiness_reaches_order_stub(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(controlled_execution["order_result"]["order_id"], 42)

    def test_partial_fill_retcode_reported_as_partial_unreconciled(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_partial_fill_unreconciled",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 43)
        self.assertIn(
            "mt5_partial_fill_unreconciled",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_requote_retcode_reported_as_unretried_requote(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_requote_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5RequoteStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "requote")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_requote_unretried",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 44)
        self.assertIn(
            "mt5_requote_unretried",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_real_builder_chain_produces_non_live_readiness_defaults(self) -> None:
        csv_path = Path(self._mkdtemp(prefix="execution_gate_builder_")) / "xauusd.csv"
        csv_path.write_text(
            "time,open,high,low,close,tick_volume\n"
            "1700000000,2000.0,2000.5,1999.5,2000.1,100\n"
            "1700000060,2000.1,2000.6,1999.6,2000.2,101\n",
            encoding="utf-8",
        )
        adapter = MT5Adapter(
            MT5Config(
                symbol="XAUUSD",
                bars=2,
                csv_fallback_path=str(csv_path),
                fail_safe_blocked_state=True,
            )
        )
        _ = adapter.get_bars()
        readiness = adapter.get_controlled_readiness_state()
        self.assertTrue(readiness["live_execution_blocked"])
        self.assertFalse(readiness["order_execution_enabled"])
        self.assertTrue(readiness["execution_refused"])
        self.assertIn(readiness["execution_gate"], {"controlled_non_live", "refused_unsafe_readiness"})

    def test_unknown_execution_gate_is_refused_even_with_live_flags(self) -> None:
        kwargs = _base_kwargs(self._mkdtemp(prefix="execution_gate_unknown_"))
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "typo_live_enabled",
        }
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "refused")
        self.assertIn(
            "pretrade_check_failed:readiness_allows_live_order",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_real_pipeline_chain_explicit_live_authorization_path(self) -> None:
        sample_path = Path(self._mkdtemp(prefix="execution_gate_pipeline_samples_")) / "xauusd.csv"
        ensure_sample_data(sample_path)
        with patch.dict(sys.modules, {"MetaTrader5": _MT5LivePipelineStub()}):
            blocked_output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="execution_gate_pipeline_blocked_"),
                    mode="live",
                    live_execution_enabled=True,
                    live_authorization_enabled=False,
                )
            )
            blocked_readiness = blocked_output["status_panel"]["execution_state"]["controlled_mt5_readiness"]
            self.assertTrue(blocked_readiness["live_execution_blocked"])
            self.assertFalse(blocked_readiness["order_execution_enabled"])
            self.assertNotEqual(
                blocked_readiness.get("execution_gate"),
                "live_authorized_controlled_execution",
            )
            blocked_audit = blocked_readiness["live_authorization_audit"]
            self.assertFalse(blocked_audit["enabled"])
            self.assertFalse(blocked_audit["authorized"])
            self.assertIn("flag_enabled", blocked_audit["failed_conditions"])

            authorized_output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="execution_gate_pipeline_authorized_"),
                    mode="live",
                    live_execution_enabled=True,
                    live_authorization_enabled=True,
                )
            )
            authorized_readiness = authorized_output["status_panel"]["execution_state"]["controlled_mt5_readiness"]
            self.assertFalse(authorized_readiness["live_execution_blocked"])
            self.assertTrue(authorized_readiness["order_execution_enabled"])
            self.assertFalse(authorized_readiness["execution_refused"])
            self.assertEqual(authorized_readiness["execution_gate"], "live_authorized_controlled_execution")
            audit = authorized_readiness["live_authorization_audit"]
            self.assertTrue(audit["enabled"])
            self.assertTrue(audit["authorized"])
            self.assertEqual(audit["failed_conditions"], [])


if __name__ == "__main__":
    unittest.main()
