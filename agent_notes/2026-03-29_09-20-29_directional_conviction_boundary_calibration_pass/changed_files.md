## Changed files

- `src/tests/test_run_pipeline_decision_quality.py`  
  Added focused directional-boundary tests for 4:3 and 5:4 slight-majority cases, covering weak vs strong conviction behavior and action/confidence/reason coherence.
- `run.py`  
  Minimal directional-conviction boundary refinement in existing decision assembly: allow margin-1 slight-majority only when high-sample/high-conviction/high-support conditions are met; otherwise keep degradation to WAIT.
- `agent_notes/2026-03-29_09-20-29_directional_conviction_boundary_calibration_pass/summary.md`  
  Pass summary and final result.
- `agent_notes/2026-03-29_09-20-29_directional_conviction_boundary_calibration_pass/changed_files.md`  
  File-level change inventory.
- `agent_notes/2026-03-29_09-20-29_directional_conviction_boundary_calibration_pass/tests.md`  
  Exact test commands and outcomes.
- `agent_notes/2026-03-29_09-20-29_directional_conviction_boundary_calibration_pass/next_steps.md`  
  Ranked remaining gaps after this pass.
- `agent_notes/2026-03-29_09-20-29_directional_conviction_boundary_calibration_pass/risks.md`  
  Residual risks and limitations.
- `agent_notes/2026-03-29_09-20-29_directional_conviction_boundary_calibration_pass/evidence.md`  
  Exact gap proof, minimal fix, and post-fix evidence.
