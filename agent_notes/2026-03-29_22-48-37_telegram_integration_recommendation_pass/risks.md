## Risks / constraints
- Telegram transport introduces external failure modes (network, token/chat misconfig), so alert-send errors must be fail-open relative to signal generation.
- Duplicate suppression must be scoped to alerts only and must not alter signal/action computation in `run.py`.
- `run.py` currently prints whole output dict in CLI mode; directly embedding Telegram send inside `run_pipeline()` increases blast radius if send fails.
- If only replay is used, `EXIT` signals may depend on open-position context in `status_panel.entry_exit_decision`, so wrapper logic must use this field instead of only `signal.action`.
