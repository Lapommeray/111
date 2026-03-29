## Telegram setup

1. Create/open your Telegram bot in BotFather and obtain a bot token.
2. Add the bot to the target chat (direct chat or group).
3. Obtain `chat_id` (for group chats, ensure the bot has permission to post).
4. Export credentials before running wrapper:
   - `export TELEGRAM_BOT_TOKEN='YOUR_BOT_TOKEN'`
   - `export TELEGRAM_CHAT_ID='YOUR_CHAT_ID'`
5. Keep credentials out of repository files; use environment variables.
