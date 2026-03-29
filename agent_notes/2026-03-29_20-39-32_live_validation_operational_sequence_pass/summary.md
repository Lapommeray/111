## Task
Operationalize the live MT5 validation stage using existing readiness/checklist/template artifacts, without reopening deterministic repo-level work.

## What I did
- Converted the scenario list into an exact run-order sequence with prerequisites, monitoring requirements, mandatory artifact bundle capture, and pre-next-scenario review gates.
- Defined strict per-scenario post-run review rules (pass/fail/inconclusive) across broker verification payload fields, `signal.reasons`, `entry_exit_decision`, delayed-recheck metadata, retry/refusal metadata, and action/confidence coherence.
- Built a live-failure escalation map that ties observed failure signatures to concrete repository investigation zones and whether deterministic reproduction should be attempted.
- Defined explicit live-validation completion criteria for this stage (minimum successful runs per scenario class, stability evidence thresholds, and return-to-code triggers).

## Final result
- Produced an execution-ready, reviewable, escalation-ready live validation protocol package.
- No production code changes were made; this pass is documentation/operations only and is anchored to current readiness state and existing artifact schema.
