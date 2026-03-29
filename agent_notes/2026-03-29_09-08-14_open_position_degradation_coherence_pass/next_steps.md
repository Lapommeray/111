## Next steps (ranked from updated repository state)

1. Add focused directional-conviction boundary tests around 4:3 and 5:4 vote splits to verify BUY/SELL vs WAIT threshold behavior is intentional and stable.
2. Add explicit spread-filter boundary tests (`== threshold`, `> threshold by epsilon`) to tighten false-block precision.
3. Expand open-position degradation coverage for unresolved exit-close retry paths to verify reason propagation stays coherent under repeated non-confirmation outcomes.
