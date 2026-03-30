# REALISTIC METRICS SUMMARY

## Assessment Date: 2026-03-30

---

## Test Suite Metrics

| Metric | Value | Source |
|--------|-------|--------|
| Total tests | 779 | `python3 -m pytest src/tests/ -q` |
| Passed | 779 | Same |
| Failed | 0 | Same |
| Duration | ~29s | Same |

**Tests verify code correctness, NOT trading performance.**

---

## Replay Evaluation Metrics (Actual Run)

| Metric | Value | Source |
|--------|-------|--------|
| Total replay steps | 21 | `memory/replay_evaluation_report.json` |
| BUY signals | **0** | `action_distribution.BUY` |
| SELL signals | **0** | `action_distribution.SELL` |
| WAIT signals | **21** | `action_distribution.WAIT` |
| Blocked signals | 12 | `signal_counts.blocked` |
| Abstained signals | 9 | `decision_completeness.counts.abstain` |
| Actionable signals | **0** | `decision_completeness.counts.actionable` |
| Closed trades | **0** | `analytics_summary.closed_trade_count` |
| Win count | 0 | `analytics_summary.win_count` |
| Loss count | 0 | `analytics_summary.loss_count` |
| **Win rate** | **0.0%** | `analytics_summary.win_rate` |
| Gross PnL | 0.0 pts | `analytics_summary.average_gross_pnl_points` |
| Net PnL | 0.0 pts | `analytics_summary.average_net_pnl_points` |
| Expectancy | 0.0 pts | `analytics_summary.expectancy_points` |
| Max drawdown | 0.0 pts | `analytics_summary.max_drawdown_points` |
| Profit factor | None | `analytics_summary.profit_factor` |

---

## Out-of-Sample (OOS) Metrics

| Metric | Value | Source |
|--------|-------|--------|
| Walk-forward enabled | **false** | `config/settings.json:20` |
| OOS closed trades | 0 | `total_oos_closed_trades` |
| OOS win rate | 0.0% | `oos_win_rate` |

**No OOS validation has been performed.**

---

## Execution Cost Configuration

| Setting | Value | Realistic? |
|---------|-------|------------|
| Spread cost | 0.0 pts | ❌ Should be 2-5 pts for XAUUSD |
| Commission cost | 0.0 pts | ❌ Broker-dependent |
| Slippage cost | 0.0 pts | ❌ Should be 0.5-2 pts |
| Realism v2 enabled | false | ❌ |
| Calibration status | `temporary_defaults_pending_broker_measurement` | ❌ |

---

## Data Quality

| Item | Value |
|------|-------|
| Data file | `data/samples/xauusd.csv` |
| Rows | 320 |
| Type | **Synthetic** (auto-generated) |
| Generator | `ensure_sample_data()` in `run.py:226-259` |
| Pattern | Deterministic linear drift: up 14pts → down 7pts → up 10pts |
| Time intervals | Uniform 60-second gaps |
| Data sufficiency tier | `insufficient` |

---

## Module Vote Analysis (Why Zero Trades)

| Category | Count | Modules |
|----------|-------|---------|
| Always neutral (never vote directional) | 16 | displacement, compression_expansion, fvg*, volatility, sessions, spread_state, spread_filter, session_filter, session_behavior, self_destruct_protocol, setup_score, regime_score, execution_quality, meta_adaptive_ai, quantum_tremor_scanner, human_lag_exploit |
| Can vote directional | 7 | conflict_filter, memory_filter, invisible_data_miner, market_regime, spectral_signal_fusion, liquidity_sweep, meta_conscious_routing |

*fvg can theoretically vote directional but returned neutral on all 21 synthetic data windows

**Max possible directional votes: 8 (7 modules + 1 base direction)**
**Always-neutral votes (counted as WAIT): 16**
**Required for BUY: buy >= wait → 8 >= 16 → IMPOSSIBLE**

---

## Blocker Breakdown (21 Signals)

| Blocker Reason | Count | % |
|----------------|-------|---|
| `structure_liquidity_conflict` (hard) | 10 | 47.6% |
| `advanced_direction=WAIT` (neutral majority) | 9 | 42.9% |
| `confidence_below_threshold` | 2 | 9.5% |

---

## "99% Win Rate" Verification

**The exact verified number is: 0.0% win rate on 0 trades.**

| Claim | Evidence | Verdict |
|-------|----------|---------|
| "99% win rate" | No trades ever executed | **FALSE — undefined (0/0)** |
| | No evaluation produced any trade | |
| | No walk-forward OOS results exist | |
| | No real market data tested | |

**Source:** `memory/replay_evaluation_report.json` → `replay_outcome.win_rate: 0.0`, `replay_outcome.closed_trades: 0`

---

## Statistical Significance

| Requirement | Status |
|-------------|--------|
| Minimum 30 trades for basic significance | ❌ 0 trades |
| 100+ trades for reliable statistics | ❌ 0 trades |
| OOS validation | ❌ Not performed |
| Multiple market regimes tested | ❌ Only synthetic data |
| Results statistically meaningful? | **NO — zero sample size** |
