## Evidence (consolidation basis)

### 1) Deterministic readiness and live-observability baseline
- **Source paths**:
  - `agent_notes/2026-03-29_19-48-27_live_boundary_scope_and_validation_readiness_pass/live_only_scope.md`
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_execution_readiness.md`
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/evidence.md`
- **Why used**:
  - These define the live-only boundary and confirm that required artifact fields already exist.
- **Live artifact implication**:
  - Required verification timeline fields are mandatory review targets:
    - `initial_confirmation`
    - `delayed_recheck_attempted`
    - `delayed_recheck_confirmation`
    - `final_confirmation`
    - `verification_checked_at`
  - Required coherence fields:
    - `signal.reasons`
    - `status_panel.entry_exit_decision`
    - `rollback_refusal_reasons`
    - retry metadata fields in `order_result`.

### 2) Scenario definitions and field-level checks
- **Source paths**:
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_checklist.md`
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_evidence_template.md`
- **Why used**:
  - These provide scenario set A–G and required per-run evidence schema.
- **Live artifact implication**:
  - Every scenario packet and worksheet in this master handoff inherits the exact same required post-run artifact set:
    - `mt5_controlled_execution_artifact.json`
    - `mt5_controlled_execution_history.json`
    - `mt5_controlled_execution_state.json`
  - Every worksheet requires explicit pass/fail/inconclusive verdict.

### 3) Execution order and progression gates
- **Source paths**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/live_run_sequence.md`
- **Why used**:
  - It defines the canonical order A→B→C→D→E→F→G and prerequisite confidence before advancing.
- **Live artifact implication**:
  - Advancement decisions must be based on complete artifact bundles and coherent field-level outcomes.

### 4) Failure escalation mapping
- **Source path**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/live_failure_escalation_map.md`
- **Why used**:
  - It maps failure signatures to concrete file/function investigation zones.
- **Live artifact implication**:
  - Escalation from operations to code investigation is artifact-triggered, not assumption-triggered.
  - Deterministic reproduction should only be attempted when the map criteria are met.

### 5) Completion thresholds
- **Source path**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/live_validation_completion_criteria.md`
- **Why used**:
  - It defines minimum successful runs per scenario class and stability thresholds.
- **Live artifact implication**:
  - No scenario class is stage-closed without the configured count of successful artifact-backed runs and no unresolved contradictions.

### 6) A/B operator precision uplift
- **Source paths**:
  - `agent_notes/2026-03-29_20-55-42_first_live_run_operator_packet_pass/scenario_A_operator_packet.md`
  - `agent_notes/2026-03-29_20-55-42_first_live_run_operator_packet_pass/scenario_B_operator_packet.md`
  - `agent_notes/2026-03-29_20-55-42_first_live_run_operator_packet_pass/scenario_A_review_worksheet.md`
  - `agent_notes/2026-03-29_20-55-42_first_live_run_operator_packet_pass/scenario_B_review_worksheet.md`
- **Why used**:
  - These provide more granular step-by-step operator controls for first runs.
- **Live artifact implication**:
  - This master package preserves that operational detail and extends it to scenarios C–G in consistent format.

### Consolidation outcome
- **Production/code changes in this pass**: none.
- **Reason**: this is a master handoff consolidation pass only; no fresh live artifacts were produced in this pass to justify code changes.
