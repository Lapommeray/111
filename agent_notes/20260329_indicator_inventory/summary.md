# Indicator Inventory — Summary

**Date**: 2026-03-29  
**Scope**: Strict, grounded inspection only — zero code changes  
**Tests run**: `python -m pytest -q --tb=no` → 696 passed in 29.66s  
**Changed files**: None. Zero code or configuration modifications.

---

## Entrypoint

`run.py:main()` → `parse_args()` → `load_runtime_config()` → either `run_pipeline()` or `run_replay_evaluation()`.

## Execution Path (run_pipeline, line 2885)

1. **Config** → `validate_runtime_config()`, `ensure_sample_data()`
2. **Data** → CSV replay or MT5 adapter → bars (list of OHLCV+tick_volume dicts)
3. **MT5 readiness** → readiness chain, quarantine state, resume state, self-audit report
4. **Core features** → `classify_market_structure(bars)`, `assess_liquidity_state(bars)`, `compute_confidence(structure, liquidity)`
5. **Pipeline** → `run_advanced_modules()` through `OversoulDirector`:
   - 10 always-on feature modules + 3 quarantinable feature modules
   - 5 filter modules
   - 2 always-on scoring modules + 2 quarantinable scoring modules
   - 1 memory module (MetaAdaptiveAI)
6. **Macro** → `collect_xauusd_macro_state()` (10 external adapters, disabled in replay by default)
7. **LossBlocker** → standalone blocker check on confidence + structure/liquidity conflict
8. **Strategy intelligence** → `score_signal_intelligence()` — adaptive confidence reweighting
9. **Capital guard** → `evaluate_capital_protection()` — daily loss, drawdown, loss streak, anomaly
10. **Blocker aggregation** → combines pipeline-blocked + LossBlocker + capital_guard + macro_risk + MT5 refusal
11. **Decision logic** → direction conviction thresholds (conviction < 0.62 → WAIT, margin < 2 → WAIT)
12. **MT5 execution** → `_run_controlled_mt5_live_execution()` (live only)
13. **Outcome tracking** → `OutcomeTracker.evaluate_and_record()`, `SelfCoder.generate_rules_from_outcomes()`
14. **Evolution** → `run_evolution_kernel()`
15. **Output** → `build_signal_output()` → `build_chart_objects()` → `build_status_panel()` → `build_indicator_output()`

## Replay Evaluation Path (run_replay_evaluation, line 3570)

Calls `evaluate_replay()` which invokes `run_pipeline()` repeatedly, then:
1. Decision-completeness gate (classifies records, never blocks)
2. Decision-quality gate (validates distribution sanity, strict=False → warn only)
3. Replay-outcome gate (validates economics — can raise ReplayOutcomeError)
4. Threshold-calibration report (diagnostic only, never blocks)

## What Is Really Inside

- **13 feature modules** (10 always-on + 3 quarantinable)
- **5 filter modules** (always-on)
- **4 scoring modules** (2 always-on + 2 quarantinable)
- **1 memory module** (MetaAdaptiveAI)
- **1 standalone blocker** (LossBlocker)
- **1 macro intelligence layer** (collect_xauusd_macro_state with 10 adapters)
- **1 strategy intelligence layer** (signal scoring + adaptive weighting)
- **1 capital guard** (position sizing + risk limits)
- **1 monitoring module** (system state tracker)
- **1 evolution kernel** (autonomous code generation pipeline)
- **3 output builders** (signal, chart objects, status panel)
- **4 replay evaluation gates** (completeness, quality, outcome, calibration)
- **~16,900 lines of disconnected learning code** (not in any active path)
