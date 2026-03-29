# Critical Files List

## Tier 1 — System Cannot Run Without These

| File | Lines | Why Critical |
|------|-------|-------------|
| `run.py` | 3,906 | Monolithic entrypoint. Contains `main()`, `run_pipeline()`, `run_replay_evaluation()`, `run_evolution_kernel()`, all MT5 execution logic, config loading/validation, bar loading, and the full decision pipeline. **If this file breaks, nothing works.** |
| `src/pipeline.py` | 250 | `OversoulDirector` (module map) + `run_advanced_modules()` (feature→filter→scoring pipeline). Core of the decision engine. |
| `src/state.py` | 108 | `PipelineState`, `ModuleResult`, `ModuleHealth`, `ConnectorHook`, `EvolutionStatus` dataclasses. Used everywhere. |
| `src/utils.py` | 114 | `aggregate_direction()`, `aggregate_confidence()`, `clamp()`, `write_json_atomic()`, `normalize_reasons()`. Fundamental utilities. |
| `config/settings.json` | 36 | Runtime configuration. Required for startup. |

## Tier 2 — Core Feature/Filter/Scoring Modules

| File | Lines | Why Important |
|------|-------|--------------|
| `src/features/market_structure.py` | 94 | Market bias detection — foundational input |
| `src/features/liquidity.py` | 136 | Liquidity sweep detection — foundational input |
| `src/features/volatility.py` | 120 | Volatility regime — used by regime scoring, macro, routing |
| `src/features/sessions.py` | 120 | Session classification — blocks off-hours trades |
| `src/features/spread_state.py` | 105 | Spread estimation — blocks high-spread trades |
| `src/features/displacement.py` | 48 | Momentum displacement vote |
| `src/features/fvg.py` | 48 | Fair value gap detection |
| `src/scoring/confidence_score.py` | 31 | Base confidence computation |
| `src/filters/loss_blocker.py` | 53 | Primary trade blocker |
| `src/risk/capital_guard.py` | 180 | Capital protection — can refuse any trade |
| `src/memory/pattern_store.py` | 127 | All memory persistence |
| `src/memory/tracker.py` | 105 | Outcome recording |
| `src/mt5/adapter.py` | 279 | Data source adapter |

## Tier 3 — Replay Evaluation System

| File | Lines | Why Important |
|------|-------|--------------|
| `src/evaluation/replay_evaluator.py` | 1,297 | Core replay evaluation engine |
| `src/evaluation/decision_completeness.py` | 158 | Completeness gate |
| `src/evaluation/decision_quality.py` | 287 | Quality gate |
| `src/evaluation/replay_outcome.py` | 407 | Outcome gate |
| `src/evaluation/threshold_calibration.py` | 313 | Calibration report |
| `src/evaluation/drawdown_comparison.py` | 187 | Drawdown A/B utility |

## Tier 4 — Supporting but Not Essential

| File | Lines | Why Lower Priority |
|------|-------|-------------------|
| `src/macro/gold_macro.py` | 1,257 | Valuable for live mode, but degrades gracefully to no-op when API keys absent |
| `src/macro/adapters.py` | 710 | External data adapters — all optional |
| `src/strategy/intelligence.py` | 204 | Signal scoring — enhances but doesn't block |
| `src/learning/live_feedback.py` | 200 | Live learning loop — diagnostic only |
| `src/indicator/signal_model.py` | 111 | Output formatting |
| `src/indicator/chart_objects.py` | 39 | Chart visualization |
| `src/indicator/indicator_output.py` | 40 | Output wrapper |
| `src/monitoring/system_state.py` | 118 | Health monitoring |
| `src/module_factory.py` | 109 | Module discovery — used only by OversoulDirector |
| `src/main.py` | 14 | Thin wrapper |

## Tier 5 — Evolution/Knowledge Expansion (Optional, Feature-Flagged)

| File | Lines | Why Optional |
|------|-------|-------------|
| `src/evolution/experimental_module_spec_flow.py` | 3,860 | Knowledge expansion phases — only runs when `knowledge_expansion_enabled=True` |
| `src/evolution/knowledge_expansion_orchestrator.py` | 901 | Phase A orchestrator |
| `src/learning/self_evolving_indicator_layer.py` | 16,332 | Massive self-evolution engine — never runs in default config |
| `src/learning/autonomous_behavior_layer.py` | 560 | Autonomous behavior — only called by SEIL |
| All other `src/evolution/*` files | ~600 total | Evolution kernel support — runs but produces proposals, never modifies runtime |

## Files That Could Be Removed Without Impact

| File | Reason |
|------|--------|
| `quant-trading-system-main-12.zip` | 13 MB zip archive — provenance unclear, not referenced by any code |
| `PHASE1_CODEX_PROMPT.txt` | Original design prompt — historical reference only |
| `src/features/invisible_data_miner.py` | Quarantinable experimental module |
| `src/features/human_lag_exploit.py` | Quarantinable experimental module |
| `src/features/quantum_tremor_scanner.py` | Quarantinable experimental module |
| `src/scoring/spectral_signal_fusion.py` | Quarantinable experimental module |
| `src/scoring/meta_conscious_routing.py` | Quarantinable experimental module |
