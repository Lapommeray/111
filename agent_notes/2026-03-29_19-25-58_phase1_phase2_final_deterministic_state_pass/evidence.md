## Evidence

### Phase 1 — co-occurrence integration (unresolved exit + macro + spread)
- **Files/functions traced**:
  - `run.py::run_pipeline` around macro penalty application, `combined_blocked` merge, `reasons` assembly, and open-position exit/retry propagation.
  - `run.py::_build_entry_exit_decision_contract` for EXIT contract coherence.
- **Scenario proven by new stricter test**:
  - `test_unresolved_exit_retry_with_macro_penalty_and_spread_above_keeps_full_retry_reason_set`
  - Verifies co-occurrence keeps:
    - spread blocker + confidence blocker,
    - open-position management reason,
    - both retry/refusal reasons (`exit_close_order_send_refused` and `retry_not_attempted_fail_closed_guard_blocked`),
    - retry policy reason,
    - coherent `entry_exit_decision` EXIT contract/invalidation reason.
- **Result classification**:
  - Phase 1 remains tied to a previously proven production defect (reason loss under blocked co-occurrence) that is fixed in current code; this pass adds stricter coverage to keep it locked.

### Phase 2 — replay vs live parity pinning
- **Files/functions traced**:
  - `run.py::run_pipeline` replay path vs live path (`MT5Adapter`), live-only macro pause guard, shared reason assembly.
  - `src/tests/test_run_pipeline_contract.py::test_run_pipeline_live_macro_pause_blocks_with_reason` as baseline live-only guard proof.
- **Scenario proven by new stricter test**:
  - `test_replay_live_parity_with_macro_penalty_and_spread_above_matches_blockers_and_retry_reasons`
  - Same base co-occurrence scenario in replay/live with no live-only pause blocker; verifies both modes match on blockers and unresolved-exit reason propagation.
- **Result classification**:
  - Coverage gap hardened; no new production defect proven in this phase.

### Final deterministic state evidence
- Focused phase suite command passed: `7 passed`.
- Nearby regression bundle command passed: `150 passed`.
- Therefore, requested deterministic checks are complete for this stage.
