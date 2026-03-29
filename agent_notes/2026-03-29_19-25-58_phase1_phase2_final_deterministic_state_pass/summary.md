## Task
Execute remaining deterministic checks in one real pass:
1) co-occurrence integration (unresolved exit-retry + macro penalty + spread blocker),
2) replay-vs-live parity pinning,
3) explicit deterministic completion state.

## What I did
- Re-validated the exact code path in `run.py` for macro penalty application, spread blocker merge, open-position exit/retry reason propagation, and final entry/exit contract assembly.
- Added two new stricter tests (in addition to prior phase tests) that lock:
  - full retry reason-set propagation in co-occurrence blocked scenarios,
  - replay/live parity under the same spread+macro+unresolved baseline.
- Ran focused phase tests and nearby regressions.

## Final result
- Phase 1: remains a proven production-defect area that is now fixed and further hardened with stricter assertions.
- Phase 2: parity behavior is now additionally pinned under co-occurrence baseline; no new production defect detected.
- Deterministic repo-level checks requested in this stage are complete and green.
