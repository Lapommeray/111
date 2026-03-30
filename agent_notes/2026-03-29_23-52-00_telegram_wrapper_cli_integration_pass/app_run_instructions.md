# Application Run Instructions

## Replay mode (no external services needed)

### Without Telegram
```bash
python3 run.py --mode replay --replay-source csv --config config/settings.json
```

### With Telegram alerts
```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python3 run.py --mode replay --replay-source csv --config config/settings.json --telegram true
```

## Output format
The command prints two Python dicts to stdout when `--telegram true`:
1. The full pipeline output dict (same as without `--telegram`)
2. The Telegram delivery result dict

### Delivery result shapes

**Non-actionable signal (WAIT/NO_TRADE):**
```python
{'attempted': False, 'sent': False, 'skipped': True, 'reason': 'non_actionable'}
```

**Actionable signal sent successfully:**
```python
{'attempted': True, 'sent': True, 'skipped': False, 'reason': '', 'error': '', 'alert': {...}}
```

**Duplicate alert skipped:**
```python
{'attempted': False, 'sent': False, 'skipped': True, 'reason': 'duplicate_alert', 'error': '', 'alert': {...}}
```

**Send failed (fail-open):**
```python
{'attempted': True, 'sent': False, 'skipped': False, 'reason': 'send_failed_fail_open', 'error': '...', 'alert': {...}}
```

**Missing credentials:**
```python
{'attempted': False, 'sent': False, 'skipped': True, 'reason': 'telegram_credentials_missing', 'error': '', 'alert': {...}}
```

## Safe one-shot test (no real Telegram send)
```bash
python3 -c "
from src.alerts.telegram_sidecar import deliver_output_to_telegram
output = {
    'symbol': 'XAUUSD',
    'signal': {'action': 'BUY', 'confidence': 0.85, 'reasons': ['test'], 'memory_context': {'latest_snapshot_id': 'safe_test_001'}},
    'status_panel': {'entry_exit_decision': {'action': 'LONG_ENTRY', 'entry_price': 2380.5}},
}
result = deliver_output_to_telegram(output, bot_token='', chat_id='')
print(result)
"
```
Expected: `{'attempted': False, 'sent': False, 'skipped': True, 'reason': 'telegram_credentials_missing', ...}`
