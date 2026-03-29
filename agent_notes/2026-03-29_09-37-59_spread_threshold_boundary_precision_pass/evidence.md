## Gap evaluated in this pass

### Ranked task: spread-filter threshold boundary precision (`==` vs `>`)
- **Location traced**:
  - spread computation: `src/features/spread_state.py::compute_spread_state`
  - threshold gate: `src/filters/spread_filter.py::apply_spread_filter`
  - integration wiring: `src/pipeline.py::run_advanced_modules` (`spread_filter`)
  - final assembly: `run.py::run_pipeline` (`advanced_state.blocked_reasons` into blocker reasons).

## Evidence outcome
- This pass found a **coverage gap**, not a production defect:
  - production code already uses strict greater-than:
    - `blocked = spread_points > max_spread_points`
  - therefore:
    - exact threshold should allow,
    - just below should allow,
    - just above should block.

## Tests added/proved
- Added/verified filter-level boundary tests:
  - equal threshold -> not blocked
  - just below threshold -> not blocked
  - just above threshold -> blocked
- Added/verified run-pipeline boundary coherence tests:
  - exact threshold path remains tradable and does not include `spread_too_wide`
  - just below threshold path remains tradable and does not include `spread_too_wide`
  - above threshold path blocks to WAIT and surfaces explicit blocker reason `spread_filter:spread_too_wide`.

## Minimal fix applied
- No production-code fix required (behavior already correct).
- Minimal change was test coverage expansion only, to remove ambiguity at threshold edges.

## Post-pass result
- Focused spread boundary tests passed.
- Focused+nearby regressions passed (`44 passed` combined run).
