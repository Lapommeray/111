# Setup

## What was added
- Minimal Telegram sidecar wrapper module: `src/alerts/telegram_sidecar.py`
- Sidecar exports: `src/alerts/__init__.py`
- Focused tests: `src/tests/test_telegram_sidecar.py`
- Usage docs: `TELEGRAM_ALERTS.md`

## Prerequisites
- Existing repository runtime config (`config/settings.json`) remains unchanged.
- Python environment with stdlib only (sidecar uses `urllib`).
- Telegram bot token and chat id.

## Environment variables
Set both before running:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Example:
- `export TELEGRAM_BOT_TOKEN="123456:ABC..."`
- `export TELEGRAM_CHAT_ID="-1001234567890"`

## Optional dedupe state path
- Default path: `memory/telegram_alert_state.json`
- You can override via function argument in wrapper calls.
