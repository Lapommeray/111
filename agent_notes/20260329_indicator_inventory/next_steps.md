# Next Steps — Derived from Verified Findings Only

These next steps follow strictly from the gaps and findings documented in this inventory. No assumptions beyond what was observed in the actual code.

---

## Must Fix First (High Priority)

### 1. Quarantine the 3 weak modules by default

**Why**: invisible_data_miner, human_lag_exploit, and quantum_tremor_scanner contribute direction votes and confidence deltas on weak/duplicate logic (G2). They are already quarantinable — the mechanism exists in pipeline.py:178-183 and RuntimeConfig.quarantined_modules.

**How**: Set `quarantined_modules` default in config/settings.json or RuntimeConfig to include these 3 modules. No architecture change needed.

**Test first**: Run replay evaluation with and without quarantine. Compare results via existing drawdown comparison tooling.

### 2. Exclude weak modules from spectral_signal_fusion inputs

**Why**: 3 of 6 fusion inputs are the same weak modules (G3). Fusing noise with real signals degrades the fusion output.

**How**: Remove quantum_tremor_scanner, invisible_data_miner, human_lag_exploit from the selected list in spectral_signal_fusion.py:8-15. Only fuse displacement, fvg, volatility.

**Test first**: Add unit test verifying fusion output with only 3 real inputs matches expected behavior. Run replay to measure impact.

---

## Should Stay Unchanged

### Core feature modules
- displacement, fvg, volatility, sessions, market_structure, market_regime, liquidity_sweep — all use real OHLC data with sound logic.

### Filter modules
- session_filter, conflict_filter, memory_filter, self_destruct_protocol — all use clear, measurable conditions.

### LossBlocker
- Sound standalone blocker with explicit confidence, structure, and liquidity conflict checks.

### Capital guard
- Real risk management with daily loss, drawdown, loss streak, anomaly tracking.

### Macro intelligence layer
- Extensive but appropriately disabled in replay. No changes needed.

### Evaluation gates
- completeness, quality, outcome, calibration — well-tested and appropriately gated.

### Evolution kernel
- Autonomous code generation pipeline — architectural infrastructure, not signal logic.

### Output builders
- signal_model, chart_objects, indicator_output — pass-through formatting, no logic changes needed.

---

## Can Be Strengthened Using Existing Architecture

### 3. Increase agreement weight in confidence scoring

**Why**: Agreement between structure and liquidity has only 10% weight (G4). Direction conflicts barely reduce confidence.

**How**: Adjust weights in confidence_score.py:15. For example: 0.45 structure + 0.30 liquidity + 0.25 agreement. No architecture change.

**Test first**: Run replay with different weight configurations. Measure impact on decision quality report.

### 4. Apply quality weighting to confidence delta aggregation

**Why**: All deltas are summed equally (G5). Modules with proven track records should carry more weight.

**How**: Use strategy intelligence's `feature_contributors` (already computed per-module scores) to weight deltas. Requires small change to `aggregate_confidence()` or its caller.

**Test first**: Add unit tests for weighted aggregation. Run replay comparison.

### 5. Threshold calibration → actual threshold adjustment

**Why**: The threshold calibration report already produces distributional stats and recommendations, but they are diagnostic only (G8). The conviction threshold (0.62) and vote margin (2) are untested against data.

**How**: Use calibration report output to inform threshold values. Can be applied manually after reviewing calibration output.

**Test first**: Review calibration report output from a full replay evaluation. Validate recommendations before applying.

---

## Tests That Must Be Added Before Touching Logic

### T1. Baseline replay with default config
Run `run_replay_evaluation()` with current defaults and save full report. This becomes the "before" baseline for any change.

### T2. Quarantine A/B comparison
Run replay with `quarantined_modules=["invisible_data_miner", "human_lag_exploit", "quantum_tremor_scanner"]` vs default empty list. Compare using existing drawdown comparison tooling.

### T3. Agreement weight sensitivity test
Add unit test in test_scoring.py that verifies confidence changes meaningfully when structure and liquidity disagree. Currently the test suite does not verify this specific scenario at the decision level.

### T4. Fusion module isolation test
Add test that verifies `fuse_spectral_signals()` behavior when weak modules are absent (empty dict inputs). Verify it still produces valid output.

### T5. Conviction threshold boundary test
Add test that verifies decision=BUY when conviction is exactly 0.62 and exactly 0.619. Verify margin=2 vs margin=1 boundary behavior.

### T6. Session behavior small-sample guard test
Add test that verifies session_behavior with exactly 1 and 2 samples produces appropriately conservative confidence_delta.
