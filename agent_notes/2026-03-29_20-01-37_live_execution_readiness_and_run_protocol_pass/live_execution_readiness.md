## Live execution readiness confirmation

### Confirmed runtime paths (current code)
- MT5 controlled live execution:
  - `run.py::_run_controlled_mt5_live_execution`
- Broker position linkage verification:
  - `run.py::_verify_accepted_send_position_linkage`
  - consumed in `_run_controlled_mt5_live_execution` via `order_result.broker_position_verification`
- Broker exit-close disappearance verification:
  - `run.py::_verify_exit_close_position_disappearance`
  - consumed in `_run_controlled_mt5_live_execution` via `order_result.broker_exit_verification`
- Partial quantity verification:
  - `run.py::_verify_partial_send_deal_quantity`
  - consumed in `_run_controlled_mt5_live_execution` via `order_result.partial_quantity_verification`
- Entry/exit decision contract assembly:
  - `run.py::_build_entry_exit_decision_contract`
  - attached in `run.py` to `status_panel["entry_exit_decision"]`
- Controlled execution artifact persistence:
  - `run.py::_run_controlled_mt5_live_execution` writes:
    - `mt5_controlled_execution_artifact.json`
    - `mt5_controlled_execution_state.json`
    - `mt5_controlled_execution_history.json`
- Final signal reason propagation for open-position/retry context:
  - `run.py` reasons include:
    - `open_position_exit_management:*`
    - `open_position_exit_retry:*`
    - `open_position_exit_retry_policy:*`

### Required fields confirmed present
- Delayed-recheck timeline metadata in verification payloads:
  - `initial_confirmation`
  - `delayed_recheck_attempted`
  - `delayed_recheck_confirmation`
  - `final_confirmation`
  - `verification_checked_at`
- Retry/refusal metadata:
  - `order_result.retry_policy_truth`
  - `order_result.retry_attempted_count`
  - `order_result.retry_blocked_reason`
  - `rollback_refusal_reasons`
- Final signal and contract coherence fields:
  - `signal.reasons`
  - `status_panel.entry_exit_decision`
  - `open_position_state`
  - `exit_decision`

### Test-backed readiness confirmation
- `src/tests/test_execution_gate_unittest.py`:
  - delayed recheck linkage, delayed close verification, partial delayed recheck tests pass.
- `src/tests/test_memory.py`:
  - artifact/state/history persistence test passes.
- `src/tests/test_run_pipeline_decision_quality.py`:
  - unresolved exit-retry reason propagation and replay/live parity tests pass.

### Readiness conclusion
- Observability and artifact persistence are sufficient for trustworthy live postmortems.
- No additional production observability change is justified before real live artifacts exist.
