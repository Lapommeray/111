## Tests run
1. `python3 -m pytest -q src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_accepted_send_delayed_recheck_confirms_exact_linkage_when_broker_truth_appears src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_exit_close_send_without_disappearance_fails_closed_unresolved_open src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_partial_fill_delayed_recheck_confirms_exact_linked_deal_when_broker_truth_appears`
- Result: PASS
- Output: `3 passed in 0.60s`

2. `python3 -m pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_filter_gates.py src/tests/test_conflict_filter_precision.py src/tests/test_fusion_router_scoring.py src/tests/test_execution_gate_unittest.py src/tests/test_memory.py src/tests/test_macro_replay_bypass.py src/tests/test_quarantine_threading.py`
- Result: PASS
- Output: `150 passed in 9.78s`
