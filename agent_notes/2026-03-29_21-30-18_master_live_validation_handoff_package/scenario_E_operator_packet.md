## Scenario E operator packet — Live macro pause during open-position management

### Objective
- Validate that live macro pause behavior blocks trading as intended while preserving open-position management/retry context in reasons and contract output.

### Pre-run checks
1. Confirm Scenarios A-D have at least one conclusive pass each in this live campaign.
2. Confirm live macro feed can produce/represent pause-active state (`pause_trading=true`) during the run window.
3. Confirm there is an open or actively managed position context so open-position reason propagation can be observed.
4. Prepare `scenario_E_review_worksheet.md`.
5. Confirm artifact files are accessible immediately post-run:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`

### Environment prerequisites
- Live mode active.
- Macro state source connected and observable.
- Position-management path active or expected in same run.

### Run steps
1. Start Scenario E worksheet and capture run identity/context.
2. Execute live cycle while macro pause is active and open-position management context exists.
3. Monitor blocker and reason composition during run.
4. Immediately capture artifact bundle and fill worksheet.
5. Classify pass/fail/inconclusive.

### What to monitor
- `signal.blocker_reasons` for `macro_feed_unsafe_pause`
- `signal.reasons` for:
  - `open_position_exit_management:*`
  - `open_position_exit_retry:*` (if unresolved retry context exists)
- `signal.action`, `signal.confidence`, `signal.classification`
- `status_panel.entry_exit_decision.action`
- `status_panel.entry_exit_decision.invalidation_reason`
- `status_panel.entry_exit_decision.open_position_state.status`

### Immediate artifact capture requirements
- Files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
- Required fields:
  - `signal.blocker_reasons`
  - `signal.reasons`
  - `signal.action`
  - `signal.confidence`
  - `signal.classification`
  - `status_panel.entry_exit_decision.action`
  - `status_panel.entry_exit_decision.invalidation_reason`
  - `status_panel.entry_exit_decision.open_position_state.*`
  - `rollback_refusal_reasons` (if present)
  - verification payload timeline fields if close/linkage verification branches execute

### Pass criteria
- Macro pause blocker is explicit when active.
- Open-position management/retry context remains visible in `signal.reasons` when applicable.
- Contract action/invalidation remains coherent with blocker and position state.

### Fail criteria
- Macro pause appears but active open-position management/retry context is hidden.
- Contract and reason layers contradict blocker/state context.

### Inconclusive criteria
- Macro pause state at trigger cannot be evidenced.
- Artifact capture is incomplete.

### Escalation trigger
- Repeat Scenario E for inconclusive macro-state capture.
- Escalate if:
  - one complete artifact shows macro-blocker suppression of active open-position context, or
  - same suppression pattern repeats in 2 complete Scenario E artifacts.
- Investigation zones:
  - `run.py` blocker/reason composition in live mode,
  - `run.py::_build_entry_exit_decision_contract` for contract coherence.
