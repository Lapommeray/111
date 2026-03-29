## Tests run

1. `pytest -q src/tests/test_fusion_router_scoring.py` (pre-fix)
- Result: fail
- Output: `2 failed, 3 passed`
- Failing tests:
  - `test_spectral_signal_fusion_does_not_dilute_when_optional_modules_missing`
  - `test_spectral_signal_fusion_ignores_quarantined_missing_vote_slots`

2. `pytest -q src/tests/test_fusion_router_scoring.py` (post-fix)
- Result: pass
- Output: `5 passed`

3. `pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `16 passed`

4. `pytest -q src/tests/test_fusion_router_scoring.py src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_exit_decision_contract_for_existing_open_position src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal src/tests/test_quarantine_threading.py::test_pipeline_quarantine_removes_suspect_modules_from_results`
- Result: pass
- Output: `21 passed`

Artifact log: `/opt/cursor/artifacts/run_pipeline_deeper_signal_quality_tests.log`
