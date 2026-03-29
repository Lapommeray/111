## Task
Execute both remaining deterministic checks in order:
1) unresolved-exit retry + macro penalty + spread co-occurrence integration coverage,
2) replay-vs-live parity pinning for reason propagation.

## What I did
- Traced exact reason assembly path in `run.py` for macro blockers, spread blockers, open-position exit reasons, retry reasons, and entry/exit contract generation.
- Added focused tests for three spread boundary co-occurrence scenarios (above/equal/below threshold) with unresolved exit-retry state and macro penalty.
- Added focused replay-vs-live parity tests for:
  - expected same behavior (no live-only blocker),
  - expected intentional difference (live macro pause blocker).
- Applied one minimal production fix after failing-test proof: open-position exit/retry reasons are now preserved for WAIT+open-position cases regardless of blocked status.
- Re-ran focused tests and nearby regressions.

## Final result
- Phase 1: proven production defect fixed (reason drop under blocked co-occurrence).
- Phase 2: parity pinning added; behavior now explicitly test-locked.
- Deterministic repo-level check bundle for this stage is complete and regression-clean.
