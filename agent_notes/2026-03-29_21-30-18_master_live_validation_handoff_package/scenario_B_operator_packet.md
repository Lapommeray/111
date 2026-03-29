## Scenario B operator packet — Exit close confirmation delay window

### Objective
- Validate live close-send confirmation timeline coherence for managed open-position exits.

### Pre-run checks
1. Confirm Scenario A has at least one conclusive pass in current live cycle.
2. Confirm `mode=live`, terminal connected, account can send/close orders.
3. Confirm an open position exists and is eligible for managed exit.
4. Confirm worksheet `scenario_B_review_worksheet.md` is prepared.
5. Confirm artifact files are writable and paths known.

### Environment prerequisites
- Live account connected.
- Open position present before trigger.
- Exit path expected to be executed by current signal/management state.

### Run steps
1. Start worksheet and fill identity + pre-state context.
2. Trigger run expected to execute managed close logic.
3. Monitor immediate vs delayed confirmation.
4. Immediately capture artifacts after run.
5. Fill worksheet and classify pass/fail/inconclusive.

### What to monitor
- `order_result.broker_exit_verification.initial_confirmation`
- `order_result.broker_exit_verification.delayed_recheck_attempted`
- `order_result.broker_exit_verification.delayed_recheck_confirmation`
- `order_result.broker_exit_verification.final_confirmation`
- `order_result.broker_exit_verification.verification_checked_at`
- `order_result.broker_exit_verification.broker_state_outcome`
- `signal.action`, `signal.confidence`, `signal.reasons`, `signal.blocker_reasons`, `signal.classification`
- `status_panel.entry_exit_decision.action`, `status_panel.entry_exit_decision.invalidation_reason`, `status_panel.entry_exit_decision.open_position_state.status`

### Immediate artifact capture requirements
- Files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
- Required fields:
  - `order_result.status`, `order_result.broker_state_confirmation`, `order_result.broker_state_outcome`
  - `order_result.broker_exit_verification.*`
  - `rollback_refusal_reasons` (if present)
  - `signal.*` fields listed above
  - `status_panel.entry_exit_decision.*`
  - `open_position_state.position_state_outcome`
  - `pnl_snapshot.position_open_truth`

### Pass criteria
- Delay-window timeline fields are present and coherent.
- Confirmed-close branch: open state transitions to flat coherently.
- Unresolved-close branch: unresolved context explicit across verification + reasons + contract.

### Fail criteria
- Confirmed close with `open_position_state.status=open` and no coherent transition reason.
- Missing `open_position_exit_management:*` context in unresolved/managed transition.
- Contract action/invalidation contradicts verification + open state.

### Inconclusive criteria
- Artifact files missing/truncated.
- Session interruption prevented complete capture.
- Required close pre-state context missing.

### Escalation trigger
- Repeat Scenario B if inconclusive.
- Escalate if one high-severity contradiction in complete artifact bundle or same contradiction repeats in 2 complete Scenario B runs.
- First investigation zones:
  - `run.py::_run_controlled_mt5_live_execution`
  - `run.py::_build_entry_exit_decision_contract`
