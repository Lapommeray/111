# Master Live Validation Handoff (Command Center)

## 1) Project status (single source summary)
- Deterministic repo-level work for the scoped decision/exit coherence and observability surface is complete.
- Live readiness is confirmed: required runtime paths, artifact persistence, delayed-recheck metadata, retry/refusal metadata, and signal/contract reason surfaces are present.
- Remaining uncertainty is live-only and must be resolved through real MT5 artifacts, not additional deterministic re-hardening.

Reference:
- `current_status.md`
- `master_live_only_scope.md`

## 2) Scenario execution order (authoritative)
1. Scenario A — broker send/linkage timing race
2. Scenario B — exit close confirmation delay window
3. Scenario C — retry/refusal under true latency
4. Scenario D — spread-sensitive near-threshold behavior
5. Scenario E — live macro pause during open-position management
6. Scenario F — network interruption/partition during verification
7. Scenario G — broker-truth reconciliation mismatch over time

Reference:
- `master_live_run_sequence.md`

## 3) Operator packets (execute from these files)
- `scenario_A_operator_packet.md`
- `scenario_B_operator_packet.md`
- `scenario_C_operator_packet.md`
- `scenario_D_operator_packet.md`
- `scenario_E_operator_packet.md`
- `scenario_F_operator_packet.md`
- `scenario_G_operator_packet.md`

## 4) Review worksheets (fill one per run)
- `scenario_A_review_worksheet.md`
- `scenario_B_review_worksheet.md`
- `scenario_C_review_worksheet.md`
- `scenario_D_review_worksheet.md`
- `scenario_E_review_worksheet.md`
- `scenario_F_review_worksheet.md`
- `scenario_G_review_worksheet.md`

## 5) Escalation rules (artifact-driven)
- Use `master_failure_escalation_map.md` to classify each failure as:
  - observability,
  - reason-propagation,
  - execution-contract,
  - broker/network uncertainty,
  - reconciliation/state-tracking.
- Escalate to deterministic code/test work only when map thresholds are met (complete artifacts + contradiction or repetition thresholds).

## 6) Completion criteria (when to call this stage sufficiently complete)
- Use `master_live_validation_completion_criteria.md`:
  - minimum successful run counts per scenario class,
  - stability evidence requirements,
  - explicit return-to-code triggers,
  - residual open risk surface after initial closure.

## 7) Exact next action (start here)
1. Execute Scenario A using `scenario_A_operator_packet.md`.
2. Fill `scenario_A_review_worksheet.md` immediately after run completion.
3. Apply A decision gate from `master_live_run_sequence.md`:
   - proceed to B only if A is conclusive pass with complete artifact bundle and coherent fields;
   - otherwise repeat A or escalate per `master_failure_escalation_map.md`.
