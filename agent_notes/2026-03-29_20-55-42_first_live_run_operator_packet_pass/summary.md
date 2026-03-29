## Task
Produce an operator-ready packet for the first live MT5 runs only:
- Scenario A (broker send/linkage timing race)
- Scenario B (exit close confirmation delay window)

## What I did
- Converted existing live sequence/review/escalation/completion docs into step-by-step human execution packets for Scenario A and Scenario B.
- Created two copy-ready run review worksheets (blank but structured) for immediate post-run use.
- Defined explicit artifact-driven decision rules for:
  - move from A -> B,
  - repeat A,
  - escalate after A,
  - move from B -> C later,
  - repeat B,
  - escalate after B.

## Final result
- First-live-run operations are now executable, reviewable, and escalation-ready without ambiguity.
- No production code changes were made in this pass.
