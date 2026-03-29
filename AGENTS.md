# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a **XAUUSD (Gold) quantitative trading indicator system** — a pure Python codebase with no web framework, no database, and no Docker. It reads market data, classifies market structure, applies aggressive trade filtering, and outputs BUY/SELL/WAIT signals.

### Tech Stack

- **Language:** Python 3.12+ (stdlib only at runtime; `MetaTrader5` package is optional and only for live trading on Windows)
- **Testing:** `pytest` (the sole dev dependency)
- **Persistence:** JSON files in `memory/` directory; no database

### Running Tests

```bash
python3 -m pytest src/tests/ -v --tb=short
```

All ~696 tests are pure-Python unit/integration tests with no external service dependencies.

### Running the Application

The entry point is `run.py`. The application supports two primary modes:

**Replay mode (recommended for dev/testing — no external services needed):**
```bash
python3 run.py --mode replay --replay-source csv --config config/settings.json
```

If the sample CSV (`data/samples/xauusd.csv`) doesn't exist, `run.py` auto-generates it via `ensure_sample_data()`.

**Replay evaluation mode:**
```bash
python3 run.py --mode replay --replay-source csv --evaluate-replay true --config config/settings.json
```

**Live mode** requires a running MetaTrader 5 terminal (Windows only) and is not applicable in cloud dev environments.

### Key Caveats

- There is no `requirements.txt`, `pyproject.toml`, or `setup.py` in the repo. The only dev dependency is `pytest`.
- The `data/` directory is not checked into git; it is auto-created at runtime by `ensure_sample_data()` in `run.py`.
- All imports are stdlib except the optional `MetaTrader5` package. No pip packages are needed at runtime.
- Config files live in `config/` (`settings.json`, `symbols.json`, `connectors.json`).
- Memory/state artifacts are written to `memory/` and many subdirectories are gitignored.
- The output of `run.py` is a Python dict printed to stdout (not JSON — uses single quotes). Parse carefully if piping.
