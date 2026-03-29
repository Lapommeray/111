## Next steps (verified and prioritized)

1. Add a run_pipeline-level scenario that exercises a 2:1 directional split end-to-end and verifies it no longer receives `direction_conflict` hard block while conviction guards still apply.
2. Add one focused test for conflict-filter behavior at higher vote counts (e.g. 3:2 and 4:3) to validate the `active_votes >= 4` near-even threshold remains calibrated.
3. Evaluate whether conflict severity should emit a graded reason in non-blocked cases (informational only) to improve explainability without reintroducing over-blocking.
