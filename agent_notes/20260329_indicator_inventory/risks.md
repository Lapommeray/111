# Risks — From Verified Findings

Each risk below is grounded in actual code observed during this inspection.

---

## R1: Weak modules produce false direction votes (HIGH)

**Source**: G2, G3 in gaps.md  
**Modules**: invisible_data_miner, human_lag_exploit, quantum_tremor_scanner  

These 3 modules are active by default and each produce direction votes (buy/sell/neutral) and confidence_deltas that are aggregated equally with real technical modules. In `aggregate_direction()`, all votes count equally. 3 weak votes can flip a WAIT to BUY/SELL or vice versa.

**Probability**: Certain — these modules always run and always vote.  
**Severity**: Medium — mitigated partially by conviction threshold and conflict filter.

---

## R2: Spread proxy creates false confidence about execution quality (MEDIUM)

**Source**: G1, G9 in gaps.md  
**Modules**: compute_spread_state, track_execution_quality

Spread proxy reports values 10-30× larger than real bid-ask spreads. Execution quality module uses this proxy to classify execution as "efficient" / "degraded" / "normal" based on bar data, not real execution data.

**Probability**: Certain — always runs.  
**Severity**: Low-Medium — spread_filter has high threshold (60 points) so false blocks are rare, but the reported values carry false certainty in output fields.

---

## R3: Agreement-insensitive base confidence (MEDIUM)

**Source**: G4 in gaps.md  
**Module**: compute_confidence in confidence_score.py

When structure says BUY but liquidity sweep says SELL, base confidence drops by only ~0.06. This weak penalty means conflicting signals produce nearly the same confidence as agreeing signals.

**Probability**: Certain — always computes this way.  
**Severity**: Medium — conflicting signals may produce signals that pass the 0.6 LossBlocker threshold when they should be blocked.

---

## R4: Spectral fusion amplifies noise (MEDIUM)

**Source**: G3 in gaps.md  
**Module**: fuse_spectral_signals in spectral_signal_fusion.py

Equal-weight averaging of 3 weak + 3 real module deltas. If weak modules agree on direction, their combined delta can dominate the fusion output.

**Probability**: Depends on market conditions — when all 3 weak modules align, fusion amplifies.  
**Severity**: Medium — fusion is quarantinable but active by default.

---

## R5: Unvalidated decision thresholds (MEDIUM)

**Source**: G8 in gaps.md  
**Logic**: run.py:3230-3231

Conviction < 0.62 and vote margin < 2 thresholds have no documented empirical backing. Too high → valid signals suppressed. Too low → weak signals pass.

**Probability**: Uncertain — threshold calibration report exists but outputs are not applied.  
**Severity**: Medium — directly determines signal quality.

---

## R6: 16,892 lines of disconnected learning code (LOW)

**Source**: Findings section 9  
**Files**: autonomous_behavior_layer.py (560 lines) + self_evolving_indicator_layer.py (16,332 lines)

This code is exported from `src/learning/__init__.py` and imported by evolution spec flow, but never called from `run_pipeline()` or `run_replay_evaluation()`.

**Probability**: N/A — code is inactive.  
**Severity**: Low — no runtime impact, but creates maintenance burden and confusion about system capabilities.

---

## R7: Feature scoring rewards any directional vote (LOW)

**Source**: G10 in gaps.md  
**Module**: _feature_score in strategy/intelligence.py

```python
directional_bias = 0.04 if direction_vote in {"buy", "sell"} else 0.0
```

Any module that votes buy or sell gets a +0.04 bonus in feature scoring, regardless of vote quality. Weak modules that always produce directional votes get systematically higher feature scores.

**Probability**: Certain — always computes this way.  
**Severity**: Low — signal_score is blended with other factors, so isolated impact is small.

---

## What is NOT at risk

These areas were verified as sound and do not require changes:

- Core structure/liquidity/volatility analysis from real OHLC data
- Session classification from bar timestamps
- Filter logic (session, spread threshold, conflict, memory, self-destruct)
- LossBlocker standalone gate
- Capital guard risk management
- Macro intelligence layer (appropriately gated)
- Evaluation pipeline (4 gates with incremental persistence)
- Memory system (pattern store, outcome tracker, self-coder)
- MT5 execution safety chain (readiness, quarantine, resume, audit)
