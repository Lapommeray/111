from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from run import RuntimeConfig, run_pipeline


ACTION_MAP = {
    "LONG_ENTRY": "BUY",
    "SHORT_ENTRY": "SELL",
    "EXIT": "EXIT",
}
ACTIONABLE_ACTIONS = {"BUY", "SELL", "EXIT"}


@dataclass(frozen=True)
class TelegramAlertPayload:
    symbol: str
    action: str
    confidence: float
    timestamp: str
    price: float | None
    top_reasons: list[str]
    signal_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "price": self.price,
            "top_reasons": self.top_reasons,
            "signal_id": self.signal_id,
        }


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _round_confidence(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


def _top_reasons(signal_reasons: Any, limit: int = 3) -> list[str]:
    if not isinstance(signal_reasons, list):
        return []
    cleaned = [str(reason).strip() for reason in signal_reasons if str(reason).strip()]
    return cleaned[:limit]


def _derive_signal_id(
    *,
    symbol: str,
    action: str,
    confidence: float,
    reasons: list[str],
    memory_context: dict[str, Any],
    timestamp: str,
    price: float | None,
) -> str:
    snapshot_id = str(memory_context.get("latest_snapshot_id", "")).strip()
    if snapshot_id:
        return snapshot_id
    reason_head = reasons[0] if reasons else ""
    price_repr = "" if price is None else f"{price:.5f}"
    seed = f"{symbol}|{action}|{confidence:.4f}|{reason_head}|{timestamp[:16]}|{price_repr}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return f"telegram_{digest}"


def _extract_price(output: dict[str, Any], mapped_action: str) -> float | None:
    contract = (
        output.get("status_panel", {})
        .get("entry_exit_decision", {})
    )
    if mapped_action in {"BUY", "SELL"}:
        value = contract.get("entry_price")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return None


def build_telegram_payload(output: dict[str, Any]) -> TelegramAlertPayload | None:
    signal = dict(output.get("signal") or {})
    contract = dict(output.get("status_panel", {}).get("entry_exit_decision") or {})
    contract_action = str(contract.get("action", "")).strip()
    mapped_action = ACTION_MAP.get(contract_action)
    if not mapped_action and signal.get("action") in {"BUY", "SELL"}:
        mapped_action = str(signal.get("action"))
    if mapped_action not in ACTIONABLE_ACTIONS:
        return None

    symbol = str(output.get("symbol") or signal.get("symbol") or "XAUUSD")
    confidence = _round_confidence(signal.get("confidence", contract.get("confidence", 0.0)))
    timestamp = _utc_now_iso()
    reasons = _top_reasons(signal.get("reasons", []))
    price = _extract_price(output, mapped_action)
    memory_context = dict(signal.get("memory_context") or {})
    signal_id = _derive_signal_id(
        symbol=symbol,
        action=mapped_action,
        confidence=confidence,
        reasons=reasons,
        memory_context=memory_context,
        timestamp=timestamp,
        price=price,
    )
    return TelegramAlertPayload(
        symbol=symbol,
        action=mapped_action,
        confidence=confidence,
        timestamp=timestamp,
        price=price,
        top_reasons=reasons,
        signal_id=signal_id,
    )


def _load_sent_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        sent_keys = payload.get("sent_keys", []) if isinstance(payload, dict) else []
        if isinstance(sent_keys, list):
            return {str(item) for item in sent_keys if str(item).strip()}
    except Exception:
        return set()
    return set()


def _save_sent_keys(path: Path, sent_keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "telegram_alert_state.v1",
        "sent_keys": sorted(list(sent_keys))[-1000:],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_dedupe_key(alert: TelegramAlertPayload) -> str:
    return f"{alert.symbol}|{alert.action}|{alert.signal_id}"


def _build_telegram_text(alert: TelegramAlertPayload) -> str:
    lines = [
        f"{alert.symbol} {alert.action}",
        f"confidence: {alert.confidence:.4f}",
        f"timestamp: {alert.timestamp}",
        f"signal_id: {alert.signal_id}",
    ]
    if alert.price is not None:
        lines.append(f"price: {alert.price:.5f}")
    if alert.top_reasons:
        lines.append(f"reasons: {'; '.join(alert.top_reasons)}")
    return "\n".join(lines)


def _send_telegram_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_seconds: float = 5.0,
) -> tuple[bool, str]:
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return True, body
    except error.HTTPError as exc:
        return False, f"http_error:{exc.code}"
    except error.URLError as exc:
        return False, f"url_error:{exc.reason}"
    except Exception as exc:
        return False, f"send_exception:{type(exc).__name__}"


def deliver_output_to_telegram(
    output: dict[str, Any],
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
    dedupe_state_path: str | Path = "memory/telegram_alert_state.json",
    sender: Callable[[TelegramAlertPayload, str, str, float], None] | None = None,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    alert = build_telegram_payload(output)
    if alert is None:
        return {
            "attempted": False,
            "sent": False,
            "skipped": True,
            "reason": "non_actionable",
        }

    token = (bot_token if bot_token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    cid = (chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", "")).strip()
    if not token or not cid:
        return {
            "attempted": False,
            "sent": False,
            "skipped": True,
            "reason": "telegram_credentials_missing",
            "error": "",
            "alert": alert.to_dict(),
        }

    state_path = Path(dedupe_state_path)
    sent_keys = _load_sent_keys(state_path)
    key = _build_dedupe_key(alert)
    if key in sent_keys:
        return {
            "attempted": False,
            "sent": False,
            "skipped": True,
            "reason": "duplicate_alert",
            "error": "",
            "alert": alert.to_dict(),
        }

    send_callable = sender or (
        lambda payload, tok, ch, timeout: _send_telegram_message(
            bot_token=tok,
            chat_id=ch,
            text=_build_telegram_text(payload),
            timeout_seconds=timeout,
        )
    )
    try:
        send_callable(alert, token, cid, timeout_seconds)
    except Exception as exc:
        return {
            "attempted": True,
            "sent": False,
            "skipped": False,
            "reason": "send_failed_fail_open",
            "error": str(exc),
            "alert": alert.to_dict(),
        }

    sent_keys.add(key)
    _save_sent_keys(state_path, sent_keys)
    return {
        "attempted": True,
        "sent": True,
        "skipped": False,
        "reason": "",
        "error": "",
        "alert": alert.to_dict(),
    }


def run_pipeline_with_telegram(
    config: RuntimeConfig,
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
    dedupe_state_path: str | Path = "memory/telegram_alert_state.json",
    sender: Callable[[str, str, str], tuple[bool, str]] | None = None,
    runner: Callable[[RuntimeConfig], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pipeline_runner = runner or run_pipeline
    output = pipeline_runner(config)
    delivery = deliver_output_to_telegram(
        output,
        bot_token=bot_token,
        chat_id=chat_id,
        dedupe_state_path=dedupe_state_path,
        sender=sender,
    )
    return output, delivery

