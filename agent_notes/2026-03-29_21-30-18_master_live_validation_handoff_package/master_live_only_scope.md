## Master live-only scope (consolidated)

This is the complete live-only uncertainty surface from current repository + baseline notes.

### 1) Broker send/linkage timing race
- File/function path:
  - `run.py::_run_controlled_mt5_live_execution`
  - `run.py::_verify_accepted_send_position_linkage`
- Why live-only:
  - Real broker acknowledgement/materialization timing is non-deterministic and cannot be fully represented by stubs.
- Artifact proof of success:
  - `order_result.broker_position_verification` shows coherent timeline and eventual coherent state:
    - `initial_confirmation`
    - `delayed_recheck_attempted`
    - `delayed_recheck_confirmation`
    - `final_confirmation`
    - `verification_checked_at`
  - No contradiction with `open_position_state` and `status_panel.entry_exit_decision`.
- Artifact proof of failure:
  - repeated unconfirmed linkage progression with contradictory state/contract, or missing required timeline fields on a complete run.

### 2) Exit close confirmation delay window
- File/function path:
  - `run.py::_run_controlled_mt5_live_execution`
  - `run.py::_verify_exit_close_position_disappearance`
- Why live-only:
  - Position disappearance confirmation timing depends on real broker/server behavior.
- Artifact proof of success:
  - `order_result.broker_exit_verification` timeline fields present and coherent.
  - Confirmed-close branch aligns with `open_position_state.status=flat`, or unresolved branch remains explicitly coherent.
- Artifact proof of failure:
  - confirmed close with persistent open-state contradiction, or unresolved-close branch without auditable timeline fields.

### 3) Retry/refusal outcomes under true latency/tick behavior
- File/function path:
  - retry branch in `run.py::_run_controlled_mt5_live_execution`
  - `run.py::_resolve_broker_retry_price`
- Why live-only:
  - Tick freshness, retcode timing, and terminal latency are external runtime factors.
- Artifact proof of success:
  - Explicit bounded retry/refusal metadata:
    - `order_result.retry_policy_truth`
    - `order_result.retry_attempted_count`
    - `order_result.retry_blocked_reason`
    - `order_result.retry_final_outcome_status`
    - `rollback_refusal_reasons`
  - coherent signal/contract outcomes.
- Artifact proof of failure:
  - retry/refusal happened but reasons are silently missing or contradictory across artifact vs signal vs contract.

### 4) Spread-sensitive near-threshold behavior in real market feed
- File/function path:
  - spread path in `run.py` and spread filter wiring (`run_advanced_modules`)
- Why live-only:
  - Real spread feed near threshold can be noisy and timing-sensitive.
- Artifact proof of success:
  - `signal.blocker_reasons` aligns with observed spread context.
  - co-occurring reasons remain preserved (`signal.reasons` includes open-position context when applicable).
- Artifact proof of failure:
  - spread-related blocking/classification mismatch not explained by co-occurring blockers, or reason suppression in co-occurrence.

### 5) Live macro pause co-occurrence during open-position management
- File/function path:
  - live-mode blocker/reason composition in `run.py`
- Why live-only:
  - Macro pause in live operation is a live-state branch requiring runtime macro feed conditions.
- Artifact proof of success:
  - `signal.blocker_reasons` includes `macro_feed_unsafe_pause` when active,
  - while `signal.reasons` retains open-position management/retry context,
  - and `status_panel.entry_exit_decision` remains coherent.
- Artifact proof of failure:
  - pause blocker appears but active open-position management/retry context is hidden.

### 6) Network interruption / partition during verification calls
- File/function path:
  - verification helpers used by `run.py::_run_controlled_mt5_live_execution`:
    - `_verify_accepted_send_position_linkage`
    - `_verify_exit_close_position_disappearance`
    - `_verify_partial_send_deal_quantity`
- Why live-only:
  - Transport interruptions are external runtime phenomena.
- Artifact proof of success:
  - explicit `fail_closed_reason` fields in relevant verification payloads and coherent downstream action/reason/contract handling.
- Artifact proof of failure:
  - unresolved verification without explicit fail-closed classification and contradictory downstream state.

### 7) Reconciliation mismatch across successive live artifacts
- File/function path:
  - `run.py::_run_controlled_mt5_live_execution` state progression:
    - `open_position_state`
    - `exit_decision`
    - `pnl_snapshot.position_open_truth`
    - persisted history in `mt5_controlled_execution_history.json`
- Why live-only:
  - Asynchronous broker truth reconciliation over time cannot be fully proven by deterministic harness.
- Artifact proof of success:
  - multi-run history shows coherent progression and no unresolved contradictions.
- Artifact proof of failure:
  - persistent open/flat contradiction over sequential artifacts without matching verification explanation.
