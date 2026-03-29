## Task
Inspect the repository to identify the exact modules/files and execution flow for the trading indicator pipeline, then propose the next three implementation steps without architecture drift.

## What I did
- Verified the pipeline entrypoint and orchestration in `run.py`, including `main()`, `run_pipeline()`, and `run_replay_evaluation()`.
- Verified advanced module execution in `src/pipeline.py` (`run_advanced_modules`, `OversoulDirector`, `state_to_dict`).
- Verified final indicator contract builders in `src/indicator/signal_model.py`, `src/indicator/chart_objects.py`, and `src/indicator/indicator_output.py`.
- Verified replay path reuse via `src/evaluation/replay_evaluator.py` (`pipeline_runner=run_pipeline` model).

## Why
To safely continue indicator work using the existing architecture and avoid replacing or bypassing current flow.

## Verified current flow (short)
1. CLI `main()` loads config and dispatches to `run_pipeline()` (or replay evaluation path).
2. `run_pipeline()` loads bars/readiness, computes structure+liquidity+base confidence.
3. `run_pipeline()` executes `run_advanced_modules()` for features/filters/scoring aggregation.
4. `run_pipeline()` applies macro/risk/block/decision logic, persists outcomes, then builds output.
5. Final response is assembled by `build_signal_output` -> `build_chart_objects` -> `build_status_panel` -> `build_indicator_output`.
6. Replay evaluation repeatedly invokes the same `run_pipeline()` through `evaluate_replay()`.

## Next 3 implementation steps (priority)
1. Add/extend pipeline contract tests around `run_pipeline()` output shape and key indicator payload keys.
2. Implement only missing indicator behavior inside existing feature/filter/scoring modules and `run_advanced_modules` wiring.
3. Add focused replay/live scenario tests to validate final decision/reason/confidence behavior after the minimal logic change.

## Final result
Inspection complete with architecture-preserving plan and no source-code architecture rewrite.
