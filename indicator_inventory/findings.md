# Complete Findings — Indicator Inventory

## 1. Execution Path (Entry to Output)

### Entrypoint
- `main()` at `run.py:3804` → `parse_args()` → `load_runtime_config()`
- Two paths: `run_pipeline()` (live/replay) or `run_replay_evaluation()` (evaluation)

### Live/Replay Path (`run_pipeline`, run.py:2885)

**Step-by-step in order:**

1. **Config validation** — `validate_runtime_config()` (run.py:2886)
2. **Data loading** — MT5Adapter for live, CSV/memory for replay (run.py:2892-2927)
3. **MT5 readiness chain** — 9 readiness/quarantine/audit steps (run.py:2928-3007)
4. **Market structure** — `classify_market_structure(bars)` → trend_up/trend_down/range + bias (run.py:3048)
5. **Liquidity state** — `assess_liquidity_state(bars)` → sweep/stable + direction_hint (run.py:3049)
6. **Base confidence** — `compute_confidence(structure, liquidity)` → 0-1 score (run.py:3050)
7. **Advanced modules** — `run_advanced_modules()` via OversoulDirector (run.py:3055-3056):
   - 13 feature modules → 5 filter modules → 4 scoring modules → 1 memory module
   - Produces: `final_direction`, `final_confidence`, `blocked`, `blocked_reasons`
8. **Macro state** — `collect_xauusd_macro_state()` → 10 external feeds analyzed (run.py:3071)
9. **Loss blocker** — `LossBlocker().evaluate()` → structure/liquidity conflict check (run.py:3097)
10. **Strategy intelligence** — `score_signal_intelligence()` → adaptive weighting (run.py:3103)
11. **Capital protection** — `evaluate_capital_protection()` → position sizing + limits (run.py:3120)
12. **Decision determination** (run.py:3168-3248):
    - Directional votes aggregation
    - Conviction threshold (< 0.62 → WAIT)
    - Vote margin checks (< 2 → WAIT)
    - Conflict filter enforcement
13. **Blocker aggregation** (run.py:3134-3167):
    - Combines: capital_guard + macro_risk + loss_blocker + mt5_refusal
    - Any blocked → decision = "WAIT"
14. **Signal lifecycle** — `_build_signal_lifecycle_context()` (run.py:3249)
15. **MT5 execution** — `_run_controlled_mt5_live_execution()` (run.py:3272)
16. **Outcome tracking** — snapshot → blocked/promoted → evaluate_and_record (run.py:3355-3419)
17. **Rule generation** — `SelfCoder().generate_rules_from_outcomes()` (run.py:3418)
18. **Evolution kernel** — `run_evolution_kernel()` (run.py:3439)
19. **Signal output** — `build_signal_output()` (run.py:3448)
20. **Chart objects** — `build_chart_objects()` (run.py:3502)
21. **Status panel** — `build_status_panel()` (run.py:3509)
22. **Final output** — `build_indicator_output()` (run.py:3561)

### Replay Evaluation Path (`run_replay_evaluation`, run.py:3570)

Runs `evaluate_replay()` which calls `run_pipeline()` repeatedly, then:
1. `run_knowledge_expansion_phase_a()` — if enabled
2. `run_continuous_governed_improvement_cycle()` — always
3. `run_decision_completeness_gate()` — classifies records
4. `run_decision_quality_gate(strict=False)` — validates quality
5. `run_replay_outcome_gate()` — validates economics
6. `run_threshold_calibration()` — produces diagnostic stats

---

## 2. All Active Modules

### Feature Modules (10 always-active + 3 optional)

| Module | File | Function | Active | Quality |
|--------|------|----------|--------|---------|
| Displacement | displacement.py | `compute_displacement()` | ✅ Always | ✅ Sound |
| FVG | fvg.py | `detect_fvg_state()` | ✅ Always | ⚠️ Low predictive power alone |
| Liquidity (assess) | liquidity.py | `assess_liquidity_state()` | ✅ Always | ✅ Sound |
| Liquidity (sweep) | liquidity.py | `detect_liquidity_sweep_state()` | ✅ Always | ✅ Sound |
| Market Structure | market_structure.py | `classify_market_structure()` | ✅ Always | ✅ Sound |
| Market Regime | market_structure.py | `classify_market_regime()` | ✅ Always | ✅ Sound |
| Sessions | sessions.py | `compute_session_state()` | ✅ Always | ✅ Sound |
| Session Behavior | sessions.py | `track_session_behavior()` | ✅ Always | ⚠️ Small sample bias risk |
| Spread State | spread_state.py | `compute_spread_state()` | ✅ Always | ⚠️ Heuristic proxy |
| Execution Quality | spread_state.py | `track_execution_quality()` | ✅ Always | ⚠️ Heuristic proxy |
| Volatility | volatility.py | `compute_volatility_state()` | ✅ Always | ✅ Sound |
| Compression/Expansion | volatility.py | `detect_compression_expansion_state()` | ✅ Always | ⚠️ Weak probability formula |
| **Human Lag Exploit** | human_lag_exploit.py | `measure_human_lag_signal()` | ⚠️ Optional | ❌ Weak heuristic |
| **Invisible Data Miner** | invisible_data_miner.py | `mine_internal_patterns()` | ⚠️ Optional | ❌ Placeholder logic |
| **Quantum Tremor Scanner** | quantum_tremor_scanner.py | `scan_tremor_state()` | ⚠️ Optional | ❌ Duplicates volatility |

### Filter Modules (5 active + 1 unused)

| Filter | File | Function | Active | Logic |
|--------|------|----------|--------|-------|
| Session Filter | session_filter.py | `apply_session_filter()` | ✅ Active | ⚠️ Only blocks "off_hours" |
| Spread Filter | spread_filter.py | `apply_spread_filter()` | ✅ Active | ✅ Sound (60-point threshold) |
| Conflict Filter | conflict_filter.py | `apply_conflict_filter()` | ✅ Active | ✅ Sound |
| Memory Filter | memory_filter.py | `apply_memory_filter()` | ✅ Active | ✅ Sound (3-loss cluster) |
| Self-Destruct | self_destruct_protocol.py | `apply_self_destruct_protocol()` | ✅ Active | ⚠️ Aggressive (4-loss trigger) |
| **Loss Blocker** | loss_blocker.py | `LossBlocker.evaluate()` | ❌ **Not in pipeline.py** | Called separately in run.py |

### Scoring Modules (2 always + 2 optional)

| Module | File | Function | Active | Quality |
|--------|------|----------|--------|---------|
| Setup Score | setup_score.py | `compute_setup_score()` | ✅ Always | ⚠️ Informational only (delta=0) |
| Regime Score | regime_score.py | `compute_regime_score()` | ✅ Always | ⚠️ Arbitrary thresholds |
| **Spectral Fusion** | spectral_signal_fusion.py | `fuse_spectral_signals()` | ⚠️ Optional | ❌ Fuses weak modules |
| **Meta-Conscious Routing** | meta_conscious_routing.py | `compute_meta_conscious_routing()` | ⚠️ Optional | ⚠️ Hard-coded thresholds |

### Output Fields

| Field | Source | Description |
|-------|--------|-------------|
| `action` | Decision logic (run.py:3168-3248) | BUY / SELL / WAIT |
| `confidence` | Strategy intelligence blending | 0.0 – 1.0 |
| `blocked` | Blocker aggregation (run.py:3134-3167) | Boolean |
| `blocker_reasons` | All blocking modules | List of strings |
| `setup_classification` | `classify_setup()` | high_confluence / moderate / low / blocked / observe |
| `reasons` | Aggregated from all modules | List of contributing factors |
| `memory_context` | PatternStore state | snapshot_id, blocked_count, promoted_count |
| `rule_context` | SelfCoder rules | active_rule_count, matching_rule_ids |
| `schema_version` | Fixed | "phase3.v1" |

### Chart Objects (3)

| Object | Type | Content |
|--------|------|---------|
| Structure State | label | "Structure: {state}" + strength value |
| Liquidity State | label | "Liquidity: {state} / sweep={type}" + score |
| Signal Action | signal_tag | "Action: {BUY/SELL/WAIT}" + confidence + blocked |

### Status Panel Fields

| Field | Content |
|-------|---------|
| structure_state | From market structure module |
| liquidity_state | From liquidity module |
| confidence | Final computed confidence |
| blocker_result | blocked bool + blocker_reasons list |
| memory_result | PatternStore summary |
| generated_rule_result | SelfCoder rule summary |
| advanced_module_result | Pipeline director + module health |
| evolution_result | Evolution kernel state |

---

## 3. Direction Decision Path

**Where direction is determined (run.py:3168-3233):**

1. Base direction from `advanced_state.final_direction` (pipeline.py aggregate_direction)
2. Directional votes collected from all module results
3. `directional_support_ratio` = votes_for_direction / total_votes
4. `directional_conviction` computed from support_ratio
5. **Forced to WAIT if:**
   - `directional_conviction < 0.62`
   - Vote margin < 2
   - Conflict filter triggered
   - Any blocker active (capital, macro, loss_blocker, MT5)

## 4. Confidence Decision Path

**Where confidence is determined:**

1. **Base**: `compute_confidence(structure, liquidity)` — 55% structure + 35% liquidity + 10% agreement
2. **Adjusted by**: Each module's `confidence_delta` summed via `aggregate_confidence()`
3. **Re-weighted by**: `score_signal_intelligence()` — adaptive blending with win_rate
4. **Final formula**: `(base * adaptive_weight) + (signal_score * (1 - adaptive_weight) * 0.7) + (confirmation_ratio * 0.3)`
5. **Clamped**: [0.0, 1.0]

## 5. Blocker Logic Path

**Where blocking is determined:**

1. **Pipeline filters** (pipeline.py:191-197): session, spread, conflict, memory, self-destruct
2. **Loss blocker** (run.py:3097): structure-liquidity conflict, confidence threshold
3. **Capital guard** (run.py:3120): daily loss, drawdown, loss streak, anomaly clusters
4. **Macro risk** (run.py:3071): macro regime blockers
5. **MT5 refusal** (run.py:3272): connection/readiness failures
6. **Decision thresholds** (run.py:3168-3248): conviction < 0.62, margin < 2

---

## 6. Implemented but Unused / Disconnected

| Item | File | LOC | Status |
|------|------|-----|--------|
| `autonomous_behavior_layer.py` | src/learning/ | 560 | Imported, never called |
| `self_evolving_indicator_layer.py` | src/learning/ | 16,332 | Test-only, not in pipeline |
| `LossBlocker` | src/filters/loss_blocker.py | 53 | Not called in pipeline.py filter stage |
| `EvolutionStatus` | src/state.py:36 | 8 | Defined, never instantiated |
| `timeframe_to_minutes()` | src/utils.py:34 | 5 | Dead code |
| `ensure_required_keys()` | src/utils.py:53 | 4 | Dead code |
| `ModuleFactory.refresh()` | src/module_factory.py:56 | 2 | Never called |
| `ModuleFactory.create_all_modules()` | src/module_factory.py:80 | 10 | Never called |
| `ModuleFactory.get_module_count()` | src/module_factory.py:67 | 2 | Never called |

## 7. Duplicated / Conflicting Logic

| Issue | Files | Problem |
|-------|-------|---------|
| Volatility duplication | volatility.py + quantum_tremor_scanner.py | Both compute range ratio from same data with similar thresholds |
| Confidence computed twice | confidence_score.py + run.py strategy intelligence | Base confidence computed, then fully recalculated by intelligence layer |
| LossBlocker vs pipeline filters | loss_blocker.py + run.py | LossBlocker runs separately from pipeline filter stage; partially overlaps |
| Direction determined twice | pipeline.py + run.py | pipeline aggregate_direction, then run.py overrides with conviction checks |

## 8. Weak Logic Likely to Create False Signals

| Module | Problem | Impact |
|--------|---------|--------|
| human_lag_exploit | Assumes retail traders lag systematically — unvalidated | False continuation signals during reversals |
| invisible_data_miner | Step-counting with arbitrary alignment bonus | Fake confidence boost in choppy markets |
| quantum_tremor_scanner | Duplicate of volatility with no added value | Redundant votes dilute signal quality |
| spectral_signal_fusion | Averages 3 weak modules equally with 3 real modules | Drags fused score toward noise |
| session_behavior | Win-rate from small samples used predictively | Look-ahead bias risk, unreliable confidence |
| confidence_score | 10% weight on agreement means disagreement barely hurts | High confidence possible despite signal conflict |
| All scoring thresholds | Hard-coded magic numbers (0.62, 0.6, 1.8, 1.2, etc.) | No empirical basis; potentially miscalibrated |
