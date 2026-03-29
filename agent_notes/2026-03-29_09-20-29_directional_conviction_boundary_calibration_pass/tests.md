## Tests run

1. `pytest -q src/tests/test_run_pipeline_decision_quality.py::test_4v3_boundary_degrades_to_wait_with_coherent_confidence_and_reason src/tests/test_run_pipeline_decision_quality.py::test_5v4_boundary_degrades_when_conviction_is_weak src/tests/test_run_pipeline_decision_quality.py::test_5v4_boundary_allows_entry_when_conviction_is_strong` (pre-fix)
- Result: fail
- Output: `1 failed, 2 passed`
- Failing evidence:
  - strong 5:4 scenario still produced `WAIT` (over-degraded boundary behavior).

2. `pytest -q src/tests/test_run_pipeline_decision_quality.py::test_4v3_boundary_degrades_to_wait_with_coherent_confidence_and_reason src/tests/test_run_pipeline_decision_quality.py::test_5v4_boundary_degrades_when_conviction_is_weak src/tests/test_run_pipeline_decision_quality.py::test_5v4_boundary_allows_entry_when_conviction_is_strong` (post-fix)
- Result: pass
- Output: `3 passed`

3. `pytest -q src/tests/test_run_pipeline_decision_quality.py::test_slight_majority_setup_rebases_confidence_after_directional_degradation src/tests/test_run_pipeline_decision_quality.py::test_manipulated_setup_conflict_votes_abstains_with_explicit_reason src/tests/test_conflict_filter_precision.py`
- Result: pass
- Output: `5 passed`

4. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_conflict_filter_precision.py src/tests/test_filter_gates.py src/tests/test_fusion_router_scoring.py`
- Result: pass
- Output: `28 passed`

5. `pytest -q src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_uses_partial_exposure_condition src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_falls_back_to_reason_when_condition_unavailable src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `10 passed`

6. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_conflict_filter_precision.py src/tests/test_filter_gates.py src/tests/test_fusion_router_scoring.py src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_uses_partial_exposure_condition src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_falls_back_to_reason_when_condition_unavailable src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `38 passed`
