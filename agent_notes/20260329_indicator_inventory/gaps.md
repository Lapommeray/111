# Gaps — Verified Issues That Can Create Fake, Misleading, or Weak Signals

Each gap below is grounded in actual code reviewed during this inspection.

---

## G1: Spread proxy is not real spread data

**File**: src/features/spread_state.py:20  
**Code**: `spread_points = max(5.0, min(120.0, round(avg_range * 2.0, 2)))`

The spread proxy is calculated from average candle range × 2.0. XAUUSD M5 candle ranges are typically $3-$8, so spread_points will typically be 6-16.

**Why this is a gap**: This does not reflect actual bid-ask spread. On XAUUSD, real spreads are typically 0.2-0.5 points during London/NY and 1-3 points during Asia/off-hours. The proxy can be 10-30× larger than reality. Filters and modules that read spread_points may make wrong decisions.

**Impact**: spread_filter uses this value with threshold 60. With the 2.0 multiplier, false blocks should be rare, but the value carries through to execution_quality, LossBlocker, capital_guard status output, and strategy intelligence feature scoring — as if it were real spread data.

---

## G2: Three weak modules vote with equal weight

**Files**: src/features/invisible_data_miner.py, src/features/human_lag_exploit.py, src/features/quantum_tremor_scanner.py  
**Pipeline**: pipeline.py:178-183

These three modules are quarantinable but **active by default** (quarantined_modules defaults to empty list in RuntimeConfig:136).

- **invisible_data_miner**: Counts up vs down closes over 30 bars + alignment bonus. This is simple momentum restatement — it adds no information beyond what market_structure already captures.
- **human_lag_exploit**: Assumes body-size-vs-average ratio >1.1 with positive momentum = "late buy continuation." This is an unvalidated behavioral hypothesis presented as a direction vote.
- **quantum_tremor_scanner**: Computes range ratio identical to volatility module but with different thresholds (1.8 vs 1.6). Adds duplicate information.

**Impact**: Each module gets a direction vote and confidence delta. In aggregate_direction(), these 3 weak votes count equally with structure, liquidity, and real technical votes. This can tip BUY/SELL decisions on weak data.

---

## G3: Spectral fusion averages weak modules with real ones

**File**: src/scoring/spectral_signal_fusion.py:8-15

Fuses exactly these 6 modules: displacement, fvg, volatility, quantum_tremor_scanner, invisible_data_miner, human_lag_exploit.

3 of 6 are weak (G2). All confidence_deltas are averaged equally.

**Impact**: If the 3 weak modules produce positive deltas, the fusion module amplifies them. If they produce noise, the fusion injects noise into the pipeline's confidence calculation.

---

## G4: Agreement weight in base confidence is only 10%

**File**: src/scoring/confidence_score.py:15  
**Code**: `confidence = (0.55 * structure_strength) + (0.35 * liquidity_score) + (0.10 * agreement)`

Agreement = 1.0 if structure bias and liquidity hint agree, else 0.4.

**Impact**: When structure says BUY but liquidity says SELL, confidence drops by only 0.06 (from 0.10 * 1.0 to 0.10 * 0.4). This means conflicting signals barely affect confidence. A strong structure trend (0.7 strength) with an opposing liquidity sweep produces confidence ~0.61, which passes the 0.6 LossBlocker threshold.

---

## G5: Confidence aggregation is unweighted additive

**File**: src/utils.py:30-31  
**Code**: `base_confidence + sum(deltas)`

All module confidence_deltas are summed without any quality weighting. A weak module's +0.04 delta is treated identically to a strong module's +0.04.

**Impact**: The 3 weak modules (G2) can inject up to ~0.10 combined delta, which is enough to cross decision thresholds. The spectral fusion module (G3) adds another delta on top.

---

## G6: Session behavior extrapolates from tiny samples

**File**: src/features/sessions.py:103-105  
**Code**: Prunes with "weak_pattern_pruned" when samples < 2, but 2 samples is the minimum needed to produce a non-default win_rate.

**Impact**: With 2 samples, win_rate can be 0.0, 0.5, or 1.0. A 100% win rate from 2 samples would produce confidence_delta +0.03. A 0% win rate from 2 samples would produce -0.01. The asymmetry favors false confidence boosts from tiny sample sizes.

---

## G7: Breakout probability formula is a heuristic

**File**: src/features/volatility.py:76-79  
**Code**: `0.55 if volatility_contracted else 0.25 + max(0, expansion_ratio - 1.0) * 0.25`

This formula has no empirical backing. The 0.55 base for contracted markets and the 0.25 coefficients are arbitrary.

**Impact**: Produces confidence values and direction votes that are presented as probabilistic assessments but are not calibrated against any outcome data.

---

## G8: Direction conviction thresholds are untested against real data

**File**: run.py:3230-3231  
**Code**: `directional_conviction < 0.62` and `directional_vote_margin < 2`

These thresholds determine when a BUY/SELL decision is forced to WAIT. The 0.62 threshold and margin-of-2 requirement were chosen without documented empirical evidence.

**Impact**: If too high, valid signals are suppressed (false WAIT). If too low, weak signals pass through (false BUY/SELL). The threshold calibration report exists to diagnose this, but it is diagnostic only — it does not actually adjust these values.

---

## G9: Execution quality tracking uses proxy data only

**File**: src/features/spread_state.py:44-105

- Slippage proxy = abs(current_open - previous_close)
- Fill timing ratio = latest bar duration / previous bar duration

Neither is real execution data. On M5 timeframes, bar-to-bar open/close gaps and duration ratios have little to do with actual order execution quality.

**Impact**: The module reports "efficient," "degraded," or "normal" execution quality based on data that has no direct relationship to actual trade execution.

---

## G10: Strategy intelligence reweights confidence using historical win rate

**File**: src/strategy/intelligence.py:84  
**Code**: `adaptive_weight = 0.5 + (win_rate - 0.5) * 0.6`

With no closed outcomes (startup), win_rate defaults to 0.5 → adaptive_weight = 0.5. This is reasonable. But the entire confidence formula combines signal_score (from feature scoring), base_confidence, and confirmation_ratio.

**Impact**: feature scoring uses `_feature_score()` which gives +0.04 bonus to any module that has a BUY or SELL vote, regardless of vote quality. This means the 3 weak modules (G2) boost signal_score simply by having non-neutral votes.

---

## G11: setup_score has zero effect

**File**: src/scoring/setup_score.py:33  
**Code**: `"confidence_delta": 0.0`

The setup_score module computes a score but intentionally sets confidence_delta to 0.0. It is purely diagnostic and has zero effect on any decision.

**Impact**: No direct impact, but consumers of the output might assume it contributes to scoring when it does not.
