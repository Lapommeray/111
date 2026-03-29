## Task
Execute the ranked next gap: directional-conviction boundary behavior around 4:3 / 5:4 slight-majority splits.

## What I did
- Read prior audit/pass artifacts as source-of-truth.
- Traced directional-conviction path in `run.py`:
  - directional vote counting
  - margin/support ratio computation
  - degradation branch for weak conviction or insufficient margin
  - confidence/reason wiring.
- Added focused boundary tests:
  - 4:3 degrades to WAIT coherently.
  - 5:4 degrades when conviction is weak.
  - 5:4 remains tradable when conviction is strong.
- Proved current blunt behavior defect with failing test (`5:4 strong` still forced WAIT).
- Applied minimal fix in directional decision assembly only.
- Re-ran focused plus nearby regression suites.

## Final result
- Boundary behavior is now less blunt and test-backed:
  - 4:3 still degrades to WAIT.
  - 5:4 weak conviction degrades to WAIT.
  - 5:4 high-conviction/high-sample scenario remains tradable.
- Combined targeted+nearby regression verification: `38 passed`.
