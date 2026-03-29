## Task
Execute the remaining deterministic checks in order:
1) spread-boundary + macro-penalty integration,
2) guarded margin-1 override regression under macro-risk tags,
3) live-mode unresolved-exit follow-up reproducibility decision with exact repository evidence.

## What I did
- Added focused integration tests in `src/tests/test_run_pipeline_decision_quality.py` for spread/macro and margin-1/macro interactions.
- Kept changes architecture-preserving (tests only); no production-path rewrite.
- Validated unresolved-exit live follow-up reproducibility from existing execution/memory harness tests.
- Re-ran focused + nearby regressions for decision, contract, filter, scoring, execution-gate, and memory paths.

## Final result
- Phase 1 complete: spread-boundary + macro penalties are now explicitly covered and coherent.
- Phase 2 complete: margin-1 override behavior under macro-risk tags is now explicitly guarded.
- Phase 3 complete: unresolved live close-follow-up is reproducible in the current harness (not an untestable live-only gap).
- Net code change: tests only; no production code changed in this pass.
