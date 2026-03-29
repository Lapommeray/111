## Risks

- End-to-end broker-connected live execution and true broker reconciliation behavior are still unverified in this pass; tests use controlled/stubbed execution payloads.
- The fix attaches explicit open-position management reason in non-blocked WAIT paths; additional scenario expansion may still be needed for rare mixed refusal + open-position states.
- Runtime-generated artifact `memory/generated_code_registry.json` remains modified during tests and intentionally uncommitted.
