from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.alerts.telegram_sidecar import (
    _build_dedupe_key,
    _load_sent_keys,
    _save_sent_keys,
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
