## Risks

- End-to-end broker-connected live execution is still unverified in this pass; all evidence is from focused and nearby automated tests/stubs.
- Confidence rebasing now covers three abstain/degradation pathways (directional degradation, execution refusal, and non-blocked WAIT final action). Additional abstain pathways should still be explicitly tested as coverage expands.
- Runtime-generated artifact `memory/generated_code_registry.json` continues to change during runs and is intentionally uncommitted.
