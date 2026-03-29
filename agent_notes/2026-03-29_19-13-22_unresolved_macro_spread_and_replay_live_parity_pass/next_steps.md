## Deterministic repo-level remaining work
- None identified for the explicitly requested deterministic checks in this stage (Phase 1 + Phase 2 are now test-locked and green).
- Any further deterministic changes should start from a new failing scenario not yet covered by current decision-quality/contract/execution suites.

## Outside-harness / live-only remaining work
- Broker/network/timing-dependent MT5 behaviors remain outside deterministic harness scope (e.g., true terminal latency spikes, broker-specific retcode timing races, network partitions during confirmation windows).
- These require controlled live/broker validation artifacts, not repository-only assertions.
