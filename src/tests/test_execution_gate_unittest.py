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


RETCODE_DONE = 100
RETCODE_DONE_PARTIAL = 101
RETCODE_REQUOTE = 102
RETCODE_PRICE_CHANGED = 103
RETCODE_NO_MONEY = 104
RETCODE_MARKET_CLOSED = 105
RETCODE_TRADE_DISABLED = 106
RETCODE_INVALID_VOLUME = 107
RETCODE_INVALID_STOPS = 108
RETCODE_PRICE_OFF = 109
RETCODE_TOO_MANY_REQUESTS = 110


class _AcceptedResult:
    retcode = RETCODE_DONE
    order = 42


class _PartialResult:
    retcode = RETCODE_DONE_PARTIAL
    order = 43


class _RequoteResult:
    retcode = RETCODE_REQUOTE
    order = 44


class _RejectedResult:
    retcode = 199
    order = 45


class _PriceChangedResult:
    retcode = RETCODE_PRICE_CHANGED
    order = 46


class _NoMoneyResult:
    retcode = RETCODE_NO_MONEY
    order = 47


class _MarketClosedResult:
    retcode = RETCODE_MARKET_CLOSED
    order = 48


class _TradeDisabledResult:
    retcode = RETCODE_TRADE_DISABLED
    order = 49


class _InvalidVolumeResult:
    retcode = RETCODE_INVALID_VOLUME
    order = 50


class _InvalidStopsResult:
    retcode = RETCODE_INVALID_STOPS
    order = 51


class _PriceOffResult:
    retcode = RETCODE_PRICE_OFF
    order = 52


class _TooManyRequestsResult:
    retcode = RETCODE_TOO_MANY_REQUESTS
    order = 53


class _MT5BaseStub:
    TRADE_RETCODE_DONE = RETCODE_DONE

    def initialize(self) -> bool:
        return True

    def shutdown(self) -> None:
        return None


class _MT5AcceptedStub(_MT5BaseStub):

    def order_send(self, _request: dict[str, object]) -> object:
        return _AcceptedResult()


class _MT5PartialStub(_MT5BaseStub):
    TRADE_RETCODE_DONE_PARTIAL = RETCODE_DONE_PARTIAL

    def order_send(self, _request: dict[str, object]) -> object:
        return _PartialResult()


class _MT5RequoteStub(_MT5BaseStub):
    TRADE_RETCODE_REQUOTE = RETCODE_REQUOTE

    def order_send(self, _request: dict[str, object]) -> object:
        return _RequoteResult()


class _MT5RejectedStub(_MT5BaseStub):

    def order_send(self, _request: dict[str, object]) -> object:
        return _RejectedResult()


class _MT5PriceChangedStub(_MT5BaseStub):
    TRADE_RETCODE_PRICE_CHANGED = RETCODE_PRICE_CHANGED

    def order_send(self, _request: dict[str, object]) -> object:
        return _PriceChangedResult()


class _MT5NoMoneyStub(_MT5BaseStub):
    TRADE_RETCODE_NO_MONEY = RETCODE_NO_MONEY

    def order_send(self, _request: dict[str, object]) -> object:
        return _NoMoneyResult()


class _MT5MarketClosedStub(_MT5BaseStub):
    TRADE_RETCODE_MARKET_CLOSED = RETCODE_MARKET_CLOSED

    def order_send(self, _request: dict[str, object]) -> object:
        return _MarketClosedResult()


class _MT5TradeDisabledStub(_MT5BaseStub):
    TRADE_RETCODE_TRADE_DISABLED = RETCODE_TRADE_DISABLED

    def order_send(self, _request: dict[str, object]) -> object:
        return _TradeDisabledResult()


class _MT5InvalidVolumeStub(_MT5BaseStub):
    TRADE_RETCODE_INVALID_VOLUME = RETCODE_INVALID_VOLUME

    def order_send(self, _request: dict[str, object]) -> object:
        return _InvalidVolumeResult()


class _MT5InvalidStopsStub(_MT5BaseStub):
    TRADE_RETCODE_INVALID_STOPS = RETCODE_INVALID_STOPS

    def order_send(self, _request: dict[str, object]) -> object:
        return _InvalidStopsResult()


class _MT5PriceOffStub(_MT5BaseStub):
    TRADE_RETCODE_PRICE_OFF = RETCODE_PRICE_OFF

    def order_send(self, _request: dict[str, object]) -> object:
        return _PriceOffResult()


class _MT5TooManyRequestsStub(_MT5BaseStub):
    TRADE_RETCODE_TOO_MANY_REQUESTS = RETCODE_TOO_MANY_REQUESTS

    def order_send(self, _request: dict[str, object]) -> object:
        return _TooManyRequestsResult()


class _MT5Info:
    visible = True


class _MT5Account:
    trade_allowed = True
    login = 12345


class _AcceptedPipelineResult:
    retcode = RETCODE_DONE
    order = 77


class _MT5LivePipelineStub:
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TRADE_RETCODE_DONE = RETCODE_DONE

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
        self.assertFalse(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "not_applicable",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "no_order_send_attempt",
        )
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
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_outcome",
        )
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
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
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
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 44)
        self.assertIn(
            "mt5_requote_unretried",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_rejected_send_outcome_is_labeled_unconfirmed_broker_state(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_rejected_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5RejectedStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "rejected")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_retcode_199",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 45)
        self.assertIn(
            "mt5_retcode_199",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_price_changed_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_price_changed_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PriceChangedStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "price_changed")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_price_changed_unretried",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 46)
        self.assertIn(
            "mt5_price_changed_unretried",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_no_money_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_no_money_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5NoMoneyStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "insufficient_margin")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_no_money",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 47)
        self.assertIn(
            "mt5_no_money",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_market_closed_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_market_closed_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5MarketClosedStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "market_closed")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_market_closed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 48)
        self.assertIn(
            "mt5_market_closed",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_trade_disabled_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_trade_disabled_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5TradeDisabledStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "trade_disabled")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_trade_disabled",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 49)
        self.assertIn(
            "mt5_trade_disabled",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_invalid_volume_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_invalid_volume_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5InvalidVolumeStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "invalid_volume")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_invalid_volume",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 50)
        self.assertIn(
            "mt5_invalid_volume",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_invalid_stops_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_invalid_stops_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5InvalidStopsStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "invalid_stops")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_invalid_stops",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 51)
        self.assertIn(
            "mt5_invalid_stops",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_price_off_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_price_off_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PriceOffStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "price_off")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_price_off",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 52)
        self.assertIn(
            "mt5_price_off",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_too_many_requests_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_too_many_requests_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5TooManyRequestsStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "too_many_requests")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_too_many_requests",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 53)
        self.assertIn(
            "mt5_too_many_requests",
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
