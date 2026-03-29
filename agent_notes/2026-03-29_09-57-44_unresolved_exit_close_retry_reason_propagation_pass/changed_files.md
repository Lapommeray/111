## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added focused unresolved-exit-close retry reason-propagation test for open-position exit management path coherence.
- `run.py`  
  Minimal reason-propagation fix in existing decision assembly for unresolved open-position close/retry states:
  - propagate `rollback_refusal_reasons` into `signal.reasons` as `open_position_exit_retry:<reason>`
  - propagate `order_result.retry_policy_truth` into `signal.reasons` as `open_position_exit_retry_policy:<policy>`.
- `agent_notes/2026-03-29_09-57-44_unresolved_exit_close_retry_reason_propagation_pass/summary.md`  
  Pass summary and verified result.
- `agent_notes/2026-03-29_09-57-44_unresolved_exit_close_retry_reason_propagation_pass/changed_files.md`  
  File-level change list.
- `agent_notes/2026-03-29_09-57-44_unresolved_exit_close_retry_reason_propagation_pass/tests.md`  
  Exact commands and pass/fail outcomes.
- `agent_notes/2026-03-29_09-57-44_unresolved_exit_close_retry_reason_propagation_pass/next_steps.md`  
  Remaining ranked gaps after this pass.
- `agent_notes/2026-03-29_09-57-44_unresolved_exit_close_retry_reason_propagation_pass/risks.md`  
  Residual risks and limitations.
- `agent_notes/2026-03-29_09-57-44_unresolved_exit_close_retry_reason_propagation_pass/evidence.md`  
  Exact defect proof, minimal fix, and post-fix results.
