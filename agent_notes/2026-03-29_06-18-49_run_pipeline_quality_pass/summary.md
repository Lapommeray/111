## Task
Perform the next real implementation pass for entry/exit decision quality inside existing architecture, with evidence-backed tests and minimal fixes.

## What I changed
- Added `src/tests/test_run_pipeline_decision_quality.py` with focused scenarios:
  - strong setup entry
  - low effective-confidence setup
  - manipulated/conflicting vote setup
  - invalidated setup with open-position exit contract
- Tightened final decision logic in `run.py`:
  - if decision is BUY/SELL and `effective_signal_confidence < blocker.min_confidence`, force blocked WAIT with reason `confidence_below_threshold`.
- Updated `src/tests/test_run_pipeline_contract.py` expectation to match intentionally tightened behavior in macro-penalty scenario.

## Why
- Failing test evidence showed low effective confidence could still produce BUY entries (false-entry risk).
- Minimal fix was applied in final decision assembly (existing path) to fail-close low-confidence trade entries.

## Final result
- Decision-quality and regression suite used for this pass now passes: `15 passed`.
- No architecture rewrite, no parallel path, no unrelated refactor.
