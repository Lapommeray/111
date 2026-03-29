## Task
Handle the remaining live-only validation boundary after deterministic repo-level checks:
1) map exact live-only unverified scope,
2) assess live observability readiness,
3) produce explicit live validation plan,
4) state final live-boundary status.

## What I did
- Traced live MT5 execution and verification paths in `run.py` and aligned them with execution/memory tests.
- Mapped exact live-only categories with file/function evidence.
- Identified one concrete observability gap: delayed broker recheck timing metadata was not explicit enough for live postmortem timelines.
- Applied minimal architecture-preserving observability instrumentation in `run.py` (no execution policy change).
- Added focused assertions in execution-gate tests and re-ran nearby regressions.

## Final result
- Deterministic repo-level scope remains complete.
- Live-only boundary is now more auditable via explicit delayed-recheck metadata in broker verification payloads.
- Remaining uncertainty is strictly broker/network runtime behavior requiring real live artifacts.
