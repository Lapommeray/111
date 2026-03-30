# Signal Schema

## Pipeline output schema: `phase3.output.v1`

```
{
  "schema_version": "phase3.output.v1",
  "symbol": "XAUUSD",
  "signal": {
    "action": "BUY" | "SELL" | "WAIT",
    "confidence": 0.0..1.0,
    "reasons": ["reason_1", "reason_2", ...],
    "blocker_reasons": [...],
    "memory_context": {
      "latest_snapshot_id": "snap_...",
      ...
    },
    "schema_version": "phase3.v1",
    "consumer_hints": {
      "action_values": ["BUY", "SELL", "WAIT"],
      "confidence_range": [0.0, 1.0]
    },
    ...
  },
  "chart_objects": [...],
  "status_panel": {
    "entry_exit_decision": {
      "action": "LONG_ENTRY" | "SHORT_ENTRY" | "EXIT" | "NO_TRADE",
      "entry_price": float | null,
      "stop_loss": float | null,
      "take_profit": float | null,
      "exit_rule": str | null,
      "invalidation_reason": str,
      "confidence": float,
      "why_this_trade": str,
      "why_not_trade": str
    },
    ...
  }
}
```

## Telegram alert payload schema

```
{
  "symbol": "XAUUSD",
  "action": "BUY" | "SELL" | "EXIT",
  "confidence": 0.0..1.0 (4 decimal places),
  "timestamp": "ISO 8601 UTC",
  "price": float | null,
  "top_reasons": ["reason_1", "reason_2", "reason_3"],
  "signal_id": "snap_..." | "telegram_<hash>"
}
```

## Action mapping

| Contract action | Telegram action | Actionable? |
|----------------|----------------|-------------|
| LONG_ENTRY     | BUY            | Yes         |
| SHORT_ENTRY    | SELL           | Yes         |
| EXIT           | EXIT           | Yes         |
| NO_TRADE       | —              | No (skipped)|

Fallback: if `entry_exit_decision.action` is not in the map but `signal.action` is `BUY` or `SELL`, the signal action is used directly.

## Dedupe key format
```
{symbol}|{action}|{signal_id}
```

## Signal ID derivation
1. If `signal.memory_context.latest_snapshot_id` is present and non-empty, use it.
2. Otherwise, compute SHA-256 hash of `{symbol}|{action}|{confidence}|{first_reason}|{timestamp[:16]}|{price}` and use first 20 hex chars prefixed with `telegram_`.
