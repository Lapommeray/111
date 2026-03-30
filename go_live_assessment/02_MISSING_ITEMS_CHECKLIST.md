# MISSING ITEMS CHECKLIST

## Critical Blockers (Must Fix Before Any Live Use)

- [ ] **Real market data** — Current CSV is synthetic (auto-generated linear drift, 320 bars, ~5 hours). Need real historical XAUUSD M5 data (minimum months of data).
- [ ] **System must generate actual trades** — 21/21 replay signals were WAIT. Zero BUY or SELL signals ever produced. Root cause: `structure_liquidity_conflict` (10/21) and `confidence_below_threshold` (2/21) block everything.
- [ ] **Execution cost modeling** — All costs at 0.0:
  - `execution_spread_cost_points: 0.0`
  - `execution_commission_cost_points: 0.0`
  - `execution_slippage_cost_points: 0.0`
  - `execution_realism_v2_enabled: false`
- [ ] **Telegram credentials** — `.env` not created. `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` not set.
- [ ] **MT5 terminal** — MetaTrader5 package not installed. Live execution path untestable without Windows + MT5 terminal.
- [ ] **Walk-forward validation** — `walk_forward_enabled: false`. No OOS testing performed.

## High Priority (Should Fix Before Live)

- [ ] **Macro data API keys** — `ALPHA_VANTAGE_API_KEY` and `FRED_API_KEY` not set. Macro analysis defaults to neutral/disabled.
- [ ] **Signal lifecycle** — `signal_lifecycle_enabled: false`. Stale signals won't be rejected.
- [ ] **Minimum trade sample** — Need ≥30 closed trades for any statistical reliability, ≥100 for confidence.
- [ ] **Realistic backtest with costs** — Even with trades, need to verify edge survives after spread/commission/slippage.
- [ ] **Live execution authorization** — `live_authorization_enabled: false` (correct default, but needs explicit activation path documentation).

## Medium Priority (Should Verify Before Scaling)

- [ ] **Weak/quarantinable modules** — `human_lag_exploit`, `invisible_data_miner`, `quantum_tremor_scanner` are flagged as weak (per repo memories). Currently active (quarantined_modules: []).
- [ ] **Position size limits** — Current: 0.01 lots, risk fraction 0.1%. Verify this is appropriate for account size.
- [ ] **Max daily loss limits** — 3.0 points daily, 12.0 points total drawdown. Verify these are calibrated.
- [ ] **Multi-session testing** — CSV covers only ~5 hours. System has session filters that block off-hours. Need data spanning multiple trading sessions.

## Already Working (Verified)

- [x] Test suite: 779/779 tests pass
- [x] Pipeline execution: All modules compute real values (no stubs)
- [x] Risk controls: Capital guard, daily loss limit, drawdown limit, consecutive loss limit, emergency stop
- [x] Kill switches: Auto-stop after 3 consecutive failures, quarantine system
- [x] MT5 adapter: Real implementation with proper error handling and fallbacks
- [x] Telegram sidecar: Real HTTP integration with dedup and fail-open
- [x] Order execution code: Real MT5 order_send with comprehensive error handling
- [x] Symbol guard: Locked to XAUUSD only
- [x] Execution state: All gates default to blocked/disabled (safe defaults)
- [x] Pre-trade checks: 11-point readiness chain
- [x] Retry logic: Bounded single retry for transient errors
- [x] Evaluation gates: Completeness, quality, outcome, calibration gates exist
