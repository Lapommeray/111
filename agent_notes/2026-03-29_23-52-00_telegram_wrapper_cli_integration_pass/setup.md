# Setup

## Prerequisites
- Python 3.12+
- pytest (for running tests)
- No other dependencies required

## Install
```bash
pip install pytest
```

## Environment variables
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

Or copy `.env.example` to `.env` and source it:
```bash
cp .env.example .env
# Edit .env with real values
source .env  # or use a tool like direnv
```

## Verify installation
```bash
python3 -m pytest src/tests/test_telegram_sidecar.py -v --tb=short
```
Expected: 38 passed.

## Run pipeline with Telegram alerts
```bash
python3 run.py --mode replay --replay-source csv --config config/settings.json --telegram true
```

## Run pipeline WITHOUT Telegram alerts (default)
```bash
python3 run.py --mode replay --replay-source csv --config config/settings.json
```
