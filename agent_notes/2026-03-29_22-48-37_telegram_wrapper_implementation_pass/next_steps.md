## Immediate next steps
1. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. Execute wrapper via:
   - `python3 -c "from run import RuntimeConfig; from src.alerts.telegram_sidecar import run_pipeline_with_telegram; output, delivery = run_pipeline_with_telegram(RuntimeConfig(mode='replay', live_execution_enabled=False)); print(delivery)"`
3. Verify first actionable signal sends once, and immediate identical rerun is deduped.

## Optional hardening (wrapper-only)
- Add a tiny CLI wrapper script for easier operator usage (still calling existing sidecar functions).
- Add cooldown window behavior if needed beyond strict `signal_id` dedupe.

## Explicitly unchanged
- No signal engine logic changes in `run.py`.
- No model/output schema rewrites.
- No app/dashboard work.
