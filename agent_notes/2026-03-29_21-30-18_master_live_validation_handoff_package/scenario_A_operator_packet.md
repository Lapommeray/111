## Scenario A operator packet — Broker send/linkage timing race

### Objective
- Validate that accepted live sends produce coherent broker linkage timelines and coherent final signal/contract state.

### Pre-run checks
1. Confirm run mode is live and MT5 terminal/account are connected and authorized.
2. Confirm intended symbol/timeframe for the run.
3. Start a fresh Scenario A worksheet and record run timestamp before execution.
4. Confirm immediate access to:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`

### Environment prerequisites
- Flow reaches live BUY/SELL send path.
- Branch under inspection: `order_result.broker_position_verification.*`.

### Run steps
1. Execute live cycle expected to send BUY/SELL order.
2. Observe whether send is accepted.
3. Observe linkage confirmation behavior (immediate vs delayed recheck).
4. Immediately capture required artifacts and fill worksheet.

### Monitor during run
- `order_result.status`
- `order_result.broker_state_confirmation`
- `order_result.broker_state_outcome`
- linkage delayed-recheck timeline fields.

### Immediate artifact capture
- Required files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
- Required fields:
  - `order_result.broker_position_verification.initial_confirmation`
  - `order_result.broker_position_verification.delayed_recheck_attempted`
  - `order_result.broker_position_verification.delayed_recheck_confirmation`
  - `order_result.broker_position_verification.final_confirmation`
  - `order_result.broker_position_verification.verification_checked_at`
  - `signal.action`, `signal.confidence`, `signal.reasons`, `signal.blocker_reasons`, `signal.classification`
  - `status_panel.entry_exit_decision.action`
  - `status_panel.entry_exit_decision.invalidation_reason`
  - `status_panel.entry_exit_decision.open_position_state.status`

### Pass criteria
- Complete linkage timeline fields present.
- No contradiction between broker linkage outcome, signal layer, and entry/exit contract.

### Fail criteria
- Complete artifact shows contradiction (for example, confirmed linkage with incoherent open-position/contract state).
- Missing required timeline fields in a branch where linkage verification is present.

### Inconclusive criteria
- Any required artifact file missing/truncated.
- Branch expected but not evidenced due to incomplete capture/session interruption.

### Escalation trigger
- Repeat Scenario A when inconclusive.
- Escalate to code investigation when:
  - one complete run has missing required timeline fields, or
  - same contradiction appears in 2 complete Scenario A artifacts.
