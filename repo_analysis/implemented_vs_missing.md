# Implemented vs Missing

## What Is Fully Implemented

### Core Pipeline (Functional)
- **Config loading & validation** (`run.py:337-461`): Loads JSON config, validates types, ranges, supported values. Robust.
- **Bar data loading** (`run.py:464-494`): From CSV files or memory snapshots. Works.
- **Market structure classification** (`src/features/market_structure.py`): Classifies bias (bullish/bearish/neutral) and regime from bar data.
- **Liquidity assessment** (`src/features/liquidity.py`): Detects liquidity sweeps, stop-runs, direction hints.
- **Base confidence scoring** (`src/scoring/confidence_score.py`): Derives confidence from structure + liquidity.
- **Advanced module pipeline** (`src/pipeline.py`): OversoulDirector wires 13 features, 5 filters, 4+ scoring modules, 1 memory module. Each produces direction votes, confidence deltas, and blocked flags.
- **Direction aggregation** (`src/utils.py:14-27`): Vote-based direction resolution (BUY/SELL/WAIT).
- **Confidence aggregation** (`src/utils.py:30-31`): Sum of deltas clamped to [0,1].
- **Filter gates** (`src/filters/`): Session, spread, conflict, memory, self-destruct filters. Each can block a trade.
- **Loss blocker** (`src/filters/loss_blocker.py`): Blocks when confidence < threshold or spread too wide.
- **Capital protection** (`src/risk/capital_guard.py`): Daily loss limits, drawdown limits, consecutive-loss streaks.
- **MT5 adapter** (`src/mt5/adapter.py`): Attempts MT5 connection, falls back to CSV. Controlled readiness checks.
- **Signal output** (`src/indicator/signal_model.py`, `indicator_output.py`, `chart_objects.py`): Builds final indicator output with chart objects and status panel.
- **Pattern store** (`src/memory/pattern_store.py`): JSON-file-backed persistence for patterns, blocked/promoted setups, trade outcomes.
- **Outcome tracking** (`src/memory/tracker.py`): Records and summarizes trade outcomes.
- **Self-coded rules** (`src/memory/self_coder.py`): Auto-generates rules from outcome history.
- **Signal intelligence** (`src/strategy/intelligence.py`): Scores signal quality using module feature contributions.

### Replay Evaluation System (Functional)
- **Replay evaluator** (`src/evaluation/replay_evaluator.py`): Steps through CSV data in windows, runs pipeline at each step, collects records with P&L, drawdown, trades.
- **Decision completeness gate** (`src/evaluation/decision_completeness.py`): Validates every record reaches a terminal state (actionable/blocked/abstain/invalid).
- **Decision quality gate** (`src/evaluation/decision_quality.py`): Validates distribution sanity, confidence diversity, reason quality.
- **Replay outcome gate** (`src/evaluation/replay_outcome.py`): Validates economic sanity (win rate, expectancy, max drawdown). Hard-fails on 0% win rate, negative expectancy with ≥2 closed trades.
- **Threshold calibration** (`src/evaluation/threshold_calibration.py`): Distributional P&L/drawdown stats with evidence-based threshold recommendations.
- **Drawdown comparison** (`src/evaluation/drawdown_comparison.py`): A/B comparison utility for attribution dicts.
- **Module contribution report** (`src/evaluation/module_contribution_report.py`): Per-module analysis.
- **Blocker effect report** / **Session report**: Analysis of blocker effectiveness and per-session performance.

### Evolution System (Functional but Mostly Theoretical)
- **Self-inspector** (`src/evolution/self_inspector.py`): Inspects project for coverage gaps.
- **Gap discovery** (`src/evolution/gap_discovery.py`): Identifies missing capabilities.
- **Code generator** (`src/evolution/code_generator.py`): Generates code proposals from gaps.
- **Verifier** (`src/evolution/verifier.py`): Validates generated proposals.
- **Architecture guard** (`src/evolution/architecture_guard.py`): Enforces architecture constraints.
- **Duplication audit** (`src/evolution/duplication_audit.py`): Detects duplicates.
- **Promoter** (`src/evolution/promoter.py`): Decides proposal status.
- **Evolution registry** (`src/evolution/evolution_registry.py`): Tracks lifecycle.
- **Knowledge expansion phases A-L** (`src/evolution/experimental_module_spec_flow.py`, `knowledge_expansion_orchestrator.py`): 12 phases of knowledge expansion. All implemented as pure computation — generate state files, never modify runtime behavior.

### Macro Data System (Implemented, External Dependencies)
- **Gold macro state** (`src/macro/gold_macro.py`): Comprehensive macro data collection (DXY, yields, calendar, COMEX, etc.).
- **Adapters** (`src/macro/adapters.py`): Alpha Vantage, FRED, Treasury, Economic Calendar, COMEX, ETF flows, option magnets, physical premiums, central bank reserves, MT5 DXY proxy. All require API keys or endpoints — gracefully degrade when unavailable.

### MT5 Live Execution (Implemented, Gated)
- **Live order placement** (`run.py:957-1113`): Full order lifecycle: send, verify deals, verify order acknowledgement, verify position linkage. Heavily gated behind readiness checks.
- **Exit/close logic** (`run.py:1740-1924`): Resolves positions to close, verifies disappearance.
- **Retry logic** (`run.py:1659-1738`): Single-retry with broker price resolution.
- **Signal lifecycle** (`run.py:535-608`): Age-based signal freshness validation.

### Self-Evolving Indicator Layer (Implemented, Never Executed in Main Path)
- **16,332 lines** (`src/learning/self_evolving_indicator_layer.py`): Massive module with 70+ functions covering pain memory, capability evolution, synthetic features, execution microstructure, adversarial intelligence, market-maker deception inference, liquidity decay, etc.
- Called only from `experimental_module_spec_flow.py` (knowledge expansion), which itself runs only when `knowledge_expansion_enabled=True` (default: False).

---

## What Is Missing or Incomplete

### No Real Market Data
- No actual XAUUSD CSV data with realistic price action is committed. The `ensure_sample_data()` function (run.py:226-259) generates synthetic data with a simple drift formula. All evaluation runs against this synthetic data.

### No Live MT5 Connection
- MT5 adapter always falls back to CSV because no MT5 terminal is available in this environment. The entire MT5 execution path is implemented but untestable without a real broker.

### No External API Keys Configured
- `alpha_vantage_api_key`, `fred_api_key` default to empty strings. All macro adapters degrade gracefully but produce no real data.

### No Documentation
- The `docs/` directory mentioned in PHASE1_CODEX_PROMPT.txt was never created. No architecture.md, rules.md, or research_notes.md exist.

### No Logging Infrastructure
- The `logs/` directory mentioned in the prompt was never created. No runtime.log, signals.log, or errors.log. The system uses `print()` for output.

### No Data Processing Pipeline
- The `data/raw/`, `data/processed/` directories mentioned in the prompt were never created.

### Walk-Forward Validation
- Config key exists (`walk_forward_enabled`, defaults to False). The replay evaluator has walk-forward window logic, but it is disabled by default and has no documentation on expected usage.

### Continuous Governed Improvement
- Runs only when `knowledge_expansion_enabled=True`. Produces JSON state files. Does not actually modify the runtime pipeline or promote changes.
