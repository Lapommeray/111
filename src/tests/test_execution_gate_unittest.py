from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from run import _run_controlled_mt5_live_execution


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
    def test_blocked_default_readiness_refuses_execution(self) -> None:
        kwargs = _base_kwargs(tempfile.mkdtemp(prefix="execution_gate_blocked_"))
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "refused")
        self.assertIn(
            "pretrade_check_failed:readiness_allows_live_order",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_explicit_live_authorized_readiness_reaches_order_stub(self) -> None:
        memory_root = tempfile.mkdtemp(prefix="execution_gate_live_")
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


if __name__ == "__main__":
    unittest.main()
