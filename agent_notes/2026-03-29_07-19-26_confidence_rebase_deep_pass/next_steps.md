## Next steps (verified and prioritized)

1. Add one focused test for multi-cause non-blocked degradation (both vote-margin and conviction) to confirm confidence rebase remains bounded and reasons stay complete.
2. Add one focused replay-evaluation artifact test ensuring abstain records produced by directional degradation carry low confidence consistently in persisted records.
3. Evaluate whether directional-conviction threshold should be symbol/timeframe-specific via existing config only, but only if failing evidence shows current fixed threshold causes false abstains.
