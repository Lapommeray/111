# MISSING / BLOCKING ITEMS CHECKLIST

**Assessment Date:** 2026-03-30

## Critical Blockers (Must Fix Before Any Live Trading)

- [ ] **Real market data** — Current data is synthetic (320 rows, uniform 60s intervals, deterministic linear drift). Need real XAUUSD M5 OHLCV data.
- [ ] **System generates trades** — All 21 replay steps produce WAIT. Zero BUY/SELL signals ever generated. Root cause: aggressive filtering (12/21 blocked by `structure_liquidity_conflict`, 2/21 by `confidence_below_threshold`, remaining 9 abstain on conflicting direction signals).
- [ ] **Execution cost realism** — All costs are 0.0. `execution_realism_v2_enabled: false`. Must set realistic spread (3-5 pts for XAUUSD), commission, and slippage before any evaluation is meaningful.
- [ ] **Walk-forward validation** — `walk_forward_enabled: false`. No out-of-sample testing performed.
- [ ] **Minimum trade sample size** — Need ≥30 closed trades for basic statistical significance. Currently at 0.
- [ ] **MT5 terminal** — Requires Windows with MetaTrader5 terminal running. Cannot verify order execution path without it.
- [ ] **Telegram credentials** — `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` must be set in environment or `.env` file.

## Important but Not Strictly Blocking

- [ ] **Macro data API keys** — `ALPHA_VANTAGE_API_KEY` and `FRED_API_KEY` unset. Macro analysis defaults to neutral (non-blocking but reduces signal quality).
- [ ] **Quarantined modules review** — `quarantined_modules: []` in config. Three modules identified as weak/placeholder (`human_lag_exploit`, `invisible_data_miner`, `quantum_tremor_scanner`) are not quarantined. Should be quarantined or validated.
- [ ] **Calibration status** — `calibration_status: "temporary_defaults_pending_broker_measurement"`. Need real broker-measured values.
- [ ] **Data sufficiency tier** — Evaluation reports `data_sufficiency_tier: "insufficient"`.

## What IS Working

- [x] **Test suite** — 779/779 tests pass
- [x] **Pipeline architecture** — Full signal pipeline executes without errors
- [x] **Safety defaults** — Live execution blocked by default, requires dual authorization flags
- [x] **Risk controls** — Capital guard, daily loss limits, drawdown limits, emergency stop, consecutive loss streak limits — all implemented and tested
- [x] **MT5 adapter code** — Real MT5 integration (not mocked), with proper fallback to CSV
- [x] **Order execution code** — Real `mt5.order_send()` with comprehensive error handling for all MT5 return codes
- [x] **Telegram sidecar** — Real Telegram Bot API integration with deduplication, fail-open design
- [x] **Symbol guard** — Locked to XAUUSD only
- [x] **Evaluation gates** — Decision completeness, decision quality, replay outcome, and threshold calibration gates all functional
- [x] **Error handling** — Connection failures, order rejections, retries (bounded), auto-stop after 3 consecutive failures
- [x] **Multi-layer safety** — 11-point pre-trade readiness chain, quarantine system, auto-stop mechanism
