# Risks

## Low risk
- **Telegram API rate limits**: Bot API allows ~30 messages/second to a single chat. The pipeline runs at most once per timeframe bar (e.g., every 5 minutes), so rate limiting is not a concern under normal usage.
- **Dedupe state file corruption**: The `_load_sent_keys` function handles corrupted JSON gracefully (returns empty set). Worst case: a duplicate alert is sent once after corruption.

## Medium risk
- **Token exposure**: If `TELEGRAM_BOT_TOKEN` is logged or printed in a shared environment, it can be used to impersonate the bot. Mitigation: never commit tokens; use environment variables only.
- **Replay signals are mostly WAIT/NO_TRADE**: In replay mode, most signals are non-actionable. To test Telegram delivery end-to-end, you need either a live BUY/SELL signal or a crafted test (see setup.md).

## Not a risk
- **Core pipeline breakage**: The Telegram wrapper is a pure sidecar. It reads the pipeline output dict after `run_pipeline()` completes. No core logic is modified.
- **Fail-open guarantee**: All Telegram/network failures are caught and returned as a result dict. The pipeline output is always returned regardless of send success/failure.
