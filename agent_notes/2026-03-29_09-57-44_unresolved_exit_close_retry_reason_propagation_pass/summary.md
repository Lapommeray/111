## Task
Execute the ranked #1 remaining gap: unresolved exit-close retry reason-propagation coverage under repeated non-confirmed close outcomes.

## What I did
- Read the requested source-of-truth artifacts from prior passes.
- Traced unresolved close / retry path in current code:
  - open-position close branch and unresolved close outcomes in `_run_controlled_mt5_live_execution`
  - final action/confidence/reason assembly in `run_pipeline`
  - exit contract assembly in `_build_entry_exit_decision_contract`
- Added focused failing test proving unresolved close retry reasons were not propagated to `signal.reasons`.
- Applied minimal fix in existing decision assembly to propagate:
  - unresolved close refusal reasons
  - retry policy truth marker
  for open/partial position WAIT->EXIT management paths.
- Re-ran focused tests and nearby regressions.

## Final result
- Proven and fixed: unresolved close/retry causes were silently dropped from final signal reasons.
- Final signal layer now preserves unresolved close and retry context coherently alongside action/confidence/exit contract.
- Combined targeted+nearby verification passed: `45 passed`.
