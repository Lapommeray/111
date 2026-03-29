## Risks / constraints

- This pass rebases confidence for execution-refusal-driven abstains; broader confidence calibration across every possible abstain reason remains unchanged.
- End-to-end broker-connected live execution is still not run in this pass; validation is test-driven using focused and nearby suites.
- Runtime artifact `memory/generated_code_registry.json` continues to change as a side effect and remains intentionally uncommitted.
