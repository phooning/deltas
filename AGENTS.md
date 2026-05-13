# AGENTS.md - Deltas

Deltas is a local-first financial trading analyst desk.

Strategic focus:

- 1-week to 2-month trades: options and shares.
- multi-month to 1 year: ETF shares and long calls.

## Architecture

The stack consists of light python frameworks: `Panel + Plotly + Polars + DuckDB + Parquet + vectorbt`

```
trading-desk/
  app.py                    # Panel dashboard entrypoint
  pages/
    options_calculator.py
    strategy_lab.py         # Input: ticker + expiry -> core engine creates 3 spreads.
    backtests.py
    fundamentals.py
    catalysts.py
    macro.py

  core/
    pricing.py              # Black-Scholes, Greeks, payoff models, volatility surface modeling
    strategies.py           # vertical spreads, covered calls, calendars, etc.
    backtest.py             # vectorbt/custom wrappers
    risk.py                 # drawdown, exposure, Greeks aggregation
    volatility.py           # IV Surface, Term Structure, Skew analysis
    signals.py              # Logic that converts data into "Buy/Sell" bits

  data/
    lake/
      prices/
      options/
      fundamentals/
      macro/
      catalysts/
    trading.duckdb

  repositories/             # The layer between the Panel app and ingest with SQL lines/dataframes.
    prices_repo.py
    options_repo.py
    fundamentals_repo.py
    macro_repo.py
    catalysts_repo.py

  agents/
    prompts/
    chains/
    tools/

  infra/
    db_manager.py           # DuckDB connection pooling & Parquet maintenance
    llm_provider.py         # Local inference (vLLM/Ollama) or API wrapper

  ingest/
    prices.py
    options.py
    fundamentals.py
    macro.py
    news.py                 # Catalyst engine focuses on the Expected Move.

  research/
    notebooks/
```

### UI

- Panel: app shell, pages, widgets, layout
- Plotly: payoff charts, P/L curves, Greeks curves
- HoloViews: fast exploratory linked charts
- Tabulator: interactive tables inside Panel

### Data Storage

- Parquet files: raw and semi-clean time series
- DuckDB: query/index/catalog layer

#### Example layout

```
data/lake/prices/symbol=NVDA/1d.parquet
data/lake/prices/symbol=NVDA/5m.parquet
data/lake/options/symbol=NVDA/date=2026-05-13/chain.parquet
data/lake/fundamentals/symbol=NVDA/facts.parquet
data/lake/news/date=2026-05-13/items.parquet
```

#### ETF Daily Prices

- bronze: raw vendor data, append-only
- silver: cleaned canonical OHLCV by ticker/year
- gold: analysis-ready derived views

```
data/
  lake/
    prices/
      bronze/
        source=yfinance/
          asset_type=etf/
            interval=1d/
              ingest_date=2026-05-13/
                part-000.parquet

      silver/
        source=yfinance/
          asset_type=etf/
            interval=1d/
              ticker=SPY/
                year=2025/
                  prices.parquet
              ticker=QQQ/
                year=2025/
                  prices.parquet

      gold/
        etf_daily_ohlcv.parquet
```

## Safety

* Do not rewrite unrelated files.
* Do not perform large refactors unless asked.
* Keep changes minimal, focused, and reversible.
* If a command fails, explain the failure and the smallest next fix.

## Code exploration — prefer `ast-outline` over full reads

**For this Python Panel financial analyst trading desk application**, always start with `ast-outline` on `.py` and `.pyi` files (and other supported languages like `.js`/`.tsx` for custom Panel widgets or `.md` when relevant) before any full read. This surfaces classes, methods, Panel reactive patterns (`@pn.depends`, `param.Parameterized`, `pn.Viewable`), trading logic (strategies, risk, P&L), and dashboard structure while keeping token usage minimal.

**Stop at the earliest step that answers the question:**

1. **Unfamiliar directory** — `ast-outline digest <dir>`: one-page map of every file’s classes, functions, Panel components, and public APIs.

2. **One file’s shape** — `ast-outline <file>`: signatures with line ranges, decorators, and inheritance (5–10× smaller than a full read). No bodies.

3. **One symbol (class, method, Panel component, or markdown section)** — `ast-outline show <file> <Symbol>`
   - Suffix matching: `calculate_pnl`, `Portfolio.update_positions`, `TradingDashboard.render`
   - Multiple at once: `ast-outline show dashboard.py main_view execute_trade on_market_data`
   - For markdown: use the heading text (e.g. `## Risk Management`).

4. **Who implements/extends a type** — `ast-outline implements <Type> <dir>`: e.g. `BaseStrategy`, `pn.Viewable`, `DataFeed`. AST-accurate and transitive by default with `[via Parent]` tags on indirect matches. Add `--direct` for level-1 only.

Fall back to a full read **only** when you need the actual body or context beyond what `show` returned (e.g., complex callback logic, data pipelines, or surrounding imports).

If the outline header contains `# WARNING: N parse errors`, the outline for that file is partial — read the source directly for the affected region.

`ast-outline help` for flags and rare options.
