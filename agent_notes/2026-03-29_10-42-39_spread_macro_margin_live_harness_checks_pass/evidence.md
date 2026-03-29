## Evidence

### Phase 1: Spread-boundary + macro penalty integration
- Issue type: coverage gap (not a proven production defect).
- Location: `src/tests/test_run_pipeline_decision_quality.py`.
- Added tests:
  - `test_spread_at_threshold_with_macro_penalty_blocks_by_confidence_not_spread`
  - `test_spread_just_below_threshold_with_macro_penalty_blocks_by_confidence_only`
  - `test_spread_above_threshold_with_macro_penalty_stays_spread_blocked_and_consistent`
- Proof/result:
  - At threshold and just below threshold with penalty, outputs block for `confidence_below_threshold` and do not mis-tag spread blocker.
  - Above threshold with penalty, spread blocker remains present and may coexist with confidence blocker.
  - Assertions now explicitly enforce coherent blocker/action/confidence expectations.

### Phase 2: Margin-1 override under macro-risk tags
- Issue type: coverage gap (guarded regression surface).
- Location: `src/tests/test_run_pipeline_decision_quality.py`.
- Added tests:
  - `test_5v4_strong_setup_with_macro_penalty_degrades_to_wait_coherently`
  - `test_5v4_strong_setup_with_macro_pause_tag_does_not_block_in_replay`
  - `test_6v5_strong_setup_with_macro_penalty_stays_conservative_and_blocked_by_confidence`
  - `test_5v4_strong_setup_with_conflicting_macro_tags_and_no_penalty_remains_tradable`
- Proof/result:
  - Macro penalty can force confidence-based WAIT/block even for strong margin-1 directional setups.
  - Replay mode does not apply live-only pause blocking.
  - 6:5 stays conservative with macro penalty.
  - Non-penalized conflicting macro tags do not incorrectly force a block.

### Phase 3: Live-mode unresolved-exit follow-up reproducibility feasibility
- Question: is this currently reproducible in harness or only live-manual?
- Repository evidence used:
  - `src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_close_send_without_disappearance_fails_closed_unresolved_open`
  - `src/tests/test_execution_gate_unittest.py` assertions across `retry_policy_truth` and `rollback_refusal_reasons` paths.
  - `src/tests/test_memory.py::test_run_pipeline_persists_controlled_mt5_execution_artifacts`
- Result:
  - Reproducible in harness (deterministic unresolved-close and persistence paths already exist).
  - Therefore this item is not blocked as “live-only unverified” in current repo state.

## Regression confirmation
- Command: `python3 -m pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_filter_gates.py src/tests/test_conflict_filter_precision.py src/tests/test_fusion_router_scoring.py src/tests/test_execution_gate_unittest.py src/tests/test_memory.py`
- Result: `125 passed in 12.09s`.
