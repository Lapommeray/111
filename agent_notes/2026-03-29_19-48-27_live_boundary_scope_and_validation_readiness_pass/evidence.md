## Evidence

### Live-only boundary mapping basis
- Exact runtime paths traced in `run.py`:
  - `_run_controlled_mt5_live_execution`
  - `_verify_accepted_send_position_linkage`
  - `_verify_exit_close_position_disappearance`
  - `_verify_partial_send_deal_quantity`
  - `_build_entry_exit_decision_contract`
- Existing deterministic harness evidence:
  - `src/tests/test_execution_gate_unittest.py` delayed confirmation/retry/unresolved tests
  - `src/tests/test_memory.py::test_run_pipeline_persists_controlled_mt5_execution_artifacts`

### Observability gap found and fixed
- **Gap**: delayed broker recheck outcomes had confirmation/fail-closed reason but insufficient explicit timeline fields to reconstruct first-check vs delayed-check progression in a live postmortem.
- **Exact file/function**: `run.py::_run_controlled_mt5_live_execution`.
- **Fix applied (minimal)**:
  - Added metadata fields (`initial_confirmation`, `delayed_recheck_attempted`, `delayed_recheck_confirmation`, `final_confirmation`, `verification_checked_at`) into:
    - `order_result.broker_position_verification`
    - `order_result.broker_exit_verification`
    - `order_result.partial_quantity_verification`
- **Proof tests**:
  - `test_accepted_send_delayed_recheck_confirms_exact_linkage_when_broker_truth_appears`
  - `test_exit_close_send_without_disappearance_fails_closed_unresolved_open`
  - `test_partial_fill_delayed_recheck_confirms_exact_linked_deal_when_broker_truth_appears`
- **Result**:
  - Focused tests pass (`3 passed`), full nearby regressions pass (`150 passed`).

### Why remaining items are still live-only
- Broker acceptance/refusal timing, network partitions, and real terminal latency are external runtime factors not deterministically reproducible by current stubs/tests.
- Repository now captures sufficient artifact context to audit these events when they occur live.
