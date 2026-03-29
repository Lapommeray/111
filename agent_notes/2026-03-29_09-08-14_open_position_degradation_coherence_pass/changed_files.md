## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added focused tests proving open-position WAIT->EXIT coherence gap in signal reasons and confidence/reason/action consistency.
- `run.py`  
  Minimal decision-assembly fix: when `decision == "WAIT"` and open position is `open` or `partial_exposure_unresolved`, append explicit transition reason `open_position_exit_management:<state_outcome_or_exit_reason>` to `signal.reasons`.
- `agent_notes/2026-03-29_09-08-14_open_position_degradation_coherence_pass/summary.md`  
  Pass summary and result.
- `agent_notes/2026-03-29_09-08-14_open_position_degradation_coherence_pass/changed_files.md`  
  File-level change list.
- `agent_notes/2026-03-29_09-08-14_open_position_degradation_coherence_pass/tests.md`  
  Exact commands and pass/fail outcomes.
- `agent_notes/2026-03-29_09-08-14_open_position_degradation_coherence_pass/next_steps.md`  
  Remaining top-ranked next tasks after this pass.
- `agent_notes/2026-03-29_09-08-14_open_position_degradation_coherence_pass/risks.md`  
  Verified residual risks.
- `agent_notes/2026-03-29_09-08-14_open_position_degradation_coherence_pass/evidence.md`  
  Exact gap -> failing tests -> minimal fix -> post-fix results.
