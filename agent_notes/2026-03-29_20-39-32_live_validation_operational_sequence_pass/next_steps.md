## Immediate live execution actions
1. Execute Scenario A then Scenario B in order from `live_run_sequence.md` using one filled `live_run_evidence_template.md` per run.
2. Continue Scenario C -> D -> E only after Scenario A/B artifacts are reviewed and marked pass/conclusive.
3. Run Scenario F and Scenario G as monitoring/incident-driven cases once baseline scenarios have artifact-backed coherence.

## Artifact review actions
1. Apply `per_scenario_review_rules.md` after each run before permitting the next scenario.
2. Classify each run as pass/fail/inconclusive with exact field-level evidence.
3. If failed, route immediately through `live_failure_escalation_map.md` and record suspected file/function from artifact proof.

## Conditions that justify return to deterministic code/test work
- Two or more artifact-backed failures of the same failure class across comparable live conditions.
- One severe contradiction proving cross-layer incoherence (verification payload vs `signal.reasons` vs `entry_exit_decision`).
- Any missing required field (`initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, `verification_checked_at`) in a live artifact payload.
