## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added a focused failing test proving execution-refusal downgrade to WAIT still left confidence too high.
- `run.py`  
  Minimal fix in execution-refusal branch: rebase confidence (cap `<= 0.59`) when action is downgraded to WAIT due to execution refusal.
- `agent_notes/2026-03-29_07-49-22_execution_refusal_confidence_pass/summary.md`  
  Summary of this pass.
- `agent_notes/2026-03-29_07-49-22_execution_refusal_confidence_pass/changed_files.md`  
  File-level inventory for this pass.
- `agent_notes/2026-03-29_07-49-22_execution_refusal_confidence_pass/tests.md`  
  Exact commands and outcomes.
- `agent_notes/2026-03-29_07-49-22_execution_refusal_confidence_pass/next_steps.md`  
  Verified next actions.
- `agent_notes/2026-03-29_07-49-22_execution_refusal_confidence_pass/risks.md`  
  Explicit risks/constraints.
- `agent_notes/2026-03-29_07-49-22_execution_refusal_confidence_pass/evidence.md`  
  Exact issue -> proof -> minimal fix -> post-fix result mapping.
