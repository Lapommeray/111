from __future__ import annotations

import unittest
import tempfile
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

from run import (
    RuntimeConfig,
    _build_entry_exit_decision_contract,
    _run_controlled_mt5_live_execution,
    ensure_sample_data,
    run_pipeline,
)
from src.state import ModuleResult, PipelineState
from src.mt5.adapter import MT5Adapter, MT5Config


# MT5 retcode fixture values used by test stubs to simulate controlled send outcomes.
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
RETCODE_INVALID_PRICE = 111


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


class _InvalidPriceResult:
    retcode = RETCODE_INVALID_PRICE
    order = 54


class _Position:
    def __init__(
        self,
        *,
        ticket: int | None = None,
        identifier: int | None = None,
        symbol: str = "XAUUSD",
        type_value: object = 0,
        volume: float = 0.01,
    ) -> None:
        if ticket is not None:
            self.ticket = ticket
        if identifier is not None:
            self.identifier = identifier
        self.symbol = symbol
        self.type = type_value
        self.volume = volume


class _Order:
    def __init__(
        self,
        *,
        ticket: int | None = None,
        order: int | None = None,
        symbol: str = "XAUUSD",
        type_value: object = 0,
        volume_current: float | None = None,
        volume_initial: float | None = None,
        volume: float | None = None,
    ) -> None:
        if ticket is not None:
            self.ticket = ticket
        if order is not None:
            self.order = order
        self.symbol = symbol
        self.type = type_value
        if volume_current is not None:
            self.volume_current = volume_current
        if volume_initial is not None:
            self.volume_initial = volume_initial
        if volume is not None:
            self.volume = volume


class _Deal:
    def __init__(
        self,
        *,
        order: int | None = None,
        symbol: str = "XAUUSD",
        type_value: object = 0,
        volume: float | None = None,
    ) -> None:
        if order is not None:
            self.order = order
        self.symbol = symbol
        self.type = type_value
        if volume is not None:
            self.volume = volume


class _MT5BaseStub:
    TRADE_RETCODE_DONE = RETCODE_DONE

    def initialize(self) -> bool:
        return True

    def shutdown(self) -> None:
        return None


class _MT5AcceptedStub(_MT5BaseStub):

    def order_send(self, _request: dict[str, object]) -> object:
        return _AcceptedResult()


class _MT5AcceptedWithLinkedPositionStub(_MT5AcceptedStub):
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    def positions_get(self) -> list[object]:
        return [
            _Position(
                ticket=42,
                identifier=42,
                symbol="XAUUSD",
                type_value=self.POSITION_TYPE_BUY,
                volume=0.01,
            )
        ]


class _MT5AcceptedWithMetadataOnlyPositionStub(_MT5AcceptedStub):
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    def positions_get(self) -> list[object]:
        return [
            _Position(
                ticket=None,
                identifier=None,
                symbol="XAUUSD",
                type_value=self.POSITION_TYPE_BUY,
                volume=0.01,
            )
        ]


class _MT5AcceptedWithLinkedOrderOnlyStub(_MT5AcceptedStub):
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def positions_get(self) -> list[object]:
        return []

    def orders_get(self) -> list[object]:
        return []

    def history_orders_get(self) -> list[object]:
        return [
            _Order(
                ticket=42,
                symbol="XAUUSD",
                type_value=self.ORDER_TYPE_BUY,
                volume_initial=0.01,
            )
        ]


class _MT5AcceptedWithOrderLookupUnavailableStub(_MT5AcceptedStub):
    def positions_get(self) -> list[object]:
        return []


class _MT5AcceptedWithLinkedOrderSupportingMismatchStub(_MT5AcceptedStub):
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def positions_get(self) -> list[object]:
        return []

    def orders_get(self) -> list[object]:
        return []

    def history_orders_get(self) -> list[object]:
        return [
            _Order(
                ticket=42,
                symbol="XAUUSD",
                type_value=self.ORDER_TYPE_BUY,
                volume_initial=0.02,
            )
        ]


class _MT5AcceptedDelayedLinkedPositionStub(_MT5AcceptedStub):
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    def __init__(self) -> None:
        self._positions_calls = 0

    def positions_get(self) -> list[object]:
        self._positions_calls += 1
        if self._positions_calls == 1:
            return []
        return [
            _Position(
                ticket=42,
                identifier=42,
                symbol="XAUUSD",
                type_value=self.POSITION_TYPE_BUY,
                volume=0.01,
            )
        ]


class _MT5PartialStub(_MT5BaseStub):
    TRADE_RETCODE_DONE_PARTIAL = RETCODE_DONE_PARTIAL

    def order_send(self, _request: dict[str, object]) -> object:
        return _PartialResult()


class _MT5PartialWithLinkedDealStub(_MT5PartialStub):
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def history_deals_get(self) -> list[object]:
        return [
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.004,
            )
        ]


class _MT5PartialWithMultipleLinkedDealsStub(_MT5PartialStub):
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def history_deals_get(self) -> list[object]:
        return [
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.004,
            ),
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.003,
            ),
        ]


class _MT5PartialWithLinkedDealSupportingMismatchStub(_MT5PartialStub):
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def history_deals_get(self) -> list[object]:
        return [
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.004,
            ),
            _Deal(
                order=43,
                symbol="EURUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.003,
            ),
        ]


class _MT5PartialWithLinkedDealQuantityInconsistentStub(_MT5PartialStub):
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def history_deals_get(self) -> list[object]:
        return [
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.006,
            ),
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.005,
            ),
        ]


class _MT5PartialWithPositionsOnlyStub(_MT5PartialStub):
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    def positions_get(self) -> list[object]:
        return [
            _Position(
                ticket=43,
                identifier=43,
                symbol="XAUUSD",
                type_value=self.POSITION_TYPE_BUY,
                volume=0.004,
            )
        ]


class _MT5PartialDelayedLinkedDealStub(_MT5PartialStub):
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def __init__(self) -> None:
        self._deals_calls = 0

    def history_deals_get(self) -> list[object]:
        self._deals_calls += 1
        if self._deals_calls == 1:
            return []
        return [
            _Deal(
                order=43,
                symbol="XAUUSD",
                type_value=self.DEAL_TYPE_BUY,
                volume=0.004,
            )
        ]


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


class _MT5RequoteThenAcceptedStub(_MT5BaseStub):
    TRADE_RETCODE_REQUOTE = RETCODE_REQUOTE

    def __init__(self) -> None:
        self.send_calls = 0
        self.last_request_price = None

    def symbol_info_tick(self, _symbol: str) -> object:
        return {"ask": 2100.45, "bid": 2100.35}

    def order_send(self, request: dict[str, object]) -> object:
        self.send_calls += 1
        self.last_request_price = request.get("price")
        if self.send_calls == 1:
            return _RequoteResult()
        return _AcceptedResult()


class _MT5PriceChangedThenAcceptedStub(_MT5BaseStub):
    TRADE_RETCODE_PRICE_CHANGED = RETCODE_PRICE_CHANGED

    def __init__(self) -> None:
        self.send_calls = 0
        self.last_request_price = None

    def symbol_info_tick(self, _symbol: str) -> object:
        return {"ask": 2100.55, "bid": 2100.25}

    def order_send(self, request: dict[str, object]) -> object:
        self.send_calls += 1
        self.last_request_price = request.get("price")
        if self.send_calls == 1:
            return _PriceChangedResult()
        return _AcceptedResult()


class _MT5RequoteInvalidTickStub(_MT5BaseStub):
    TRADE_RETCODE_REQUOTE = RETCODE_REQUOTE

    def __init__(self) -> None:
        self.send_calls = 0

    def symbol_info_tick(self, _symbol: str) -> object:
        return {"ask": 0.0, "bid": 2100.2}

    def order_send(self, _request: dict[str, object]) -> object:
        self.send_calls += 1
        return _RequoteResult()


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


class _MT5PriceOffThenAcceptedStub(_MT5BaseStub):
    TRADE_RETCODE_PRICE_OFF = RETCODE_PRICE_OFF

    def __init__(self) -> None:
        self.send_calls = 0
        self.last_request_price = None

    def symbol_info_tick(self, _symbol: str) -> object:
        return {"ask": 2101.05, "bid": 2100.95}

    def order_send(self, request: dict[str, object]) -> object:
        self.send_calls += 1
        self.last_request_price = request.get("price")
        if self.send_calls == 1:
            return _PriceOffResult()
        return _AcceptedResult()


class _MT5PriceOffInvalidTickStub(_MT5BaseStub):
    TRADE_RETCODE_PRICE_OFF = RETCODE_PRICE_OFF

    def __init__(self) -> None:
        self.send_calls = 0

    def symbol_info_tick(self, _symbol: str) -> object:
        return {"ask": 0.0, "bid": 2100.8}

    def order_send(self, _request: dict[str, object]) -> object:
        self.send_calls += 1
        return _PriceOffResult()


class _MT5TooManyRequestsStub(_MT5BaseStub):
    TRADE_RETCODE_TOO_MANY_REQUESTS = RETCODE_TOO_MANY_REQUESTS

    def order_send(self, _request: dict[str, object]) -> object:
        return _TooManyRequestsResult()


class _MT5InvalidPriceStub(_MT5BaseStub):
    TRADE_RETCODE_INVALID_PRICE = RETCODE_INVALID_PRICE

    def order_send(self, _request: dict[str, object]) -> object:
        return _InvalidPriceResult()


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
        self.assertEqual(controlled_execution["order_result"]["retry_eligible"], False)
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 0)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy"],
            "bounded_single_retry_execution_policy_for_requote_price_changed_price_off",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_not_attempted_fail_closed_guard_blocked",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_eligibility_reason"],
            "no_order_send_attempt",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_blocked_reason"],
            "no_order_send_attempt",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_final_outcome_status"],
            "refused",
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
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_unreconciled",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 42)
        self.assertEqual(
            controlled_execution["open_position_state"]["broker_position_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["position_state_outcome"],
            "assumed_open_from_accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["exit_decision"]["reason"],
            "assumed_open_position_from_accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["pnl_snapshot"]["position_open_truth"],
            "assumed_from_accepted_send_unreconciled",
        )

    def test_accepted_send_upgrades_to_confirmed_only_on_exact_linkage_match(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_confirmed_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedWithLinkedPositionStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_position_confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["linkage_field_used"],
            "ticket",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["linkage_value_matched"],
            42,
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["broker_position_confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["position_state_outcome"],
            "broker_confirmed_open_position",
        )
        self.assertEqual(
            controlled_execution["exit_decision"]["reason"],
            "broker_confirmed_open_position",
        )
        self.assertEqual(
            controlled_execution["pnl_snapshot"]["position_open_truth"],
            "broker_confirmed_open_position",
        )

    def test_accepted_send_with_metadata_only_position_match_fails_closed_unconfirmed(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_metadata_only_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedWithMetadataOnlyPositionStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["fail_closed_reason"],
            "mt5_order_lookup_unavailable",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["broker_position_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["position_state_outcome"],
            "assumed_open_from_accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["exit_decision"]["reason"],
            "assumed_open_position_from_accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["pnl_snapshot"]["position_open_truth"],
            "assumed_from_accepted_send_unreconciled",
        )

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
        self.assertEqual(controlled_execution["order_result"]["requested_volume"], 0.01)
        self.assertIsNone(controlled_execution["order_result"]["filled_volume"])
        self.assertIsNone(controlled_execution["order_result"]["remaining_volume"])
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["broker_position_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["status"],
            "partial_exposure_unresolved",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["position_state_outcome"],
            "partial_fill_exposure_unresolved",
        )
        self.assertEqual(controlled_execution["open_position_state"]["requested_volume"], 0.01)
        self.assertIsNone(controlled_execution["open_position_state"]["filled_volume"])
        self.assertIsNone(controlled_execution["open_position_state"]["remaining_volume"])
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["fail_closed_reason"],
            "mt5_history_deals_get_unavailable",
        )
        self.assertEqual(controlled_execution["pnl_snapshot"]["position_open"], None)
        self.assertEqual(
            controlled_execution["pnl_snapshot"]["position_open_truth"],
            "partial_fill_exposure_unresolved",
        )
        self.assertEqual(
            controlled_execution["exit_decision"]["decision"],
            "defer_exit_partial_exposure_unresolved",
        )
        self.assertEqual(
            controlled_execution["exit_decision"]["reason"],
            "partial_fill_exposure_unresolved",
        )
        self.assertIn(
            "mt5_partial_fill_unreconciled",
            controlled_execution["rollback_refusal_reasons"],
        )

    def test_partial_fill_upgrades_quantity_only_on_exact_linked_broker_deal_truth(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_linked_deal_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialWithLinkedDealStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "broker_confirmed_partial_quantity",
        )
        self.assertEqual(controlled_execution["order_result"]["filled_volume"], 0.004)
        self.assertEqual(controlled_execution["order_result"]["remaining_volume"], 0.006)
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["broker_quantity_outcome"],
            "partial_quantity_confirmed_from_linked_deal",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["linkage_field_used"],
            "order",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["linkage_value_matched"],
            43,
        )
        self.assertEqual(controlled_execution["open_position_state"]["status"], "partial_exposure_unresolved")
        self.assertEqual(
            controlled_execution["open_position_state"]["position_state_outcome"],
            "partial_fill_exposure_unresolved",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "broker_confirmed_partial_quantity",
        )
        self.assertEqual(controlled_execution["open_position_state"]["filled_volume"], 0.004)
        self.assertEqual(controlled_execution["open_position_state"]["remaining_volume"], 0.006)

    def test_partial_fill_aggregates_exact_linked_broker_deal_quantities_strictly(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_linked_multi_deal_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialWithMultipleLinkedDealsStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "broker_confirmed_partial_quantity",
        )
        self.assertEqual(controlled_execution["order_result"]["filled_volume"], 0.007)
        self.assertEqual(controlled_execution["order_result"]["remaining_volume"], 0.003)
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["linked_deal_count"],
            2,
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["linkage_field_used"],
            "order",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["linkage_value_matched"],
            43,
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "broker_confirmed_partial_quantity",
        )
        self.assertEqual(controlled_execution["open_position_state"]["filled_volume"], 0.007)
        self.assertEqual(controlled_execution["open_position_state"]["remaining_volume"], 0.003)

    def test_partial_fill_multi_deal_fails_closed_on_any_linked_deal_supporting_mismatch(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_linked_multi_deal_mismatch_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialWithLinkedDealSupportingMismatchStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertIsNone(controlled_execution["order_result"]["filled_volume"])
        self.assertIsNone(controlled_execution["order_result"]["remaining_volume"])
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["fail_closed_reason"],
            "linked_deal_supporting_mismatch",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertIsNone(controlled_execution["open_position_state"]["filled_volume"])
        self.assertIsNone(controlled_execution["open_position_state"]["remaining_volume"])

    def test_partial_fill_multi_deal_fails_closed_on_aggregated_quantity_inconsistency(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_linked_multi_deal_inconsistent_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialWithLinkedDealQuantityInconsistentStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertIsNone(controlled_execution["order_result"]["filled_volume"])
        self.assertIsNone(controlled_execution["order_result"]["remaining_volume"])
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["fail_closed_reason"],
            "linked_deal_quantity_inconsistent",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertIsNone(controlled_execution["open_position_state"]["filled_volume"])
        self.assertIsNone(controlled_execution["open_position_state"]["remaining_volume"])

    def test_partial_fill_with_positions_only_fails_closed_unresolved_without_deal_truth(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_positions_only_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialWithPositionsOnlyStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertIsNone(controlled_execution["order_result"]["filled_volume"])
        self.assertIsNone(controlled_execution["order_result"]["remaining_volume"])
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["fail_closed_reason"],
            "mt5_history_deals_get_unavailable",
        )
        self.assertEqual(controlled_execution["open_position_state"]["status"], "partial_exposure_unresolved")
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "unresolved",
        )
        self.assertIsNone(controlled_execution["open_position_state"]["filled_volume"])
        self.assertIsNone(controlled_execution["open_position_state"]["remaining_volume"])

    def test_accepted_send_with_exact_order_acknowledgement_stays_position_unconfirmed(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_order_ack_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedWithLinkedOrderOnlyStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_order_acknowledged_position_unconfirmed",
        )
        self.assertTrue(
            controlled_execution["order_result"]["broker_position_verification"]["order_acknowledged"]
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["order_ack_source"],
            "history_orders_get",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["matched_order_ticket"],
            42,
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["broker_position_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["position_state_outcome"],
            "assumed_open_from_accepted_send_unreconciled",
        )

    def test_accepted_send_order_ack_lookup_unavailable_fails_closed_unreconciled(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_order_lookup_unavailable_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedWithOrderLookupUnavailableStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["fail_closed_reason"],
            "mt5_order_lookup_unavailable",
        )

    def test_accepted_send_with_linked_order_supporting_mismatch_fails_closed_unreconciled(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_order_supporting_mismatch_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedWithLinkedOrderSupportingMismatchStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_unreconciled",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["fail_closed_reason"],
            "order_linkage_supporting_mismatch",
        )

    def test_accepted_send_delayed_recheck_confirms_exact_linkage_when_broker_truth_appears(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_live_delayed_confirmed_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5AcceptedDelayedLinkedPositionStub()
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_position_confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_position_verification"]["linkage_value_matched"],
            42,
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["broker_position_confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["pnl_snapshot"]["position_open_truth"],
            "broker_confirmed_open_position",
        )

    def test_requote_retcode_retries_once_and_accepts_when_second_send_succeeds(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_requote_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        retry_stub = _MT5RequoteThenAcceptedStub()
        kwargs["mt5_module"] = retry_stub
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(controlled_execution["order_result"]["error_reason"], "")
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "accepted_send_unreconciled",
        )
        self.assertEqual(controlled_execution["order_result"]["retry_eligible"], True)
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 1)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy"],
            "bounded_single_retry_execution_policy_for_requote_price_changed_price_off",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_attempted_bounded_single_retry_execution_policy",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_eligibility_reason"],
            "transient_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["retry_blocked_reason"], "")
        self.assertEqual(controlled_execution["order_result"]["retry_final_outcome_status"], "accepted")
        self.assertEqual(retry_stub.send_calls, 2)
        self.assertEqual(retry_stub.last_request_price, 2100.45)

    def test_partial_fill_delayed_recheck_confirms_exact_linked_deal_when_broker_truth_appears(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_partial_delayed_confirmed_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5PartialDelayedLinkedDealStub()
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "partial")
        self.assertEqual(
            controlled_execution["order_result"]["partial_outcome_quantity_truth"],
            "broker_confirmed_partial_quantity",
        )
        self.assertEqual(controlled_execution["order_result"]["filled_volume"], 0.004)
        self.assertEqual(controlled_execution["order_result"]["remaining_volume"], 0.006)
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["confirmation"],
            "confirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["partial_quantity_verification"]["broker_quantity_outcome"],
            "partial_quantity_confirmed_from_linked_deal",
        )
        self.assertEqual(
            controlled_execution["open_position_state"]["partial_outcome_quantity_truth"],
            "broker_confirmed_partial_quantity",
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

    def test_price_changed_retcode_retries_once_and_accepts_when_second_send_succeeds(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_price_changed_retry_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        retry_stub = _MT5PriceChangedThenAcceptedStub()
        kwargs["mt5_module"] = retry_stub
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(controlled_execution["order_result"]["retry_eligible"], True)
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 1)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy"],
            "bounded_single_retry_execution_policy_for_requote_price_changed_price_off",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_attempted_bounded_single_retry_execution_policy",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_eligibility_reason"],
            "transient_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["retry_blocked_reason"], "")
        self.assertEqual(controlled_execution["order_result"]["retry_final_outcome_status"], "accepted")
        self.assertEqual(retry_stub.send_calls, 2)
        self.assertEqual(retry_stub.last_request_price, 2100.55)

    def test_price_changed_sell_retry_uses_tick_bid_price(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_price_changed_retry_sell_")
        kwargs = _base_kwargs(memory_root)
        kwargs["decision"] = "SELL"
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        retry_stub = _MT5PriceChangedThenAcceptedStub()
        kwargs["mt5_module"] = retry_stub
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 1)
        self.assertEqual(retry_stub.send_calls, 2)
        self.assertEqual(retry_stub.last_request_price, 2100.25)

    def test_requote_retry_fails_closed_when_broker_tick_price_invalid(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_requote_retry_fail_closed_tick_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        retry_stub = _MT5RequoteInvalidTickStub()
        kwargs["mt5_module"] = retry_stub
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "requote")
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 0)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_not_attempted_fail_closed_guard_blocked",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_blocked_reason"],
            "refreshed_price_valid;broker_price_refresh_tick_sides_invalid",
        )
        self.assertEqual(retry_stub.send_calls, 1)

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
        self.assertEqual(controlled_execution["order_result"]["retry_eligible"], False)
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 0)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy"],
            "bounded_single_retry_execution_policy_for_requote_price_changed_price_off",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_not_attempted_fail_closed_guard_blocked",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_eligibility_reason"],
            "non_transient_non_accepted_send_outcome",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_blocked_reason"],
            "first_status_in_retry_slice",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_final_outcome_status"],
            "insufficient_margin",
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

    def test_price_off_retcode_retries_once_and_accepts_when_second_send_succeeds(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_price_off_retry_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        retry_stub = _MT5PriceOffThenAcceptedStub()
        kwargs["mt5_module"] = retry_stub
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "accepted")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(controlled_execution["order_result"]["retry_eligible"], True)
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 1)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy"],
            "bounded_single_retry_execution_policy_for_requote_price_changed_price_off",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_attempted_bounded_single_retry_execution_policy",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_eligibility_reason"],
            "transient_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["retry_blocked_reason"], "")
        self.assertEqual(controlled_execution["order_result"]["retry_final_outcome_status"], "accepted")
        self.assertEqual(retry_stub.send_calls, 2)
        self.assertEqual(retry_stub.last_request_price, 2101.05)

    def test_price_off_retry_fails_closed_when_broker_tick_price_invalid(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_price_off_retry_fail_closed_tick_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        retry_stub = _MT5PriceOffInvalidTickStub()
        kwargs["mt5_module"] = retry_stub
        with patch("run.time.sleep", return_value=None):
            controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "price_off")
        self.assertEqual(controlled_execution["order_result"]["retry_attempted_count"], 0)
        self.assertEqual(
            controlled_execution["order_result"]["retry_policy_truth"],
            "retry_not_attempted_fail_closed_guard_blocked",
        )
        self.assertEqual(
            controlled_execution["order_result"]["retry_blocked_reason"],
            "refreshed_price_valid;broker_price_refresh_tick_sides_invalid",
        )
        self.assertEqual(retry_stub.send_calls, 1)

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

    def test_invalid_price_retcode_has_explicit_non_accepted_classification(self) -> None:
        memory_root = self._mkdtemp(prefix="execution_gate_invalid_price_")
        kwargs = _base_kwargs(memory_root)
        kwargs["controlled_mt5_readiness"] = {
            **dict(kwargs["controlled_mt5_readiness"]),
            "live_execution_blocked": False,
            "order_execution_enabled": True,
            "execution_refused": False,
            "execution_gate": "live_authorized_controlled_execution",
        }
        kwargs["mt5_module"] = _MT5InvalidPriceStub()
        controlled_execution, _state, _paths = _run_controlled_mt5_live_execution(**kwargs)
        self.assertEqual(controlled_execution["order_result"]["status"], "invalid_price")
        self.assertTrue(controlled_execution["order_result"]["order_sent"])
        self.assertEqual(
            controlled_execution["order_result"]["error_reason"],
            "mt5_invalid_price",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_confirmation"],
            "unconfirmed",
        )
        self.assertEqual(
            controlled_execution["order_result"]["broker_state_outcome"],
            "unconfirmed_non_accepted_send_outcome",
        )
        self.assertEqual(controlled_execution["order_result"]["order_id"], 54)
        self.assertIn(
            "mt5_invalid_price",
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

    def test_pipeline_includes_clean_no_trade_decision_contract_when_not_authorized(self) -> None:
        sample_path = Path(self._mkdtemp(prefix="decision_contract_no_trade_samples_")) / "xauusd.csv"
        ensure_sample_data(sample_path)
        with patch.dict(sys.modules, {"MetaTrader5": _MT5LivePipelineStub()}):
            output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="decision_contract_no_trade_memory_"),
                    mode="live",
                    live_execution_enabled=True,
                    live_authorization_enabled=False,
                )
            )
        decision = output["status_panel"]["entry_exit_decision"]
        self.assertEqual(
            sorted(decision.keys()),
            sorted(
                [
                    "action",
                    "entry_price",
                    "stop_loss",
                    "take_profit",
                    "invalidation_reason",
                    "confidence",
                    "why_not_trade",
                ]
            ),
        )
        self.assertEqual(decision["action"], "NO_TRADE")
        self.assertIsNone(decision["entry_price"])
        self.assertIsNone(decision["stop_loss"])
        self.assertIsNone(decision["take_profit"])
        self.assertIsInstance(decision["invalidation_reason"], str)
        self.assertTrue(bool(decision["invalidation_reason"]))
        self.assertIn("NO_TRADE", decision["why_not_trade"])

    def test_pipeline_applies_directional_conviction_gate_on_insufficient_vote_margin(self) -> None:
        sample_path = Path(self._mkdtemp(prefix="directional_conviction_samples_")) / "xauusd.csv"
        ensure_sample_data(sample_path)
        bars = [
            {"time": 1_700_000_000 + (idx * 60), "open": 2100.0, "high": 2100.5, "low": 2099.5, "close": 2100.2, "tick_volume": 140.0}
            for idx in range(60)
        ]
        structure = {"state": "trend_up", "bias": "buy", "strength": 0.9}
        liquidity = {"liquidity_state": "stable", "direction_hint": "buy", "score": 0.8}
        weak_margin_state = PipelineState(
            symbol="XAUUSD",
            mode="replay",
            bars=bars,
            structure=structure,
            liquidity=liquidity,
            base_confidence=0.9,
            base_direction="BUY",
            final_confidence=0.95,
            final_direction="BUY",
            blocked=False,
            blocked_reasons=[],
            module_results={
                "sessions": ModuleResult(
                    name="sessions",
                    role="session_classifier",
                    direction_vote="neutral",
                    confidence_delta=0.0,
                    blocked=False,
                    reasons=[],
                    payload={"state": "london"},
                ),
                "spread_state": ModuleResult(
                    name="spread_state",
                    role="spread_proxy_estimator",
                    direction_vote="neutral",
                    confidence_delta=0.0,
                    blocked=False,
                    reasons=[],
                    payload={"spread_points": 15.0},
                ),
                "volatility": ModuleResult(
                    name="volatility",
                    role="volatility_regime",
                    direction_vote="neutral",
                    confidence_delta=0.0,
                    blocked=False,
                    reasons=[],
                    payload={"volatility_ratio": 1.0, "state": "balanced", "metrics": {"ratio": 1.0}},
                ),
                "direction_buy_a": ModuleResult(
                    name="direction_buy_a",
                    role="vote_a",
                    direction_vote="buy",
                    confidence_delta=0.02,
                    blocked=False,
                    reasons=[],
                    payload={},
                ),
                "direction_buy_b": ModuleResult(
                    name="direction_buy_b",
                    role="vote_b",
                    direction_vote="buy",
                    confidence_delta=0.02,
                    blocked=False,
                    reasons=[],
                    payload={},
                ),
                "direction_sell_a": ModuleResult(
                    name="direction_sell_a",
                    role="vote_c",
                    direction_vote="sell",
                    confidence_delta=0.0,
                    blocked=False,
                    reasons=[],
                    payload={},
                ),
                "conflict_filter": ModuleResult(
                    name="conflict_filter",
                    role="vote_conflict_gate",
                    direction_vote="neutral",
                    confidence_delta=0.01,
                    blocked=False,
                    reasons=["buy_votes=2", "sell_votes=1"],
                    payload={},
                ),
            },
        )

        with (
            patch("run.classify_market_structure", return_value=structure),
            patch("run.assess_liquidity_state", return_value=liquidity),
            patch("run.compute_confidence", return_value={"confidence": 0.9, "direction": "BUY", "reasons": ["seed_buy"]}),
            patch("run.run_advanced_modules", return_value=weak_margin_state),
            patch(
                "run.collect_xauusd_macro_state",
                return_value={
                    "trade_tags": {},
                    "risk_behavior": {"pause_trading": False, "confidence_penalty": 0.0, "size_multiplier": 1.0, "reasons": []},
                },
            ),
            patch(
                "run.evaluate_capital_protection",
                return_value={
                    "effective_volume": 0.01,
                    "trade_refused": False,
                    "daily_loss_check": {"allowed": True},
                    "trigger_reasons": [],
                },
            ),
        ):
            output = run_pipeline(
                RuntimeConfig(
                    symbol="XAUUSD",
                    timeframe="M5",
                    bars=60,
                    sample_path=str(sample_path),
                    replay_source="csv",
                    replay_csv_path=str(sample_path),
                    memory_root=self._mkdtemp(prefix="directional_conviction_memory_"),
                    mode="replay",
                    evolution_enabled=False,
                    live_execution_enabled=False,
                    macro_feed_enabled=False,
                )
            )

        decision = output["status_panel"]["entry_exit_decision"]
        self.assertEqual(decision["action"], "NO_TRADE")
        reasons = output["signal"]["reasons"]
        self.assertIn("directional_vote_margin_insufficient", reasons)

    def test_clean_long_entry_decision_contract_for_buy_signal(self) -> None:
        decision = _build_entry_exit_decision_contract(
            decision="BUY",
            effective_signal_confidence=0.81,
            bars=[{"close": 2100.2}],
            reasons=["advanced_direction=BUY"],
            controlled_execution={
                "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
                "rollback_refusal_reasons": [],
                "order_result": {"status": "accepted", "requested_price": 2100.2},
                "open_position_state": {"status": "flat"},
                "exit_decision": {"reason": "no_position_exit"},
            },
        )
        self.assertEqual(
            sorted(decision.keys()),
            sorted(
                [
                    "action",
                    "entry_price",
                    "stop_loss",
                    "take_profit",
                    "invalidation_reason",
                    "confidence",
                    "why_this_trade",
                ]
            ),
        )
        self.assertEqual(decision["action"], "LONG_ENTRY")
        self.assertIsInstance(decision["entry_price"], float)
        self.assertIsInstance(decision["stop_loss"], float)
        self.assertIsInstance(decision["take_profit"], float)
        self.assertEqual(decision["invalidation_reason"], "")
        self.assertIn("LONG_ENTRY", decision["why_this_trade"])

    def test_clean_exit_decision_contract_for_existing_open_position(self) -> None:
        decision = _build_entry_exit_decision_contract(
            decision="WAIT",
            effective_signal_confidence=0.77,
            bars=[{"close": 2100.2}],
            reasons=["existing_open_position_requires_exit_management"],
            controlled_execution={
                "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
                "rollback_refusal_reasons": [],
                "order_result": {},
                "open_position_state": {
                    "status": "open",
                    "entry_price": 2100.2,
                    "stop_loss": 2098.2,
                    "take_profit": 2104.2,
                },
                "exit_decision": {"reason": "broker_confirmed_open_position"},
            },
        )
        self.assertEqual(
            sorted(decision.keys()),
            sorted(
                [
                    "action",
                    "entry_price",
                    "stop_loss",
                    "exit_rule",
                    "invalidation_reason",
                    "confidence",
                    "why_not_trade",
                ]
            ),
        )
        self.assertEqual(decision["action"], "EXIT")
        self.assertIsInstance(decision["entry_price"], float)
        self.assertIsInstance(decision["stop_loss"], float)
        self.assertIsInstance(decision["exit_rule"], str)
        self.assertTrue(bool(decision["exit_rule"]))
        self.assertIn("open_position_management_exit", decision["exit_rule"])
        self.assertIn("No new entry", decision["why_not_trade"])

    def test_exit_rule_uses_stop_loss_breach_condition(self) -> None:
        decision = _build_entry_exit_decision_contract(
            decision="WAIT",
            effective_signal_confidence=0.77,
            bars=[{"close": 2097.9}],
            reasons=["existing_open_position_requires_exit_management"],
            controlled_execution={
                "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
                "rollback_refusal_reasons": [],
                "order_result": {},
                "open_position_state": {
                    "status": "open",
                    "side": "BUY",
                    "entry_price": 2100.2,
                    "stop_loss": 2098.2,
                    "take_profit": 2104.2,
                },
                "exit_decision": {"reason": "broker_confirmed_open_position"},
            },
        )
        self.assertEqual(decision["action"], "EXIT")
        self.assertIn("stop_loss_breached_exit", decision["exit_rule"])
        self.assertIn("side=BUY", decision["exit_rule"])

    def test_exit_rule_uses_take_profit_reached_condition(self) -> None:
        decision = _build_entry_exit_decision_contract(
            decision="WAIT",
            effective_signal_confidence=0.77,
            bars=[{"close": 2105.0}],
            reasons=["existing_open_position_requires_exit_management"],
            controlled_execution={
                "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
                "rollback_refusal_reasons": [],
                "order_result": {},
                "open_position_state": {
                    "status": "open",
                    "side": "BUY",
                    "entry_price": 2100.2,
                    "stop_loss": 2098.2,
                    "take_profit": 2104.2,
                },
                "exit_decision": {"reason": "broker_confirmed_open_position"},
            },
        )
        self.assertEqual(decision["action"], "EXIT")
        self.assertIn("take_profit_reached_exit", decision["exit_rule"])
        self.assertIn("side=BUY", decision["exit_rule"])

    def test_exit_rule_uses_partial_exposure_condition(self) -> None:
        decision = _build_entry_exit_decision_contract(
            decision="WAIT",
            effective_signal_confidence=0.77,
            bars=[{"close": 2100.2}],
            reasons=["existing_open_position_requires_exit_management"],
            controlled_execution={
                "stop_loss_take_profit": {"stop_loss": 2098.2, "take_profit": 2104.2},
                "rollback_refusal_reasons": [],
                "order_result": {},
                "open_position_state": {
                    "status": "partial_exposure_unresolved",
                    "side": "BUY",
                    "entry_price": 2100.2,
                    "stop_loss": 2098.2,
                    "take_profit": 2104.2,
                },
                "exit_decision": {"reason": "partial_fill_exposure_unresolved"},
            },
        )
        self.assertEqual(decision["action"], "EXIT")
        self.assertIn("partial_exposure_unresolved_manage_exit", decision["exit_rule"])

    def test_exit_rule_falls_back_to_reason_when_condition_unavailable(self) -> None:
        decision = _build_entry_exit_decision_contract(
            decision="WAIT",
            effective_signal_confidence=0.77,
            bars=[],
            reasons=["existing_open_position_requires_exit_management"],
            controlled_execution={
                "stop_loss_take_profit": {"stop_loss": None, "take_profit": None},
                "rollback_refusal_reasons": [],
                "order_result": {},
                "open_position_state": {
                    "status": "open",
                    "side": "UNKNOWN",
                    "entry_price": 2100.2,
                    "stop_loss": None,
                    "take_profit": None,
                },
                "exit_decision": {"reason": "broker_confirmed_open_position"},
            },
        )
        self.assertEqual(decision["action"], "EXIT")
        self.assertEqual(decision["exit_rule"], "broker_confirmed_open_position")


if __name__ == "__main__":
    unittest.main()
