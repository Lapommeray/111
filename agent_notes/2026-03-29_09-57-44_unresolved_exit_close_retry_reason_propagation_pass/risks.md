## Risks

- Live broker-connected repeated close-confirmation behavior is still not validated in this pass; tests use deterministic controlled/stubbed execution payloads.
- The new propagation is intentionally scoped to non-blocked WAIT paths with `open`/`partial_exposure_unresolved` state and available retry/refusal metadata.
- Runtime-generated artifact `memory/generated_code_registry.json` continues to change during test runs and is intentionally uncommitted.
