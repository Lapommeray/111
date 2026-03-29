## Live validation plan (operational)

### Scenario A — Unresolved close with retry/refusal handling
- **Setup**: live mode with an existing open position, execute managed exit path.
- **Capture**: `mt5_controlled_execution_artifact.json`, `mt5_controlled_execution_history.json`, final `signal.reasons` and `status_panel.entry_exit_decision`.
- **Inspect fields**:
  - `rollback_refusal_reasons`
  - `order_result.retry_policy_truth`, `retry_attempted_count`, `retry_blocked_reason`
  - `open_position_state.position_state_outcome`
  - `signal.reasons` (`open_position_exit_management:*`, `open_position_exit_retry:*`, `open_position_exit_retry_policy:*`)
- **Pass**: reasons/contract remain coherent and unresolved/retry causes are explicit.
- **Fail**: silent reason drop or contradiction between signal and execution contract.

### Scenario B — Open-position exit under delayed confirmation
- **Setup**: live close send where broker confirmation may lag.
- **Capture**: artifact `order_result.broker_exit_verification` and history snapshots.
- **Inspect fields**:
  - `initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, `verification_checked_at`
  - `broker_state_outcome`
  - `open_position_state.status`
- **Pass**: timeline fields explain delayed progression and final state is coherent.
- **Fail**: unresolved close without auditable verification timeline.

### Scenario C — Spread-sensitive live behavior near threshold
- **Setup**: live periods with spread around configured boundary.
- **Capture**: final `signal.blocker_reasons`, `signal.reasons`, execution artifact.
- **Inspect fields**:
  - spread blocker presence/absence vs runtime spread outcome
  - confidence blocker co-occurrence
  - open-position retry reason retention under blocked states
- **Pass**: spread/macro/exit reasons coexist coherently without silent drops.
- **Fail**: missing spread or exit-retry reasons when conditions occur.

### Scenario D — Live macro pause behavior during managed setup
- **Setup**: live macro pause active (`pause_trading=true`) while open-position management path is active.
- **Capture**: signal blockers/reasons and entry_exit_decision contract.
- **Inspect fields**:
  - `macro_feed_unsafe_pause` blocker
  - `open_position_exit_management:*` reason propagation
  - `entry_exit_decision.action`
- **Pass**: live-only pause block appears while exit-management reasons remain visible.
- **Fail**: pause blocks but hides ongoing exit management/retry context.

### Scenario E — Broker/network timing anomalies
- **Setup**: observe live sessions with intermittent connectivity/lookup failures.
- **Capture**: verification `fail_closed_reason` fields and rollback reasons over history.
- **Inspect fields**:
  - `broker_position_verification.fail_closed_reason`
  - `broker_exit_verification.fail_closed_reason`
  - `partial_quantity_verification.fail_closed_reason`
- **Pass**: failures are explicitly classified and later reconciled without state contradiction.
- **Fail**: ambiguous unresolved state with insufficient artifact detail.

## Evidence thresholds
- **Deterministic proven**: decision/exit coherence and reason propagation invariants covered by current tests.
- **Awaiting live confirmation**: timing/transport-dependent broker behaviors above.
- **Validated by live artifacts only**: claims about real broker/network robustness.
