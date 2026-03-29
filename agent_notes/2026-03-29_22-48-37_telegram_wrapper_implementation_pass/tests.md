## Tests run
1. `python3 -m pytest -q src/tests/test_telegram_sidecar.py src/tests/test_run_pipeline_contract.py`
- Result: PASS
- Output: `11 passed in 0.15s`

2. `python3 -m pytest -q src/tests/test_execution_gate_unittest.py::TestExecutionGateSemantics::test_clean_long_entry_decision_contract_for_buy_signal`
- Result: PASS
- Output: `1 passed in 0.07s`
