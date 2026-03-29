# Gaps Preventing Higher Reliability

## Critical Gaps

### 1. No Real Spread Data
- **Location**: `src/features/spread_state.py:20`
- **Current**: Spread estimated as `avg_range * 2.0` from candle data
- **Problem**: This is a proxy, not actual bid-ask spread. XAUUSD bar ranges of $3-5 produce proxy values that may not reflect execution reality.
- **Impact**: Spread filter may block/allow incorrectly. Execution quality assessment is approximate.
- **Fix complexity**: Medium — requires MT5 tick data or SymbolInfo spread field

### 2. Weak Feature Modules Still Vote
- **Location**: `src/pipeline.py:178-183` (optional modules)
- **Current**: human_lag_exploit, invisible_data_miner, quantum_tremor_scanner are quarantinable but not always quarantined
- **Problem**: When active, they contribute direction votes and confidence deltas based on weak/placeholder logic
- **Impact**: Can tip votes toward false signals or inflate confidence
- **Fix complexity**: Low — quarantine by default or reduce their confidence_delta weight

### 3. Confidence Disagreement Ignored
- **Location**: `src/scoring/confidence_score.py:15`
- **Current**: Agreement between structure and liquidity has only 10% weight in confidence formula
- **Problem**: When structure says BUY but liquidity says SELL, confidence drops by only ~0.06 points
- **Impact**: High confidence possible despite fundamental signal conflict
- **Fix complexity**: Low — increase agreement weight or add conflict penalty

### 4. Hard-Coded Thresholds Without Empirical Basis
- **Locations**: Throughout scoring and filter modules
- **Current**: Thresholds like conviction < 0.62, displacement > 1.8, regime > 0.6, etc. are arbitrary
- **Problem**: No statistical backing; no calibration data to verify these values
- **Impact**: May be too aggressive or too passive for actual market conditions
- **Fix complexity**: Medium — requires replay data analysis to calibrate

### 5. Execution Costs Set to Zero
- **Location**: `config/settings.json`
- **Current**: `"execution_costs"` all set to 0.0
- **Problem**: No slippage, commission, or spread modeling in replay evaluation
- **Impact**: Replay results overestimate real performance; outcome gate passes too easily
- **Fix complexity**: Low — set realistic values for XAUUSD

### 6. Spectral Signal Fusion Includes Weak Modules
- **Location**: `src/scoring/spectral_signal_fusion.py:12-17`
- **Current**: Fuses outputs from displacement, fvg, volatility, quantum_tremor_scanner, invisible_data_miner, human_lag_exploit
- **Problem**: 3 out of 6 modules are weak/placeholder. Equal-weight averaging means noise has 50% influence.
- **Impact**: Fusion score is unreliable; can boost or drag confidence incorrectly
- **Fix complexity**: Low — exclude weak modules or weight by quality

### 7. Session Filter Too Simplistic
- **Location**: `src/filters/session_filter.py:9`
- **Current**: Only blocks state == "off_hours"
- **Problem**: Does not distinguish between weak sessions (late Tokyo) and strong sessions (London open)
- **Impact**: Allows trading in suboptimal session windows
- **Fix complexity**: Low — add graduated session quality scoring

### 8. LossBlocker Not Integrated in Pipeline
- **Location**: `src/filters/loss_blocker.py` vs `src/pipeline.py`
- **Current**: LossBlocker exists as a class but pipeline.py never calls it in the filter stage. It's called separately in run.py.
- **Problem**: Two-stage blocking creates architectural inconsistency. Pipeline filters don't include this gate.
- **Impact**: Potential for missed blocking in some code paths
- **Fix complexity**: Medium — decide whether to integrate into pipeline.py or keep separate

### 9. Self-Destruct Protocol May Be Overly Aggressive
- **Location**: `src/filters/self_destruct_protocol.py:15`
- **Current**: 4 losses out of 20 trades triggers complete module shutdown
- **Problem**: 20% loss rate is common during natural drawdowns; disabling modules may prevent recovery
- **Impact**: May cause the indicator to go silent during recoverable periods
- **Fix complexity**: Low — adjust threshold or add decay logic

### 10. No Traceability from Output to Source Modules
- **Location**: `src/indicator/signal_model.py`, `src/indicator/indicator_output.py`
- **Current**: Final output doesn't show which modules contributed what to the final direction/confidence
- **Problem**: Cannot debug or explain why a specific signal was generated
- **Impact**: Makes post-trade analysis and system improvement harder
- **Fix complexity**: Medium — add feature_contributors to output schema

---

## Secondary Gaps

### 11. Disconnected Code Mass
- 16,332 LOC in `self_evolving_indicator_layer.py` and 560 LOC in `autonomous_behavior_layer.py` are imported but never used in the main pipeline. This dead code mass creates confusion about system capabilities.

### 12. Chart Objects Are Minimal
- Only 3 chart objects (structure label, liquidity label, signal tag). No visualization of:
  - Module health or evolution state
  - Macro regime
  - Capital guard state
  - Blocking reasons
  - Confidence breakdown

### 13. Compact Signal Payload Not Documented
- `_build_compact_signal_payload()` exists but its output schema is not documented. Unknown which fields are retained vs. discarded.

### 14. MetaAdaptiveAI Partially Connected
- Called in pipeline.py via MetaAdaptiveAI but not directly instantiated in run.py main flow. Config path exists but integration is unclear.

### 15. No Real-Time Alerting
- System monitors health metrics but has no alerting mechanism for critical failures, unusual drawdowns, or system degradation.
