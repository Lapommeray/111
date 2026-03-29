## App run instructions (wrapper/sidecar)

### Option A — Use from Python (recommended)
1. Build your runtime config as usual:
   - `from run import RuntimeConfig`
2. Call wrapper:
   - `from src.alerts.telegram_sidecar import run_pipeline_with_telegram`
   - `output, delivery = run_pipeline_with_telegram(config)`
3. Inspect:
   - `output` (unchanged pipeline output)
   - `delivery` (alert attempt metadata)

### Option B — Pass explicit credentials per call
- `run_pipeline_with_telegram(config, bot_token="...", chat_id="...")`
- This overrides env vars.

### Wrapper behavior summary
- Calls `run_pipeline(config)` first.
- Derives final actionable action from `status_panel.entry_exit_decision.action`.
- Maps:
  - `LONG_ENTRY -> BUY`
  - `SHORT_ENTRY -> SELL`
  - `EXIT -> EXIT`
- Ignores non-actionable states.
- Dedupes by:
  - `symbol|action|signal_id`
- Sends Telegram message via Bot API only when actionable and non-duplicate.
- Fail-open:
  - send failure returns delivery error metadata,
  - pipeline output is still returned.
