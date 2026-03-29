## Evidence map

### Issue 1: Direction degraded to WAIT while confidence stayed trade-high
- **Exact location**: `run.py` final decision assembly around directional degradation (`directional_conviction` / `directional_vote_margin` checks).
- **Pre-fix behavior**:
  - In slight-majority low-quality setups (e.g. `3:2`), action degraded from `BUY` to `WAIT`,
  - but `signal.confidence` remained high (e.g. `0.88`), creating direction/confidence mismatch.
- **Proof test (pre-fix failing)**:
  - `src/tests/test_run_pipeline_decision_quality.py::test_slight_majority_setup_rebases_confidence_after_directional_degradation`
- **Observed failure evidence**:
  - Expected `signal["confidence"] <= 0.59`, observed `0.88`.
- **Minimal fix applied**:
  - In `run.py`, track when decision is degraded to `WAIT` by non-blocked directional checks.
  - In that specific path only, cap `effective_signal_confidence` to `<= 0.59`.
- **Post-fix result**:
  - Same scenario now returns `WAIT` with reduced confidence, matching abstain semantics.

### Issue 2: Need explicit guard coverage for confidence rebasing after directional degradation
- **Exact location**: `src/tests/test_run_pipeline_decision_quality.py`
- **What was added**:
  - `test_slight_majority_setup_rebases_confidence_after_directional_degradation`
- **Post-fix result**:
  - Focused and consolidated suites pass and protect against regression.
