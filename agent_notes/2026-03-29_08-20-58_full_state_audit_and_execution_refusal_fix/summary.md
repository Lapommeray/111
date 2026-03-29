## Task
Perform exact repository-state audit from files/tests, rank remaining gaps, then execute the highest-value next task with failing-test-first evidence and minimal edits.

## What I did
- Inspected and mapped the required files and wiring path (`run.py`, `src/pipeline.py`, filter/scoring modules, contract/decision tests, execution gate tests).
- Produced:
  - `current_state_inventory.md`
  - `coverage_map.md`
  - `remaining_gaps_ranked.md`
- Ranked top gap as confidence consistency for non-blocked `WAIT` transitions not explicitly rebased yet.
- Added failing focused test:
  - `src/tests/test_run_pipeline_decision_quality.py::test_unblocked_wait_direction_rebases_confidence_to_abstain_band`
- Applied minimal fix in `run.py`:
  - when `decision == "WAIT"` and not hard-blocked, cap confidence to `<= 0.59` and add reason `abstain_confidence_rebased`.
- Re-ran focused and nearby regressions.

## Final result
- Exact repository state audit delivered with file-backed evidence.
- New proven defect fixed: non-blocked `WAIT` no longer keeps trade-ready confidence.
- Consolidated targeted + nearby regression verification: `31 passed`.
