## Task
Find and fix the next evidence-backed deeper precision weakness beyond conflict hard-block tuning, inside existing architecture only.

## What changed
- Added a focused decision-quality test for slight-majority downstream degradation confidence behavior in `src/tests/test_run_pipeline_decision_quality.py`.
- Proved and fixed a direction/confidence mismatch in `run.py` final decision assembly:
  - when directional logic degrades BUY/SELL to WAIT for non-blocked directional reasons, confidence is now rebased to non-trade range.
- Re-ran focused and nearby regression suites.

## Why
- Failing evidence showed abstain action (`WAIT`) could still carry trade-high confidence (`0.88`), which is internally inconsistent and can mislead downstream consumers.

## Result
- Slight-majority degraded setup now outputs WAIT with low confidence, preserving consistency.
- Consolidated suite for this pass is green (`29 passed`).
