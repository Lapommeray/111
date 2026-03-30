from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.alerts.telegram_sidecar import (
    ACTION_MAP,
    ACTIONABLE_ACTIONS,
    TelegramAlertPayload,
    _build_dedupe_key,
    _build_telegram_text,
    _derive_signal_id,
    _extract_price,
    _load_sent_keys,
    _round_confidence,
    _save_sent_keys,
    _top_reasons,
    build_telegram_payload,
    deliver_output_to_telegram,
    RuntimeConfig,
    run_pipeline_with_telegram,
)


def _base_output(contract_action: str, *, entry_price: float | None = 2350.5) -> dict[str, object]:
    return {
        "symbol": "XAUUSD",
        "signal": {
            "action": "WAIT",
            "confidence": 0.8123,
            "reasons": ["open_position_exit_management:broker_confirmed_open_position", "seed_buy"],
            "blocker_reasons": [],
            "memory_context": {"latest_snapshot_id": "snap_20260329230000000000"},
        },
        "status_panel": {
            "entry_exit_decision": {
                "action": contract_action,
                "entry_price": entry_price,
            }
        },
    }


def test_action_mapping_long_short_exit_and_non_actionable() -> None:
    buy_payload = build_telegram_payload(_base_output("LONG_ENTRY"))
    assert buy_payload is not None
    assert buy_payload.action == "BUY"

    sell_payload = build_telegram_payload(_base_output("SHORT_ENTRY"))
    assert sell_payload is not None
    assert sell_payload.action == "SELL"

    exit_payload = build_telegram_payload(_base_output("EXIT"))
    assert exit_payload is not None
    assert exit_payload.action == "EXIT"

    non_actionable = build_telegram_payload(_base_output("NO_TRADE"))
    assert non_actionable is None


def test_actionable_filter_uses_final_contract_not_raw_signal() -> None:
    output = _base_output("EXIT")
    # Raw signal action intentionally non-actionable.
    output["signal"]["action"] = "WAIT"  # type: ignore[index]
    payload = build_telegram_payload(output)
    assert payload is not None
    assert payload.action == "EXIT"


def test_dedupe_key_uses_symbol_action_signal_id() -> None:
    payload = build_telegram_payload(_base_output("LONG_ENTRY"))
    assert payload is not None
    key = _build_dedupe_key(payload)
    assert key == "XAUUSD|BUY|snap_20260329230000000000"


def test_dedupe_store_load_and_save_roundtrip(tmp_path: Path) -> None:
    dedupe_path = tmp_path / "telegram_alert_state.json"
    _save_sent_keys(dedupe_path, {"a|b|c", "x|y|z"})
    loaded = _load_sent_keys(dedupe_path)
    assert loaded == {"a|b|c", "x|y|z"}
    parsed = json.loads(dedupe_path.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == "telegram_alert_state.v1"
    assert sorted(parsed["sent_keys"]) == ["a|b|c", "x|y|z"]


def test_fail_open_when_send_raises(tmp_path: Path) -> None:
    sent_attempts = {"count": 0}

    def _raise_sender(_payload, _token: str, _chat_id: str, _timeout_seconds: float) -> None:
        sent_attempts["count"] += 1
        raise RuntimeError("network down")

    output = _base_output("LONG_ENTRY")
    result = deliver_output_to_telegram(
        output,
        bot_token="token",
        chat_id="chat",
        dedupe_state_path=tmp_path / "state.json",
        sender=_raise_sender,
    )
    assert result["attempted"] is True
    assert result["sent"] is False
    assert result["skipped"] is False
    assert result["reason"] == "send_failed_fail_open"
    assert result["error"] == "network down"
    assert sent_attempts["count"] == 1


def test_dedupe_skips_repeat_alert(tmp_path: Path) -> None:
    sent_payloads: list[str] = []

    def _sender(payload, _token: str, _chat_id: str, _timeout_seconds: float) -> None:
        sent_payloads.append(payload.signal_id)

    output = _base_output("SHORT_ENTRY")
    state_path = tmp_path / "state.json"

    first = deliver_output_to_telegram(
        output,
        bot_token="token",
        chat_id="chat",
        dedupe_state_path=state_path,
        sender=_sender,
    )
    second = deliver_output_to_telegram(
        output,
        bot_token="token",
        chat_id="chat",
        dedupe_state_path=state_path,
        sender=_sender,
    )
    assert first["sent"] is True
    assert first["skipped"] is False
    assert second["sent"] is False
    assert second["skipped"] is True
    assert second["reason"] == "duplicate_alert"
    assert len(sent_payloads) == 1


def test_run_pipeline_with_telegram_returns_output_even_on_send_failure(tmp_path: Path) -> None:
    output = _base_output("LONG_ENTRY")

    def _runner(_config: Any) -> dict[str, object]:
        return output

    def _sender(_token: str, _chat_id: str, _text: str) -> tuple[bool, str]:
        raise RuntimeError("send_failure")

    pipeline_output, delivery = run_pipeline_with_telegram(
        RuntimeConfig(symbol="XAUUSD", timeframe="M5"),
        runner=_runner,  # type: ignore[arg-type]
        bot_token="token",
        chat_id="chat",
        dedupe_state_path=tmp_path / "state.json",
        sender=_sender,
    )
    assert pipeline_output == output
    assert delivery["attempted"] is True
    assert delivery["sent"] is False
    assert delivery["skipped"] is False


# --- ACTION_MAP exhaustive coverage ---

def test_action_map_covers_all_contract_actions() -> None:
    assert ACTION_MAP == {"LONG_ENTRY": "BUY", "SHORT_ENTRY": "SELL", "EXIT": "EXIT"}


def test_actionable_actions_matches_map_values() -> None:
    assert ACTIONABLE_ACTIONS == {"BUY", "SELL", "EXIT"}


# --- Mapping: signal.action fallback when contract is missing ---

def test_signal_action_buy_fallback_when_contract_absent() -> None:
    output: dict[str, Any] = {
        "symbol": "XAUUSD",
        "signal": {"action": "BUY", "confidence": 0.7, "reasons": ["r1"], "memory_context": {}},
        "status_panel": {"entry_exit_decision": {"action": ""}},
    }
    payload = build_telegram_payload(output)
    assert payload is not None
    assert payload.action == "BUY"


def test_signal_action_sell_fallback_when_contract_absent() -> None:
    output: dict[str, Any] = {
        "symbol": "XAUUSD",
        "signal": {"action": "SELL", "confidence": 0.6, "reasons": [], "memory_context": {}},
        "status_panel": {"entry_exit_decision": {"action": ""}},
    }
    payload = build_telegram_payload(output)
    assert payload is not None
    assert payload.action == "SELL"


def test_wait_signal_with_no_trade_contract_returns_none() -> None:
    output = _base_output("NO_TRADE")
    output["signal"]["action"] = "WAIT"  # type: ignore[index]
    assert build_telegram_payload(output) is None


# --- Actionable filter: all non-actionable contract values ---

def test_non_actionable_empty_string_contract() -> None:
    output: dict[str, Any] = {
        "symbol": "XAUUSD",
        "signal": {"action": "WAIT", "confidence": 0.5, "reasons": [], "memory_context": {}},
        "status_panel": {"entry_exit_decision": {"action": ""}},
    }
    assert build_telegram_payload(output) is None


def test_non_actionable_unknown_contract_action() -> None:
    output: dict[str, Any] = {
        "symbol": "XAUUSD",
        "signal": {"action": "WAIT", "confidence": 0.5, "reasons": [], "memory_context": {}},
        "status_panel": {"entry_exit_decision": {"action": "HOLD"}},
    }
    assert build_telegram_payload(output) is None


def test_missing_status_panel_returns_none_when_signal_wait() -> None:
    output: dict[str, Any] = {
        "symbol": "XAUUSD",
        "signal": {"action": "WAIT", "confidence": 0.5, "reasons": [], "memory_context": {}},
    }
    assert build_telegram_payload(output) is None


def test_missing_entry_exit_decision_returns_none_when_signal_wait() -> None:
    output: dict[str, Any] = {
        "symbol": "XAUUSD",
        "signal": {"action": "WAIT", "confidence": 0.5, "reasons": [], "memory_context": {}},
        "status_panel": {},
    }
    assert build_telegram_payload(output) is None


# --- Dedupe: different actions on same signal_id are NOT deduped ---

def test_dedupe_allows_different_actions_same_signal_id(tmp_path: Path) -> None:
    sent: list[str] = []

    def _sender(payload: Any, _t: str, _c: str, _to: float) -> None:
        sent.append(payload.action)

    state_path = tmp_path / "state.json"

    buy_output = _base_output("LONG_ENTRY")
    sell_output = _base_output("SHORT_ENTRY")

    r1 = deliver_output_to_telegram(
        buy_output, bot_token="t", chat_id="c", dedupe_state_path=state_path, sender=_sender,
    )
    r2 = deliver_output_to_telegram(
        sell_output, bot_token="t", chat_id="c", dedupe_state_path=state_path, sender=_sender,
    )
    assert r1["sent"] is True
    assert r2["sent"] is True
    assert sent == ["BUY", "SELL"]


# --- Dedupe: corrupted state file recovers gracefully ---

def test_dedupe_corrupted_state_file_recovers(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("NOT VALID JSON", encoding="utf-8")
    loaded = _load_sent_keys(state_path)
    assert loaded == set()


def test_dedupe_state_missing_sent_keys_field(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text('{"schema_version": "v1"}', encoding="utf-8")
    loaded = _load_sent_keys(state_path)
    assert loaded == set()


# --- Fail-open: multiple exception types ---

def test_fail_open_on_connection_error(tmp_path: Path) -> None:
    def _sender(_p: Any, _t: str, _c: str, _to: float) -> None:
        raise ConnectionError("refused")

    result = deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="t", chat_id="c",
        dedupe_state_path=tmp_path / "s.json",
        sender=_sender,
    )
    assert result["attempted"] is True
    assert result["sent"] is False
    assert result["reason"] == "send_failed_fail_open"
    assert "refused" in result["error"]


def test_fail_open_on_timeout_error(tmp_path: Path) -> None:
    def _sender(_p: Any, _t: str, _c: str, _to: float) -> None:
        raise TimeoutError("timed out")

    result = deliver_output_to_telegram(
        _base_output("SHORT_ENTRY"),
        bot_token="t", chat_id="c",
        dedupe_state_path=tmp_path / "s.json",
        sender=_sender,
    )
    assert result["attempted"] is True
    assert result["sent"] is False
    assert result["reason"] == "send_failed_fail_open"


def test_fail_open_does_not_persist_dedupe_key(tmp_path: Path) -> None:
    state_path = tmp_path / "s.json"

    def _sender(_p: Any, _t: str, _c: str, _to: float) -> None:
        raise RuntimeError("fail")

    deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="t", chat_id="c",
        dedupe_state_path=state_path,
        sender=_sender,
    )
    loaded = _load_sent_keys(state_path)
    assert len(loaded) == 0


# --- Credentials missing: skips gracefully ---

def test_missing_token_skips_gracefully(tmp_path: Path) -> None:
    result = deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="", chat_id="chat",
        dedupe_state_path=tmp_path / "s.json",
    )
    assert result["attempted"] is False
    assert result["skipped"] is True
    assert result["reason"] == "telegram_credentials_missing"


def test_missing_chat_id_skips_gracefully(tmp_path: Path) -> None:
    result = deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="token", chat_id="",
        dedupe_state_path=tmp_path / "s.json",
    )
    assert result["attempted"] is False
    assert result["skipped"] is True
    assert result["reason"] == "telegram_credentials_missing"


# --- Payload shape and content ---

def test_payload_to_dict_shape() -> None:
    payload = build_telegram_payload(_base_output("LONG_ENTRY"))
    assert payload is not None
    d = payload.to_dict()
    assert set(d.keys()) == {"symbol", "action", "confidence", "timestamp", "price", "top_reasons", "signal_id"}
    assert d["symbol"] == "XAUUSD"
    assert d["action"] == "BUY"
    assert isinstance(d["confidence"], float)
    assert isinstance(d["timestamp"], str)
    assert isinstance(d["top_reasons"], list)


def test_telegram_text_format() -> None:
    payload = build_telegram_payload(_base_output("LONG_ENTRY"))
    assert payload is not None
    text = _build_telegram_text(payload)
    assert "XAUUSD BUY" in text
    assert "confidence:" in text
    assert "timestamp:" in text
    assert "signal_id:" in text
    assert "price:" in text


def test_telegram_text_exit_no_price() -> None:
    payload = build_telegram_payload(_base_output("EXIT", entry_price=None))
    assert payload is not None
    text = _build_telegram_text(payload)
    assert "XAUUSD EXIT" in text
    assert "price:" not in text


# --- Helper function coverage ---

def test_round_confidence_edge_cases() -> None:
    assert _round_confidence(0.123456789) == 0.1235
    assert _round_confidence("0.5") == 0.5
    assert _round_confidence(None) == 0.0
    assert _round_confidence("not_a_number") == 0.0


def test_top_reasons_limits() -> None:
    assert _top_reasons(["a", "b", "c", "d", "e"]) == ["a", "b", "c"]
    assert _top_reasons(["a", "b", "c", "d", "e"], limit=2) == ["a", "b"]
    assert _top_reasons(None) == []
    assert _top_reasons("not_a_list") == []
    assert _top_reasons(["", "  ", "valid"]) == ["valid"]


def test_extract_price_buy_sell_returns_float() -> None:
    output = _base_output("LONG_ENTRY", entry_price=2400.12345)
    price = _extract_price(output, "BUY")
    assert price == 2400.12345


def test_extract_price_exit_returns_none() -> None:
    output = _base_output("EXIT", entry_price=2400.0)
    price = _extract_price(output, "EXIT")
    assert price is None


def test_extract_price_missing_entry_price() -> None:
    output: dict[str, Any] = {
        "status_panel": {"entry_exit_decision": {}},
    }
    assert _extract_price(output, "BUY") is None


def test_derive_signal_id_uses_snapshot_when_present() -> None:
    sid = _derive_signal_id(
        symbol="XAUUSD", action="BUY", confidence=0.8, reasons=["r1"],
        memory_context={"latest_snapshot_id": "snap_abc"}, timestamp="2026-01-01T00:00:00", price=2350.0,
    )
    assert sid == "snap_abc"


def test_derive_signal_id_fallback_hash_when_no_snapshot() -> None:
    sid = _derive_signal_id(
        symbol="XAUUSD", action="BUY", confidence=0.8, reasons=["r1"],
        memory_context={}, timestamp="2026-01-01T00:00:00", price=2350.0,
    )
    assert sid.startswith("telegram_")
    assert len(sid) == len("telegram_") + 20


def test_derive_signal_id_deterministic() -> None:
    kwargs: dict[str, Any] = dict(
        symbol="XAUUSD", action="SELL", confidence=0.75, reasons=["reason"],
        memory_context={}, timestamp="2026-03-29T12:00:00", price=None,
    )
    assert _derive_signal_id(**kwargs) == _derive_signal_id(**kwargs)


# --- Successful send persists dedupe key ---

def test_successful_send_persists_key(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    def _sender(_p: Any, _t: str, _c: str, _to: float) -> None:
        pass

    result = deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="t", chat_id="c",
        dedupe_state_path=state_path,
        sender=_sender,
    )
    assert result["sent"] is True
    loaded = _load_sent_keys(state_path)
    assert "XAUUSD|BUY|snap_20260329230000000000" in loaded


# --- Delivery result includes alert dict ---

def test_delivery_result_contains_alert_on_success(tmp_path: Path) -> None:
    def _sender(_p: Any, _t: str, _c: str, _to: float) -> None:
        pass

    result = deliver_output_to_telegram(
        _base_output("SHORT_ENTRY"),
        bot_token="t", chat_id="c",
        dedupe_state_path=tmp_path / "s.json",
        sender=_sender,
    )
    assert "alert" in result
    assert result["alert"]["action"] == "SELL"
    assert result["alert"]["symbol"] == "XAUUSD"


def test_delivery_result_contains_alert_on_dedupe(tmp_path: Path) -> None:
    state_path = tmp_path / "s.json"

    def _sender(_p: Any, _t: str, _c: str, _to: float) -> None:
        pass

    deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="t", chat_id="c", dedupe_state_path=state_path, sender=_sender,
    )
    dup = deliver_output_to_telegram(
        _base_output("LONG_ENTRY"),
        bot_token="t", chat_id="c", dedupe_state_path=state_path, sender=_sender,
    )
    assert dup["alert"]["action"] == "BUY"
    assert dup["reason"] == "duplicate_alert"
