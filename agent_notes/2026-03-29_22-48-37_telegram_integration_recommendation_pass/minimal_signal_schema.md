## Minimal Telegram signal schema (actionable-only)

### Action filter
- Send only when final action is:
  - `BUY`
  - `SELL`
  - `EXIT`
- Ignore non-actionable states such as `WAIT` / `NO_TRADE`.

### Payload fields (minimum)
- `symbol`:
  - from `output["symbol"]` (or `output["signal"]["symbol"]`).
- `action`:
  - preferred from `output["status_panel"]["entry_exit_decision"]["action"]` mapped to:
    - `LONG_ENTRY` -> `BUY`
    - `SHORT_ENTRY` -> `SELL`
    - `EXIT` -> `EXIT`
  - fallback from `output["signal"]["action"]` for BUY/SELL.
- `confidence`:
  - from `output["signal"]["confidence"]` (or contract confidence fallback).
- `timestamp`:
  - from current UTC send time in wrapper.
- `price`:
  - for BUY/SELL: `output["status_panel"]["entry_exit_decision"]["entry_price"]` (fallback to latest bar close if wrapper has bars).
  - for EXIT: optional `null` if no explicit current/exit price field is available.
- `top_reasons`:
  - first 1–3 items from `output["signal"]["reasons"]`.
- `signal_id`:
  - preferred: `output["signal"]["memory_context"]["latest_snapshot_id"]` (maps to `snap_...` from `PatternStore.record_snapshot`).

### Example normalized alert object
- `symbol`: `XAUUSD`
- `action`: `BUY|SELL|EXIT`
- `confidence`: `0.00..1.00`
- `timestamp`: `2026-03-29T22:00:00Z`
- `price`: `float | null`
- `top_reasons`: `list[str]`
- `signal_id`: `snap_YYYYMMDD...` (or fallback hash id if missing)

### Duplicate prevention key (wrapper-side)
- Use:
  - `dedupe_key = f"{symbol}|{action}|{signal_id}"`
- If `signal_id` missing, fallback:
  - `dedupe_key = sha256(f"{symbol}|{action}|{round(confidence,4)}|{first_reason}|{minute_bucket_timestamp}")`
- Persist last sent keys in a small local JSON state (separate from signal engine memory files).
