## Evidence

### Phase 1 — unresolved-exit retry + macro penalty + spread co-occurrence
- **Exact file/function path inspected**:
  - `run.py::run_pipeline` reason assembly and blockers (`macro_confidence_penalty`, spread blocker merge, `combined_blocked`, open-position reason propagation)
  - `run.py::_build_entry_exit_decision_contract`
- **Exact failing proof before fix**:
  - New tests initially failed because open-position exit/retry reasons were omitted when `combined_blocked=True`.
  - Failing command output showed missing reasons in blocked co-occurrence path and demonstrated assertion mismatch from existing behavior.
- **Exact minimal fix applied**:
  - In `run.py`, broadened open-position reason propagation guard from:
    - `decision == "WAIT" and not combined_blocked and open_status in {open, partial_exposure_unresolved}`
    - to
    - `decision == "WAIT" and open_status in {open, partial_exposure_unresolved}`
  - No architecture changes; only condition widening in existing decision assembly.
- **Exact tests proving fixed behavior**:
  - `test_unresolved_exit_retry_with_macro_penalty_and_spread_above_threshold_preserves_cooccurring_reasons`
  - `test_unresolved_exit_retry_with_macro_penalty_and_spread_at_threshold_preserves_retry_reasons`
  - `test_unresolved_exit_retry_with_macro_penalty_and_spread_below_threshold_preserves_retry_reasons`
- **Exact result after fix**:
  - Co-occurrence scenarios now preserve exit-management + retry reasons while keeping coherent action/confidence/classification and entry_exit_decision contract.

### Phase 2 — replay vs live parity pinning
- **Exact file/function path inspected**:
  - `run.py::run_pipeline` mode branch (`replay` vs `live`), live macro pause gate, final reason assembly.
  - Existing replay/live macro contract coverage in `src/tests/test_run_pipeline_contract.py`.
- **Coverage/tests added**:
  - `test_replay_live_parity_preserves_unresolved_exit_retry_reasons_when_no_live_only_blockers`
    - proves expected parity (replay and live both preserve unresolved exit reasons when no live-only blocker applies).
  - `test_replay_live_parity_live_pause_blocks_but_keeps_unresolved_exit_reason_propagation`
    - proves expected intentional difference (live adds `macro_feed_unsafe_pause` blocker; replay does not), while both still preserve unresolved-exit reasons.
- **Result classification**:
  - Phase 2 is coverage hardening/parity pinning; no additional production defect found beyond Phase 1 fix.

### Regression evidence
- `python3 -m pytest -q ...` targeted phase tests: `5 passed`.
- Nearby regression bundle across decision/contract/filter/execution/memory/macro/quarantine suites: `148 passed`.
