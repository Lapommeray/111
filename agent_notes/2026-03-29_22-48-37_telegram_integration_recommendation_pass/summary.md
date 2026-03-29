## Task
Inspect the current repository and recommend the safest, simplest Telegram integration path for final actionable signals only (`BUY`, `SELL`, `EXIT`) without architecture rewrite or risky refactor.

## What I did
- Inspected the exact final output assembly path in `run.py` and indicator output models.
- Verified where actionable signal and contract fields are finalized.
- Verified no existing Telegram/alert sender exists in the repository.
- Assessed safest integration options for this codebase and selected the lowest-risk pattern.

## Final result
- Recommended a minimal sidecar/wrapper integration that consumes existing `run_pipeline` output and sends Telegram alerts only for final actions (`BUY`, `SELL`, `EXIT`).
- Recommended avoiding direct send logic inside `run_pipeline` to keep the signal engine deterministic and isolated.
- Defined a minimum Telegram payload schema and duplicate-prevention approach using existing output fields.
