## Risks / constraints

- This pass improved scoring behavior in `spectral_signal_fusion` only; it did not retune all feature/filter/scoring thresholds.
- End-to-end broker-connected MT5 live execution quality was not run in this pass; validation is code-level tests and targeted pipeline regressions.
- Runtime artifact `memory/generated_code_registry.json` remains modified by runtime side effects and is intentionally uncommitted.
