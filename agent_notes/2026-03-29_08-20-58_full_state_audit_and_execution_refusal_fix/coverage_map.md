## Coverage map (current repository state)

### Entry gating
- **Covered**:
  - low effective confidence fail-close and blocker reason:
    - `src/tests/test_run_pipeline_decision_quality.py::test_low_effective_confidence_blocks_entry_with_explicit_reason`
  - macro live pause blocks:
    - `src/tests/test_run_pipeline_contract.py::test_run_pipeline_live_macro_pause_blocks_with_reason`
  - strong setup allows entry:
    - `src/tests/test_run_pipeline_decision_quality.py::test_strong_setup_allows_entry_with_consistent_direction_and_confidence`

### Conflict handling
- **Covered**:
  - true deadlock conflict blocks:
    - `src/tests/test_conflict_filter_precision.py::test_conflict_filter_blocks_when_both_sides_strong_and_close`
  - 2:1 and 3:2 splits do not hard-block:
    - `src/tests/test_conflict_filter_precision.py::test_conflict_filter_does_not_block_clear_majority_split`
    - `src/tests/test_conflict_filter_precision.py::test_conflict_filter_does_not_hard_block_three_vs_two_split`
  - filter-level conflict gate presence:
    - `src/tests/test_filter_gates.py::test_conflict_filter_blocks_near_balanced_opposite_votes`

### Confidence handling
- **Covered**:
  - macro-penalty confidence reflected and blocked when below threshold:
    - `src/tests/test_run_pipeline_contract.py::test_run_pipeline_replay_macro_penalty_updates_public_confidence_and_classification`
  - directional degradation confidence rebased:
    - `src/tests/test_run_pipeline_decision_quality.py::test_slight_majority_setup_rebases_confidence_after_directional_degradation`
  - execution-refusal abstain confidence rebased:
    - `src/tests/test_run_pipeline_decision_quality.py::test_execution_refusal_degrades_wait_confidence_and_reasons`
  - unblocked WAIT-direction abstain confidence rebased:
    - `src/tests/test_run_pipeline_decision_quality.py::test_unblocked_wait_direction_rebases_confidence_to_abstain_band`
- **Partially covered**:
  - confidence behavior across all abstain reasons is not exhaustively scenario-tested.

### Abstain/degradation handling
- **Covered**:
  - manipulated conflict setup abstains with explicit reason:
    - `src/tests/test_run_pipeline_decision_quality.py::test_manipulated_setup_conflict_votes_abstains_with_explicit_reason`
  - directional margin degradation to WAIT:
    - `src/tests/test_execution_gate_unittest.py` pipeline case around `directional_vote_margin_insufficient` (line block around 2320+)

### Execution-refusal handling
- **Covered**:
  - refusal reason + WAIT action:
    - `src/tests/test_run_pipeline_decision_quality.py::test_execution_refusal_degrades_wait_confidence_and_reasons`
  - confidence rebase on refusal:
    - same test above

### Exit handling
- **Covered**:
  - direct contract behavior for open positions and exit rule generation:
    - `src/tests/test_execution_gate_unittest.py::test_clean_exit_decision_contract_for_existing_open_position`
    - `::test_exit_rule_uses_stop_loss_breach_condition`
    - `::test_exit_rule_uses_take_profit_reached_condition`
    - `::test_exit_rule_uses_partial_exposure_condition`
    - `::test_exit_rule_falls_back_to_reason_when_condition_unavailable`

### Invalidation handling
- **Covered**:
  - open-position invalidation emits EXIT decision contract when strategy is WAIT:
    - `src/tests/test_run_pipeline_decision_quality.py::test_invalidated_setup_with_open_position_surfaces_exit_contract`
- **Partially covered**:
  - rapid invalidation transitions for broader degraded-open-position variants (beyond the mocked scenario) are not comprehensively covered in one focused suite.

### Open-position behavior
- **Covered**:
  - replay simulated open-position and entry-exit contract semantics:
    - `src/tests/test_execution_gate_unittest.py::test_replay_simulated_open_position_state_has_entry_price`
    - `::test_replay_pipeline_does_not_add_non_live_mode_refusal_for_buy_sell`
  - WAIT + open-position => EXIT contract:
    - `src/tests/test_run_pipeline_decision_quality.py::test_invalidated_setup_with_open_position_surfaces_exit_contract`

### Scoring aggregation behavior
- **Covered**:
  - spectral fusion missing/quarantine non-dilution:
    - `src/tests/test_fusion_router_scoring.py::test_spectral_signal_fusion_does_not_dilute_when_optional_modules_missing`
    - `::test_spectral_signal_fusion_ignores_quarantined_missing_vote_slots`
  - routing and regime scoring baseline behavior:
    - `src/tests/test_fusion_router_scoring.py::test_meta_conscious_routing_uses_regime_liquidity_volatility`
    - `::test_regime_score_changes_with_volatility_state`

### Feature-layer behavior
- **Partially covered**:
  - feature outputs are exercised through integration (`run_pipeline`) and some feature tests in broader suite,
  - but not all feature edge cases are explicitly covered in this pass set.
  - concrete exercised path: `src/pipeline.py::run_advanced_modules` uses feature functions listed in `current_state_inventory.md`.

### Filter-layer behavior
- **Covered**:
  - conflict, memory, self-destruct, session filters have direct tests:
    - `src/tests/test_filter_gates.py`
    - `src/tests/test_conflict_filter_precision.py`
- **Partially covered**:
  - spread filter threshold boundaries are exercised indirectly; explicit boundary tests in this pass set are limited.
