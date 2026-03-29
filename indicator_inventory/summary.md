# Indicator Inventory Summary

**Date**: 2026-03-29
**Repository**: Lapommeray/111
**Branch**: copilot/document-repo-structure-and-issues
**Tests**: 696 passed (full suite, zero failures)

---

## What This Indicator Is

A self-evolving XAUUSD (Gold) trading indicator built in Python, designed to run against MetaTrader 5 via a custom adapter. It combines technical analysis (market structure, liquidity, FVG, displacement, volatility) with macro intelligence (DXY, yields, economic calendar, COMEX OI, ETF flows), automated rule generation, and a multi-gate evaluation pipeline.

## Architecture (Unchanged, Verified)

```
main() → run_pipeline() or run_replay_evaluation()
              │
              ├─ Data: MT5Adapter → bars (OHLCV + tick_volume)
              ├─ Features: 10 core + 3 optional feature modules
              ├─ Filters: 5 active blocking filters + 1 unused (LossBlocker)
              ├─ Scoring: 2 core + 2 optional scoring modules
              ├─ Strategy: signal intelligence + adaptive weighting
              ├─ Macro: 10 external adapters (gold-specific)
              ├─ Risk: capital protection + position sizing
              ├─ Memory: pattern store + outcome tracker + self-coder
              ├─ Evolution: 16-module autonomous code generation pipeline
              ├─ Monitoring: system health tracker
              └─ Output: signal + chart objects + status panel
```

## Total Code Inventory

| Area | Files | LOC (approx) | Active % |
|------|-------|-------------|----------|
| run.py (entrypoint) | 1 | 3,906 | 100% |
| Features | 10 | ~650 | 100% |
| Filters | 6 | ~300 | 83% (LossBlocker unused in pipeline) |
| Scoring | 5 | ~250 | 100% |
| Indicator/Output | 3 | ~150 | 100% |
| Strategy | 1 | ~200 | 100% |
| Pipeline | 1 | 250 | 100% |
| State | 1 | 108 | 90% (EvolutionStatus unused) |
| Utils | 1 | 114 | 83% (2 dead functions) |
| Module Factory | 1 | 109 | 60% (3 methods unused) |
| Memory | 5 | 398 | 100% |
| Learning | 4 | 769 | 25% (2 large files disconnected) |
| Evolution | 16 | 5,991 | 100% |
| Macro | 3 | 1,967 | 95% |
| MT5 | 4 | 388 | 100% |
| Risk | 2 | 193 | 100% |
| Monitoring | 2 | 121 | 100% |
| Evaluation | 10 | ~1,500 | 100% |
| Tests | 43 | ~6,000 | 696 pass |
| **TOTAL** | **~118** | **~23,000** | **~92%** |

## Truth-Only Verdict

### What's Real and Working
1. **Market structure analysis** — higher-high/higher-low classification from real OHLC data
2. **Liquidity sweep detection** — stop-run pattern recognition with volume confirmation
3. **Volatility classification** — range-based expansion/compression detection
4. **Session awareness** — time-based trading window filtering
5. **Displacement detection** — candle body momentum measurement
6. **FVG detection** — 3-candle gap pattern identification
7. **Macro intelligence** — 10 external data adapters for gold-specific factors
8. **Risk management** — capital guard with daily loss limits, position sizing, drawdown caps
9. **Memory system** — persistent trade outcomes, pattern storage, rule generation
10. **Multi-gate evaluation** — completeness → quality → outcome → calibration gates
11. **Evolution pipeline** — autonomous code generation with governance

### What's Weak or Heuristic
1. **Spread proxy** — estimates spread from candle ranges (not real bid-ask data)
2. **Human lag exploit** — speculative "retail lag" assumption, unvalidated
3. **Invisible data miner** — simplistic step-counting, placeholder-level logic
4. **Quantum tremor scanner** — duplicates volatility with misleading name
5. **Spectral signal fusion** — fuses 3 weak modules, degrades score quality
6. **Session behavior tracking** — win-rate extrapolation from small samples
7. **Confidence scoring** — directional disagreement barely impacts final score (10% weight)
8. **All scoring thresholds** — hard-coded magic numbers without empirical backing

### What's Disconnected
1. `autonomous_behavior_layer.py` (560 LOC) — imported but never called
2. `self_evolving_indicator_layer.py` (16,332 LOC) — test-only, not in pipeline
3. `LossBlocker` class — exported but not used in pipeline.py filter stage
4. `EvolutionStatus` dataclass — defined but never instantiated
5. `timeframe_to_minutes()`, `ensure_required_keys()` — dead utility functions
6. `ModuleFactory.refresh()`, `.create_all_modules()`, `.get_module_count()` — unused methods
