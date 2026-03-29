## Risks / constraints

- This pass tuned conflict blocking sensitivity in `apply_conflict_filter`; it did not retune downstream directional conviction thresholds.
- End-to-end broker-connected live execution behavior is still not validated in this pass; validation remains test-driven via stubs/fixtures and replay/live contract suites.
- Runtime artifact `memory/generated_code_registry.json` continues to change as a side effect and remains intentionally uncommitted.
