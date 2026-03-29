## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added two focused tests: one proving execution-refusal WAIT confidence mismatch and one proving non-blocked WAIT confidence mismatch.
- `run.py`  
  Minimal fix in final decision assembly:
  - execution-refusal branch confidence cap to `<= 0.59`
  - generalized non-blocked WAIT confidence rebase and explicit reason tag (`abstain_confidence_rebased`).
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/summary.md`  
  This run summary.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/changed_files.md`  
  File-level change inventory.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/tests.md`  
  Exact commands and pass/fail results.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/next_steps.md`  
  Next actions based on audited state and proven gaps.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/risks.md`  
  Exact remaining risks/constraints.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/evidence.md`  
  Exact issue -> proof -> minimal fix -> post-fix result.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/current_state_inventory.md`  
  Exact repository state inventory from inspected files.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/coverage_map.md`  
  Current behavior coverage map by category.
- `agent_notes/2026-03-29_08-20-58_full_state_audit_and_execution_refusal_fix/remaining_gaps_ranked.md`  
  Ranked top remaining gaps with concrete file/function/test plans.
