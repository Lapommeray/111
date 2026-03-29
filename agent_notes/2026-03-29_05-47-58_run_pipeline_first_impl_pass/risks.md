## Risks / uncertainty

- This pass made no changes to feature/filter/scoring module internals because new contract failures were isolated to final signal assembly in `run.py`.
- Live MT5 broker execution behavior was not validated end-to-end in this pass; tests are scoped to replay/live pipeline decision contracts via local test stubs and fixtures.
- Local runtime artifact `memory/generated_code_registry.json` remains modified by runtime side effects and is intentionally not committed.
