## Scenario F operator packet — Network interruption / partition effects during verification

### Objective
- Validate that infrastructure-side verification uncertainty is explicitly and coherently represented across verification payloads, signal reasons, and entry/exit contract fields.

### Pre-run checks
1. Confirm Scenarios A through E each have at least one complete artifact-backed review in this live cycle.
2. Confirm terminal/session logging context is available to annotate interruption timing.
3. Confirm operator can capture artifact bundle immediately post-run.
4. Prepare `scenario_F_review_worksheet.md` before triggering this run.

### Environment prerequisites
- Live mode with a run likely to hit verification lookup under unstable connectivity or service interruptions.
- Operator must be able to document interruption timing and observed symptom.

### Run steps
1. Fill run identity/context in Scenario F worksheet.
2. Execute live cycle during/around observed interruption conditions.
3. Capture artifact bundle immediately on run completion.
4. Populate required verification fail-closed fields and downstream contract/signal outcomes.
5. Label pass/fail/inconclusive and apply escalation rules.

### What to monitor during run
- Verification payload fail-closed fields:
  - `broker_position_verification.fail_closed_reason` (if linkage path)
  - `broker_exit_verification.fail_closed_reason` (if exit path)
  - `partial_quantity_verification.fail_closed_reason` (if partial path)
- Signal/contract coherence:
  - `signal.action`, `signal.reasons`, `signal.blocker_reasons`, `signal.classification`
  - `status_panel.entry_exit_decision.action`, `invalidation_reason`, `open_position_state.*`
- Delayed-recheck timeline fields when branch includes recheck metadata.

### Immediate artifact capture requirements
- Files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
- Required fields:
  - verification `fail_closed_reason` values
  - delayed-recheck fields where present
  - retry/refusal metadata where present
  - full signal/contract/open-position coherence fields
  - interruption timing note in worksheet.

### Pass criteria
- Infrastructure-induced uncertainty is explicit (fail-closed reason present) and downstream signal/contract is coherent.

### Fail criteria
- Verification uncertainty present but fail-closed reason missing/ambiguous in complete artifact.
- Downstream state contradicts verification outcome without coherent reason path.

### Inconclusive criteria
- Artifact capture failed during interruption.
- Interruption evidence not recorded well enough to classify.

### Escalation trigger
- Repeat Scenario F if inconclusive due to artifact incompleteness.
- Escalate when:
  - fail-closed reason absence repeats in complete artifacts, or
  - one high-confidence contradiction appears with complete artifacts.
- Primary investigation zones:
  - `run.py::_run_controlled_mt5_live_execution`,
  - verification helper fail-closed classification paths.
