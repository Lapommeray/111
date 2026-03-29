## Scenario A operator packet — Broker send/linkage timing race

### Objective
- Validate that an accepted live send preserves a coherent broker linkage timeline and coherent downstream signal/contract state in one run.

### Pre-run checks (must be completed in order)
1. Confirm operator is running in `mode=live` with MT5 terminal connected and account authorized for execution.
2. Confirm symbol and timeframe are the intended live target for this run.
3. Confirm no unresolved prior run artifact confusion:
   - note current timestamp,
   - start a new run record for Scenario A.
4. Confirm operator has access to collect these files immediately post-run:
   - `mt5_controlled_execution_artifact.json`
   - `mt5_controlled_execution_history.json`
   - `mt5_controlled_execution_state.json`
5. Confirm a fresh worksheet file (`scenario_A_review_worksheet.md`) is ready to fill immediately after run.

### Environment/state prerequisites
- Decision flow must reach a live BUY/SELL send path (Scenario A trigger).
- Expected branch to inspect:
  - `order_result.status` accepted send outcome,
  - `order_result.broker_position_verification.*` timeline metadata.
- Existing deterministic constraints remain unchanged; this run only validates live timing behavior.

### What to monitor during run
- Whether send is accepted and whether position linkage is:
  - immediately confirmed, or
  - delayed then confirmed/unconfirmed after recheck.
- Any runtime signs of interruption that could make artifacts incomplete.

### Immediate post-run artifact capture (do not delay)
1. Copy/record exact values from `mt5_controlled_execution_artifact.json`:
   - `order_result.status`
   - `order_result.broker_state_confirmation`
   - `order_result.broker_state_outcome`
   - `order_result.broker_position_verification.initial_confirmation`
   - `order_result.broker_position_verification.delayed_recheck_attempted`
   - `order_result.broker_position_verification.delayed_recheck_confirmation`
   - `order_result.broker_position_verification.final_confirmation`
   - `order_result.broker_position_verification.verification_checked_at`
   - `signal.action`, `signal.confidence`, `signal.reasons`, `signal.blocker_reasons`, `signal.classification`
   - `status_panel.entry_exit_decision.action`
   - `status_panel.entry_exit_decision.invalidation_reason`
   - `status_panel.entry_exit_decision.open_position_state.status`
2. Record matching paths and run timestamp in worksheet.
3. Snapshot latest appended entry from `mt5_controlled_execution_history.json`.

### Pass criteria
- Verification timeline fields are present and non-ambiguous for linkage branch.
- `signal.*` and `entry_exit_decision.*` remain coherent with open-position state.
- No contradiction such as confirmed linkage with flat state and no matching transition path.

### Fail criteria
- Contradictory state relationship in one complete artifact bundle, including:
  - confirmed linkage but no coherent open-position/contract alignment,
  - or clear reason/contract mismatch against verification outcome.

### Inconclusive criteria
- Any required artifact file is missing/truncated for this run.
- Verification branch expected but timeline fields are absent due to incomplete write/environment interruption.

### Escalation trigger if result is not clean
- **Repeat Scenario A** if result is inconclusive and artifact capture was incomplete.
- **Escalate to code investigation** if:
  - one complete artifact shows missing required timeline fields, or
  - the same contradiction pattern appears in 2 complete Scenario A runs.
- Escalation path reference: `live_failure_escalation_map.md` failure types 1/3.
