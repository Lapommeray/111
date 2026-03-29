## Task
Implement the approved minimal Telegram wrapper/sidecar path that consumes final `run_pipeline` output and sends actionable alerts (`BUY`, `SELL`, `EXIT`) with dedupe and fail-open behavior.

## What I implemented
- Added `src/alerts/telegram_sidecar.py` as the only Telegram delivery layer.
- Added `src/alerts/__init__.py` exports for sidecar usage.
- Added focused unit tests in `src/tests/test_telegram_sidecar.py` covering:
  - action mapping from final contract,
  - actionable-only filtering,
  - dedupe logic,
  - fail-open behavior when send fails.
- Added `TELEGRAM_ALERTS.md` with setup and run instructions.

## Core safety constraints honored
- No edits to `run.py` signal logic.
- No network send logic added to core signal model/output modules.
- Telegram transport failures are fail-open and do not break `run_pipeline`.

## Result
- Minimal sidecar delivery path is implemented and test-backed.
