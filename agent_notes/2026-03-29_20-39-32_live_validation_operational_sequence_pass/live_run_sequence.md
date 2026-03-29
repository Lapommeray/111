## Live run order of operations (exact sequence)

This sequence is based on current readiness state from:
- `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_execution_readiness.md`
- `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_checklist.md`
- `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_evidence_template.md`

### Sequence step 1 — Scenario A: broker send/linkage timing race
- Why first:
  - It validates accepted-send linkage timeline fields before layering exit/macro/network complexity.
- Prerequisite artifact confidence:
  - Verification timeline fields must exist in `order_result.broker_position_verification`.
  - Contract and reason propagation must already be deterministic-proven.
- Monitor during run:
  - Accepted send outcome and linkage confirmation transition behavior.
- Artifact bundle to collect immediately after run:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
  - Filled `live_run_evidence_template.md` record.
- Must review before moving on:
  - `initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, `verification_checked_at`
  - coherence between `signal.reasons`, `entry_exit_decision`, `open_position_state`.

### Sequence step 2 — Scenario B: exit close confirmation delay window
- Why second:
  - Depends on confidence that entry linkage timelines are interpretable (step 1).
  - Exercises delayed close confirmation path using same timeline primitives.
- Prerequisite artifact confidence:
  - Scenario A produced at least one coherent linkage run record.
- Monitor during run:
  - Exit send, disappearance confirmation delay, and state transition to `flat` or unresolved.
- Artifact bundle:
  - Same 3 artifact files + filled evidence template.
- Must review before moving on:
  - `order_result.broker_exit_verification.*` timeline fields
  - `open_position_state.status` vs `entry_exit_decision.action`/`invalidation_reason`
  - `signal.reasons` includes `open_position_exit_management:*`.

### Sequence step 3 — Scenario C: retry/refusal under true latency
- Why third:
  - Requires confidence that accepted-send and exit-delay timelines are already readable.
  - Adds retry/refusal branch complexity and bounded retry semantics.
- Prerequisite artifact confidence:
  - A and B each have artifact-backed coherent outcomes.
- Monitor during run:
  - Non-accepted first send, retry policy branch, refusal/blocked reason classification.
- Artifact bundle:
  - Same 3 artifact files + filled evidence template.
- Must review before moving on:
  - `retry_policy_truth`, `retry_attempted_count`, `retry_blocked_reason`, `retry_final_outcome_status`
  - `rollback_refusal_reasons`
  - signal/action/confidence contract coherence on refusal paths.

### Sequence step 4 — Scenario D: spread-sensitive near-threshold live behavior
- Why fourth:
  - Builds on established send/exit/retry observability and checks boundary behavior under live spread variability.
- Prerequisite artifact confidence:
  - C confirms refusal/retry metadata is auditable under true latency.
- Monitor during run:
  - Spread around threshold and co-occurring reason propagation.
- Artifact bundle:
  - Same 3 artifact files + filled evidence template (include spread context snapshot).
- Must review before moving on:
  - `signal.blocker_reasons`, `signal.reasons`, `signal.classification`
  - entry/exit contract coherence under spread boundary outcomes.

### Sequence step 5 — Scenario E: live macro pause during open-position management
- Why fifth:
  - Adds live-only macro pause interaction once base timing and spread behavior are established.
- Prerequisite artifact confidence:
  - D confirms boundary blocker behavior does not hide critical reasons.
- Monitor during run:
  - `macro_feed_unsafe_pause` alongside open-position management/retry reasons.
- Artifact bundle:
  - Same 3 artifact files + filled evidence template (include macro state context).
- Must review before moving on:
  - co-presence of macro blocker and open-position exit/retry reasons
  - no reason suppression in `signal.reasons` and coherent `entry_exit_decision`.

### Sequence step 6 — Scenario F: network interruption/partition effects during verification
- Why sixth:
  - Intentionally stress conditions should follow validation of normal-path semantics.
- Prerequisite artifact confidence:
  - A–E have coherent baseline outcomes and interpretable evidence records.
- Monitor during run:
  - verification fail-closed reasons and downstream contract behavior.
- Artifact bundle:
  - Same 3 artifact files + filled evidence template (include network incident notes).
- Must review before moving on:
  - `*.fail_closed_reason` in verification payloads
  - consistency of WAIT/management contract and reason completeness.

### Sequence step 7 — Scenario G: broker-truth reconciliation mismatch over time
- Why last:
  - It is longitudinal and depends on multi-run history interpretation from prior scenarios.
- Prerequisite artifact confidence:
  - History records from prior scenarios are populated and reliable.
- Monitor during run:
  - state transitions across successive artifacts and reconciliation consistency.
- Artifact bundle:
  - Same 3 artifact files + per-run template records across the observed window.
- Must review before completion:
  - `mt5_controlled_execution_history.json` progression
  - `open_position_state.position_state_outcome`
  - `pnl_snapshot.position_open_truth`
  - verification payload confirmations/outcomes vs final contract state.
