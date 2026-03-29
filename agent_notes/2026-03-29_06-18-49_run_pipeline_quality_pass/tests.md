## Tests run

1. `pytest -q src/tests/test_run_pipeline_decision_quality.py` (pre-fix)
- Result: fail
- Output: `1 failed, 3 passed`
- Failing test: `test_low_effective_confidence_blocks_entry_with_explicit_reason`

2. `pytest -q src/tests/test_run_pipeline_decision_quality.py` (post-fix)
- Result: pass
- Output: `4 passed`

3. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode`
- Result: pass
- Output: `13 passed`

4. `pytest -q src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal`
- Result: pass
- Output: `2 passed`

5. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal`
- Result: pass
- Output: `15 passed`

Artifact log: `/opt/cursor/artifacts/run_pipeline_quality_pass_tests.log`
