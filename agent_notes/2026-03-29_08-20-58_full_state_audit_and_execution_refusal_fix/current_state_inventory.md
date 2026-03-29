## Required-file inventory (verified from repository state)

### Core decision assembly
- `run.py::run_pipeline`
  - Computes structure/liquidity/base confidence.
  - Runs `run_advanced_modules`.
  - Applies macro/risk/guard logic.
  - Applies directional degradation checks.
  - Builds signal/status/output payload.
  - Contains current confidence-rebase behaviors:
    - low effective confidence hard-block to WAIT
    - non-blocked directional degradation to WAIT confidence cap
    - execution-refusal degradation to WAIT confidence cap

### Filter precision
- `src/filters/conflict_filter.py::apply_conflict_filter`
  - Hard-block is tie-deadlock only with sufficient directional evidence (`buy_count == sell_count` and active directional votes >= 4).
  - Non-tie slight-majority splits are not hard-blocked here.

### Scoring aggregation
- `src/scoring/spectral_signal_fusion.py::fuse_spectral_signals`
  - Uses only module outputs actually present in `module_outputs`.
  - Missing/quarantined modules do not contribute implicit zero-delta dilution.

### Contract and decision-quality tests
- `src/tests/test_run_pipeline_contract.py`
  - Envelope shape and required keys.
  - Blocked output must include blocker reasons.
  - Macro-penalty scenario -> blocked WAIT with confidence threshold reason.
  - Live macro pause block semantics.

- `src/tests/test_run_pipeline_decision_quality.py`
  - Strong setup entry allowed.
  - Low effective confidence block.
  - Manipulated conflict setup degrades to WAIT.
  - Slight-majority downstream degradation rebases confidence.
  - Open-position invalidation path surfaces EXIT contract.
  - Execution-refusal degradation rebases confidence.

- `src/tests/test_fusion_router_scoring.py`
  - Spectral fusion vote/delta behavior.
  - Missing-module no-dilution checks.
  - Meta routing and regime scoring sanity.

- `src/tests/test_conflict_filter_precision.py`
  - 2:1 not hard-blocked.
  - 2:2 hard-blocked.
  - 3:2 not hard-blocked.

- `src/tests/test_filter_gates.py`
  - Memory filter loss-cluster block.
  - Conflict gate balanced contradiction block.
  - Self-destruct trigger.
  - Session off-hours block.

### Execution/exit contract tests in repo
- `src/tests/test_execution_gate_unittest.py`
  - `_build_entry_exit_decision_contract` behavior:
    - clean long entry contract
    - clean exit contract for open position
    - stop-loss / take-profit / partial-exposure exit-rule variants
    - fallback exit-rule behavior
  - Replay simulated execution contract behavior and no-autostop semantics.

### run_advanced_modules wiring (actual called modules)
- `src/pipeline.py::run_advanced_modules`
  - Feature modules called:
    - `compute_displacement`
    - `detect_fvg_state`
    - `compute_volatility_state`
    - `compute_session_state`
    - `compute_spread_state`
    - `detect_liquidity_sweep_state`
    - `detect_compression_expansion_state`
    - `track_session_behavior`
    - `classify_market_regime`
    - `track_execution_quality`
    - optional/quarantinable: `mine_internal_patterns`, `measure_human_lag_signal`, `scan_tremor_state`
  - Filter modules called:
    - `apply_session_filter`
    - `apply_spread_filter`
    - `apply_conflict_filter`
    - `apply_memory_filter`
    - `apply_self_destruct_protocol`
  - Scoring modules called:
    - `compute_setup_score`
    - `compute_regime_score`
    - optional/quarantinable: `fuse_spectral_signals`, `compute_meta_conscious_routing`
  - Aggregation:
    - `aggregate_direction`
    - `aggregate_confidence`
