## Issue proven in this pass

### Defect: unresolved exit-close retry causes were not propagated to final signal reasons
- **Location**: `run.py::run_pipeline` final decision assembly after controlled execution artifacts are available.
- **Observed mismatch**:
  - open position unresolved close path correctly produced `entry_exit_decision.action == "EXIT"` and base open-position transition reason,
  - but retry/refusal causes from repeated unresolved close (`rollback_refusal_reasons`, `order_result.retry_policy_truth`) were not surfaced in `signal.reasons`.
- **Failing test proving defect**:
  - `src/tests/test_run_pipeline_decision_quality.py::test_unresolved_exit_close_retry_reasons_propagate_to_signal_layer`
- **Pre-fix failure evidence**:
  - expected:
    - `open_position_exit_retry:exit_close_order_send_refused`
    - `open_position_exit_retry_policy:retry_attempted_bounded_single_retry_execution_policy`
  - observed reasons omitted both retry-cause tags.

## Minimal fix applied
- **File/function**: `run.py::run_pipeline`
- **Change**:
  - in existing non-blocked WAIT + open/partial position reason-propagation block, append:
    - `open_position_exit_retry:<rollback_refusal_reason>` for each rollback refusal reason
    - `open_position_exit_retry_policy:<retry_policy_truth>` when present in controlled execution order result
- **Why minimal**:
  - no architecture rewrite
  - no execution-state model changes
  - no contract shape changes
  - reason-propagation only.

## Post-fix result
- Focused unresolved-close retry test passed.
- Nearby open-position and execution-contract tests remained green.
- Combined targeted+nearby regression run passed (`45 passed`).
