# Repository Map

## Top-Level Structure

```
111/
├── run.py                          # 3,906 lines — monolithic entrypoint & orchestrator
├── src/                            # All source modules
│   ├── __init__.py                 # Empty
│   ├── main.py                     # Thin wrapper that calls run.main()
│   ├── pipeline.py                 # OversoulDirector + run_advanced_modules()
│   ├── state.py                    # Dataclasses: PipelineState, ModuleResult, ModuleHealth, etc.
│   ├── utils.py                    # Helpers: clamp, aggregate_direction, aggregate_confidence, JSON I/O
│   ├── module_factory.py           # Filesystem-backed module discovery/loading
│   ├── features/                   # 11 feature-extraction modules
│   ├── filters/                    # 6 filter/gate modules
│   ├── scoring/                    # 5 scoring modules
│   ├── indicator/                  # 3 output-formatting modules
│   ├── memory/                     # 4 persistence & adaptive-profile modules
│   ├── learning/                   # 3 learning/self-evolution modules
│   ├── macro/                      # 2 macro-economic data modules
│   ├── risk/                       # 1 capital-guard module
│   ├── strategy/                   # 1 signal-intelligence module
│   ├── mt5/                        # 3 MT5 broker-adapter modules
│   ├── monitoring/                 # 1 system-state monitor
│   ├── evaluation/                 # 10 replay-evaluation & gate modules
│   ├── evolution/                  # 16 self-evolution & knowledge-expansion modules
│   └── tests/                      # 42 test files (~17,000 lines)
├── config/
│   ├── settings.json               # Runtime configuration
│   ├── connectors.json             # Connector-hook declarations
│   └── symbols.json                # Allowed symbols (XAUUSD only)
├── memory/                         # 196 persisted state files (JSON, CSV, .gitkeep)
├── PHASE1_CODEX_PROMPT.txt         # Original design prompt
├── quant-trading-system-main-12.zip # 13 MB zip archive (provenance unclear)
└── .gitignore
```

## Module Breakdown by Subdirectory

### src/features/ (11 modules, ~833 lines)
| File | Lines | Purpose |
|------|-------|---------|
| market_structure.py | 94 | Classifies market structure (bias detection, regime) |
| liquidity.py | 136 | Detects liquidity sweeps, stop-runs, scoring |
| displacement.py | 48 | Computes momentum displacement from bars |
| fvg.py | 48 | Detects Fair Value Gaps |
| volatility.py | 120 | Volatility regime, compression/expansion detection |
| sessions.py | 120 | Session classifier (Asia/London/NY), behavior tracking |
| spread_state.py | 105 | Spread proxy estimation, execution quality tracking |
| invisible_data_miner.py | 58 | Mines internal patterns from bars/structure/liquidity |
| human_lag_exploit.py | 42 | Models delayed continuation/reversal behavior |
| quantum_tremor_scanner.py | 42 | Micro-volatility tremor analysis |

### src/filters/ (6 modules, ~184 lines)
| File | Lines | Purpose |
|------|-------|---------|
| loss_blocker.py | 53 | Blocks trades when confidence or spread thresholds fail |
| conflict_filter.py | 24 | Blocks on vote conflicts |
| session_filter.py | 24 | Blocks during unfavorable sessions |
| spread_filter.py | 18 | Blocks when spread is too wide |
| memory_filter.py | 35 | Blocks based on outcome memory |
| self_destruct_protocol.py | 30 | Down-ranks failing logic |

### src/scoring/ (5 modules, ~172 lines)
| File | Lines | Purpose |
|------|-------|---------|
| confidence_score.py | 31 | Computes base confidence from structure + liquidity |
| setup_score.py | 41 | Scores setup quality from feature + filter outputs |
| regime_score.py | 25 | Scores regime quality |
| spectral_signal_fusion.py | 37 | Fuses multiple module outputs into a combined signal |
| meta_conscious_routing.py | 38 | Routes based on entropy/liquidity/regime |

### src/evaluation/ (10 modules, ~3,073 lines)
| File | Lines | Purpose |
|------|-------|---------|
| replay_evaluator.py | 1,297 | Core replay evaluation engine |
| replay_outcome.py | 407 | Replay outcome gate (economic sanity validation) |
| decision_completeness.py | 158 | Validates every record reaches terminal state |
| decision_quality.py | 287 | Distribution sanity, confidence diversity, reason quality |
| threshold_calibration.py | 313 | Distributional stats, evidence-based threshold recommendations |
| drawdown_comparison.py | 187 | A/B comparison of drawdown attributions |
| module_contribution_report.py | 200 | Per-module contribution analysis |
| blocker_effect_report.py | 40 | Blocker effectiveness analysis |
| session_report.py | 40 | Per-session analysis |

### src/evolution/ (16 modules, ~5,509 lines)
| File | Lines | Purpose |
|------|-------|---------|
| experimental_module_spec_flow.py | 3,860 | Knowledge expansion phases A-L, governed improvement cycle |
| knowledge_expansion_orchestrator.py | 901 | Phase A orchestrator |
| evolution_registry.py | 94 | Tracks proposed/verified/promoted modules |
| self_inspector.py | 123 | Inspects project for gaps |
| code_generator.py | 63 | Generates code proposals |
| verifier.py | 105 | Verifies proposals |
| promoter.py | 58 | Decides promotion status |
| promotion_policy.py | 96 | Promotion threshold evaluation |
| overlap_scoring.py | 135 | Scores overlap between modules |
| architecture_guard.py | 48 | Guards architecture constraints |
| duplication_audit.py | 39 | Detects duplicate proposals |
| candidate_module_factory.py | 53 | Creates candidate modules |
| gap_discovery.py | 34 | Discovers coverage gaps |
| hypothesis_registry.py | 47 | Tracks hypotheses |
| governance_report.py | 25 | Governance reporting |

### src/learning/ (3 modules, ~16,892 lines)
| File | Lines | Purpose |
|------|-------|---------|
| self_evolving_indicator_layer.py | 16,332 | Massive self-evolution engine (70+ functions) |
| autonomous_behavior_layer.py | 560 | Autonomous behavior adaptation |
| live_feedback.py | 200 | Processes live trade feedback |

### src/macro/ (2 modules, ~1,967 lines)
| File | Lines | Purpose |
|------|-------|---------|
| gold_macro.py | 1,257 | XAUUSD macro-economic state collection |
| adapters.py | 710 | Data adapters (Alpha Vantage, FRED, COMEX, etc.) |

### src/mt5/ (3 modules, ~387 lines)
| File | Lines | Purpose |
|------|-------|---------|
| adapter.py | 279 | MT5 broker adapter with CSV fallback |
| execution_state.py | 56 | Execution state dataclass |
| symbol_guard.py | 52 | Validates symbol (XAUUSD only) |

### src/risk/ (1 module)
| File | Lines | Purpose |
|------|-------|---------|
| capital_guard.py | 180 | Capital protection: daily loss, drawdown, streak limits |

### src/strategy/ (1 module)
| File | Lines | Purpose |
|------|-------|---------|
| intelligence.py | 204 | Signal intelligence scoring with pattern memory |

### src/indicator/ (3 modules)
| File | Lines | Purpose |
|------|-------|---------|
| signal_model.py | 111 | Signal output data model |
| indicator_output.py | 40 | Builds final indicator output dict |
| chart_objects.py | 39 | Builds chart visualization objects |

### src/monitoring/ (1 module)
| File | Lines | Purpose |
|------|-------|---------|
| system_state.py | 118 | System health monitoring |

### src/memory/ (4 modules)
| File | Lines | Purpose |
|------|-------|---------|
| pattern_store.py | 127 | JSON-file-backed pattern storage |
| tracker.py | 105 | Trade outcome tracking |
| self_coder.py | 69 | Auto-generates trading rules from outcomes |
| meta_adaptive_ai.py | 97 | Adaptive profile from internal memory |

## Config Files
- **settings.json**: Full runtime config (symbol, timeframe, bars, paths, thresholds, feature toggles)
- **connectors.json**: 6 connector hooks mapping modules to bus interfaces
- **symbols.json**: Only XAUUSD allowed

## Memory Directory (196 files)
Hierarchical JSON state persistence across ~30 subdirectories covering:
- Autonomous behavior state
- Capability arbitration, competition, lineage
- Knowledge expansion (phases A-L)
- Continuous governed improvement
- Evolution parameter control
- Hypothesis falsification
- Cross-layer integration
- Strategic focus
- Evaluation windows (4 CSV files)

## Total Codebase Size
- **Source code**: ~30,000 lines (excluding tests)
- **Test code**: ~17,000 lines
- **Total Python**: ~47,000 lines
- **Memory/state files**: 196 files
- **Total files**: ~332 files
