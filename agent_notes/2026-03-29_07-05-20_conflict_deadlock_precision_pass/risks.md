## Risks / constraints

- This pass refines conflict deadlock behavior only; it does not retune downstream directional-conviction threshold values.
- End-to-end broker-connected live execution remains out of scope for this pass; verification is based on focused/nearby automated tests.
- Runtime artifact `memory/generated_code_registry.json` continues to change as a side effect and remains intentionally uncommitted.
