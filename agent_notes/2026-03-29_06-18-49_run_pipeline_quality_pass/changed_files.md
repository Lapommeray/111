## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added focused decision-quality scenarios: strong setup, low-effective-confidence setup, manipulated/conflict setup, invalidated setup with open-position exit contract.
- `run.py`  
  Minimal final-decision guard: block BUY/SELL when `effective_signal_confidence` is below confidence threshold, with explicit blocker reason.
- `src/tests/test_run_pipeline_contract.py`  
  Updated macro-penalty scenario expectations to match tightened low-effective-confidence guard behavior.
- `agent_notes/2026-03-29_06-18-49_run_pipeline_quality_pass/summary.md`  
  Run summary and outcomes.
- `agent_notes/2026-03-29_06-18-49_run_pipeline_quality_pass/changed_files.md`  
  File-level change record.
- `agent_notes/2026-03-29_06-18-49_run_pipeline_quality_pass/tests.md`  
  Exact commands and pass/fail results.
- `agent_notes/2026-03-29_06-18-49_run_pipeline_quality_pass/next_steps.md`  
  Prioritized next actions from verified evidence.
- `agent_notes/2026-03-29_06-18-49_run_pipeline_quality_pass/risks.md`  
  Explicit uncertainty and review items.
- `agent_notes/2026-03-29_06-18-49_run_pipeline_quality_pass/evidence.md`  
  Issue-by-issue evidence map (where, proof, fix, result).
