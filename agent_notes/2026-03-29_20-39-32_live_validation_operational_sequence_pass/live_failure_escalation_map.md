## Live failure escalation map (artifact-driven)

### Failure type 1: Missing/invalid delayed-recheck timeline
- **Likely investigation zone**:
  - `run.py::_run_controlled_mt5_live_execution` (verification payload assembly for `broker_position_verification`, `broker_exit_verification`, `partial_quantity_verification`).
- **Artifact field proof**:
  - Missing or blank `initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, or `verification_checked_at` despite a verification branch run.
- **Classification**:
  - Observability issue.
- **Deterministic reproduction after live failure**:
  - Yes. Add/adjust focused execution-gate tests to reproduce missing fields in that branch.
- **Code-fix bar**:
  - One artifact-backed failure with missing required timeline fields is sufficient to justify a minimal production fix.

### Failure type 2: Retry/refusal occurred but reason not reflected in final signal
- **Likely investigation zone**:
  - `run.py::_run_controlled_mt5_live_execution` (retry/refusal metadata),
  - `run.py` reason propagation near final signal assembly (`open_position_exit_retry:*`, `open_position_exit_retry_policy:*`, `mt5_controlled_refusal:*`).
- **Artifact field proof**:
  - `rollback_refusal_reasons` or retry metadata present in `order_result`, but absent from `signal.reasons` in same run.
- **Classification**:
  - Reason-propagation issue.
- **Deterministic reproduction after live failure**:
  - Yes. Add a focused decision-quality test with an equivalent artifact-shape scenario.
- **Code-fix bar**:
  - Two artifact-backed occurrences in equivalent conditions, or one occurrence with fully coherent artifacts proving deterministic logic gap.

### Failure type 3: entry_exit_decision contradicts execution artifact outcome
- **Likely investigation zone**:
  - `run.py::_build_entry_exit_decision_contract`.
- **Artifact field proof**:
  - Example: `open_position_state.status=open` and unresolved exit outcome, but `entry_exit_decision.action=NO_TRADE` with no invalidation reason.
- **Classification**:
  - Execution-contract issue.
- **Deterministic reproduction after live failure**:
  - Yes. Build a focused contract test from captured artifact shape.
- **Code-fix bar**:
  - One high-confidence contradiction with complete artifact bundle.

### Failure type 4: Verification fail-closed reason absent/ambiguous during network interruption
- **Likely investigation zone**:
  - `run.py` verification helpers and fail-closed classifications used by `_verify_accepted_send_position_linkage`, `_verify_exit_close_position_disappearance`, `_verify_partial_send_deal_quantity`.
- **Artifact field proof**:
  - Verification outcome unresolved while `fail_closed_reason` missing/empty in a known interrupted run.
- **Classification**:
  - Observability issue or broker/network uncertainty only (depends on artifact completeness).
- **Deterministic reproduction after live failure**:
  - Attempt only if interruption can be deterministically emulated in test stubs.
- **Code-fix bar**:
  - If artifacts are incomplete: minimal observability fix justified.
  - If artifacts are complete and only external outage present: no code fix; gather more live runs.

### Failure type 5: Persistent broker-truth reconciliation mismatch across history
- **Likely investigation zone**:
  - `run.py::_run_controlled_mt5_live_execution` state progression (`open_position_state`, `pnl_snapshot.position_open_truth`, verification outcomes).
- **Artifact field proof**:
  - Successive `mt5_controlled_execution_history.json` records show unresolved contradiction (e.g., repeated confirmed close while open state remains unresolved) without matching transition reason.
- **Classification**:
  - Reconciliation/state-tracking issue.
- **Deterministic reproduction after live failure**:
  - Yes, if artifact timeline can be modeled in multi-step tests.
- **Code-fix bar**:
  - Two consecutive contradictory history snapshots in one scenario class, or same contradiction repeated in two separate runs.

### Failure type 6: Live macro pause suppression hides open-position management reasons
- **Likely investigation zone**:
  - `run.py` final blocker/reason composition in live mode.
- **Artifact field proof**:
  - `signal.blocker_reasons` contains macro pause but `signal.reasons` lacks active `open_position_exit_management:*`/retry context for unresolved open status.
- **Classification**:
  - Reason-propagation issue.
- **Deterministic reproduction after live failure**:
  - Yes. Replay-vs-live parity tests plus live-only blocker composition tests.
- **Code-fix bar**:
  - One artifact-backed contradiction with complete state fields.

### Failure type 7: Spread boundary behavior inconsistent with configured threshold in live run
- **Likely investigation zone**:
  - spread feature/filter path in `run.py` and spread-filter module wiring (`run_advanced_modules` path already proven deterministically).
- **Artifact field proof**:
  - Runtime spread context near threshold plus mismatched blocker/classification behavior not explained by co-occurring blockers.
- **Classification**:
  - Broker/network uncertainty only (if spread feed noisy) or execution-contract issue (if repeatable mismatch).
- **Deterministic reproduction after live failure**:
  - Yes for deterministic threshold logic; no for raw feed noise.
- **Code-fix bar**:
  - Require repeated artifact-backed mismatch under comparable spread context before production fix.

### Escalation decision ladder
1. Confirm artifact completeness (`artifact`, `history`, `state` JSONs + filled evidence template).
2. If incomplete artifact fields -> observability escalation first (minimal fix only).
3. If complete artifacts show internal contradiction -> deterministic reproduction attempt + focused test-first pass.
4. If complete artifacts show external outage/latency only with no internal contradiction -> classify as live uncertainty; gather additional live evidence before code changes.
