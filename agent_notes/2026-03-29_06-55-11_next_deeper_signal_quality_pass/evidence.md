## Evidence map

### Issue 1: Conflict filter over-blocked sparse 2:1 directional splits
- **Exact location**: `src/filters/conflict_filter.py::apply_conflict_filter`
- **Pre-fix behavior**:
  - Block condition was `buy_count > 0 and sell_count > 0 and abs(buy_count - sell_count) <= 1`.
  - This blocked a `2 buy : 1 sell` split (sparse evidence), which can suppress valid entries.
- **Proof test (pre-fix failing)**:
  - `src/tests/test_conflict_filter_precision.py::test_conflict_filter_does_not_block_clear_majority_split`
- **Observed failure evidence**:
  - Expected `blocked=False`, got `blocked=True`.
- **Minimal fix applied**:
  - Keep same filter and architecture.
  - Require contradiction to be both near-even **and** materially strong:
    - `near_even_split = abs(buy_count - sell_count) <= 1`
    - `active_votes = buy_count + sell_count`
    - block only when `buy_count > 0 and sell_count > 0 and near_even_split and active_votes >= 4`
- **Post-fix result**:
  - 2:1 sparse split no longer hard-blocks.
  - 2:2 strong conflict still hard-blocks.

### Issue 2: Need explicit guard coverage for the new conflict precision behavior
- **Exact location**: `src/tests/test_conflict_filter_precision.py`
- **What was added**:
  - `test_conflict_filter_does_not_block_clear_majority_split`
  - `test_conflict_filter_blocks_when_both_sides_strong_and_close`
- **Post-fix result**:
  - New precision tests pass and protect against regression.
