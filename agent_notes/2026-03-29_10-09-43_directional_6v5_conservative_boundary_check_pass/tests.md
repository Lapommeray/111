## Tests run

1. `pytest -q src/tests/test_run_pipeline_decision_quality.py::test_6v5_boundary_degrades_when_conviction_is_weak src/tests/test_run_pipeline_decision_quality.py::test_6v5_boundary_moderate_conviction_remains_conservatively_degraded src/tests/test_run_pipeline_decision_quality.py::test_6v5_boundary_remains_conservative_even_when_signal_is_strong`
- Result: pass
- Output: `3 passed`

2. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_conflict_filter_precision.py src/tests/test_filter_gates.py src/tests/test_fusion_router_scoring.py`
- Result: pass
- Output: `38 passed`

3. `pytest -q src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_uses_partial_exposure_condition src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_falls_back_to_reason_when_condition_unavailable src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `10 passed`

4. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_conflict_filter_precision.py src/tests/test_filter_gates.py src/tests/test_fusion_router_scoring.py src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_uses_partial_exposure_condition src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_rule_falls_back_to_reason_when_condition_unavailable src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `48 passed`
