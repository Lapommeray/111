## Immediate live execution actions
1. Execute Scenario A first using:
   - `scenario_A_operator_packet.md`
   - `scenario_A_review_worksheet.md`
2. If Scenario A outcome is pass (complete artifact bundle, coherent fields), execute Scenario B using:
   - `scenario_B_operator_packet.md`
   - `scenario_B_review_worksheet.md`
3. Continue through master order in `master_live_run_sequence.md` only when each scenario’s move-forward criteria are satisfied.

## Artifact review actions
1. After every live run, complete the matching scenario worksheet immediately.
2. Store and cross-reference:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`
3. Classify each run as pass/fail/inconclusive with explicit field-level reasons.
4. Apply escalation routing from `master_failure_escalation_map.md` if any fail condition is present.

## Conditions that justify return to deterministic code/test work
- One complete artifact run with missing required delayed-recheck timeline fields where verification branch executed.
- One high-severity contradiction with complete artifacts (e.g., confirmed close but persistent open state without coherent transition reason).
- Same failure signature repeated in 2+ complete artifacts for the same scenario class.
