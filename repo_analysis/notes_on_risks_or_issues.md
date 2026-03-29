# Notes on Risks and Issues

## Architectural Risks

### 1. Monolithic run.py (3,906 lines)
`run.py` is a single file containing the entire orchestration layer. It includes:
- Config loading, validation, and CLI parsing
- Bar data loading
- MT5 readiness chain (~15 helper functions)
- Full MT5 live execution logic (entry, exit, retry, verification — ~1,600 lines)
- Evolution kernel
- Replay evaluation orchestration
- Signal/chart output construction

**Risk**: Any change to execution, evaluation, or config has a high chance of unintended side effects. Merge conflicts are highly likely in collaborative work.

### 2. Self-Evolving Indicator Layer (16,332 lines)
`src/learning/self_evolving_indicator_layer.py` is the largest file in the repo with 70+ functions. It contains:
- Pain memory survival layers
- Synthetic feature invention
- Negative space pattern recognition
- Temporal invariance break detection
- Pain geometry fields
- Counterfactual trade engine
- Fractal liquidity decay functions
- Execution microstructure intelligence
- Adversarial execution intelligence
- Market maker deception inference
- Intelligence gap discovery
- Synthetic data plane expansion
- Capability evolution governance
- Recursive self-modeling
- Structural memory graph
- Latent transition hazard

**Risk**: This module is only invoked through the knowledge expansion path (disabled by default). It has never been tested with real data in a production context. Its 70+ functions are heavily interdependent and share mutable state through the `memory/` directory.

### 3. All Data Is Synthetic
The `ensure_sample_data()` function generates a simple drift-based price series. All evaluation results are derived from this synthetic data. **No real market data is committed to the repo.** Evaluation metrics (win rate, drawdown, expectancy) are artifacts of synthetic price behavior, not market reality.

---

## Code Quality Issues

### 4. Duplicated Logic
- `_closed_outcomes()` is defined identically in at least 3 files: `self_evolving_indicator_layer.py`, `strategy/intelligence.py`, and `learning/live_feedback.py`
- `_drawdown()` and `_expectancy()` are defined in both `self_evolving_indicator_layer.py` and `replay_outcome.py`
- Direction/vote normalization logic appears in multiple places with slight variations

### 5. Module Names Are Misleading
Several module names suggest capabilities that don't match their implementation:
- **`quantum_tremor_scanner.py`**: No quantum computing. Computes micro-bar-range statistics.
- **`invisible_data_miner.py`**: Mines obvious bar/structure/liquidity cross features.
- **`human_lag_exploit.py`**: Computes delayed continuation statistics from bar data.
- **`spectral_signal_fusion.py`**: Not spectral analysis. Combines existing module outputs.
- **`meta_conscious_routing.py`**: Not consciousness. Routes based on regime + liquidity + volatility.
- **`self_destruct_protocol.py`**: Down-ranks failing logic; doesn't self-destruct.

These names may cause confusion during code review or onboarding.

### 6. Dead/Unused Code
- `quant-trading-system-main-12.zip` (13 MB): Not referenced by any code. Unclear provenance. Bloats the repo.
- `src/evolution/governance_report.py` (25 lines): Minimal stub, unclear if used outside tests.
- Many `memory/*.json` files are committed but may be regenerated at runtime by tests (known issue per repository memories).

### 7. No Error Logging
The system uses `print()` for final output. There is no structured logging (no `logging` module usage, no log files, no log levels). Failures in macro adapters, MT5 connections, and file I/O are silently caught and degraded.

---

## Testing Issues

### 8. Test Artifacts Contaminate Commits
Per stored repository memory: `pytest` regenerates `memory/` artifacts at runtime. The `report_progress` tool does `git add .` which stages them. Previous commits have accidentally included 100+ memory artifact files. The workaround is to `git checkout -- memory/` before committing.

### 9. Test Coverage Is Uneven
- **Well-tested**: Evaluation gates (completeness, quality, outcome, calibration), knowledge expansion phases, execution safety, filter gates
- **Lightly tested**: Core pipeline (`test_module_factory.py` = 33 lines), features (`test_features.py` = 124 lines), scoring (`test_scoring.py` = 47 lines)
- **Not directly tested**: `run_pipeline()` integration, MT5 live execution path, macro data collection with real APIs

### 10. 687 Tests May Give False Confidence
The large test count (687) is driven by the knowledge expansion, self-evolving layer, and execution gate tests — subsystems that are disabled by default or only run in specific modes. The core trading logic (market structure → confidence → direction → block/promote) has relatively fewer tests.

---

## Security / Operational Risks

### 11. API Keys in Config
`alpha_vantage_api_key` and `fred_api_key` are config keys with empty defaults. If populated, they'd be in `settings.json` which is committed. The `.gitignore` does not exclude `config/settings.json`.

### 12. MT5 Execution Safety
The MT5 execution path has extensive safety gates (11 pre-trade checks, readiness chain, quarantine state, fail-safe blocking, signal freshness). However, these have never been exercised against a real broker. Edge cases in order verification, partial fills, and position linkage are untested with live data.

### 13. Unbounded Memory File Growth
Many subsystems append to JSON files in `memory/`. There is no rotation, size limit, or cleanup mechanism for most of these files. Over time, files like `capability_lineage_history.json`, `evolution_registry.json`, and various governance state files could grow unboundedly.

---

## Completeness vs Original Design Prompt

The `PHASE1_CODEX_PROMPT.txt` specified a directory structure including:
- `docs/` (architecture.md, rules.md, research_notes.md) — **Not created**
- `logs/` (runtime.log, signals.log, errors.log) — **Not created**
- `data/raw/`, `data/processed/` — **Not created**
- `self_generated/` (generated_rules.json, generated_filters.py, generated_notes.md) — **Partially implemented** (rules in memory/, no generated_filters.py)

The prompt called for "no fake functionality or placeholder intelligence" — several module names (quantum, invisible, conscious) may violate the spirit of this rule, though their implementations are legitimate statistical computations.

---

## Summary of Priorities

| Priority | Issue | Effort |
|----------|-------|--------|
| High | Refactor run.py into smaller modules | Large |
| High | Replace synthetic data with real market data | Medium |
| High | Add structured logging | Medium |
| Medium | Remove or rename misleading module names | Small |
| Medium | Remove quant-trading-system-main-12.zip | Trivial |
| Medium | Deduplicate shared helpers | Small |
| Medium | Add .gitignore for config with secrets | Trivial |
| Low | Create docs/ directory per original spec | Small |
| Low | Add memory file rotation/cleanup | Medium |
| Low | Test core pipeline integration | Medium |
