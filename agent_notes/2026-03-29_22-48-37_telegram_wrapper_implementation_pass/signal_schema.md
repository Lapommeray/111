## Telegram signal schema (implemented)

### Action eligibility
- Sidecar sends only when mapped final contract action is:
  - `BUY`
  - `SELL`
  - `EXIT`
- Non-actionable states (for example `NO_TRADE`) are skipped.

### Source fields from pipeline output
- `symbol`:
  - `output["symbol"]` fallback `output["signal"]["symbol"]`
- `action`:
  - mapped from `output["status_panel"]["entry_exit_decision"]["action"]`:
    - `LONG_ENTRY` -> `BUY`
    - `SHORT_ENTRY` -> `SELL`
    - `EXIT` -> `EXIT`
  - fallback to raw `signal.action` only for `BUY`/`SELL`
- `confidence`:
  - `output["signal"]["confidence"]`
- `timestamp`:
  - sidecar UTC timestamp at alert build time
- `price`:
  - for BUY/SELL: `status_panel.entry_exit_decision.entry_price` when available
  - for EXIT: `null` (unless price is present in contract in future)
- `top_reasons`:
  - first 1–3 entries from `output["signal"]["reasons"]`
- `signal_id`:
  - preferred: `output["signal"]["memory_context"]["latest_snapshot_id"]`
  - fallback: deterministic hash over symbol/action/confidence/reason head/time bucket/price

### Dedupe key
- `dedupe_key = f"{symbol}|{action}|{signal_id}"`
- Persisted state file: `memory/telegram_alert_state.json`

