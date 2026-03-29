## Tests run

1. `pytest -q src/tests/test_run_pipeline_contract.py`  
- Result: pass  
- Output: `4 passed`

2. `pytest -q src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode`  
- Result: pass  
- Output: `5 passed`

3. `pytest -q src/tests/test_run_pipeline_contract.py src/tests/test_macro_replay_bypass.py src/tests/test_memory.py::test_run_pipeline_first_run_live_and_replay_csv src/tests/test_memory.py::test_run_pipeline_compact_output_mode`  
- Result: pass  
- Output: `9 passed`

Artifact log: `/opt/cursor/artifacts/run_pipeline_first_impl_pass_tests.log`
