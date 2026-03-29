## Evidence map

### Issue 1: Execution-refusal downgrade to WAIT kept trade-high confidence
- **Exact location**: `run.py` execution-refusal branch in `run_pipeline` where:
  - `decision in {"BUY","SELL"}` and MT5 controlled execution returns non-accepted status
  - action is downgraded to `WAIT` with reason `mt5_controlled_execution_refused`
- **Pre-fix behavior**:
  - action became `WAIT` but `signal["confidence"]` remained high (e.g. `0.88`), creating abstain confidence inconsistency.
- **Proof test (pre-fix failing)**:
  - `src/tests/test_run_pipeline_decision_quality.py::test_execution_refusal_degrades_wait_confidence_and_reasons`
- **Observed failure evidence**:
  - Expected `signal["confidence"] <= 0.59`, observed `0.88`.
- **Minimal fix applied**:
  - In execution-refusal branch, when action is downgraded to WAIT, cap `effective_signal_confidence` to `<= 0.59`.
- **Post-fix result**:
  - Same scenario returns `WAIT` with low confidence and explicit refusal reason.

### Issue 2: Missing regression guard for execution-refusal abstain confidence semantics
- **Exact location**: `src/tests/test_run_pipeline_decision_quality.py`
- **What was added**:
  - `test_execution_refusal_degrades_wait_confidence_and_reasons`
- **Post-fix result**:
  - Focused and consolidated suites pass, locking behavior.
