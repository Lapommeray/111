## Risks

- Boundary behavior is now explicitly calibrated for margin-1 cases with strong/high-sample conviction, but live broker-connected outcomes are still not validated in this pass.
- The new override is intentionally narrow (`margin == 1`, `vote_total >= 9`, `directional_conviction >= 0.8`, `support_ratio >= 0.55`); additional calibration may be needed only if future failing evidence appears.
- Runtime-generated artifact `memory/generated_code_registry.json` remains modified by test execution and is intentionally uncommitted.
