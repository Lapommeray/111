# Changed Files

## Modified
- `run.py` — Added `--telegram true|false` CLI argument and Telegram delivery branch in `main()`
- `src/tests/test_telegram_sidecar.py` — Expanded from 7 to 38 tests

## Added
- `.env.example` — Placeholder-only environment variable template
- `agent_notes/2026-03-29_23-52-00_telegram_wrapper_cli_integration_pass/` — This documentation folder (9 files)

## Not changed
- `src/alerts/telegram_sidecar.py` — Existing sidecar, untouched
- `src/alerts/__init__.py` — Existing exports, untouched
- `TELEGRAM_ALERTS.md` — Existing docs, untouched
- All core signal engine files — untouched
