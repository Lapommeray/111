# VERIFIED METRICS SUMMARY

## Actual Performance Numbers (From Repository Artifacts)

| Metric | Value | Source |
|--------|-------|--------|
| **Win Rate** | 0.0% | memory/system_monitor/performance_metrics.json |
| **Closed Trades** | 0 | memory/system_monitor/performance_metrics.json |
| **Drawdown** | 0.0 | memory/system_monitor/performance_metrics.json |
| **Execution Failures** | 0 | memory/system_monitor/performance_metrics.json |
| **Total P&L (points)** | 0.0 | memory/trade_outcomes.json (all entries: pnl_points=0.0) |
| **Net Expectancy** | 0.0 | Replay evaluation output |
| **OOS Win Rate** | N/A | walk_forward_enabled=false, never run |
| **Walk-Forward Results** | N/A | Not performed |
| **Sample Size** | 0 trades | No trades ever taken |

## Replay Evaluation Results (Run 2026-03-30)

| Metric | Value | Source |
|--------|-------|--------|
| **Total Steps** | 21 | replay_evaluation_report.json |
| **BUY Signals** | 0 | action_distribution |
| **SELL Signals** | 0 | action_distribution |
| **WAIT Signals** | 21 | action_distribution |
| **Blocked Signals** | 12 | signal_counts.blocked |
| **Actionable Signals** | 0 | signal_counts |
| **Top Blocker** | structure_liquidity_conflict (10/21) | blocker_effect_report |
| **Second Blocker** | structure_liquidity_conflict_soft (10/21) | blocker_effect_report |
| **Confidence Distribution** | low=19, medium=2, high=0 | confidence_distribution |

## Persisted Memory Artifacts (From memory/ directory)

| Artifact | Value | Source |
|----------|-------|--------|
| **Meta Adaptive Win Rate** | 0.0% | memory/meta_adaptive_profile.json |
| **Meta Adaptive Samples** | 0 | memory/meta_adaptive_profile.json |
| **Preferred Direction** | WAIT | memory/meta_adaptive_profile.json |
| **Strategy Confidence Win Rate** | 0.5 (default) | memory/strategy_intelligence/strategy_confidence_state.json |
| **Daily Loss (points)** | 0.0 | memory/risk_state/capital_guard_state.json |
| **Consecutive Loss Streak** | 0 | memory/risk_state/capital_guard_state.json |
| **Emergency Stop** | false | memory/risk_state/capital_guard_state.json |
| **Trade Refused** | false | memory/risk_state/capital_guard_state.json |

## Are We "Winning 99%"?

**NO. The exact real number is 0.0% win rate on 0 trades.**

- The system has never taken a single trade.
- There are zero wins, zero losses, zero P&L data points.
- 99% is not supported by any evidence in the repository.
- All 21 replay evaluation signals resulted in WAIT (no BUY or SELL).
- There is no statistical basis for any performance claim.
- The test suite (779 tests) validates code correctness, NOT trading performance.

## Statistical Significance

- **Sample size:** 0 closed trades → **No statistical significance possible**
- **Minimum required:** ≥30 trades for basic reliability, ≥100 for moderate confidence, ≥500 for high confidence
- **Sharpe ratio:** Cannot compute (no returns)
- **Sortino ratio:** Cannot compute (no returns)
- **P-value tests:** None implemented in the codebase
- **Bootstrap/permutation tests:** None implemented
