## Remaining gaps ranked (exact repository-state view)

### 1) High-value: open-position degradation path confidence/action/reason coherence
- **Location**: `run.py` + `_build_entry_exit_decision_contract`, interaction with controlled execution and open-position state transitions.
- **Why real gap**: exit contract action behavior is covered, but explicit confidence semantics for open-position-driven WAIT/EXIT transitions are only partially covered.
- **Gap type**: coverage gap.
- **Proof test to add**:
  - Scenario with open position + degraded setup + explicit refusal path; assert entry_exit_decision action, signal action, reasons, and confidence are mutually consistent.
- **Likely improvement area**: exit/invalidation speed and false-exit reduction.
- **Why #1**: high operational impact on real trade management semantics after abstain confidence rebasing is now broadened.

### 2) Medium-high: conviction threshold calibration behavior around 4:3 and similar slight majorities
- **Location**: `run.py` directional conviction section (vote margin/support ratio thresholds).
- **Why real gap**: 2:1 and 3:2 filter-level hard blocks are fixed; downstream conviction gating remains blunt and may still over/under-degrade near boundary cases.
- **Gap type**: coverage gap currently; no failing proof yet for 4:3 boundary.
- **Proof test to add**:
  - Controlled module-vote setup for 4:3 with strong/weak confidence variants; verify expected BUY/WAIT split with coherent reasons.
- **Likely improvement area**: false entry reduction, unjustified abstain reduction, late entry reduction.
- **Why #2**: value remains high for entry precision after the generalized WAIT-confidence fix.

### 3) Medium: spread-filter threshold boundary precision tests
- **Location**: `src/filters/spread_filter.py::apply_spread_filter`, integration through `run_advanced_modules`.
- **Why real gap**: filter gate exists and is indirectly exercised, but explicit boundary tests around exactly-at-threshold and near-threshold regimes are limited.
- **Gap type**: coverage gap.
- **Proof test to add**:
  - direct filter test for `spread_points == max_spread_points` (not blocked) and `spread_points = max_spread_points + epsilon` (blocked).
- **Likely improvement area**: unjustified abstain reduction (false block reduction) and consistency.
- **Why #3**: worthwhile precision hardening but lower immediate impact than open-position and directional-conviction coherence.
