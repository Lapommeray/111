## Tests run
1. `python3 -m pytest -q src/tests/test_run_pipeline_decision_quality.py::test_unresolved_exit_retry_with_macro_penalty_and_spread_above_threshold_preserves_cooccurring_reasons src/tests/test_run_pipeline_decision_quality.py::test_unresolved_exit_retry_with_macro_penalty_and_spread_at_threshold_preserves_retry_reasons src/tests/test_run_pipeline_decision_quality.py::test_unresolved_exit_retry_with_macro_penalty_and_spread_below_threshold_preserves_retry_reasons src/tests/test_run_pipeline_decision_quality.py::test_replay_live_parity_preserves_unresolved_exit_retry_reasons_when_no_live_only_blockers src/tests/test_run_pipeline_decision_quality.py::test_replay_live_parity_live_pause_blocks_but_keeps_unresolved_exit_reason_propagation`
- Result: PASS
- Output: `5 passed in 0.22s`

2. `python3 -m pytest -q src/tests/test_run_pipeline_decision_quality.py src/tests/test_run_pipeline_contract.py src/tests/test_filter_gates.py src/tests/test_conflict_filter_precision.py src/tests/test_fusion_router_scoring.py src/tests/test_execution_gate_unittest.py src/tests/test_memory.py src/tests/test_macro_replay_bypass.py src/tests/test_quarantine_threading.py`
- Result: PASS
- Output: `148 passed in 14.66s`
