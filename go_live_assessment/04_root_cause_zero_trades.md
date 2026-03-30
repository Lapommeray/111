# ROOT CAUSE: ZERO TRADES

## Assessment Date: 2026-03-30

---

## Summary

The system produces 0 trades because of **two independent blockers**, both of which would need to be resolved for any trade to occur.

---

## Root Cause #1: Structure-Liquidity Conflict Blocker (12/21 signals)

### What happens
The `LossBlocker.evaluate()` function detects when market structure direction conflicts with liquidity direction during a sweep event.

### Code path
```
run.py:3152 → LossBlocker.evaluate()
  → src/filters/loss_blocker.py:33-41
    → IF structure.bias != liquidity.direction_hint
    → AND liquidity_state == "sweep"
    → AND liquidity.score >= 0.7
    → THEN blocked = True, reason = "structure_liquidity_conflict"
```

### Why it triggers on sample data
The synthetic data has three phases (up/down/up). The 220-bar evaluation window spans phase transitions, creating:
- **Structure bias:** Based on last 20 bars → detects the LOCAL trend
- **Liquidity hint:** Based on sweep detection → sees the OPPOSITE pattern from the recent high/low

In phase 2→3 transition: structure sees downtrend (sell), but liquidity sweeps recent lows → hints buy. **Legitimate conflict, correctly blocked.**

In phase 3: structure sees uptrend (buy), but price sweeps through phase-2 highs → liquidity hints sell. **Again legitimate conflict.**

### Would this happen on real data?
Yes, but less uniformly. Real markets have genuine alignment periods. This blocker would fire ~30-40% of the time, not 57%.

---

## Root Cause #2: Neutral Vote Majority in aggregate_direction() (9/21 signals)

### What happens
Even when the conflict blocker does NOT fire, the direction consensus vote returns WAIT because neutral votes outnumber directional votes.

### Code path
```
src/pipeline.py:231-234 → aggregate_direction(base_direction, all_votes)
  → src/utils.py:14-26
    → Counts: buy, sell, wait (neutral counted as wait)
    → Returns BUY only if buy > sell AND buy >= wait
    → With 16+ neutral votes, buy can never >= wait
```

### Exact vote count at a typical non-blocked step (e.g., step 5)

| Vote type | Source | Count |
|-----------|--------|-------|
| BUY | base_direction | 1 |
| BUY | conflict_filter (relays base) | 1 |
| BUY | memory_filter (relays base) | 1 |
| BUY | invisible_data_miner (slope>0) | 1 |
| BUY | market_regime | 1 |
| BUY | spectral_signal_fusion | 1 |
| **BUY total** | | **6** |
| SELL | liquidity_sweep | 1 |
| SELL | meta_conscious_routing | 1 |
| **SELL total** | | **2** |
| NEUTRAL→WAIT | displacement, fvg, sessions, volatility, compression_expansion, spread_state, spread_filter, session_filter, session_behavior, self_destruct_protocol, setup_score, regime_score, execution_quality, meta_adaptive_ai, quantum_tremor_scanner, human_lag_exploit | **16** |

**Aggregation result:** `buy(6) > sell(2)` ✓ but `buy(6) >= wait(16)` ✗ → **WAIT**

### This is a STRUCTURAL impossibility, not a data issue

These 16 modules are hardcoded to return `direction_vote: "neutral"`:
1. `displacement.py` — always returns `neutral`
2. `sessions.py` — always returns `neutral`
3. `volatility.py` — always returns `neutral`
4. `spread_state.py` — always returns `neutral`
5. `compression_expansion.py` — always returns `neutral` (from pipeline, not feature code)
6. Plus scoring modules: `regime_score`, `setup_score`, `execution_quality`, `session_filter`, `spread_filter`, `self_destruct_protocol`, `session_behavior`, `meta_adaptive_ai`

Even on perfect real market data with aligned structure/liquidity, these modules will still return neutral, making it impossible for directional votes to reach majority.

---

## Root Cause #3: Additional Gate — Directional Conviction (would block even if #2 was fixed)

### Code path
```
run.py:3288-3313
  → directional_conviction = (final_confidence * 0.7) + (support_ratio * 0.2) + (margin_ratio * 0.1)
  → IF conviction < 0.62 → WAIT
  → IF vote_margin < 2 (and no slight_majority_override) → WAIT
```

### Impact
Even if `aggregate_direction()` was fixed to return BUY, the directional conviction gate provides secondary protection. With only 6 buy votes vs 2 sell votes, margin = 4 and support_ratio = 0.75, so this gate would likely pass IF confidence is adequate.

---

## Decision Tree Summary

```
Signal arrives
├── Is there structure-liquidity conflict? (sweep + score >= 0.7)
│   ├── YES → WAIT (12/21 signals) ← Root Cause #1
│   └── NO → Continue
│
├── Does aggregate_direction produce BUY/SELL?
│   ├── NO (neutral majority: 16 > 8) → WAIT (9/21 signals) ← Root Cause #2
│   └── YES (never reaches here) → Continue
│
├── Is directional conviction >= 0.62?
│   ├── NO → WAIT ← Root Cause #3
│   └── YES → Continue
│
└── Place order (never reached)
```

---

## Fix Required

The minimum fix to enable trading:

**Option A (Recommended): Modify `aggregate_direction()` to ignore neutral votes**
```python
def aggregate_direction(base_direction: str, votes: list[str]) -> str:
    # Only count active votes (buy/sell/wait), not neutral
    active = [v.lower() for v in votes if v.lower() in {"buy", "sell", "wait"}]
    active.append(base_direction.lower())
    # ... rest of logic unchanged
```
This would let 6 buy votes vs 2 sell + 0 wait = BUY (6 > 2 and 6 >= 0).

**Option B: Add directional votes to currently-neutral modules**
Have modules like displacement, sessions, volatility return directional votes when they detect patterns.

**Option C: Weight-based aggregation instead of majority vote**
Replace simple vote counting with confidence-weighted direction scoring.

**Any fix requires full re-evaluation with realistic data and costs before live deployment.**
