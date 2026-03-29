## Scenario D operator packet — Spread-sensitive near-threshold live behavior

### Objective
- Validate that spread-boundary behavior in live conditions remains coherent with blocker/reason/contract outputs.
- Confirm co-occurring open-position management/retry reasons are not dropped when spread and other blockers interact.

### Pre-run checks
1. Confirm Scenarios A-C have at least one conclusive pass each in current live cycle.
2. Confirm live spread context can be observed and recorded at trigger.
3. Confirm worksheet `scenario_D_review_worksheet.md` is ready.
4. Confirm artifact files will be captured immediately post-run.

### Environment prerequisites
- Live mode active.
- Runtime spread should be sampled near configured threshold window.
- System state should allow scenario interpretation (no artifact capture outage).

### Run steps
1. Start worksheet and record pre-run spread context.
2. Execute live cycle during near-threshold spread period.
3. Monitor blocker/reason/contract outputs in real time.
4. Capture artifact/state/history files immediately.
5. Fill worksheet and classify pass/fail/inconclusive.

### What to monitor
- `signal.blocker_reasons` presence/absence of spread blocker in boundary context.
- `signal.reasons` retention of open-position exit management/retry context when co-occurring.
- `signal.classification`, `signal.action`, `signal.confidence`.
- `status_panel.entry_exit_decision.action` and `invalidation_reason`.

### Immediate artifact capture requirements
- Files:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_history.json`
  - `mt5_controlled_execution_state.json`
- Required fields:
  - spread context snapshot (recorded externally in worksheet if not in payload)
  - `signal.blocker_reasons`
  - `signal.reasons`
  - `signal.action`
  - `signal.confidence`
  - `signal.classification`
  - `status_panel.entry_exit_decision.*`
  - verification payload delayed-recheck metadata when branch executed

### Pass criteria
- Spread boundary behavior is coherent and explicit.
- Co-occurring open-position management/retry reasons remain present when applicable.
- No contradiction between blocker/classification and contract action.

### Fail criteria
- Spread blocker appears in contradictory conditions and co-occurring reasons are silently suppressed.
- Contract output conflicts with signal blockers/reasons in the same run.

### Inconclusive criteria
- Spread context at trigger not captured.
- Artifact bundle incomplete for this run.

### Escalation trigger
- Repeat Scenario D for inconclusive captures.
- Escalate when the same co-occurrence contradiction appears in 2 complete artifacts, or one severe contradiction is fully evidenced.
