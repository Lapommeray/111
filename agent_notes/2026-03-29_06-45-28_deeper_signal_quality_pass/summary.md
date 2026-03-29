## Task
Perform the first deeper signal-quality pass inside existing feature/filter/scoring wiring, prove next weakness with failing tests, apply minimal fix, and validate with focused regressions.

## What changed
- Added scoring-focused evidence tests in `src/tests/test_fusion_router_scoring.py` for missing/quarantined-module behavior.
- Applied minimal scoring fix in `src/scoring/spectral_signal_fusion.py` so fusion uses only present module outputs (no placeholder zero-slot dilution).
- Revalidated decision-quality and nearby regressions after the scoring fix.

## Why
- Failing tests proved spectral fusion confidence was diluted when optional modules were absent, which can degrade entry timing/quality and over-neutralize confidence without true contrary evidence.

## Result
- The proven weakness is fixed with a minimal scoring-layer edit only.
- Consolidated targeted suite for this pass is green (`21 passed`).
