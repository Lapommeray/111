# Telegram Bot Setup

## Step 1: Create a bot
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`.
3. Follow prompts: choose a name and username for your bot.
4. Copy the **bot token** (format: `123456789:ABCDefGHIjklMNOpqrsTUVwxyz`).

## Step 2: Get your chat ID
1. Start a conversation with your new bot (send it any message).
2. Search for `@userinfobot` or `@RawDataBot` on Telegram and send `/start`.
3. It will reply with your **chat ID** (a numeric string like `123456789`).

Alternative: For a group chat, add the bot to the group, then use:
```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```
Look for the `chat.id` field in the response.

## Step 3: Set environment variables
```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCDefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="123456789"
```

## Step 4: Test
```bash
python3 -c "
from src.alerts.telegram_sidecar import deliver_output_to_telegram

output = {
    'symbol': 'XAUUSD',
    'signal': {
        'action': 'BUY',
        'confidence': 0.85,
        'reasons': ['test_alert'],
        'memory_context': {'latest_snapshot_id': 'test_snap_001'},
    },
    'status_panel': {
        'entry_exit_decision': {
            'action': 'LONG_ENTRY',
            'entry_price': 2380.50,
        }
    },
}

result = deliver_output_to_telegram(output)
print(result)
"
```

Expected output (with valid credentials):
```
{'attempted': True, 'sent': True, 'skipped': False, 'reason': '', 'error': '', 'alert': {'symbol': 'XAUUSD', 'action': 'BUY', ...}}
```

Expected Telegram message:
```
XAUUSD BUY
confidence: 0.8500
timestamp: 2026-03-29T23:52:00.000000+00:00
signal_id: test_snap_001
price: 2380.50000
reasons: test_alert
```
