## Master live-validation completion criteria

### 1) Required successful artifact-backed runs per scenario class
- Scenario A (broker send/linkage timing race): >= 3 successful runs across separate sessions.
- Scenario B (exit close confirmation delay window): >= 3 successful runs, including >= 1 delayed-recheck-attempted case.
- Scenario C (retry/refusal under true latency): >= 3 successful runs, including:
  - >= 1 run with `retry_attempted_count=1`
  - >= 1 run with fail-closed blocked retry.
- Scenario D (spread-sensitive near threshold): >= 3 successful runs including:
  - >= 1 below-threshold observation
  - >= 1 above-threshold observation.
- Scenario E (live macro pause during open-position management): >= 2 successful runs with pause active and open-position context visible.
- Scenario F (network interruption/partition effects): >= 2 successful runs with explicit `fail_closed_reason` classification and coherent downstream contract.
- Scenario G (reconciliation mismatch over time): >= 3 successful multi-snapshot reviews over history progression.

### 2) What counts as stable for a scenario class
- Every run in the scenario class has:
  - complete artifact bundle (`artifact`, `history`, `state` JSONs),
  - completed scenario worksheet,
  - explicit pass/fail/inconclusive verdict with field-level evidence.
- No unresolved contradiction remains between:
  - verification payload outcomes,
  - `signal.action` / `signal.confidence` / `signal.reasons` / `signal.blocker_reasons` / `signal.classification`,
  - `status_panel.entry_exit_decision` (`action`, `reason`, `invalidation_reason`, `open_position_state.*`),
  - and state progression (`open_position_state`, `pnl_snapshot.position_open_truth`, history).
- No repeated failure signature remains unresolved.

### 3) What forces return to deterministic code/test work
Return to deterministic code/test investigation if any of the following occurs:
1. Same failure signature appears in >= 2 complete artifacts for the same scenario class.
2. One high-severity contradiction appears in a complete artifact set, such as:
   - confirmed broker close with persistent `open_position_state.status=open` and no coherent transition reason.
3. Required timeline fields are repeatedly missing in branch-relevant runs:
   - `initial_confirmation`
   - `delayed_recheck_attempted`
   - `delayed_recheck_confirmation`
   - `final_confirmation`
   - `verification_checked_at`.

### 4) What remains open even after initial live validation
- Broker/network non-determinism remains an ongoing operational risk surface.
- Rare timing/race edges remain open until either observed and handled or ruled low-risk by longitudinal evidence volume.
- No claim of "99%" is justified from initial live-validation stage alone without broader live evidence and project-level evaluation artifacts.

### 5) Stage close declaration rule
The live-validation stage for this project scope can be called "sufficiently completed for current scope" only when:
1. Minimum successful run counts are met for scenarios A-G,
2. No unresolved repeated failure signature remains,
3. All runs are artifact-backed with coherent cross-layer outcomes,
4. Any residual risks are explicitly documented as live-only operational uncertainties (not hidden as deterministic gaps).
