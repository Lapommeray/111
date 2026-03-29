## Live validation completion criteria (current project stage)

### Minimum successful runs required per scenario class
- **A (send/linkage timing race)**: at least 3 successful artifact-backed runs across separate sessions.
- **B (exit close delay window)**: at least 3 successful runs with at least 1 delayed-recheck-attempted case.
- **C (retry/refusal under latency)**: at least 3 successful runs with at least 1 `retry_attempted_count=1` case and at least 1 fail-closed blocked retry case.
- **D (spread-sensitive near threshold)**: at least 3 successful runs with one below-threshold and one above-threshold observation.
- **E (macro pause during open-position management)**: at least 2 successful runs with pause active and open-position management context visible.
- **F (network interruption/partition effects)**: at least 2 successful runs showing explicit fail-closed reason classification and coherent downstream contract.
- **G (reconciliation mismatch over time)**: at least 3 successful multi-snapshot reviews using `mt5_controlled_execution_history.json`.

### Evidence required to mark a scenario stable
- One filled `live_run_evidence_template.md` per run, with non-empty artifact paths.
- For each run, explicit pass/fail verdict and exact fields inspected:
  - verification payload fields
  - delayed-recheck timeline metadata
  - retry/refusal metadata (where applicable)
  - `signal.action`, `signal.confidence`, `signal.reasons`, `signal.blocker_reasons`, `signal.classification`
  - `status_panel.entry_exit_decision.action`, `reason`, `invalidation_reason`, `open_position_state.*`
- No unresolved contradictions between:
  - broker verification outcome,
  - final signal reasons/classification/action/confidence,
  - entry/exit decision contract,
  - and open-position state progression.

### Failure repetition threshold that requires return to code/test pass
- Return to deterministic code/test investigation if any of the following happens:
  - the **same failure signature** occurs in 2 or more runs for the same scenario class, or
  - one high-severity contradiction appears (for example, confirmed broker close with persistent `open_position_state.status=open` and no coherent transition reason), or
  - artifact fields required for postmortem are repeatedly missing despite expected branch execution.

### What can be considered closed at this stage
- A scenario class can be marked **stage-closed** when:
  - minimum successful runs are met,
  - no repeated failure signature remains unresolved,
  - and all runs have complete artifact-backed evidence with coherent action/confidence/reasons/contract outcomes.
- Deterministic repo-level readiness remains closed unless new live artifacts justify reopening it.

### What remains open even after initial live validation
- Broker/network non-determinism cannot be permanently “closed”; it remains an operational risk surface requiring ongoing monitoring.
- Extreme rare timing/race edges remain open until observed (or until sufficient longitudinal live evidence accumulates).
- No claim of “99%” is justified from this stage alone without larger live evidence volume and project-level evaluation artifacts.
