## Evidence basis for operational recommendations

### 1) Run-order staging starts with verification-timeline fundamentals (A -> B -> C)
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_execution_readiness.md`
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_checklist.md`
  - `run.py::_run_controlled_mt5_live_execution`
- **Why it follows now**:
  - Readiness already confirms delayed-recheck fields exist for entry linkage, exit close, and partial verification.
  - Earliest live proof should first validate those core timelines before stress/co-occurrence scenarios.
- **Live artifact implication**:
  - Must validate `initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, and `verification_checked_at` in the scenario-specific verification payload.

### 2) Scenario ordering places spread/macro co-occurrence after execution primitives (D -> E)
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_checklist.md`
  - `run.py` reason propagation and `status_panel.entry_exit_decision` assembly
- **Why it follows now**:
  - Spread and macro checks are meaningful only after baseline linkage/close/retry timeline behavior has live confirmation.
  - This minimizes ambiguity between pure execution uncertainty and co-occurrence reason composition.
- **Live artifact implication**:
  - Require simultaneous review of `signal.reasons`, `signal.blocker_reasons`, `signal.classification`, and `status_panel.entry_exit_decision`.

### 3) Network/partition and reconciliation scenarios are sequenced last (F -> G)
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_checklist.md`
  - `run.py` verification fail-closed outcomes and persisted `mt5_controlled_execution_history.json`
- **Why it follows now**:
  - These are high-variance conditions requiring prior confidence that normal branches are interpretable.
  - Reconciliation (G) specifically depends on multi-run history context.
- **Live artifact implication**:
  - Must capture history snapshots and compare progression of `open_position_state.position_state_outcome` and `pnl_snapshot.position_open_truth`.

### 4) Per-scenario review protocol explicitly keys on required timeline fields
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_evidence_template.md`
  - `run.py` verification payload structures
- **Why it follows now**:
  - Template already defines these fields as mandatory for postmortem coherence; review rules formalize pass/fail/inconclusive cut lines.
- **Live artifact implication**:
  - Any missing required timeline field in a relevant branch is an observability or branch-routing anomaly requiring escalation classification.

### 5) Escalation map aligns live failure signatures to concrete code zones
- **Basis file/path**:
  - `run.py::_run_controlled_mt5_live_execution`
  - `run.py::_build_entry_exit_decision_contract`
  - `run.py` open-position retry/management reason assembly
  - `agent_notes/.../live_run_checklist.md` scenario defect signatures
- **Why it follows now**:
  - Current architecture exposes clear boundaries between verification payload generation, signal reason propagation, and contract assembly.
- **Live artifact implication**:
  - Failure triage can point to exact file/function entry points before any deterministic reproduction attempt.

### 6) Completion criteria require repeated artifact-backed successes, not single-run wins
- **Basis file/path**:
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/next_steps.md`
  - `agent_notes/2026-03-29_20-01-37_live_execution_readiness_and_run_protocol_pass/live_run_checklist.md`
- **Why it follows now**:
  - Remaining risks are timing/network-driven and can be intermittent; single-run pass is insufficient signal.
- **Live artifact implication**:
  - Scenario stability claims require multiple clean runs with no unresolved contradictions in verification timeline + reason/contract coherence.
