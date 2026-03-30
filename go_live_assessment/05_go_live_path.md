# GO-LIVE PATH

## Assessment Date: 2026-03-30

---

## Current State

The system has **mature infrastructure** (safety gates, risk controls, error handling, evaluation pipeline) but **cannot produce any trades** due to a structural vote aggregation issue. The path to live requires fixing this core issue first, then validating on real data.

---

## Phase 1: Paper/Shadow Mode (Signal Monitoring)

### Prerequisites (minimum to start)
1. **[MUST FIX] Vote aggregation logic** — Modify `aggregate_direction()` in `src/utils.py:14-26` to exclude neutral votes from the WAIT count. Without this, every signal is WAIT and no useful data can be collected.
2. **[MUST FIX] Load real XAUUSD M5 data** — Replace synthetic CSV with real market OHLCV data (minimum 500 bars, ideally 2000+).
3. **[MUST SET] Realistic execution costs** — In `config/settings.json`:
   - `execution_spread_cost_points`: 3.0-5.0 (typical XAUUSD)
   - `execution_commission_cost_points`: per broker
   - `execution_slippage_cost_points`: 0.5-1.0
4. **[RECOMMEND] Quarantine weak modules** — Add to `config/settings.json`:
   ```json
   "quarantined_modules": ["human_lag_exploit", "quantum_tremor_scanner"]
   ```

### Validation criteria before proceeding
- [ ] System generates at least some BUY/SELL signals (not 100% WAIT)
- [ ] Replay evaluation produces ≥ 30 closed trades
- [ ] Win rate > 0% on closed trades
- [ ] Decision quality gate passes (actionable_ratio > 0)

### How to run
```bash
python3 run.py --mode replay --replay-source csv --evaluate-replay true --config config/settings.json
```

---

## Phase 2: Limited Low-Risk Live Test

### Prerequisites (ALL required)
1. **Phase 1 completed** with positive results
2. **[MUST ENABLE] Walk-forward validation** — Set `walk_forward_enabled: true` in settings
3. **[MUST VERIFY] Walk-forward OOS metrics:**
   - OOS win rate > 45%
   - OOS net expectancy > 0
   - OOS profit factor > 1.0
   - Minimum 30 OOS trades across windows
4. **[MUST INSTALL] MetaTrader5** — On Windows machine with MT5 terminal:
   ```
   pip install MetaTrader5
   ```
5. **[MUST SET] Telegram credentials** — Create `.env`:
   ```
   TELEGRAM_BOT_TOKEN=<real_token>
   TELEGRAM_CHAT_ID=<real_chat_id>
   ```
6. **[MUST TEST] End-to-end on demo account:**
   - MT5 demo account connected
   - Live authorization enabled: `--live-authorization-enabled true`
   - Verify order placement returns `status=accepted`
   - Verify Telegram alert delivery
7. **[MUST VERIFY] Risk controls appropriate:**
   - `max_daily_loss_points`: appropriate for account size
   - `max_total_drawdown_points`: appropriate for account size
   - `live_order_volume`: 0.01 (minimum lot)

### Validation criteria before proceeding
- [ ] Walk-forward OOS results positive across ≥ 3 windows
- [ ] Demo account test: ≥ 10 trades executed successfully
- [ ] Telegram delivery confirmed
- [ ] Auto-stop triggers correctly after 3 consecutive failures
- [ ] Capital guard triggers at daily loss limit

### How to run (demo)
```bash
python3 run.py --mode live --live-execution-enabled true --live-authorization-enabled true --config config/settings.json
```

---

## Phase 3: Full Live

### Prerequisites (ALL required)
1. **Phase 2 completed** with consistent positive results
2. **[MUST HAVE] Minimum 100 demo trades** with:
   - Net positive PnL after costs
   - Win rate > 45%
   - Profit factor > 1.2
   - Max drawdown within acceptable limits
3. **[MUST HAVE] Live broker account** configured in MT5
4. **[MUST HAVE] Macro API keys** (optional but recommended):
   ```
   ALPHA_VANTAGE_API_KEY=<key>
   FRED_API_KEY=<key>
   ```
5. **[MUST SET] Production risk limits:**
   - Conservative volume: 0.01-0.05 lots
   - Tight daily loss limit
   - Emergency stop tested
6. **[MUST HAVE] Monitoring** — Telegram alerts active, state files monitored

### How to run (live)
```bash
python3 run.py --mode live --live-execution-enabled true --live-authorization-enabled true --config config/settings.json
```

---

## Timeline Estimate

| Phase | Minimum Duration | Depends On |
|-------|-----------------|------------|
| Fix vote aggregation | 1 hour | Code change + test update |
| Load real data | 1 hour | Data sourcing |
| Phase 1 validation | 1-2 days | Run replay, analyze results |
| Phase 2 demo testing | 1-2 weeks | Market hours, trade volume |
| Phase 3 live | After Phase 2 success | Risk tolerance |

---

## What NOT To Do

1. **Do NOT go live without fixing the vote aggregation** — 100% of signals will be WAIT
2. **Do NOT trust synthetic data results** — They are meaningless for real trading
3. **Do NOT assume the existing evaluation gates prove profitability** — They prove code correctness, not edge
4. **Do NOT skip walk-forward OOS testing** — In-sample results are unreliable
5. **Do NOT start with > 0.01 lot size** — Prove edge on minimum size first
