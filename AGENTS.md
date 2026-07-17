# AGENTS.md

Q-SEED is a single Python product (a local quant research engine) managed with
[`uv`](https://docs.astral.sh/uv/). All interfaces (CLI, Streamlit dashboard, local web
server, dbt) read from an embedded DuckDB warehouse at `data/stocks.db`.

For general setup and commands see `README.md`, `docs/getting-started.md`, the `Makefile`,
and `pyproject.toml`. This file only records non-obvious, durable notes.

## Cursor Cloud specific instructions

### Environment
- `uv` is installed at `~/.local/bin` and is on the PATH for login shells (the installer
  added it to `~/.bashrc` / `~/.profile`). The startup update script runs `uv sync` and
  copies the gitignored config templates (`profiles.yml`, `.env`) if missing.
- Python is pinned to 3.12 (`.python-version`); `uv sync` creates `.venv` from `uv.lock`.

### Lint / test / build / run (all via `uv run`)
- Tests: `make test` (`uv run pytest`). Tests use synthetic in-memory data (`tmp_path`) and
  need **no** warehouse or network.
- Lint/format/type-check are **not** direct deps; they run through pre-commit exactly like
  CI (`.github/workflows/lint.yml`): `uv run pre-commit run --all-files` (ruff, ruff-format,
  mypy, prettier). The first run downloads hook environments (needs network).
- `uv run pre-commit install` fails in the cloud VM with "Cowardly refusing to install hooks
  with `core.hooksPath` set" because the cloud git config sets `core.hooksPath`. This is
  harmless — run hooks directly with `uv run pre-commit run ...` instead.
- dbt requires `DBT_PROFILES_DIR=.` (set in `.env`) and `profiles.yml`. Run report models
  with `make dbt` (`uv run dbt run --select stocks`). Two heavy models
  (`int_stocks__daily_returns`, `fct_stocks__price_factors`) are disabled by default in
  `dbt_project.yml`; enable them explicitly with `--select` if needed.
- Web server: `make web` → serves `research.html` + `/api/*` over `data/stocks.db` on port
  **8000** (bind all interfaces with `--host 0.0.0.0`). Reads the `raw_stocks` table.
- Streamlit dashboard: `make dashboard` → port **8501**. It reads the `rpt_stocks__*`
  report tables, so **run `make dbt` first** or the pages will be empty/error.

### Data warehouse (required for the dashboard, web server, and factor/backtest CLIs)
- `data/stocks.db` is gitignored and must be built before running any UI or analysis; only
  the unit tests work without it.
- Building needs network (FinanceDataReader for listings + yfinance for OHLCV). The
  `--build-db` flag ingests *all* markets with full history and is very slow. For a fast,
  representative local warehouse use a bounded full run, e.g.:
  `uv run qseed --run-stock-pipeline --mode full --max-stocks 50 --chunk-size 250 --sleep-interval 0 --download-period 2y`
  (~2–3 min; the per-market `StockListing` calls are the slow part, not the batched yfinance
  download). `--max-stocks` is per-market and the pipeline always queries all 7 markets.
- After building, refresh report tables with `make dbt`. Research CLIs read the warehouse:
  `uv run qseed --list-factors`, `--run-factor-analysis`, `--run-backtest`, `--run-optimize`.
