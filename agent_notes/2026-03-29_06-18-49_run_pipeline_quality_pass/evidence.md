## Evidence map

### Issue 1: Low effective confidence could still enter BUY/SELL
- **Where it lived**: `run.py` final decision path used `advanced_state.final_confidence` for conviction and baseline blocker path before the final action decision; no explicit fail-close on low `effective_signal_confidence`.
- **Proof test (pre-fix failure)**: `src/tests/test_run_pipeline_decision_quality.py::test_low_effective_confidence_blocks_entry_with_explicit_reason`
- **Pre-fix observed result**: action was `BUY` when effective confidence was `0.23` (0.88 - 0.65), failing expected WAIT.
- **Minimal fix applied**: in `run.py`, added guard in existing final decision assembly:
  - if decision is `BUY`/`SELL` and `effective_signal_confidence < blocker.min_confidence`, set `combined_blocked = True` and append `confidence_below_threshold`.
- **Post-fix result**: same test passes; output is `WAIT` + blocked + blocker reason includes `confidence_below_threshold`.

### Issue 2: Existing contract test scenario no longer matched intentionally tightened behavior
- **Where it lived**: `src/tests/test_run_pipeline_contract.py::test_run_pipeline_replay_macro_penalty_updates_public_confidence_and_classification`
- **Proof**: regression run failed after fix because old expectation still asserted `BUY`.
- **Minimal fix applied**: updated assertions to expected guarded behavior:
  - action `WAIT`
  - blocked `True`
  - `confidence_below_threshold` present
  - setup classification `blocked`
- **Post-fix result**: contract test passes and matches current safety logic.

### Scenario quality coverage added this pass
- **Strong setup**: entry allowed with consistent direction/confidence.
- **Weak setup (low effective confidence)**: entry blocked with explicit confidence reason.
- **Manipulated setup (conflict votes)**: abstain (`WAIT`) with explicit directional conflict reason and no false blocker.
- **Invalidated setup**: open position + WAIT surfaces `EXIT` in `entry_exit_decision`.
