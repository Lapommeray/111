## Per-scenario artifact review rules

Apply this protocol immediately after each live run using:
- `mt5_controlled_execution_artifact.json`
- `mt5_controlled_execution_history.json` (for scenario G and cross-run checks)
- completed run record from `live_run_evidence_template.md`

Common mandatory checks for all scenarios:
1. Verify delayed-recheck metadata coherence when verification payload is present:
   - `initial_confirmation`
   - `delayed_recheck_attempted`
   - `delayed_recheck_confirmation`
   - `final_confirmation`
   - `verification_checked_at`
2. Verify final signal coherence:
   - `signal.action`
   - `signal.confidence`
   - `signal.reasons`
   - `signal.blocker_reasons`
   - `signal.classification`
3. Verify entry/exit contract coherence:
   - `status_panel.entry_exit_decision.action`
   - `status_panel.entry_exit_decision.invalidation_reason`
   - `status_panel.entry_exit_decision.open_position_state.*`
4. Verify retry/refusal coherence where applicable:
   - `rollback_refusal_reasons`
   - `order_result.retry_policy_truth`
   - `order_result.retry_attempted_count`
   - `order_result.retry_blocked_reason`
5. Label run outcome as one of: pass, fail, inconclusive.

---

### A) Broker send/linkage timing race
- Broker verification payload fields:
  - `order_result.broker_position_verification.initial_confirmation`
  - `order_result.broker_position_verification.delayed_recheck_attempted`
  - `order_result.broker_position_verification.delayed_recheck_confirmation`
  - `order_result.broker_position_verification.final_confirmation`
  - `order_result.broker_position_verification.verification_checked_at`
  - `order_result.broker_position_verification.broker_state_outcome`
- `signal.reasons` review:
  - Check no contradictory reasons relative to linkage outcome.
  - If unresolved, ensure management context remains explicit.
- `entry_exit_decision` review:
  - `action` aligns with open position status.
  - `invalidation_reason` not empty on no-trade/exit-required states.
- Pass:
  - Verification timeline exists and final state is coherent with position status.
- Fail:
  - Contradiction (e.g., confirmed linkage with flat state and no exit path).
- Inconclusive:
  - Missing or truncated artifact file for this run.
- Escalate to code investigation when:
  - Contradiction repeats in 2+ runs with complete artifacts.

### B) Exit close confirmation delay window
- Broker verification payload fields:
  - `order_result.broker_exit_verification.initial_confirmation`
  - `order_result.broker_exit_verification.delayed_recheck_attempted`
  - `order_result.broker_exit_verification.delayed_recheck_confirmation`
  - `order_result.broker_exit_verification.final_confirmation`
  - `order_result.broker_exit_verification.verification_checked_at`
  - `order_result.broker_exit_verification.broker_state_outcome`
- `signal.reasons` review:
  - Must retain `open_position_exit_management:*` for unresolved/managed transitions.
- `entry_exit_decision` review:
  - For confirmed close: open position becomes flat.
  - For unresolved close: exit-required state remains explicit.
- Pass:
  - Delay window is auditable and state transitions are coherent.
- Fail:
  - Final confirmation indicates close, but contract/open state remains open without coherent reason.
- Inconclusive:
  - Terminal disconnect prevented full artifact write.
- Escalate to code investigation when:
  - Same contradiction appears in 2 complete artifacts.

### C) Retry/refusal under true latency
- Broker/metadata fields:
  - `order_result.retry_policy_truth`
  - `order_result.retry_attempted_count`
  - `order_result.retry_blocked_reason`
  - `order_result.retry_final_outcome_status`
  - `rollback_refusal_reasons`
- `signal.reasons` review:
  - Check `mt5_controlled_execution_refused` and `mt5_controlled_refusal:*` on refusal.
  - Check open-position retry reasons when unresolved exit context exists.
- `entry_exit_decision` review:
  - Action and invalidation reason align with refusal/managed state.
- Pass:
  - Retry path is explicit, bounded, and reason-complete.
- Fail:
  - Retry/refusal occurred but reasons or invalidation context are silently missing.
- Inconclusive:
  - Broker-side ambiguity with missing metadata due to external outage.
- Escalate to code investigation when:
  - Missing reason propagation repeats in 2+ complete artifacts.

### D) Spread-sensitive near-threshold live behavior
- Broker/pipeline fields:
  - `signal.blocker_reasons` (spread-related blocker correctness)
  - `signal.reasons` (co-occurring open-position retry/management reasons)
- `signal.reasons` review:
  - Ensure spread blocker does not suppress exit-management/retry reasons in co-occurrence.
- `entry_exit_decision` review:
  - Action remains coherent with blocker and open-position state.
- Delayed-recheck metadata:
  - Inspect if run includes broker verification branch.
- Pass:
  - Boundary behavior and co-occurring reasons are both preserved.
- Fail:
  - Spread blocker present but open-position retry/management reason dropped despite matching context.
- Inconclusive:
  - Spread snapshot around threshold not captured.
- Escalate to code investigation when:
  - Co-occurrence reason drop reproduced with complete spread context.

### E) Live macro pause during open-position management
- Broker/pipeline fields:
  - `signal.blocker_reasons` for `macro_feed_unsafe_pause`
  - `signal.reasons` for open-position management/retry continuity
- `signal.reasons` review:
  - Both macro pause blocker and open-position context should be visible where applicable.
- `entry_exit_decision` review:
  - Action and invalidation reason should reflect no-trade/managed-exit coherence.
- Delayed-recheck metadata:
  - Review relevant verification branch fields when close/linkage checks are active.
- Pass:
  - Macro pause block and open-position management context coexist coherently.
- Fail:
  - Macro pause block hides active unresolved exit context.
- Inconclusive:
  - Macro pause state at trigger not evidenced.
- Escalate to code investigation when:
  - Hiding behavior repeats with complete artifacts.

### F) Network interruption/partition during verification
- Broker verification payload fields:
  - `broker_position_verification.fail_closed_reason` (if linkage path)
  - `broker_exit_verification.fail_closed_reason` (if exit path)
  - `partial_quantity_verification.fail_closed_reason` (if partial path)
  - delayed-recheck fields when present
- `signal.reasons` review:
  - Infrastructure-induced uncertainty must be explicit and coherent.
- `entry_exit_decision` review:
  - Action and invalidation reason must align with fail-closed state.
- Pass:
  - Fail-closed reason is explicit and downstream contract/signal are coherent.
- Fail:
  - Verification failure without explicit fail-closed reason and contradictory downstream state.
- Inconclusive:
  - Artifact capture interrupted by environment failure.
- Escalate to code investigation when:
  - Fail-closed reasons consistently missing despite complete artifact writes.

### G) Broker-truth reconciliation mismatch over time
- Broker/history fields:
  - `open_position_state.status`
  - `open_position_state.position_state_outcome`
  - `pnl_snapshot.position_open_truth`
  - verification outcomes across successive history entries
- `signal.reasons` review:
  - Management/retry context continuity across successive cycles.
- `entry_exit_decision` review:
  - Action progression follows state transitions across history.
- Delayed-recheck metadata:
  - Verify timeline continuity where branches include rechecks.
- Pass:
  - No unresolved contradiction across 3+ sequential artifacts.
- Fail:
  - Persistent open/flat contradiction over time without matching verification explanation.
- Inconclusive:
  - Insufficient sequential history entries captured.
- Escalate to code investigation when:
  - Contradictory state progression persists across at least 3 complete sequential artifacts.
