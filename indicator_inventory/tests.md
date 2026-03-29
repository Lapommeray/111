# Test Inventory

## Test Suite Status

**Run Date**: 2026-03-29
**Result**: 696 passed, 0 failed, 0 errors
**Duration**: 28.61 seconds
**Command**: `python -m pytest -q --tb=no`

---

## All Test Files (43 files)

| File | Tests | Domain |
|------|-------|--------|
| `test_autonomous_behavior_layer.py` | Autonomous behavior layer | Learning |
| `test_autonomous_capability_expansion_layer.py` | Capability expansion | Learning |
| `test_chart_objects.py` | Chart object generation | Indicator |
| `test_config_settings_json.py` | Config validation | Configuration |
| `test_continuous_governed_improvement_cycle.py` | Governed improvement | Evolution |
| `test_decision_completeness.py` | Decision completeness gate (18 tests) | Evaluation |
| `test_decision_quality.py` | Decision quality gate (27 tests) | Evaluation |
| `test_drawdown_attribution_plumbing.py` | Drawdown attribution | Evaluation |
| `test_drawdown_comparison.py` | Drawdown A/B comparison | Evaluation |
| `test_evaluation_reports.py` | Evaluation report structure | Evaluation |
| `test_evolution.py` | Evolution kernel | Evolution |
| `test_execution_gate_unittest.py` | Execution gate logic | MT5 |
| `test_execution_safety.py` | Execution safety checks | MT5 |
| `test_features.py` | All feature modules | Features |
| `test_filter_gates.py` | Filter gate integration | Filters |
| `test_filters.py` | Individual filter logic | Filters |
| `test_fusion_router_scoring.py` | Scoring fusion/routing | Scoring |
| `test_indicator_output.py` | Indicator output structure | Indicator |
| `test_institutional_layers.py` | Institutional analysis layers | Strategy |
| `test_knowledge_expansion_phase_a.py` | Knowledge expansion phase A | Evolution |
| `test_knowledge_expansion_phase_b.py` | Knowledge expansion phase B | Evolution |
| `test_knowledge_expansion_phase_c.py` | Knowledge expansion phase C | Evolution |
| `test_knowledge_expansion_phase_d.py` | Knowledge expansion phase D | Evolution |
| `test_knowledge_expansion_phase_e.py` | Knowledge expansion phase E | Evolution |
| `test_knowledge_expansion_phase_f.py` | Knowledge expansion phase F | Evolution |
| `test_knowledge_expansion_phase_g.py` | Knowledge expansion phase G | Evolution |
| `test_knowledge_expansion_phase_h.py` | Knowledge expansion phase H | Evolution |
| `test_knowledge_expansion_phase_i.py` | Knowledge expansion phase I | Evolution |
| `test_knowledge_expansion_phase_j.py` | Knowledge expansion phase J | Evolution |
| `test_knowledge_expansion_phase_k.py` | Knowledge expansion phase K | Evolution |
| `test_knowledge_expansion_phase_l.py` | Knowledge expansion phase L | Evolution |
| `test_macro_feeds.py` | Macro data feeds | Macro |
| `test_macro_replay_bypass.py` | Macro replay bypass logic | Macro |
| `test_memory.py` | Memory subsystem | Memory |
| `test_memory_evolution_support.py` | Memory-evolution integration | Memory/Evolution |
| `test_module_factory.py` | Module factory discovery | Core |
| `test_quarantine_threading.py` | Quarantine threading logic | Core |
| `test_replay_execution_costs.py` | Replay execution costs | Evaluation |
| `test_replay_outcome.py` | Replay outcome gate (36 tests) | Evaluation |
| `test_replay_override_guard.py` | Replay override protection | Evaluation |
| `test_runtime_config_hardening.py` | Runtime config validation | Configuration |
| `test_scoring.py` | Scoring modules | Scoring |
| `test_self_evolving_indicator_layer.py` | Self-evolving indicator | Learning |
| `test_spread_state.py` | Spread state computation | Features |
| `test_threshold_calibration.py` | Threshold calibration (32 tests) | Evaluation |

---

## Coverage Gaps (Tests That Should Exist But Don't)

### Missing Test Coverage:

| Area | Missing Tests | Priority |
|------|--------------|----------|
| End-to-end pipeline | No test runs `run_pipeline()` with mock bars → verifies full output | HIGH |
| Confidence conflict | No test verifies confidence drops when structure disagrees with liquidity | HIGH |
| Threshold boundaries | No test checks exact behavior at conviction=0.62, displacement=1.8, etc. | MEDIUM |
| Session filter edge cases | No test for specific session transitions (London→NY crossover) | MEDIUM |
| Signal lifecycle | No test for `_evaluate_signal_lifecycle()` path | MEDIUM |
| Chart objects validation | Tests exist but may not validate all 3 chart object fields | LOW |
| Compact signal payload | No test for `_build_compact_signal_payload()` | LOW |
| MetaAdaptiveAI integration | No test verifying MetaAdaptiveAI output affects pipeline | LOW |

### Tests Run in This Session:

```
$ python -m pytest -q --tb=no
696 passed in 28.61s
```

All 696 tests passed with zero failures. No tests were added, modified, or removed in this session.
