## Master live run sequence (A -> G)

All scenarios use the same mandatory artifact bundle:
- `mt5_controlled_execution_artifact.json`
- `mt5_controlled_execution_history.json`
- `mt5_controlled_execution_state.json`
- Completed scenario worksheet (`scenario_X_review_worksheet.md`)

### Step 1 — Scenario A: Broker send/linkage timing race
- Why first:
  - Validates accepted-send linkage timeline (`broker_position_verification`) before adding exit/macro/network complexity.
- Must be true to proceed:
  - Complete artifact bundle captured.
  - Timeline fields present and coherent:
    - `initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, `verification_checked_at`.
  - `signal.*`, `entry_exit_decision.*`, and `open_position_state.*` are non-contradictory.

### Step 2 — Scenario B: Exit close confirmation delay window
- Why second:
  - Reuses same delayed-recheck mechanics in exit-close branch (`broker_exit_verification`) after Scenario A establishes baseline timeline trust.
- Must be true to proceed:
  - Scenario A conclusive pass exists for current live session window.
  - B artifact bundle complete.
  - Confirmed-close vs unresolved-close branches are represented coherently in verification, reasons, and contract.

### Step 3 — Scenario C: Retry/refusal under true latency
- Why third:
  - Builds on A/B verification timelines; introduces retry policy and refusal metadata coherence under live latency.
- Must be true to proceed:
  - A and B both conclusive.
  - Retry/refusal metadata captured when branch is hit:
    - `retry_policy_truth`, `retry_attempted_count`, `retry_blocked_reason`, `retry_final_outcome_status`, `rollback_refusal_reasons`.
  - No silent reason drop in `signal.reasons`.

### Step 4 — Scenario D: Spread-sensitive near-threshold behavior
- Why fourth:
  - Evaluates blocker behavior once execution-branch observability (A-C) is proven in live context.
- Must be true to proceed:
  - C has at least one conclusive run.
  - Spread context around threshold recorded.
  - Co-occurring spread + open-position reason set remains coherent.

### Step 5 — Scenario E: Live macro pause during open-position management
- Why fifth:
  - Adds live-only macro pause interaction after spread and retry behavior are validated.
- Must be true to proceed:
  - D conclusive.
  - Macro state at trigger recorded.
  - `macro_feed_unsafe_pause` does not suppress open-position management/retry reasons.

### Step 6 — Scenario F: Network interruption/partition verification effects
- Why sixth:
  - Stress/incident behavior should follow normal-path validation to reduce ambiguity in failure interpretation.
- Must be true to proceed:
  - A-E baseline evidence captured and coherent.
  - Fail-closed reason fields captured when interruption branch is hit:
    - `broker_position_verification.fail_closed_reason`
    - `broker_exit_verification.fail_closed_reason`
    - `partial_quantity_verification.fail_closed_reason`.

### Step 7 — Scenario G: Broker-truth reconciliation mismatch over time
- Why last:
  - Longitudinal scenario requiring history from prior runs.
- Must be true to stage-close:
  - History progression available across multiple runs.
  - No unresolved contradiction in:
    - `open_position_state.status`
    - `open_position_state.position_state_outcome`
    - `pnl_snapshot.position_open_truth`
    - verification outcomes and contract action progression.
