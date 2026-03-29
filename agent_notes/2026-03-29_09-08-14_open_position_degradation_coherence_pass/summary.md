## Task
Execute the top-ranked remaining gap from prior audited state: open-position degradation confidence/action/reason coherence.

## What I did
- Read prior audit artifacts as source-of-truth:
  - `current_state_inventory.md`
  - `coverage_map.md`
  - `remaining_gaps_ranked.md`
  - `evidence.md`
- Traced exact open-position path in `run.py`:
  - open-position representation in controlled execution artifact
  - open/partial status to `entry_exit_decision` EXIT transition logic
  - confidence/reasons attachment in final decision assembly
- Added failing focused tests proving signal-level transition reason gap for open-position WAIT->EXIT management paths.
- Applied a minimal fix in `run.py` to append explicit open-position transition reason for non-blocked WAIT with open/partial position.
- Re-ran focused tests plus nearby execution/exit and pipeline regressions.

## Final result
- Proven and fixed: when open position status forced EXIT contract while signal action remained WAIT, signal reasons lacked explicit transition cause.
- Now signal reasons include explicit open-position management transition reason, with confidence/action/reasons coherent for open and partial exposure paths.
- Combined targeted + nearby regression run passed: `35 passed`.
