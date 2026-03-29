## Next steps (evidence-based)

1. Add a focused test for borderline effective confidence exactly at threshold (`== min_confidence`) to verify current inclusive/exclusive policy is explicit and stable.
2. Add replay evaluation record-level test coverage that confirms the new confidence-based block consistently appears in downstream replay records as `confidence_below_threshold`.
3. Add one targeted scenario for conflicting directional votes with high effective confidence to verify abstain reasons remain explicit and non-blocking unless a hard blocker applies.
