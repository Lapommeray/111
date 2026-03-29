## Risks / constraints
- Telegram transport is external I/O and can fail due to token/chat/network issues; wrapper is intentionally fail-open so signal generation is not interrupted.
- Dedupe state persistence currently uses a local JSON file; filesystem permission issues could degrade dedupe behavior (alerts may resend).
- EXIT price is often unavailable in final output contract; wrapper intentionally keeps `price` nullable for EXIT alerts.
