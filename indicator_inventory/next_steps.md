# Next Steps — Prioritized

All steps below assume: **architecture stays unchanged** unless a change is absolutely required and proven.

---

## Phase 1: Fix First (High Priority, Low Risk)

### 1.1 Set Realistic Execution Costs
- **File**: `config/settings.json`
- **Action**: Set non-zero values for slippage, commission, and spread that match XAUUSD reality
- **Why**: Current zero costs make all replay evaluations unrealistically optimistic
- **Risk**: None — configuration only

### 1.2 Quarantine Weak Optional Modules by Default
- **File**: `src/pipeline.py` (quarantine_set parameter)
- **Action**: Default quarantine `human_lag_exploit`, `invisible_data_miner`, `quantum_tremor_scanner`
- **Why**: These produce false confidence via weak heuristics. They are already quarantinable.
- **Risk**: Very low — these are already optional

### 1.3 Fix Spectral Fusion to Exclude Weak Modules
- **File**: `src/scoring/spectral_signal_fusion.py`
- **Action**: Remove quantum_tremor_scanner, invisible_data_miner, human_lag_exploit from fusion inputs
- **Why**: 50% of fusion input is noise; remaining 3 modules (displacement, fvg, volatility) are real
- **Risk**: Low — only affects fusion scoring

### 1.4 Increase Agreement Weight in Confidence Scoring
- **File**: `src/scoring/confidence_score.py`
- **Action**: Increase agreement component from 10% to at least 25%, reduce structure or liquidity weight
- **Why**: Conflicting direction signals should materially reduce confidence
- **Risk**: Low — changes confidence sensitivity, testable with replay

---

## Phase 2: Strengthen (Medium Priority, Medium Risk)

### 2.1 Add Tests for Weak Modules Before Touching Them
- **Action**: Write targeted tests that verify human_lag_exploit, invisible_data_miner, and quantum_tremor produce expected outputs for known inputs
- **Why**: Must have baseline tests before any modification to detect regressions
- **Files**: New test files in `src/tests/`

### 2.2 Calibrate Thresholds Using Replay Data
- **Action**: Use threshold_calibration.py output to adjust conviction threshold (0.62), displacement ratio (1.8), regime threshold (0.6), etc.
- **Why**: Current thresholds are arbitrary; calibration data exists but hasn't been applied
- **Risk**: Medium — threshold changes affect signal frequency and quality

### 2.3 Improve Session Filter Granularity
- **File**: `src/filters/session_filter.py`
- **Action**: Add session quality tiers (London open = strong, late Tokyo = weak) instead of binary off_hours/allowed
- **Why**: Current filter is too simplistic; allows trading in marginal sessions
- **Risk**: Low — only adds blocking conditions

### 2.4 Add Feature Contributors to Output
- **File**: `src/indicator/signal_model.py`
- **Action**: Include module-level confidence contributions in final signal output
- **Why**: Enables post-trade analysis and debugging
- **Risk**: Low — output schema extension only

---

## Phase 3: Should Stay Unchanged

### 3.1 Core Architecture
- Pipeline orchestration (OversoulDirector, run_advanced_modules) — works correctly
- Multi-gate evaluation chain (completeness → quality → outcome → calibration) — sound design
- Memory system (PatternStore, OutcomeTracker, SelfCoder) — working as intended
- Evolution pipeline (16 modules) — active and functional
- Risk management (capital_guard) — properly enforced

### 3.2 Core Feature Modules
- `market_structure.py` — established HH/HL pattern analysis
- `liquidity.py` — valid sweep detection with volume confirmation
- `volatility.py` — sound range-based classification
- `sessions.py` (compute_session_state) — correct time-based session identification
- `displacement.py` — valid momentum measurement

### 3.3 Core Filters
- `conflict_filter.py` — sound vote-conflict detection
- `spread_filter.py` — appropriate liquidity gate
- `memory_filter.py` — effective 3-loss cluster prevention

---

## Phase 4: Tests Required Before Touching Logic

### Must Write Before Any Changes:

| Test Needed | For Module | Why |
|------------|-----------|-----|
| Threshold boundary tests | All scoring modules | Verify behavior at exact threshold values |
| Conflicting signal tests | confidence_score.py | Verify confidence drops when structure and liquidity disagree |
| Session quality tests | session_filter.py | If adding graduated filtering, need baseline tests |
| Fusion isolation tests | spectral_signal_fusion.py | Verify behavior with/without weak modules |
| End-to-end signal tests | run_pipeline | Verify complete signal generation for known bar sequences |
| Replay regression tests | run_replay_evaluation | Verify evaluation gates still pass after threshold changes |

### Existing Tests to Preserve:
- 696 tests currently passing — no test should be removed or modified unless directly related to a change
- All evaluation gate tests (completeness: 18, quality: 27, outcome: 36, calibration: 32)
- All feature tests (test_features.py, test_spread_state.py)
- All filter tests (test_filters.py, test_filter_gates.py)
- All scoring tests (test_scoring.py, test_fusion_router_scoring.py)
