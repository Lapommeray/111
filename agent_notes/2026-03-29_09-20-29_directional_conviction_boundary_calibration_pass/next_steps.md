## Next steps (ranked from updated repository state)

1. Add explicit spread-filter threshold boundary tests (`spread_points == max_spread_points` and `spread_points > max_spread_points`) to tighten false-block precision.
2. Expand unresolved exit-close retry scenario coverage to verify reason propagation coherence under repeated non-confirmed close outcomes.
3. Add one additional directional boundary test around 6:5 to confirm margin-1 override remains conservative and does not over-permit weak setups.
