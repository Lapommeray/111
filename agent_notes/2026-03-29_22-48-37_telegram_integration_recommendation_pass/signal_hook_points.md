## Signal hook points (repository-verified)

### Candidate 1 (primary): `run.py::run_pipeline` final return output
- Exact point:
  - `run_pipeline` builds `signal_payload`, enriches `status_panel` (including `entry_exit_decision`), then returns via:
    - `return build_indicator_output(...)`.
- Why this is a strong hook:
  - It is the final unified output envelope (`signal`, `status_panel`, `chart_objects`) and is already the canonical output contract in tests.
  - It includes the exact fields needed for Telegram filtering and messaging:
    - `signal.action`, `signal.confidence`, `signal.reasons`, `signal.blocker_reasons`,
    - `symbol`,
    - `status_panel.entry_exit_decision` for EXIT semantics,
    - `memory_context.latest_snapshot_id` for dedupe id.

### Candidate 2 (secondary): `run.py::main` CLI call site
- Exact point:
  - `main()` prints `run_pipeline(config)` result.
- Why this is weaker than candidate 1:
  - It is CLI output transport, not business output contract.
  - Hooking by parsing printed dict text is less stable and less testable.

### Candidate 3 (not preferred): inside `build_signal_output` (`src/indicator/signal_model.py`)
- Why not preferred:
  - Too early in pipeline; EXIT is derived later from `status_panel.entry_exit_decision` and controlled execution state.
  - This risks missing final state/contract context needed for safe actionable alerts.

### Candidate 4 (not preferred): inside `build_indicator_output` (`src/indicator/indicator_output.py`)
- Why not preferred:
  - This helper should stay pure output assembly; embedding network I/O here couples transport into core output module.
  - Increases risk to stable output contract and tests.
