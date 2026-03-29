## Tests run

1. `pytest -q src/tests/test_conflict_filter_precision.py` (pre-fix)
- Result: fail
- Output: `1 failed, 2 passed`
- Failing test:
  - `test_conflict_filter_does_not_hard_block_three_vs_two_split`

2. `pytest -q src/tests/test_conflict_filter_precision.py src/tests/test_filter_gates.py src/tests/test_fusion_router_scoring.py src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py`
- Result: pass
- Output: `20 passed`

3. `pytest -q src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `8 passed`

4. `pytest -q src/tests/test_conflict_filter_precision.py src/tests/test_filter_gates.py src/tests/test_fusion_router_scoring.py src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `28 passed`

Artifact log: `/opt/cursor/artifacts/run_pipeline_deeper_pass_after_conflict_tie_fix.log`
