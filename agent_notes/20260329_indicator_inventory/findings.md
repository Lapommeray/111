# Findings — Verified Indicator Inventory

## 1. Feature Modules (src/features/)

### Always-on (10 modules, called from pipeline.py:165-176)

| Module | File | Function | Status | Assessment |
|--------|------|----------|--------|------------|
| displacement | displacement.py | `compute_displacement(bars)` | **ACTIVE** | Uses body-to-avg-body ratio. Direction vote + confidence_delta. Thresholds: ≥1.8 strong (+0.08), ≥1.2 moderate (+0.03). Sound logic using real OHLC data. |
| fvg | fvg.py | `detect_fvg_state(bars)` | **ACTIVE** | 3-candle fair value gap. Direction vote + confidence_delta (+0.04). No-gap penalty (-0.01). Sound logic. |
| volatility | volatility.py | `compute_volatility_state(bars)` | **ACTIVE** | Range ratio vs 20-bar average. High volatility (-0.05), compression (-0.02), balanced (+0.01). Sound logic. |
| sessions | sessions.py | `compute_session_state(bars)` | **ACTIVE** | Time-based session classification (asia/london/new_york/off_hours). Major session boost (+0.03), off_hours penalty (-0.04). Sound. |
| spread_state | spread_state.py | `compute_spread_state(bars)` | **ACTIVE** | ⚠️ **PROXY** — estimates spread as `avg_range * 2.0` clamped to [5, 120]. This is NOT real bid-ask spread data. |
| liquidity_sweep | liquidity.py | `detect_liquidity_sweep_state(bars)` | **ACTIVE** | Detects stop-runs using wick/body ratio and volume. Direction vote on sweep. Sound but depends on volume data quality. |
| compression_expansion | volatility.py | `detect_compression_expansion_state(bars)` | **ACTIVE** | Breakout probability from contraction + expansion ratio. ⚠️ Probability formula (`0.55 if contracted else 0.25 + expansion bonus`) is a heuristic with no empirical backing. |
| session_behavior | sessions.py | `track_session_behavior(bars, outcomes)` | **ACTIVE** | Session win-rate learning. ⚠️ Extrapolates from potentially tiny sample sizes — guards with "weak_pattern_pruned" when samples < 2, but 2 samples is still statistically worthless. |
| market_regime | market_structure.py | `classify_market_regime(structure, volatility)` | **ACTIVE** | Trend/range/high_volatility classification. Sound logic. |
| execution_quality | spread_state.py | `track_execution_quality(bars)` | **ACTIVE** | ⚠️ **PROXY** — slippage proxy from open/close gap, fill timing proxy from bar timestamps. Not real execution data. |

### Quarantinable (3 modules, pipeline.py:178-183)

| Module | File | Function | Status | Assessment |
|--------|------|----------|--------|------------|
| invisible_data_miner | invisible_data_miner.py | `mine_internal_patterns(bars, structure, liquidity)` | **ACTIVE unless quarantined** | ⚠️ **WEAK** — counts up_steps vs down_steps and slope direction over 30 bars. Alignment bonus when it agrees with structure/liquidity. This is just momentum restatement with arbitrary confidence boost. |
| human_lag_exploit | human_lag_exploit.py | `measure_human_lag_signal(bars)` | **ACTIVE unless quarantined** | ⚠️ **WEAK** — assumes last-body vs avg-body ratio >1.1 + momentum direction implies "late continuation". Unvalidated behavioral assumption. |
| quantum_tremor_scanner | quantum_tremor_scanner.py | `scan_tremor_state(bars)` | **ACTIVE unless quarantined** | ⚠️ **DUPLICATES volatility** — computes same range ratio concept as `compute_volatility_state()` with slightly different thresholds (1.8 vs 1.6 for spike). Adds no new information. |

---

## 2. Filter Modules (src/filters/)

### Active in pipeline (5 filters, pipeline.py:191-197)

| Filter | File | Function | Status | Assessment |
|--------|------|----------|--------|------------|
| session_filter | session_filter.py | `apply_session_filter(session_state)` | **ACTIVE** | Blocks off_hours. Confidence delta: blocked=-0.08, allowed=+0.01. Simple, sound. |
| spread_filter | spread_filter.py | `apply_spread_filter(spread_state)` | **ACTIVE** | Blocks when spread_points > 60. ⚠️ Depends on spread proxy (not real spread data). |
| conflict_filter | conflict_filter.py | `apply_conflict_filter(votes, base_direction)` | **ACTIVE** | Blocks when buy_count and sell_count both > 0 and margin ≤ 1. Sound. |
| memory_filter | memory_filter.py | `apply_memory_filter(direction, blocked_setups, outcomes)` | **ACTIVE** | Blocks when ≥3 losses in same direction from last 30 outcomes. Sound concept. |
| self_destruct_protocol | self_destruct_protocol.py | `apply_self_destruct_protocol(outcomes, module_outputs)` | **ACTIVE** | Blocks when ≥4 losses in last 20 trades. Down-ranks fvg, human_lag_exploit, invisible_data_miner. Sound concept. |

### Standalone blocker (NOT in pipeline, called separately in run.py:3097)

| Filter | File | Function | Status | Assessment |
|--------|------|----------|--------|------------|
| LossBlocker | loss_blocker.py | `LossBlocker.evaluate()` | **ACTIVE** (separate path) | Blocks on: confidence < 0.6, neutral structure, or hard structure-liquidity conflict (sweep with score ≥ 0.7). Sound logic. |

---

## 3. Scoring Modules (src/scoring/)

### Always-on (2 modules, pipeline.py:203-207)

| Module | File | Function | Status | Assessment |
|--------|------|----------|--------|------------|
| setup_score | setup_score.py | `compute_setup_score(module_outputs)` | **ACTIVE** | ⚠️ Informational only — produces score but sets `confidence_delta=0.0`. Does NOT affect final confidence. Purely diagnostic. |
| regime_score | regime_score.py | `compute_regime_score(structure, volatility)` | **ACTIVE** | `(structure_strength + volatility_bonus) * 0.15 offset from 0.5`. Contributes confidence_delta. ⚠️ volatility_bonus thresholds are hard-coded heuristics. |

### Quarantinable (2 modules, pipeline.py:208-215)

| Module | File | Function | Status | Assessment |
|--------|------|----------|--------|------------|
| spectral_signal_fusion | spectral_signal_fusion.py | `fuse_spectral_signals(module_outputs)` | **ACTIVE unless quarantined** | ⚠️ **FUSES WEAK MODULES** — averages confidence_delta from displacement, fvg, volatility, quantum_tremor_scanner, invisible_data_miner, human_lag_exploit. 3 of 6 inputs are weak/placeholder modules. |
| meta_conscious_routing | meta_conscious_routing.py | `compute_meta_conscious_routing(regime, liquidity, volatility)` | **ACTIVE unless quarantined** | Routes confidence using regime score, liquidity score, and volatility. Uses hard-coded thresholds (regime ≥ 0.6, liquidity ≥ 0.6). |

---

## 4. Confidence Scoring (src/scoring/confidence_score.py)

Called at run.py:3050 BEFORE advanced modules run.

```python
confidence = (0.55 * structure_strength) + (0.35 * liquidity_score) + (0.10 * agreement)
```

- agreement = 1.0 if structure and liquidity agree, else 0.4
- ⚠️ Agreement weight is only 10%. Direction conflict barely hurts confidence.

---

## 5. Aggregation Logic

### Direction (src/utils.py:14-27)

```python
aggregate_direction(base_direction, all_votes)
```

Simple majority vote counting: highest of buy/sell/wait wins. Base direction counted twice (once explicitly + once in votes list at pipeline.py:189).

### Confidence (src/utils.py:30-31)

```python
aggregate_confidence(base_confidence, all_deltas) = clamp(base + sum(deltas), 0, 1)
```

Simple additive. All module deltas summed. No weighting by module quality.

### Strategy Intelligence (src/strategy/intelligence.py:48-94)

Replaces pipeline's aggregated confidence:
```python
confidence = (base * adaptive_weight) + (signal_score * (1 - adaptive_weight) * 0.7) + (confirmation_ratio * 0.3)
```

- adaptive_weight = 0.5 + (win_rate - 0.5) * 0.6, clamped [0.2, 0.8]
- signal_score = average of per-module _feature_score()
- confirmation_ratio = fraction of modules voting same as decision

This is the **actual** confidence used in final output. Pipeline's `aggregate_confidence` result is fed as `base_confidence` input.

---

## 6. Blocker Logic (run.py:3134-3166)

Combined blocking from:
1. `LossBlocker.evaluate()` → confidence < 0.6, neutral structure, or hard conflict
2. `advanced_state.blocked` → any pipeline filter triggered
3. `mt5_unsafe_refusal` → quarantine or failed readiness
4. `capital_guard.trade_refused` → daily loss / drawdown / loss streak
5. `macro_risk.pause_trading` → macro event pause (live mode only)

If any blocked → decision forced to "WAIT".

### Additional decision gates (run.py:3229-3247):

Even if NOT blocked, BUY/SELL forced to WAIT when:
- `directional_conviction < 0.62` (conviction = 0.7*confidence + 0.2*support_ratio + 0.1*margin_ratio)
- `directional_vote_margin < 2` (absolute difference between buy and sell vote counts)
- conflict_filter was triggered

---

## 7. Output Fields

### Signal Payload (run.py:3448-3500)
- `action`: BUY / SELL / WAIT
- `confidence`: float [0,1] — from strategy intelligence, NOT pipeline aggregate
- `reasons`: list of strings
- `blocked`: bool
- `setup_classification`: high_confluence / moderate_confluence / low_confluence / blocked / observe
- `blocker_reasons`: list of strings
- `memory_context`: snapshot_id, blocked_count, promoted_count, latest_outcome
- `rule_context`: active_rule_count, matching_rule_ids
- `schema_version`: "phase3.v1"
- `advanced_modules`: director map, discovered modules, results, health, hooks
- `evolution_kernel`: enabled, inspection, gaps, lifecycle
- `signal_score`, `feature_contributors`: from strategy intelligence
- `macro_state`, `trade_tags`: from macro layer
- `live_learning_loop`: latest trade evaluation + mutation candidate
- `strategy_promotion_policy`: promotion thresholds and pass/fail
- `capital_guard`: effective_volume, trade_refused, daily_loss_check
- `signal_lifecycle`: signal age tracking

### Chart Objects (src/indicator/chart_objects.py)
3 objects:
1. `structure_state` label — structure state + strength
2. `liquidity_state` label — liquidity state + sweep type + score
3. `signal_action` tag — action + confidence + blocked

### Status Panel (src/indicator/indicator_output.py + run.py:3509-3558)
- structure_state, liquidity_state, confidence
- blocker_result (blocked + reasons)
- memory_result (latest outcome + summary)
- generated_rule_result (count + matching IDs)
- advanced_module_result (blocked, count, ready count)
- evolution_result (enabled, gaps, proposals, lifecycle counts)
- execution_state (full ExecutionState dict)
- system_monitor (health, win_rate, drawdown, positions)
- macro_state, trade_tags
- strategy_promotion_policy
- entry_exit_decision (action, entry_price, SL, TP, exit_rule)

### Final Output (indicator_output.py:27-40)
```json
{
  "schema_version": "phase3.output.v1",
  "symbol": "...",
  "signal": { /* signal payload */ },
  "chart_objects": [ /* 3 objects */ ],
  "status_panel": { /* all status fields */ }
}
```

---

## 8. Replay vs Live Path Differences

| Aspect | Replay | Live |
|--------|--------|------|
| Data source | CSV file or memory store | MT5Adapter → MT5 terminal or CSV fallback |
| MT5 execution | Skipped (readiness set to non-live) | Full controlled execution with order placement |
| Macro feeds | Disabled by default (`macro_feed_allow_replay_fetch=false`) | Enabled if `macro_feed_enabled=true` |
| Macro pause trading | Not applied | Applied if `pause_trading=true` |
| Structure override | Applied only in replay isolation memory root | Not applied |
| Execution costs | Configurable via evaluation settings | Real execution |

---

## 9. Disconnected / Inactive Code

| Item | Location | Lines | Status |
|------|----------|-------|--------|
| `run_autonomous_behavior_layer()` | src/learning/autonomous_behavior_layer.py | 560 | **DISCONNECTED** — exported from `__init__.py` but never imported by run.py or pipeline.py. Only called from `self_evolving_indicator_layer.py`. |
| `run_self_evolving_indicator_layer()` | src/learning/self_evolving_indicator_layer.py | 16,332 | **DISCONNECTED from main pipeline** — only imported by `experimental_module_spec_flow.py` (evolution). Not called from `run_pipeline()`. |
| `EvolutionStatus` dataclass | src/state.py:36-43 | 8 | **UNUSED** — never populated with real data in pipeline. Default zeros on PipelineState. |
| `setup_score` scoring module | src/scoring/setup_score.py | 42 | **ACTIVE but zero-effect** — explicitly sets `confidence_delta=0.0`. Does not affect any decision. |

---

## 10. Module-by-Module Status Labels

### ACTIVE — sound logic
- displacement, fvg, volatility, sessions, market_regime
- session_filter, conflict_filter, memory_filter, self_destruct_protocol
- LossBlocker, regime_score
- classify_market_structure, assess_liquidity_state, compute_confidence

### ACTIVE — proxy/heuristic (not backed by real data)
- spread_state (spread proxy from candle range)
- execution_quality (slippage/timing proxy from bar data)
- spread_filter (depends on spread proxy)
- compression_expansion (heuristic breakout probability)
- session_behavior (small-sample win-rate extrapolation)

### ACTIVE — weak/high-risk for false signals
- invisible_data_miner (momentum restatement with alignment bonus)
- human_lag_exploit (unvalidated behavioral assumption)
- quantum_tremor_scanner (duplicates volatility)
- spectral_signal_fusion (fuses 3 weak + 3 real modules equally)

### ACTIVE — informational only, zero effect
- setup_score (confidence_delta hardcoded to 0.0)

### DISCONNECTED
- autonomous_behavior_layer (560 lines, not in any active path)
- self_evolving_indicator_layer (16,332 lines, only in evolution spec flow)
- EvolutionStatus dataclass (never populated)
