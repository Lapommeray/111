## Immediate live execution actions
1. Execute Scenario A using `scenario_A_operator_packet.md` and complete `scenario_A_review_worksheet.md` immediately after run completion.
2. Apply Scenario A decision rule before any Scenario B attempt.
3. If Scenario A permits progression, execute Scenario B using `scenario_B_operator_packet.md` and complete `scenario_B_review_worksheet.md`.

## Artifact review actions
1. For each run, review all required fields before labeling pass/fail/inconclusive.
2. Archive run evidence packet as:
   - completed scenario worksheet,
   - `mt5_controlled_execution_artifact.json`,
   - `mt5_controlled_execution_history.json`,
   - `mt5_controlled_execution_state.json`.
3. Record explicit justification for outcome labels and any suspected file/function.

## Escalation conditions back to deterministic code/test work
- Missing required delayed-recheck fields in a branch where verification payload exists:
  - `initial_confirmation`
  - `delayed_recheck_attempted`
  - `delayed_recheck_confirmation`
  - `final_confirmation`
  - `verification_checked_at`
- High-severity contradiction in one run with complete artifacts (e.g., confirmed close but open state remains open without coherent transition reason).
- Same failure signature repeated in 2 complete artifacts for Scenario A or B.
