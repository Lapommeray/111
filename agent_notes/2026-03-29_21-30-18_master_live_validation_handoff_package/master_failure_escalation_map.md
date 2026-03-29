## Master failure escalation map (consolidated)

### How to use this map
1. Confirm artifact completeness first:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`
   - completed scenario worksheet.
2. Identify failure signature from artifact fields.
3. Route to the mapped file/function first-pass zone.
4. Apply deterministic reproduction decision rule.
5. Apply code-change threshold (fix now vs collect more live evidence).

---

## Failure class 1 — Missing delayed-recheck metadata in verification branch
- Failure proof fields:
  - missing/blank one or more:
    - `initial_confirmation`
    - `delayed_recheck_attempted`
    - `delayed_recheck_confirmation`
    - `final_confirmation`
    - `verification_checked_at`
- First inspection zone:
  - `run.py::_run_controlled_mt5_live_execution` verification payload assembly:
    - `broker_position_verification`
    - `broker_exit_verification`
    - `partial_quantity_verification`.
- Type:
  - Observability issue.
- Deterministic reproduction after live failure:
  - Yes.
- Evidence threshold before code change:
  - One complete artifact-backed occurrence is sufficient.

## Failure class 2 — Retry/refusal happened but not reflected in `signal.reasons`
- Failure proof fields:
  - `rollback_refusal_reasons` or `order_result.retry_*` present,
  - corresponding reason markers missing in `signal.reasons`.
- First inspection zone:
  - `run.py::_run_controlled_mt5_live_execution` retry/refusal metadata.
  - `run.py` final reason assembly (`open_position_exit_retry:*`, `open_position_exit_retry_policy:*`, `mt5_controlled_refusal:*`).
- Type:
  - Reason-propagation issue.
- Deterministic reproduction after live failure:
  - Yes.
- Evidence threshold before code change:
  - Two repeated complete-artifact occurrences, or one high-confidence deterministic mismatch.

## Failure class 3 — `entry_exit_decision` contradicts execution artifact outcome
- Failure proof fields:
  - mismatch between:
    - `status_panel.entry_exit_decision.action` / `invalidation_reason`,
    - `open_position_state.*`,
    - verification outcome.
- First inspection zone:
  - `run.py::_build_entry_exit_decision_contract`.
- Type:
  - Execution-contract issue.
- Deterministic reproduction after live failure:
  - Yes.
- Evidence threshold before code change:
  - One complete high-severity contradiction.

## Failure class 4 — Network/verification fail-closed ambiguity
- Failure proof fields:
  - unresolved verification outcome with missing or ambiguous `fail_closed_reason`.
- First inspection zone:
  - verification helpers and fail-closed mapping in `run.py` paths:
    - `_verify_accepted_send_position_linkage`
    - `_verify_exit_close_position_disappearance`
    - `_verify_partial_send_deal_quantity`.
- Type:
  - Observability issue OR broker/network uncertainty only (depends on artifact completeness).
- Deterministic reproduction after live failure:
  - Attempt only if emulatable in test stubs.
- Evidence threshold before code change:
  - If complete artifacts prove missing classification -> fix justified.
  - If artifacts only show external outage with coherent fail-closed behavior -> collect more live evidence first.

## Failure class 5 — Reconciliation mismatch over time
- Failure proof fields:
  - contradictions across history in:
    - `open_position_state.position_state_outcome`
    - `pnl_snapshot.position_open_truth`
    - verification confirmation/outcome progression.
- First inspection zone:
  - state progression in `run.py::_run_controlled_mt5_live_execution`.
- Type:
  - Reconciliation/state-tracking issue.
- Deterministic reproduction after live failure:
  - Yes, if timeline can be replayed in multi-step tests.
- Evidence threshold before code change:
  - two consecutive contradictory snapshots in one scenario class,
  - or same contradiction in two separate runs.

## Failure class 6 — Macro pause hides open-position management context
- Failure proof fields:
  - `signal.blocker_reasons` includes macro pause,
  - while `signal.reasons` loses active open-position management/retry context.
- First inspection zone:
  - final blocker/reason composition in `run.py`.
- Type:
  - Reason-propagation issue.
- Deterministic reproduction after live failure:
  - Yes.
- Evidence threshold before code change:
  - One complete artifact-backed contradiction.

## Failure class 7 — Spread boundary incoherence in live
- Failure proof fields:
  - spread context near threshold plus blocker/classification mismatch unexplained by co-occurring states.
- First inspection zone:
  - spread/filter decision path in `run.py` + spread module wiring.
- Type:
  - Broker feed uncertainty OR execution-contract issue (if repeatable).
- Deterministic reproduction after live failure:
  - yes for deterministic threshold logic; no for noisy feed artifacts.
- Evidence threshold before code change:
  - repeated mismatch under comparable spread context.

---

## Escalation decision ladder (single rule set)
1. If artifact bundle is incomplete -> classify run as inconclusive; repeat run first.
2. If artifact bundle is complete and failure signature maps to an internal contradiction -> escalate to deterministic reproduction.
3. If failure is clearly external (network/broker outage) with coherent internal state -> collect additional live evidence before code edits.
4. Only implement production change after mapped evidence threshold for that failure class is met.
