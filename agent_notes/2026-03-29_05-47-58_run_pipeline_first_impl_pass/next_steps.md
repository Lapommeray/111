## Next steps (verified and prioritized)

1. Add one focused contract test for compact-output mode asserting `advanced_modules.final_direction/final_confidence` and blocker reason fallback remain present in compact payload when blocked.
2. Add one replay-evaluation boundary test that validates blocked records always include non-empty `blocker_reasons` in replay report artifacts.
3. If required by downstream consumers, document in code comments that `signal.setup_classification` is intentionally derived from effective/public confidence.
