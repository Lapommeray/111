## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added focused failing test proving confidence stayed too high after non-blocked directional degradation to WAIT in a slight-majority setup.
- `run.py`  
  Minimal decision-assembly fix: rebase confidence (cap to `<= 0.59`) when BUY/SELL degrades to WAIT due to directional degradation reasons and not hard-block conditions.
- `agent_notes/2026-03-29_07-19-26_confidence_rebase_deep_pass/summary.md`  
  Summary of this pass.
- `agent_notes/2026-03-29_07-19-26_confidence_rebase_deep_pass/changed_files.md`  
  File-level change inventory.
- `agent_notes/2026-03-29_07-19-26_confidence_rebase_deep_pass/tests.md`  
  Exact commands and outcomes.
- `agent_notes/2026-03-29_07-19-26_confidence_rebase_deep_pass/next_steps.md`  
  Verified next actions.
- `agent_notes/2026-03-29_07-19-26_confidence_rebase_deep_pass/risks.md`  
  Explicit constraints and risks.
- `agent_notes/2026-03-29_07-19-26_confidence_rebase_deep_pass/evidence.md`  
  Exact issue → test proof → minimal fix → post-fix result.
