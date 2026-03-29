## Task
Execute the first real implementation pass after pipeline inspection: add run_pipeline contract/scenario tests, expose missing behavior, then apply minimal architecture-preserving fixes.

## What was implemented
- Added `src/tests/test_run_pipeline_contract.py` with contract and focused scenario coverage for `run_pipeline()`.
- Added coverage for:
  - output envelope shape and required indicator keys
  - expected final payload structure (`advanced_modules.final_direction` / `advanced_modules.final_confidence`)
  - blocker-reason presence when blocked
  - replay/live scenario behavior for final decision/confidence/blocker reasons
- Applied minimal fix in `run.py` at signal assembly only:
  - when `combined_blocked` is true and no reasons exist, inject fallback blocker reason `blocked_without_explicit_reason`
  - use `effective_signal_confidence` when calling `build_signal_output()` so `setup_classification` aligns with public signal confidence

## Why this fix was required
New tests failed before the fix and showed two concrete gaps:
1. blocked signals could have empty `blocker_reasons`
2. setup classification was computed using pre-macro confidence while the emitted public confidence was post-macro adjusted

## Final result
- Contract/scenario test set now passes.
- Behavior is aligned with test expectations using minimal edits and no architecture rewrite.
