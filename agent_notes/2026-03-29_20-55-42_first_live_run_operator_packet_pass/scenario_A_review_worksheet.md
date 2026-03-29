## Scenario A Review Worksheet (fill immediately after run)

### Scenario identity
- Scenario: A — broker send/linkage timing race
- Run datetime (UTC):
- Environment (terminal/account/mode):
- Symbol:
- Timeframe:

### Market context
- Bid/ask snapshot:
- Spread context:
- Macro pause state:
- Open position pre-state (`status`, `position_id`, `side`):

### Signal transition
- Initial `signal.action`:
- Final `signal.action`:
- Final `signal.confidence`:
- Final `signal.reasons`:
- Final `signal.blocker_reasons`:
- Final `signal.classification`:

### Entry/exit decision contract
- `status_panel.entry_exit_decision.action`:
- `status_panel.entry_exit_decision.reason`:
- `status_panel.entry_exit_decision.invalidation_reason`:
- `status_panel.entry_exit_decision.open_position.status`:
- Contract coherence verdict (pass/fail + one line):

### Broker verification payload
- `order_result.status`:
- `order_result.broker_state_confirmation`:
- `order_result.broker_state_outcome`:
- `order_result.broker_position_verification`:
  - `initial_confirmation`:
  - `delayed_recheck_attempted`:
  - `delayed_recheck_confirmation`:
  - `final_confirmation`:
  - `verification_checked_at`:

### Retry/refusal metadata
- `rollback_refusal_reasons`:
- `order_result.retry_policy_truth`:
- `order_result.retry_attempted_count`:
- `order_result.retry_blocked_reason`:
- Retry/refusal coherence verdict:

### Reconciliation and decision
- Broker truth eventually matched expected state? (yes/no/partial):
- Evidence:
- Pass / Fail / Inconclusive:
- Why (exact artifact-based reason):

### Escalation (only if fail/inconclusive)
- Suspected file/function:
- Escalation trigger observed:
- Additional live rerun required before escalation? (yes/no):

### Artifact paths used
- `mt5_controlled_execution_artifact.json`:
- `mt5_controlled_execution_history.json`:
- `mt5_controlled_execution_state.json`:
