# Risk Assessment

## Risk Level: MODERATE

The indicator has a solid core architecture with real technical analysis, but several weak modules and hard-coded thresholds create reliability concerns.

---

## High-Severity Risks

### R1: False Confidence from Weak Modules
- **Probability**: High (when weak modules are active)
- **Impact**: Trades entered with inflated confidence, leading to unexpected losses
- **Source**: human_lag_exploit, invisible_data_miner, quantum_tremor_scanner contributing votes and confidence deltas
- **Mitigation**: Quarantine these modules by default (Phase 1.2 in next_steps.md)

### R2: Zero Execution Costs in Replay
- **Probability**: Certain (config value is 0)
- **Impact**: Replay evaluations show better results than real trading will deliver; outcome gate may pass unrealistically
- **Source**: `config/settings.json` execution_costs = 0.0
- **Mitigation**: Set realistic XAUUSD execution costs (Phase 1.1)

### R3: Spectral Fusion Noise
- **Probability**: High (when fusion is active)
- **Impact**: Fused score averages 3 weak modules with 3 real modules, corrupting the aggregated signal
- **Source**: `src/scoring/spectral_signal_fusion.py` equal-weighting 6 modules
- **Mitigation**: Remove weak modules from fusion (Phase 1.3)

---

## Medium-Severity Risks

### R4: Uncalibrated Thresholds
- **Probability**: Medium
- **Impact**: Signals may be too frequent (low thresholds) or too rare (high thresholds) for current market regime
- **Source**: Hard-coded values throughout (conviction 0.62, displacement 1.8, regime 0.6, etc.)
- **Mitigation**: Use threshold_calibration.py data to verify and adjust (Phase 2.2)

### R5: Self-Destruct Over-Triggering
- **Probability**: Medium (during natural drawdowns)
- **Impact**: Indicator goes completely silent during recoverable periods; misses valid setups
- **Source**: `src/filters/self_destruct_protocol.py` — 4 losses out of 20 trades
- **Mitigation**: Adjust threshold or add time-decay (Phase 2)

### R6: Spread Proxy Inaccuracy
- **Probability**: Medium
- **Impact**: Spread filter may block valid trades (false positives) or allow trades during actual wide spreads (false negatives)
- **Source**: `src/features/spread_state.py` — `avg_range * 2.0` heuristic
- **Mitigation**: Use MT5 SymbolInfo spread data when available

### R7: Confidence Not Sensitive to Conflict
- **Probability**: High
- **Impact**: High confidence signals when structure and liquidity disagree, leading to poor entries
- **Source**: `src/scoring/confidence_score.py` — 10% agreement weight
- **Mitigation**: Increase agreement weight (Phase 1.4)

---

## Low-Severity Risks

### R8: Dead Code Confusion
- **Probability**: Low (developer confusion, not trading risk)
- **Impact**: Developers may think features like autonomous_behavior_layer or self_evolving_indicator_layer are active
- **Source**: 16,892 LOC of disconnected code still imported
- **Mitigation**: Add clear documentation or remove dead imports

### R9: Session Filter Gaps
- **Probability**: Low-Medium
- **Impact**: Trading in marginal session windows (late Tokyo) that have historically weak signals
- **Source**: `src/filters/session_filter.py` — binary off_hours/allowed
- **Mitigation**: Add session quality tiers (Phase 2.3)

### R10: No Output Traceability
- **Probability**: N/A (process risk, not trading risk)
- **Impact**: Cannot explain why a signal was generated; hinders debugging and improvement
- **Source**: SignalOutput doesn't include feature_contributors
- **Mitigation**: Add module-level contribution data to output (Phase 2.4)

---

## Risks That DO NOT Exist

These are explicitly NOT risks based on verified findings:

| Non-Risk | Why |
|----------|-----|
| Core architecture instability | Pipeline orchestration is clean and well-structured |
| Memory system corruption | PatternStore uses atomic writes, trade outcomes properly tracked |
| Evolution breaking production | Evolution kernel has governance, verification, and promotion gates |
| MT5 execution without safety | 11 pre-trade validations, readiness chain, quarantine logic |
| Evaluation bypassing gates | 4-gate chain runs in sequence; on-disk artifacts preserved |
| Capital protection gaps | Daily loss, drawdown, loss streak, anomaly detection all active |
| Test suite degradation | 696 tests pass; comprehensive coverage of evaluation gates |
