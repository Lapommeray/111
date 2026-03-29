## Risks / constraints

- This pass tightened entry gating on low effective confidence in final decision assembly; it does not retune individual feature/filter/scoring math.
- End-to-end broker-connected live execution was not run in this pass; validations are decision-path tests and focused execution-contract regressions.
- Runtime artifact `memory/generated_code_registry.json` is modified by runtime side effects and intentionally uncommitted.
