## Exact current status

### A) Already proven by deterministic repo-level work
- Decision/exit coherence for scoped logic is deterministic-proven in repository tests from prior passes:
  - confidence/action/reason coherence in WAIT/degradation/open-position paths,
  - unresolved-exit retry reason propagation to final signal reasons,
  - replay-vs-live parity guards for intentional differences,
  - verification timeline metadata persistence and contract consistency.
- This master package does not reopen deterministic validation and does not alter that status.

### B) Already prepared for live MT5 validation
- Runtime paths and artifact capture are confirmed ready:
  - MT5 controlled execution path,
  - broker linkage/exit/partial verification payloads,
  - delayed-recheck timeline fields,
  - retry/refusal metadata,
  - final signal reason propagation,
  - entry/exit decision contract assembly,
  - artifact/state/history persistence files.
- Existing operational scaffolding is already prepared and now consolidated here:
  - scenario order,
  - per-scenario review protocol,
  - escalation mapping,
  - completion criteria,
  - operator packets,
  - worksheets.

### C) Still requires real live artifacts
- Live MT5 behavior that cannot be closed by deterministic harness alone:
  - send/linkage timing race outcomes,
  - delayed close confirmation windows,
  - retry/refusal behavior under true latency/tick timing,
  - spread-near-threshold behavior under live feed conditions,
  - macro pause interactions in live managed-exit context,
  - verification behavior under network interruption,
  - longitudinal reconciliation consistency across history.

### D) Outside harness scope
- Real broker/network nondeterminism remains outside full deterministic proof.
- Claims about robust live behavior require artifact-backed live runs, not code inspection alone.
- No claim of “99%” is justified without substantial live evidence volume and project-level evaluation artifacts.
