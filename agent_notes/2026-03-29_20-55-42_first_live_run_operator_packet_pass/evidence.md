## Evidence basis for first-live-run operator packet

### 1) Scenario A and B are the correct first runs
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/live_run_sequence.md`
- **Why it follows**:
  - A validates entry-linkage verification timeline first.
  - B depends on having interpretable timeline behavior from A and then validates delayed close confirmation.
- **Artifact implication**:
  - Immediate collection of `mt5_controlled_execution_artifact.json`, `mt5_controlled_execution_history.json`, and `mt5_controlled_execution_state.json` is mandatory after both runs.

### 2) A/B pass/fail/inconclusive rules are field-driven, not narrative-driven
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/per_scenario_review_rules.md`
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_evidence_template.md`
- **Why it follows**:
  - Review rules explicitly define delayed-recheck fields, signal coherence, and entry/exit contract coherence for A and B.
- **Artifact implication**:
  - Required delayed-recheck fields for A/B:
    - `initial_confirmation`
    - `delayed_recheck_attempted`
    - `delayed_recheck_confirmation`
    - `final_confirmation`
    - `verification_checked_at`

### 3) Escalation triggers for first runs are already defined and reused here
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/live_failure_escalation_map.md`
- **Why it follows**:
  - Missing timeline fields, reason-propagation mismatch, and contract contradiction are already mapped to concrete investigation zones and fix bars.
- **Artifact implication**:
  - A single complete-artifact run with missing required timeline fields can justify observability-focused code re-entry.
  - Repeated contradictions (2+ complete artifacts) trigger deterministic reproduction + code investigation.

### 4) Decision gates A->B and B->C are tied to completion thresholds and repetition policy
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/live_validation_completion_criteria.md`
  - `agent_notes/2026-03-29_20-39-32_live_validation_operational_sequence_pass/per_scenario_review_rules.md`
- **Why it follows**:
  - Immediate progression rules require clean, complete artifacts and coherent outcomes.
  - Stage closure requires repeated successful runs; first packet only determines whether to proceed, repeat, or escalate.
- **Artifact implication**:
  - Move from A to B only on complete/coherent A artifact.
  - Move from B to C later only on complete/coherent B artifact and no unresolved contradictions.
