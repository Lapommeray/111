## Next steps (ranked from updated audited state)

1. Add targeted open-position degradation tests where setup quality collapses and verify signal confidence, signal action, and `entry_exit_decision.action` remain coherent during EXIT/no-entry transitions.
2. Add focused feature-layer edge tests for displacement/FVG/liquidity manipulated patterns to reduce false-clean entries at source.
3. Add boundary tests for directional conviction around 4:3 and 5:4 splits to verify BUY/SELL vs WAIT threshold behavior is intentional and stable.
