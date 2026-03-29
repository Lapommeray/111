## Task
Execute the ranked #1 remaining gap: additional directional boundary check around 6:5 to ensure the margin-1 override remains conservative.

## What I did
- Read requested source-of-truth artifacts from prior passes.
- Traced directional boundary logic in `run.py`:
  - vote totals, margin, support ratio, conviction
  - margin-1 override conditions
  - degradation path/reasons/confidence semantics.
- Added focused 6:5 tests for:
  - weak conviction
  - moderate conviction
  - strong conviction
- Validated whether 6:5 becomes permissive under current override.
- Re-ran focused + nearby regressions.

## Final result
- No production defect found for 6:5 conservativeness.
- Current logic remains conservative for 6:5 even under strong confidence due to existing strict support-ratio gate.
- Gap closed as explicit coverage hardening (tests only, no production code change).
- Combined targeted+nearby verification: `48 passed`.
