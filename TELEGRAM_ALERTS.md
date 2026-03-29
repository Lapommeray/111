# Telegram Alerts (Minimal Sidecar)

This repository now includes a minimal Telegram sidecar wrapper that consumes the final `run_pipeline()` output and sends only actionable alerts:

- `BUY`
- `SELL`
- `EXIT`

The core signal engine is not modified for network sending.

## Files

- `src/alerts/telegram_sidecar.py`
- `src/alerts/__init__.py`
- `src/tests/test_telegram_sidecar.py`

## Environment setup

Set these environment variables before running:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Example:

`export TELEGRAM_BOT_TOKEN="123456:ABCDEF..."`

`export TELEGRAM_CHAT_ID="123456789"`

## Run

Run via Python using the existing runtime config:

`python3 -c "from run import RuntimeConfig; from src.alerts.telegram_sidecar import run_pipeline_with_telegram; output, delivery = run_pipeline_with_telegram(RuntimeConfig()); print(delivery)"`

You can also pass token/chat directly in code:

`run_pipeline_with_telegram(config, bot_token="...", chat_id="...")`

## Behavior

1. Calls `run_pipeline(config)` and reads final output.
2. Uses final contract action from `status_panel.entry_exit_decision.action`.
3. Maps:
   - `LONG_ENTRY -> BUY`
   - `SHORT_ENTRY -> SELL`
   - `EXIT -> EXIT`
4. Ignores non-actionable states.
5. Builds minimal payload:
   - symbol, action, confidence, timestamp, price (if available), top reasons (1-3), signal_id.
6. Deduplicates alerts in sidecar state file:
   - default: `memory/telegram_alert_state.json`
7. Sends Telegram Bot API message.
8. Fails open: send failure never raises into the core pipeline caller path.

## Deduplication

Dedupe key:

`{symbol}|{action}|{signal_id}`

`signal_id` preference:

1. `signal.memory_context.latest_snapshot_id` when present.
2. fallback deterministic hash.

## Notes

- This sidecar is intentionally minimal and isolated from core signal generation logic.
- No dashboard or mobile app is included.
