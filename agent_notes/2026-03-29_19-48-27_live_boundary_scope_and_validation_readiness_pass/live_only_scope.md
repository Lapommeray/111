## Exact live-only remaining scope

### 1) Broker refusal/acceptance timing race on send + linkage
- **Path**: `run.py::_run_controlled_mt5_live_execution` -> `_verify_accepted_send_position_linkage`.
- **Why still live-only**: stubs simulate ordered outcomes; real broker acknowledgement/position materialization timing can vary non-deterministically.
- **Required live artifact**: `mt5_controlled_execution_artifact.json` with `order_result.broker_position_verification` fields and retry metadata.
- **Failure signature**: repeated `accepted_send_unreconciled` with persistent `unconfirmed` despite accepted sends.
- **Success signature**: progression to `accepted_send_position_confirmed` (possibly after delayed recheck) with coherent state transitions.

### 2) Exit close confirmation delay window
- **Path**: `run.py::_run_controlled_mt5_live_execution` -> `_verify_exit_close_position_disappearance`.
- **Why still live-only**: real broker close confirmation and position disappearance may be delayed by server/network conditions.
- **Required live artifact**: `order_result.broker_exit_verification` timeline fields + `open_position_state` + `exit_decision`.
- **Failure signature**: recurring `exit_close_unresolved_open_position` without eventual reconciliation.
- **Success signature**: transition to `exit_send_position_closed_confirmed` and `open_position_state.status=flat`.

### 3) Retry policy behavior under real terminal latency/tick availability
- **Path**: retry branch in `_run_controlled_mt5_live_execution` and `_resolve_broker_retry_price`.
- **Why still live-only**: tick freshness and retcode timing under live terminal load are external and non-deterministic.
- **Required live artifact**: `order_result.retry_*` fields plus refusal reasons and broker state outcome.
- **Failure signature**: repeated fail-closed retry blocks with unresolved order state under transient conditions.
- **Success signature**: bounded retry attempts with coherent final outcome (`accepted` or explicit fail-closed reason).

### 4) Network interruption/partition during exit management
- **Path**: MT5 initialize/positions/deals/order lookup branches in verification helpers.
- **Why still live-only**: external transport faults cannot be fully emulated as true runtime network partitions.
- **Required live artifact**: fail-closed reasons (`*_unavailable`, `*_unreadable`) captured in verification payloads + rollback reasons.
- **Failure signature**: unresolved verification with infrastructure fail-closed reasons persisting across cycles.
- **Success signature**: temporary faults followed by reconciliation with consistent reason transitions.

### 5) Live reconciliation mismatch vs deterministic expected state
- **Path**: `open_position_state` and `pnl_snapshot.position_open_truth` assignment in `_run_controlled_mt5_live_execution`.
- **Why still live-only**: broker truth may diverge from deterministic assumptions under asynchronous updates.
- **Required live artifact**: `open_position_state`, `exit_decision`, `pnl_snapshot`, and verification payloads with timing metadata.
- **Failure signature**: contradictory open/flat truth across successive artifacts without matching verification outcomes.
- **Success signature**: coherent progression and no contradiction between verification outcomes and final state fields.
