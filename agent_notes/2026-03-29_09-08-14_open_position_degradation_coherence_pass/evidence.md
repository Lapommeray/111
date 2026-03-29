## Issue proven in this pass

### Gap: open-position WAIT->EXIT transition reason was missing in signal reasons
- **Location**: `run.py::run_pipeline` final decision assembly, after controlled execution result is available.
- **Observed mismatch**:
  - `signal.action == "WAIT"` and `status_panel.entry_exit_decision.action == "EXIT"` were coherent structurally,
  - but `signal.reasons` did not include an explicit open-position transition reason.
  - This created a reason-layer coherence gap for open-position management outcomes.
- **Failing tests proving gap**:
  - `src/tests/test_run_pipeline_decision_quality.py::test_open_position_valid_hold_path_attaches_transition_reason_and_coherent_outputs`
  - `src/tests/test_run_pipeline_decision_quality.py::test_partial_exposure_degradation_attaches_transition_reason_and_exit_contract`
- **Pre-fix failing evidence**:
  - expected reason `open_position_exit_management:broker_confirmed_open_position`, but reasons were only `advanced_direction=WAIT`, `seed_buy`, `abstain_confidence_rebased`.
  - expected reason `open_position_exit_management:partial_fill_exposure_unresolved`, but same omission.

## Minimal fix applied
- **File/function**: `run.py::run_pipeline`.
- **Change**:
  - when `decision == "WAIT"` and not hard-blocked, if controlled execution reports open/partial position status (`open` or `partial_exposure_unresolved`),
  - append reason `open_position_exit_management:<position_state_outcome_or_exit_reason>`.
- **Why minimal**:
  - no architecture changes,
  - no decision-action rewrite,
  - no pipeline rewiring,
  - reason coherence only.

## Post-fix result
- Focused tests now pass and show explicit transition reason presence.
- Execution/exit contract tests remain green.
- Combined targeted+nearby regression run passed (`35 passed`).
