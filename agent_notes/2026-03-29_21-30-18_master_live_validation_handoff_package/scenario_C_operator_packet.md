## Scenario C operator packet — Retry/refusal under true latency

### Objective
- Validate bounded retry/refusal behavior and reason completeness under true live latency/tick timing.
- Confirm no silent loss between execution retry/refusal metadata and final signal/contract layers.

### Pre-run checks
1. Scenario A and Scenario B each have at least one conclusive pass in current live cycle.
2. Live terminal connected; symbol tradable; account execution permissions active.
3. Operator is prepared to capture full artifact bundle immediately after run.
4. Fresh Scenario C worksheet is prepared before run start.

### Environment prerequisites
- Mode is live.
- Run should encounter a non-accepted first send path in retry slice (or known conditions likely to trigger it).
- Runtime tick/price updates available.

### Run steps
1. Start Scenario C worksheet and record run identity and pre-state.
2. Execute live cycle expected to hit retry/refusal branch.
3. Monitor whether retry is attempted or fail-closed blocked.
4. Immediately collect artifact files and fill worksheet fields.
5. Classify run pass/fail/inconclusive using criteria below.

### What to monitor
- `order_result.retry_policy_truth`
- `order_result.retry_attempted_count`
- `order_result.retry_blocked_reason`
- `order_result.retry_final_outcome_status`
- `rollback_refusal_reasons`
- `signal.action`, `signal.confidence`, `signal.reasons`
- `status_panel.entry_exit_decision.action`, `invalidation_reason`

### Immediate artifact capture requirements
- Files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
- Fields:
  - all retry/refusal metadata listed above
  - delayed-recheck metadata if verification payload present
  - final signal and contract fields

### Pass criteria
- Retry path is explicit and bounded in artifact fields.
- If refusal occurs, refusal/retry causes are explicit in `signal.reasons` and coherent with contract action/invalidation.
- No contradiction between `order_result` retry metadata and downstream signal/contract interpretation.

### Fail criteria
- Retry/refusal happened but no corresponding reason context appears in final signal.
- Contract action/invalidation contradicts retry/refusal outcome.
- Incoherent confidence/action behavior on refusal branch.

### Inconclusive criteria
- Artifact bundle incomplete/truncated.
- Run never reached retry/refusal branch and cannot be classified for Scenario C objective.

### Escalation trigger
- Repeat Scenario C if inconclusive.
- Escalate if:
  - same reason-propagation mismatch repeats in 2 complete artifacts, or
  - one complete artifact proves severe contract contradiction.
