## Next steps (evidence-prioritized)

1. Add one focused integration test that verifies `run_advanced_modules()` confidence delta changes when quarantining each optional spectral module individually.
2. Add a replay-level test validating that spectral-fusion reason fields (`buy_votes`, `sell_votes`, `avg_delta`) remain deterministic across repeated runs with identical inputs.
3. Evaluate whether directional-conviction thresholding should consume effective confidence in addition to advanced confidence, with failing tests first before any change.
