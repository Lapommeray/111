## Scenario C Review Worksheet (copy-ready)

### 1) Run identity
- Scenario name: C — Retry/refusal path under true latency
- Run datetime (UTC):
- Environment (terminal, account type, mode=live):
- Symbol:
- Timeframe:

### 2) Market context at trigger
- Bid/ask or spread snapshot:
- Spread threshold config:
- Macro pause state:
- Open position pre-state (`open_position_state.status`, `position_id`, `side`):

### 3) Signal transition
- Initial `signal.action`:
- Final `signal.action`:
- Final `signal.confidence`:
- Final `signal.reasons`:
- Final `signal.blocker_reasons`:
- Final `signal.classification`:

### 4) Entry/exit contract checks
- `status_panel.entry_exit_decision.action`:
- `status_panel.entry_exit_decision.reason`:
- `status_panel.entry_exit_decision.invalidation_reason`:
- `status_panel.entry_exit_decision.open_position.status`:
- Contract coherence verdict (pass/fail + one line why):

### 5) Broker verification payload checks
- `order_result.status`:
- `order_result.broker_state_confirmation`:
- `order_result.broker_state_outcome`:
- `order_result.broker_position_verification` (if present):
- `order_result.broker_exit_verification` (if present):
- `order_result.partial_quantity_verification` (if present):

### 6) Delayed recheck metadata
- `initial_confirmation`:
- `delayed_recheck_attempted`:
- `delayed_recheck_confirmation`:
- `final_confirmation`:
- `verification_checked_at`:
- Timeline coherence verdict (pass/fail + one line why):

### 7) Retry/refusal metadata
- `rollback_refusal_reasons`:
- `order_result.retry_policy_truth`:
- `order_result.retry_attempted_count`:
- `order_result.retry_blocked_reason`:
- `order_result.retry_final_outcome_status`:
- Retry/refusal coherence verdict (pass/fail + one line why):

### 8) Broker truth reconciliation
- Did broker truth eventually match expected state transition? (yes/no/partial):
- Evidence (retcode/retry decision/final order status):
- If mismatch: exact contradiction observed:

### 9) Run outcome
- Outcome label (pass/fail/inconclusive):
- Why (exact criteria):
- Artifact paths used:
  - `mt5_controlled_execution_artifact.json`:
  - `mt5_controlled_execution_history.json`:
  - `mt5_controlled_execution_state.json`:

### 10) If fail or inconclusive
- Suspected file/function from artifact evidence (exact path):
- Escalation recommendation:
  - Repeat Scenario C
  - Escalate to deterministic code/test investigation
  - Collect additional live evidence first
- Why this recommendation is justified by artifact evidence:
