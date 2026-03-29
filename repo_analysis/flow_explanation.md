# Flow Explanation

## System Overview

This is a **modular XAUUSD (gold) trading indicator system** that:
1. Reads bar (OHLCV) data from MT5 broker or CSV files
2. Runs it through a multi-module analysis pipeline
3. Produces a BUY / SELL / WAIT decision with confidence score
4. Optionally executes trades via MT5
5. Records outcomes and learns from them

## Two Operational Modes

### Mode 1: Single Pipeline Run (`run_pipeline`)

**Entrypoint**: `run.py:main()` → `run_pipeline(config)`

```
1. Load config (config/settings.json or CLI args)
2. Validate config (symbol=XAUUSD, timeframe, bars, paths, thresholds)
3. Load bar data:
   - Live mode: Try MT5 → fallback to CSV
   - Replay mode: Load from CSV or memory snapshot
4. Build MT5 readiness state (connection checks, safety gates)
5. Run core analysis:
   a. classify_market_structure(bars)     → structure (bias, regime)
   b. assess_liquidity_state(bars)        → liquidity (sweeps, direction hint)
   c. compute_confidence(structure, liq)  → base confidence + direction
6. Run advanced module pipeline (pipeline.py:run_advanced_modules):
   a. Features (13 modules): displacement, FVG, volatility, sessions,
      spread, liquidity_sweep, compression, session_behavior,
      market_regime, execution_quality, invisible_data_miner,
      human_lag_exploit, quantum_tremor_scanner
   b. Filters (5 modules): session, spread, conflict, memory, self_destruct
   c. Scoring (4 modules): setup_score, regime_score, spectral_fusion,
      meta_conscious_routing
   d. Memory (1 module): meta_adaptive_ai
   → Each module produces: direction_vote, confidence_delta, blocked flag
   → Aggregate: final_direction via vote counting, final_confidence via delta sum
7. Collect macro state (DXY, yields, calendar, etc. — requires API keys)
8. Run loss blocker (confidence + spread check)
9. Run capital guard (daily loss, drawdown, streak limits)
10. Apply directional conviction filter:
    - If conviction < 0.62 or vote margin < 2 → force WAIT
11. Build signal lifecycle context (freshness check)
12. Run controlled MT5 live execution:
    - Live mode: Place real orders with full verification chain
    - Replay mode: Simulate order acceptance
13. Record outcomes (promoted or blocked)
14. Run evolution kernel (self-inspect → find gaps → propose → verify → promote)
15. Build final output:
    - Signal payload (action, confidence, reasons, modules, macro)
    - Chart objects (structure lines, liquidity levels)
    - Status panel (execution state, system health)
    → Return as JSON dict
```

### Mode 2: Replay Evaluation (`run_replay_evaluation`)

**Entrypoint**: `run.py:main()` with `--evaluate-replay true`

```
1. Load same config
2. Call evaluate_replay() which:
   a. Reads full CSV
   b. Steps through data in windows (evaluation_stride bars apart)
   c. At each step: creates isolated memory dir, runs run_pipeline()
   d. Collects results: decisions, P&L, trades, drawdown
   e. Builds summary: win rate, expectancy, max drawdown, etc.
3. Run 4 evaluation gates in sequence:
   a. Decision completeness → every record must be actionable/blocked/abstain/invalid
   b. Decision quality → distribution sanity, confidence diversity
   c. Replay outcome → economic sanity (hard-fail on 0% win rate, negative expectancy)
   d. Threshold calibration → distributional recommendations
   Each gate persists its report and the overall report is saved incrementally.
4. Optionally run knowledge expansion (if enabled):
   a. Phase A: Generate candidate module specs from replay gaps
   b. Continuous governed improvement cycle
```

## Data Flow Diagram

```
CSV/MT5 Bars
     │
     ▼
┌─────────────────┐
│ Market Structure │──→ bias, regime
│ Liquidity        │──→ sweeps, direction hint
│ Base Confidence  │──→ initial confidence + direction
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ Advanced Module Pipeline     │
│                             │
│  Features (13):             │
│  ├─ displacement            │──→ direction votes
│  ├─ fvg                     │──→ confidence deltas
│  ├─ volatility              │──→ blocked flags
│  ├─ sessions                │
│  ├─ spread_state            │
│  ├─ liquidity_sweep         │
│  ├─ compression_expansion   │
│  ├─ session_behavior        │
│  ├─ market_regime           │
│  ├─ execution_quality       │
│  ├─ invisible_data_miner*   │  * = quarantinable
│  ├─ human_lag_exploit*      │
│  └─ quantum_tremor_scanner* │
│                             │
│  Filters (5):               │
│  ├─ session_filter          │──→ can block trade
│  ├─ spread_filter           │
│  ├─ conflict_filter         │
│  ├─ memory_filter           │
│  └─ self_destruct_protocol  │
│                             │
│  Scoring (4):               │
│  ├─ setup_score             │
│  ├─ regime_score            │
│  ├─ spectral_signal_fusion* │
│  └─ meta_conscious_routing* │
│                             │
│  Memory (1):                │
│  └─ meta_adaptive_ai       │
└────────┬────────────────────┘
         │
         ▼ aggregate votes + deltas
┌──────────────────┐
│ Final Direction  │  (BUY / SELL / WAIT)
│ Final Confidence │  (0.0 - 1.0)
└────────┬─────────┘
         │
         ▼
┌───────────────────────────────┐
│ Post-Pipeline Gates           │
│ ├─ Loss Blocker              │
│ ├─ Capital Guard             │
│ ├─ Macro Risk Check          │
│ ├─ Directional Conviction    │
│ │   (conviction < 0.62 → WAIT)│
│ └─ MT5 Readiness Chain       │
└────────┬──────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Trade Execution      │
│ ├─ Live: MT5 order  │
│ └─ Replay: simulate │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Outcome Recording    │
│ Pattern Memory       │
│ Signal Output (JSON) │
└─────────────────────┘
```

## Key Decision Points

1. **Direction**: Resolved by majority vote among all modules + base direction
2. **Blocking**: Any filter or blocker can force WAIT
3. **Conviction threshold**: Even with a BUY/SELL direction, if conviction < 0.62 or vote margin < 2, forced to WAIT
4. **Capital guard**: Can refuse trades based on daily loss, total drawdown, consecutive losses
5. **MT5 readiness**: 11 pre-trade checks must pass for live execution
6. **Signal freshness**: Signals older than max_age_seconds are rejected (when enabled)
