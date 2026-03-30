# PROOF: COMMANDS AND FILES USED

## Assessment Date: 2026-03-30

---

## Commands Executed

### 1. Test Suite
```bash
cd /home/runner/work/111/111
python3 -m pytest src/tests/ -q --tb=line
# Result: 779 passed in 29.34s
```

### 2. Replay Evaluation
```bash
cd /home/runner/work/111/111
python3 run.py --mode replay --replay-source csv --evaluate-replay true --config config/settings.json
# Result: 21 steps, all WAIT, 0 trades
# Output: memory/replay_evaluation_report.json
```

### 3. Sample Data Inspection
```bash
head -3 data/samples/xauusd.csv
wc -l data/samples/xauusd.csv
# Result: 321 lines (320 data rows + header), synthetic linear drift
```

### 4. Per-Window Market Analysis
```python
# Custom script simulating classify_market_structure + assess_liquidity_state + compute_confidence
# for each of 21 evaluation windows
# Result: 11 windows have hard structure-liquidity conflict, 10 have soft or no conflict
# But ALL 21 produce WAIT due to neutral vote majority
```

### 5. Module Vote Extraction
```bash
cat memory/replay_evaluation_report.json | python3 -c "... extract module_contribution_report ..."
# Result: 16 modules always neutral, 7 modules directional
```

---

## Files Examined

### Configuration
| File | Purpose | Key Finding |
|------|---------|-------------|
| `config/settings.json` | Runtime config | `walk_forward_enabled: false`, all costs = 0.0 |
| `.env.example` | Env template | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` required |

### Core Pipeline
| File | Lines | Purpose | Key Finding |
|------|-------|---------|-------------|
| `run.py` | 226-259 | `ensure_sample_data()` | Synthetic data: 320 bars, linear drift formula |
| `run.py` | 2940-3400 | `run_pipeline()` | Decision logic, confidence gates, conviction gates |
| `run.py` | 3248-3250 | Confidence threshold | `min_confidence = 0.6` gate |
| `run.py` | 3265-3266 | Combined blocked → WAIT | Explicit WAIT on any blocker |
| `run.py` | 3288-3313 | Directional conviction | Must be ≥ 0.62, vote margin ≥ 2 |
| `run.py` | 957-1112 | `_place_controlled_mt5_order()` | Real MT5 order placement, all return codes handled |
| `run.py` | 1947-1983 | Pretrade checks | 11-point gate for live orders |
| `run.py` | 2339-2341 | Auto-stop | Triggers after 3 consecutive failures |
| `run.py` | 2005-2031 | Replay simulation | `simulated=True, order_id=0` |
| `run.py` | 2100-2118 | Live execution | Calls `_place_controlled_mt5_order()` |
| `src/utils.py` | 14-26 | `aggregate_direction()` | **ROOT CAUSE: neutral counted as WAIT** |
| `src/pipeline.py` | 231-234 | Vote collection | `all_votes` from module_results |
| `src/pipeline.py` | 178-183 | Quarantine check | Correctly gates experimental modules |

### Features (Direction Vote Analysis)
| File | Always Neutral? | Evidence |
|------|-----------------|---------|
| `src/features/displacement.py` | YES | Hardcoded `direction_vote: "neutral"` |
| `src/features/fvg.py` | Conditional | Can vote buy/sell, but neutral on synthetic data |
| `src/features/invisible_data_miner.py` | NO | Votes based on slope (buy/sell/neutral) |
| `src/features/sessions.py` | YES | Hardcoded `direction_vote: "neutral"` |
| `src/features/volatility.py` | YES | Hardcoded `direction_vote: "neutral"` |
| `src/features/spread_state.py` | YES | Hardcoded `direction_vote: "neutral"` |
| `src/features/human_lag_exploit.py` | YES | Hardcoded `direction_vote: "neutral"` |
| `src/features/quantum_tremor_scanner.py` | YES | Hardcoded `direction_vote: "neutral"` |

### Filters (Direction Vote Analysis)
| File | Behavior |
|------|----------|
| `src/filters/conflict_filter.py` | Relays base_direction when not blocked, "wait" when blocked |
| `src/filters/memory_filter.py` | Relays direction when not blocked, "wait" when blocked |
| `src/filters/loss_blocker.py` | `structure_liquidity_conflict` when sweep + score ≥ 0.7 |

### Risk / Safety
| File | Purpose | Status |
|------|---------|--------|
| `src/risk/capital_guard.py` | Daily loss, drawdown, streak limits | ✅ Working |
| `src/mt5/adapter.py` | MT5 data fallback to CSV | ✅ Working |
| `src/mt5/symbol_guard.py` | XAUUSD only | ✅ Working |
| `src/alerts/telegram_sidecar.py` | Real Telegram API integration | ✅ Code correct, needs credentials |

### Evaluation
| File | Purpose | Status |
|------|---------|--------|
| `src/evaluation/replay_evaluator.py` | Replay runner | ✅ Working |
| `src/evaluation/decision_quality.py` | Quality gate | ✅ Working |
| `src/evaluation/replay_outcome.py` | Outcome gate | ✅ Working |
| `src/evaluation/threshold_calibration.py` | Calibration | ✅ Working |
| `src/evaluation/module_contribution_report.py` | Vote analysis | ✅ Working |

### Generated Artifacts
| File | Content | Key Data |
|------|---------|----------|
| `memory/replay_evaluation_report.json` | Full evaluation | 0 trades, 0.0% win rate, all WAIT |
| `memory/meta_adaptive_profile.json` | Adaptive state | `win_rate: 0.0, samples: 0` |
| `memory/risk_state/daily_loss_tracker.json` | Risk state | `trade_count: 0` |
| `memory/mt5_readiness_chain_verification.json` | Readiness | `all_checks_passed: false` (replay mode) |
| `memory/mt5_controlled_execution_state.json` | Execution | `total_execution_attempts: 0` |

---

## Verification Methodology

1. **Ran actual evaluation** — not simulated, real `run.py` execution
2. **Read source code** — traced exact code paths, not assumptions
3. **Computed vote counts** — mathematical proof of impossibility
4. **Tested with crafted data** — confirmed issue persists even with ideal input
5. **Cross-referenced** — module_contribution_report matches code analysis
6. **Checked all 23 modules** — verified each module's direction_vote capability
