# Next Steps

1. **Set real credentials**: Export `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables with real values from @BotFather.
2. **Live test**: Run `python3 run.py --mode live --telegram true` (requires MT5 on Windows) or trigger a BUY/SELL signal in replay and verify the Telegram message arrives.
3. **Scheduled execution**: Use cron or systemd timer to run the pipeline periodically with `--telegram true`.
4. **Alert enrichment (optional)**: Add SL/TP/entry_price to the Telegram message text if desired.
5. **Rate limiting (optional)**: Add rate limiting to `_send_telegram_message` if running at high frequency.
6. **Alert history dashboard (optional)**: Parse `memory/telegram_alert_state.json` for alert audit trail.
