## Immediate next step (if approved)
1. Implement a minimal wrapper script (new file, no run.py changes) that:
   - invokes `run_pipeline(RuntimeConfig(...))`,
   - maps output to Telegram payload only for `BUY`/`SELL`/`EXIT`,
   - suppresses duplicates via persisted dedupe key in `memory/telegram_alert_state.json`,
   - sends via Telegram Bot API.
2. Add focused tests only for payload mapping + dedupe logic in the wrapper module.

## Follow-up validation step
1. Run wrapper in replay mode with patched `run_pipeline` outputs to verify:
   - actionable filtering,
   - payload shape,
   - dedupe behavior.

## Out-of-scope for this step
- No mobile app.
- No dashboard.
- No architecture changes to the current signal engine.
