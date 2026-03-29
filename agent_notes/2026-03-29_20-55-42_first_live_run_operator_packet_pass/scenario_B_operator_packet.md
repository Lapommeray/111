## Scenario B operator packet — Exit close confirmation delay window

### Objective
- Validate live close-send confirmation timeline coherence for managed open-position exits.
- Prove that delayed confirmation windows are observable and consistent across:
  - `order_result.broker_exit_verification.*`
  - `signal.reasons`
  - `status_panel.entry_exit_decision`
  - `open_position_state`.

### Pre-run checks (must pass before run)
1. Confirm Scenario A has at least one conclusive pass record from this live cycle.
2. Confirm live account/session is connected and terminal order/position visibility is available.
3. Confirm there is an open position eligible for managed exit.
4. Confirm operator worksheet file is copied and ready:
   - `scenario_B_review_worksheet.md`.
5. Confirm artifact output paths are writable for this run:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`.

### Environment/state prerequisites
- Mode is live.
- Open position exists in broker/terminal at run start.
- Exit path is expected to be reachable by the current signal/management state.
- Operator can capture:
  - trigger timestamp,
  - symbol/timeframe,
  - macro state,
  - spread context at trigger.

### Run steps (human-executable)
1. Start Scenario B worksheet and fill run identity + pre-state context.
2. Trigger the live cycle that should execute managed close logic on the existing open position.
3. During run, monitor:
   - close send attempt outcome,
   - whether confirmation is immediate vs delayed,
   - any unresolved exit indication.
4. Immediately after run completion, capture artifact bundle:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`.
5. Populate Scenario B worksheet fields from artifacts and classify pass/fail/inconclusive.
6. Apply B-specific review gates before moving forward.

### What to monitor during run (exact)
- Exit-side verification path:
  - `order_result.broker_exit_verification.initial_confirmation`
  - `order_result.broker_exit_verification.delayed_recheck_attempted`
  - `order_result.broker_exit_verification.delayed_recheck_confirmation`
  - `order_result.broker_exit_verification.final_confirmation`
  - `order_result.broker_exit_verification.verification_checked_at`
  - `order_result.broker_exit_verification.broker_state_outcome`.
- Signal/contract coherence:
  - `signal.action`
  - `signal.confidence`
  - `signal.reasons` (must retain `open_position_exit_management:*` where applicable)
  - `signal.blocker_reasons`
  - `signal.classification`
  - `status_panel.entry_exit_decision.action`
  - `status_panel.entry_exit_decision.invalidation_reason`
  - `status_panel.entry_exit_decision.open_position_state.status`.

### Artifact files/fields to capture immediately after run
- Files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`.
- Required fields:
  - `order_result.status`
  - `order_result.broker_state_confirmation`
  - `order_result.broker_state_outcome`
  - `order_result.broker_exit_verification.*`
  - `rollback_refusal_reasons` (if present)
  - `signal.action`, `signal.confidence`, `signal.reasons`, `signal.blocker_reasons`, `signal.classification`
  - `status_panel.entry_exit_decision.action`, `reason`, `invalidation_reason`, `open_position_state.*`
  - `open_position_state.position_state_outcome`
  - `pnl_snapshot.position_open_truth`.

### Pass criteria
- Delay-window timeline is fully present and internally coherent.
- Close-confirmed branch:
  - verification indicates confirmed close, and `open_position_state.status` becomes `flat`.
- Unresolved-close branch:
  - unresolved state is explicit in verification + contract + reasons.
- No contradiction between verification payload, signal layer, and contract layer.

### Fail criteria
- Final confirmation shows close confirmed while `open_position_state.status` remains open and no coherent transition explanation exists.
- Missing `open_position_exit_management:*` reason in unresolved/managed transition context.
- Contract action/invalidation_reason contradicts exit verification and open-position state.

### Inconclusive criteria
- Artifact files missing/truncated for the run.
- Terminal/session interruption prevents complete capture.
- Required close-context inputs (open-position pre-state or trigger context) are not recorded.

### Escalation trigger if result is not clean
- **Repeat Scenario B** if result is inconclusive due to capture/session interruption.
- **Escalate to code investigation** if:
  - one high-severity contradiction exists in a complete artifact set, or
  - the same contradiction repeats in two complete Scenario B artifacts.
- Primary likely investigation zones on escalation:
  - `run.py::_run_controlled_mt5_live_execution` (exit verification/state transition assembly),
  - `run.py::_build_entry_exit_decision_contract` (contract coherence).
