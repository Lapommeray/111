## Evidence

### 1) MT5 controlled live execution + entry/exit contract assembly paths confirmed
- **File/function**: `run.py::_run_controlled_mt5_live_execution` and `run.py::_build_entry_exit_decision_contract`.
- **Proof**:
  - Controlled execution artifact contains `order_result`, `rollback_refusal_reasons`, `open_position_state`, and `exit_decision`.
  - Execution artifacts are persisted to `mt5_controlled_execution_artifact.json`, `mt5_controlled_execution_state.json`, and `mt5_controlled_execution_history.json`.
  - `status_panel["entry_exit_decision"]` is assembled from controlled execution outputs.
- **Result**: readiness path is present and auditable without architecture changes.

### 2) Broker position linkage verification fields confirmed
- **File/function**: `run.py::_run_controlled_mt5_live_execution` (accepted-send branch).
- **Proof**: `order_result.broker_position_verification` includes:
  - `initial_confirmation`
  - `delayed_recheck_attempted`
  - `delayed_recheck_confirmation`
  - `final_confirmation`
  - `verification_checked_at`
- **Result**: delayed linkage race timeline is captured for live postmortem.

### 3) Broker exit close disappearance verification fields confirmed
- **File/function**: `run.py::_run_controlled_mt5_live_execution` (exit-close branch).
- **Proof**: `order_result.broker_exit_verification` includes:
  - `initial_confirmation`
  - `delayed_recheck_attempted`
  - `delayed_recheck_confirmation`
  - `final_confirmation`
  - `verification_checked_at`
- **Result**: delayed close confirmation windows are auditable.

### 4) Partial quantity verification fields confirmed
- **File/function**: `run.py::_run_controlled_mt5_live_execution` (partial branch).
- **Proof**: `order_result.partial_quantity_verification` includes:
  - `initial_confirmation`
  - `delayed_recheck_attempted`
  - `delayed_recheck_confirmation`
  - `final_confirmation`
  - `verification_checked_at`
- **Result**: partial-fill confirmation timing is auditable.

### 5) Retry/refusal metadata + reason propagation confirmed
- **File/function**: `run.py::_run_controlled_mt5_live_execution` and `run.py` final signal reason assembly.
- **Proof**:
  - `order_result` carries retry metadata (`retry_policy_truth`, `retry_attempted_count`, `retry_blocked_reason`, `retry_final_outcome_status`).
  - controlled execution carries `rollback_refusal_reasons`.
  - final signal reasons append `open_position_exit_management:*`, `open_position_exit_retry:*`, `open_position_exit_retry_policy:*`.
- **Result**: unresolved exit/retry causes are retained from execution artifact to final signal reasons.

### 6) Persistence and readiness behavior proven by tests in this pass
- **Focused tests run**:
  - delayed recheck linkage / exit / partial verification tests in `src/tests/test_execution_gate_unittest.py`
  - persistence test in `src/tests/test_memory.py`
  - unresolved retry + macro/spread coherence and replay/live parity tests in `src/tests/test_run_pipeline_decision_quality.py`
- **Result**: `6 passed`.
- **Nearby regressions run**:
  - `src/tests/test_run_pipeline_contract.py`
  - full `src/tests/test_execution_gate_unittest.py`
  - full `src/tests/test_memory.py`
  - replay/live pause parity case in `src/tests/test_run_pipeline_decision_quality.py`
- **Result**: `85 passed`.

### Production fix decision
- **Decision**: no production code change in this pass.
- **Reason**: readiness and required observability fields are already present and test-backed in current repository state.
