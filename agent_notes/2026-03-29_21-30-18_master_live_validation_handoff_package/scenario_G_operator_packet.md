## Scenario G operator packet — Broker-truth reconciliation mismatch over time

### Objective
- Validate longitudinal coherence across successive live artifacts:
  - `open_position_state`,
  - verification outcomes,
  - `pnl_snapshot.position_open_truth`,
  - final `signal.*`,
  - `status_panel.entry_exit_decision.*`.

### Pre-run checks (must pass before monitoring window starts)
1. Confirm Scenarios A-F produced at least baseline interpretable artifacts for this live cycle.
2. Confirm history capture path is available and append behavior is working:
   - `mt5_controlled_execution_history.json`.
3. Confirm monitoring window duration (for example, N consecutive cycles) is defined before start.
4. Prepare `scenario_G_review_worksheet.md` per observed run/cycle in the window.

### Environment/state prerequisites
- Live mode with ongoing sessions where position state can evolve across cycles.
- Operator can preserve ordered artifact snapshots and timestamps.
- No manual mutation of artifact files during monitoring window.

### Run steps (human-executable)
1. Define reconciliation observation window and log start timestamp.
2. For each cycle in window:
   - trigger/observe normal live cycle,
   - collect artifact/state/history snapshot,
   - fill one Scenario G worksheet.
3. After minimum window depth is reached, perform cross-run reconciliation review.
4. Label window outcome pass/fail/inconclusive with explicit contradiction evidence (if any).

### What to monitor during run window
- `open_position_state.status`
- `open_position_state.position_state_outcome`
- `pnl_snapshot.position_open_truth`
- verification confirmations/outcomes from position/exit/partial branches
- `signal.reasons` continuity for management/retry context
- `status_panel.entry_exit_decision.action` progression consistency.

### Immediate artifact capture requirements
- Per cycle:
  - `mt5_controlled_execution_artifact.json`
  - `mt5_controlled_execution_state.json`
  - latest `mt5_controlled_execution_history.json` snapshot
  - completed `scenario_G_review_worksheet.md`.
- End-of-window:
  - ordered list of all captured worksheet records with timestamps.

### Pass criteria
- Across 3+ sequential complete artifacts:
  - no unresolved contradiction between broker verification outcomes and open-position truth/state progression,
  - no contradictory action progression in `entry_exit_decision`,
  - management/retry reason continuity is coherent with observed transitions.

### Fail criteria
- Persistent contradiction across sequential snapshots, including:
  - broker-confirmed close while position remains open without coherent transition explanation,
  - repeated mismatch between `pnl_snapshot.position_open_truth` and verification-driven state.

### Inconclusive criteria
- Fewer than required sequential complete snapshots.
- Missing/truncated history snapshots.
- Timestamp/order ambiguity prevents reliable cross-run interpretation.

### Escalation trigger
- Repeat Scenario G if inconclusive due to insufficient sequence depth.
- Escalate to code investigation if:
  - contradiction persists across at least 3 complete sequential artifacts in one window, or
  - same contradiction appears in two windows.
- Primary likely investigation zone:
  - `run.py::_run_controlled_mt5_live_execution` state progression and reconciliation assignment paths.
