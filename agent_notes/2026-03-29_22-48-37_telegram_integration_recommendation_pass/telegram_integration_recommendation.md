## Telegram integration recommendation (safest + simplest)

### Direct answers to required questions

1. **Exact final signal output hook point**
   - Primary hook point: return value of `run_pipeline()` right before/at `return build_indicator_output(...)` in `run.py`.
   - Relevant output fields:
     - `output["signal"]` (includes `action`, `confidence`, `reasons`, `blocker_reasons`, `setup_classification`)
     - `output["status_panel"]["entry_exit_decision"]` (includes action/invalidation/entry_price and open-position semantics).

2. **Safest way to add Telegram delivery**
   - Add a **small external wrapper/sidecar caller** that:
     1) calls existing `run_pipeline(config)`,
     2) reads the returned output dict,
     3) filters actionable alerts (`BUY`, `SELL`, `EXIT`),
     4) dedupes, then
     5) sends Telegram message.
   - Keep the existing signal engine untouched.

3. **Where should Telegram sending happen?**
   - Prefer **very small sidecar/wrapper after final signal output**.
   - Do not put network send calls directly inside `run_pipeline` core path.

4. **Safest/simplest option for this repository and why**
   - **Sidecar/wrapper is safest and simplest for this repo** because:
     - `run_pipeline` is the orchestrator of core trading logic and heavily test-locked.
     - It currently returns a fully structured, machine-consumable output object designed for downstream consumption.
     - Injecting Telegram I/O directly into core path risks coupling live network failures/retries to signal generation behavior.
     - Wrapper preserves architecture: indicator engine remains source of truth; alerting becomes optional consumer.

5. **Minimum Telegram alert schema**
   - Required payload fields:
     - `symbol`
     - `action` (`BUY` | `SELL` | `EXIT`)
     - `confidence`
     - `timestamp`
     - `price` (if available)
     - `top_reasons` (small list)
     - `signal_id` (derived deterministic id if not native)

6. **Duplicate prevention without breaking behavior**
   - Dedupe in wrapper only, not inside signal engine.
   - Build `signal_id` deterministically from existing output fields (for example hash of:
     `symbol + action + rounded_confidence + timestamp_basis + top_reasons + price_basis`).
   - Store last sent ids in a small local state file under `memory/` (or dedicated alerts state file).
   - Skip send when same `signal_id` already sent within configured cooldown window.

7. **Smallest implementation plan preserving architecture**
   - Step 1: Add tiny `telegram_alert_sidecar.py` module/script:
     - imports `run_pipeline`, `RuntimeConfig`;
     - evaluates actionable action set (`BUY`, `SELL`, `EXIT`);
     - maps output to minimal alert schema;
     - dedupe check via local state;
     - sends Telegram via bot HTTP API.
   - Step 2: Add minimal config inputs for sidecar only (bot token/chat id/cooldown), preferably from env vars.
   - Step 3: Add focused tests for sidecar mapping/filtering/dedupe only.
   - Step 4: Keep `run.py` signal computation untouched except optional non-invasive invocation entrypoint wiring if explicitly needed.

### Recommendation summary
- **Choose wrapper/sidecar after `run_pipeline` output.**
- It is the least risky, easiest to maintain, and preserves the existing architecture and deterministic test baseline.
