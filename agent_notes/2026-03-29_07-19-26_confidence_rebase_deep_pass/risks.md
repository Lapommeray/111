## Risks / constraints

- This pass rebases confidence only for non-blocked directional degradations to WAIT; it does not retune broader confidence calibration policies across all abstain pathways.
- End-to-end broker-connected live execution behavior remains unverified in this pass; validation is test-driven via focused and nearby suites.
- Runtime artifact `memory/generated_code_registry.json` continues to change as a side effect and remains intentionally uncommitted.
