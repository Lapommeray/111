## Scenario F Review Worksheet (copy-paste ready)

### 1) Run identity
- Scenario name: F — Network interruption/partition effects during verification
- Run datetime (UTC):
- Environment (terminal, account type, mode=live):
- Symbol:
- Timeframe:

### 2) Market context at trigger
- Bid/ask or spread snapshot:
- Spread threshold config:
- Macro pause state:
- Open position pre-state (`open_position_state.status`, `position_id`, `side`):
- Network incident context (if known):

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
- `broker_position_verification.fail_closed_reason` (if present):
- `broker_exit_verification.fail_closed_reason` (if present):
- `partial_quantity_verification.fail_closed_reason` (if present):

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
- Retry/refusal coherence verdict (pass/fail + one line why):

### 8) Broker truth reconciliation
- Did broker truth eventually match expected state transition? (yes/no/partial):
- Evidence:
- If mismatch: exact contradiction observed:

### 9) Pass/fail decision
- Scenario pass/fail/inconclusive:
- Why (exact criteria):
- Artifact paths used:
  - `mt5_controlled_execution_artifact.json`:
  - `mt5_controlled_execution_history.json`:
  - `mt5_controlled_execution_state.json`:

### 10) If failed — likely code re-entry point
- Suspected file/function from artifact evidence (exact path):
- Why this location is implicated:
