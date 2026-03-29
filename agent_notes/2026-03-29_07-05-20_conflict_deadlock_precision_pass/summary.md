## Task
Continue deeper signal-quality refinement and fix the next proven precision weakness without architecture changes.

## What changed
- Added a new focused test in `src/tests/test_conflict_filter_precision.py` for a `3:2` directional split.
- Proved and fixed conflict-filter behavior in `src/filters/conflict_filter.py` so hard conflict blocks are reserved for true tie deadlocks.
- Re-ran focused and nearby regression suites.

## Why
- Failing test showed `3:2` split was still hard-blocked, causing avoidable abstains and potentially late valid entries.

## Result
- Conflict filter now blocks only tie deadlocks with sufficient evidence.
- Consolidated test suite for this pass is green (`28 passed`).
