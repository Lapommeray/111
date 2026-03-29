## Issues executed this pass (with exact proof)

### Issue 1: execution-refusal WAIT kept trade-ready confidence
- **Location**: `run.py::run_pipeline` execution-refusal branch (`if decision in {"BUY","SELL"} and order_result.status != "accepted"`).
- **Proof test**: `src/tests/test_run_pipeline_decision_quality.py::test_execution_refusal_degrades_wait_confidence_and_reasons`.
- **Pre-fix result**: failing assertion `assert signal["confidence"] <= 0.59` with observed `0.88`.
- **Minimal fix**: cap `effective_signal_confidence` to `<= 0.59` when execution refusal downgrades action to `WAIT`.
- **Post-fix result**: test passed.

### Issue 2: non-blocked WAIT path still kept trade-ready confidence
- **Location**: `run.py::run_pipeline` final decision assembly path where decision may remain `WAIT` while `combined_blocked == False`.
- **Proof test**: added `src/tests/test_run_pipeline_decision_quality.py::test_unblocked_wait_direction_rebases_confidence_to_abstain_band`.
- **Pre-fix result**: failing assertion `assert signal["confidence"] <= 0.59` with observed `0.88`.
- **Minimal fix**: add one guard after execution step:
  - if `decision == "WAIT"` and not hard blocked, cap confidence to `<= 0.59`
  - append reason `abstain_confidence_rebased` only when actual cap is applied.
- **Post-fix result**: focused new test passed; full targeted+nearby regression run passed (`31 passed`).
