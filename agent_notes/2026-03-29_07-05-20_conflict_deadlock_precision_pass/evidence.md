## Evidence map

### Issue 1: Conflict filter still hard-blocked 3:2 directional splits
- **Exact location**: `src/filters/conflict_filter.py::apply_conflict_filter`
- **Pre-fix behavior**:
  - After prior refinement, hard-block condition still allowed non-tie near-even splits (`abs(buy-sell) <= 1`) when directional votes were materially strong.
  - This still blocked `3:2` scenarios, creating unjustified abstain risk and late-entry behavior.
- **Proof test (pre-fix failing)**:
  - `src/tests/test_conflict_filter_precision.py::test_conflict_filter_does_not_hard_block_three_vs_two_split`
- **Observed failure evidence**:
  - Expected `blocked=False`, got `blocked=True`.
- **Minimal fix applied**:
  - Keep existing architecture and filter location.
  - Tightened hard-block to true deadlock only:
    - require `buy_count == sell_count` and `active_votes >= 4` (plus both sides present).
  - This leaves non-tie close splits (e.g., 3:2) to downstream conviction/margin degradation logic.
- **Post-fix result**:
  - `3:2` no longer hard-blocks in filter stage.
  - `2:2` deadlock still hard-blocks.

### Issue 2: Need explicit regression protection for tie-only hard-block intent
- **Exact location**: `src/tests/test_conflict_filter_precision.py`
- **What proved/protects it**:
  - Existing tests now jointly enforce:
    - `2:1` -> not hard-blocked
    - `3:2` -> not hard-blocked
    - `2:2` -> hard-blocked
- **Post-fix result**:
  - Precision behavior is now locked by focused tests.
