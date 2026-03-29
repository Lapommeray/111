## Task
Continue deeper decision/exit-quality refinement and fix the next proven abstain-confidence inconsistency within existing architecture.

## What changed
- Added a focused test in `src/tests/test_run_pipeline_decision_quality.py`:
  - `test_execution_refusal_degrades_wait_confidence_and_reasons`
- Proved and fixed execution-refusal abstain confidence mismatch in `run.py`.
- Preserved all prior validated fixes and re-ran focused + nearby regressions.

## Why
- Failing evidence showed execution refusal could downgrade action to `WAIT` but leave confidence high (`0.88`), which is internally inconsistent for abstain semantics.

## Result
- Execution-refusal abstain path now rebases confidence to non-trade range.
- Consolidated suite for this pass is green (`30 passed`).
