from __future__ import annotations

import unittest
import tempfile
import shutil
from pathlib import Path

from run import _run_controlled_mt5_live_execution
from src.mt5.adapter import MT5Adapter, MT5Config


class _AcceptedResult:
    retcode = 100
    order = 42


class _MT5AcceptedStub:
    TRADE_RETCODE_DONE = 100

    def initialize(self) -> bool:
        return True

    def order_send(self, _request: dict[str, object]) -> object:
        return _AcceptedResult()

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


if __name__ == "__main__":
    unittest.main()
