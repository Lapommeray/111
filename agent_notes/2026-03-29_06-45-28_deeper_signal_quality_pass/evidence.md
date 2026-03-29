## Evidence map

### Issue 1: Spectral fusion confidence dilution from missing/quarantined modules
- **Exact location**: `src/scoring/spectral_signal_fusion.py::fuse_spectral_signals`
- **Pre-fix behavior**:
  - Function selected a fixed 6-slot module list using `module_outputs.get(...)`.
  - Missing modules became `{}` entries contributing `0.0` confidence_delta and neutral votes.
  - This diluted confidence and could understate strong available signals.
- **Proof tests (pre-fix failing)**:
  - `src/tests/test_fusion_router_scoring.py::test_spectral_signal_fusion_does_not_dilute_when_optional_modules_missing`
  - `src/tests/test_fusion_router_scoring.py::test_spectral_signal_fusion_ignores_quarantined_missing_vote_slots`
- **Observed failure evidence**:
  - expected `0.0333`, got `0.0167`
  - expected `0.08`, got `0.0133`
- **Minimal fix applied**:
  - Keep same function and architecture, but select only modules that are present in `module_outputs`.
  - Average and vote aggregation now run over present evidence only.
- **Post-fix result**:
  - both failing tests pass; directional and confidence aggregation reflect actual available signals.

### Issue 2: Decision-contract consistency after scoring behavior tightening
- **Exact location**: `src/tests/test_fusion_router_scoring.py` (new/extended coverage)
- **What was added**:
  - targeted tests for missing optional modules and quarantine-equivalent missing slots.
- **Why**:
  - ensures this scoring-layer quality defect remains guarded by tests.
- **Post-fix result**:
  - full targeted suite passes.
