## Task
Continue the deeper signal-quality work and fix the next proven weakness in existing feature/filter/scoring flow using minimal edits.

## What changed
- Added focused filter-precision tests in `src/tests/test_conflict_filter_precision.py`.
- Proved and fixed conflict-filter over-blocking behavior in `src/filters/conflict_filter.py`.
- Kept previously validated gating/scoring fixes intact and reran focused+nearby regressions.

## Why
- A failing test proved that a clear 2:1 directional split was being blocked as a hard contradiction, which can create false abstains/late entries.

## Result
- Conflict filter now hard-blocks only materially strong near-even contradictions.
- Consolidated test set for this pass is green (`23 passed`).
