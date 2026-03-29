## Issue proven in this pass

### Gap: directional-conviction boundary handling was too blunt for margin-1 cases
- **Location**: `run.py::run_pipeline` directional conviction gating block.
- **Observed behavior**:
  - current logic used `insufficient_vote_margin = directional_vote_margin < 2`,
  - this hard-degraded all margin-1 slight majorities to `WAIT` regardless of strong conviction/sample context.
- **Failing test proving defect**:
  - `src/tests/test_run_pipeline_decision_quality.py::test_5v4_boundary_allows_entry_when_conviction_is_strong`
- **Pre-fix failure evidence**:
  - expected `signal["action"] == "BUY"` for strong 5:4, observed `WAIT`.

## Minimal fix applied
- **File/function**: `run.py::run_pipeline`.
- **Change**:
  - added a narrowly-scoped `slight_majority_override` in directional gating:
    - `directional_vote_margin == 1`
    - `directional_vote_total >= 9`
    - `directional_conviction >= 0.8`
    - `directional_support_ratio >= 0.55`
  - margin insufficiency now applies when `< 2` **and not** override.
- **Why minimal**:
  - no architecture rewrite,
  - no pipeline rewiring,
  - no filter/scoring redesign,
  - only boundary condition precision in existing decision assembly.

## Post-fix result
- 4:3 boundary still degrades to `WAIT` with coherent reasons/confidence.
- 5:4 weak-conviction boundary still degrades to `WAIT`.
- 5:4 strong-conviction boundary now remains tradable (`BUY`) with coherent confidence/reasons.
- Combined targeted+nearby regression run passed (`38 passed`).
