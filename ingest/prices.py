from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TICKERS_PATH = ROOT / "constants" / "tickers.toml"
DEFAULT_DB_PATH = ROOT / "data" / "db" / "trading.duckdb"
DEFAULT_LAKE_ROOT = ROOT / "data" / "lake" / "prices" / "silver"
DEFAULT_VIEW = "prices_daily"
DEFAULT_WINDOWS_VIEW = "prices_daily_performance_windows"
SCHEMA_COLUMNS = [
    "ticker",
    "asset_type",
    "source",
    "interval",
    "price_date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "dividends",
    "stock_splits",
    "ingested_at",
]


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_tickers(path: Path, category: str) -> list[str]:
    with path.open("rb") as f:
        config = tomllib.load(f)

    try:
        tickers = config[category]["tickers"]
    except KeyError as exc:
        raise ValueError(f"missing [{category}].tickers in {path}") from exc

    if not isinstance(tickers, list) or not all(isinstance(t, str) for t in tickers):
        raise ValueError(f"[{category}].tickers must be a list of ticker symbols")

    return sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})


def fetch_history(
    tickers: list[str],
    period: str,
    interval: str,
    source: str,
    asset_type: str,
) -> pd.DataFrame:
    if interval != "1d":
        raise ValueError("this ingest currently only supports interval=1d")

    frames: list[pd.DataFrame] = []
    ingested_at = datetime.now(UTC)

    for ticker in tickers:
        history = yf.Ticker(ticker).history(
            period=period,
            interval=interval,
            auto_adjust=False,
            actions=True,
        )

        if history.empty:
            print(f"warning: no price history returned for {ticker}", file=sys.stderr)
            continue

        history = history.reset_index()
        date_column = "Date" if "Date" in history.columns else "Datetime"
        history = history.rename(
            columns={
                date_column: "price_date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
                "Dividends": "dividends",
                "Stock Splits": "stock_splits",
            }
        )
        history["ticker"] = ticker
        history["asset_type"] = asset_type
        history["source"] = source
        history["interval"] = interval
        frames.append(history)

    if not frames:
        return pd.DataFrame()

    prices = pd.concat(frames, ignore_index=True)
    prices["price_date"] = pd.to_datetime(prices["price_date"]).dt.date
    prices["ingested_at"] = ingested_at

    # yfinance returns raw close and split/dividend adjusted close when auto_adjust=False.
    for column in ["open", "high", "low", "close", "adj_close", "dividends", "stock_splits"]:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce").astype("Int64")

    return prices.reindex(columns=SCHEMA_COLUMNS)


def partition_path(
    lake_root: Path,
    source: str,
    asset_type: str,
    interval: str,
    ticker: str,
    year: int,
) -> Path:
    return (
        lake_root
        / f"source={source}"
        / f"asset_type={asset_type}"
        / f"interval={interval}"
        / f"ticker={ticker}"
        / f"year={year}"
        / "prices.parquet"
    )


def write_partition(conn: duckdb.DuckDBPyConnection, path: Path, prices: pd.DataFrame) -> int:
    if prices.empty:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    conn.register("incoming_prices", prices)

    column_list = ", ".join(SCHEMA_COLUMNS)
    source_query = f"SELECT {column_list} FROM incoming_prices"
    if path.exists():
        source_query = (
            f"SELECT {column_list} FROM read_parquet({quote_literal(str(path))}, union_by_name=true) "
            f"UNION ALL SELECT {column_list} FROM incoming_prices"
        )

    conn.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE partition_prices AS
        SELECT {column_list}
        FROM (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY source, asset_type, ticker, interval, price_date
                    ORDER BY ingested_at DESC
                ) AS row_num
            FROM ({source_query})
        )
        WHERE row_num = 1
        ORDER BY ticker, price_date
        """
    )
    conn.execute(
        f"""
        COPY (
            SELECT {column_list}
            FROM partition_prices
        )
        TO {quote_literal(str(path))}
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    return len(prices)


def write_silver_parquet(
    lake_root: Path,
    source: str,
    asset_type: str,
    interval: str,
    prices: pd.DataFrame,
) -> int:
    if prices.empty:
        return 0

    rows = 0
    prices = prices.copy()
    prices["year"] = pd.to_datetime(prices["price_date"]).dt.year

    with duckdb.connect() as conn:
        for (ticker, year), partition in prices.groupby(["ticker", "year"], sort=True):
            path = partition_path(lake_root, source, asset_type, interval, ticker, int(year))
            rows += write_partition(conn, path, partition[SCHEMA_COLUMNS])

    return rows


def drop_relation_if_exists(conn: duckdb.DuckDBPyConnection, name: str) -> None:
    relation = conn.execute(
        """
        SELECT table_type
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = ?
        """,
        [name],
    ).fetchone()

    if relation is None:
        return

    relation_type = relation[0]
    sql_name = quote_identifier(name)
    if relation_type == "VIEW":
        conn.execute(f"DROP VIEW {sql_name}")
    else:
        conn.execute(f"DROP TABLE {sql_name}")


def create_empty_prices_view(conn: duckdb.DuckDBPyConnection, view_name: str) -> None:
    conn.execute(
        f"""
        CREATE VIEW {view_name} AS
        SELECT
            NULL::TEXT AS ticker,
            NULL::TEXT AS asset_type,
            NULL::TEXT AS source,
            NULL::TEXT AS interval,
            NULL::DATE AS price_date,
            NULL::DOUBLE AS open,
            NULL::DOUBLE AS high,
            NULL::DOUBLE AS low,
            NULL::DOUBLE AS close,
            NULL::DOUBLE AS adj_close,
            NULL::BIGINT AS volume,
            NULL::DOUBLE AS dividends,
            NULL::DOUBLE AS stock_splits,
            NULL::TIMESTAMPTZ AS ingested_at
        WHERE false
        """
    )


def create_parquet_prices_view(
    conn: duckdb.DuckDBPyConnection,
    view_name: str,
    parquet_glob: str,
) -> None:
    conn.execute(
        f"""
        CREATE VIEW {view_name} AS
        SELECT
            ticker::TEXT AS ticker,
            asset_type::TEXT AS asset_type,
            source::TEXT AS source,
            interval::TEXT AS interval,
            price_date::DATE AS price_date,
            open::DOUBLE AS open,
            high::DOUBLE AS high,
            low::DOUBLE AS low,
            close::DOUBLE AS close,
            adj_close::DOUBLE AS adj_close,
            volume::BIGINT AS volume,
            dividends::DOUBLE AS dividends,
            stock_splits::DOUBLE AS stock_splits,
            ingested_at::TIMESTAMPTZ AS ingested_at
        FROM read_parquet(
            {quote_literal(parquet_glob)},
            union_by_name=true,
            hive_partitioning=true
        )
        """
    )


def create_empty_performance_windows_view(
    conn: duckdb.DuckDBPyConnection,
    windows_view_name: str,
) -> None:
    conn.execute(
        f"""
        CREATE VIEW {windows_view_name} AS
        SELECT
            NULL::TEXT AS ticker,
            NULL::TEXT AS asset_type,
            NULL::TEXT AS source,
            NULL::TEXT AS interval,
            NULL::TEXT AS performance_window,
            NULL::INTEGER AS sort_order,
            NULL::DATE AS start_date,
            NULL::DATE AS end_date,
            NULL::BIGINT AS trading_days,
            NULL::DOUBLE AS start_close,
            NULL::DOUBLE AS end_close,
            NULL::DOUBLE AS start_adj_close,
            NULL::DOUBLE AS end_adj_close,
            NULL::DOUBLE AS close_return,
            NULL::DOUBLE AS adj_close_return
        WHERE false
        """
    )


def create_performance_windows_view(
    conn: duckdb.DuckDBPyConnection,
    windows_view_name: str,
    prices_view_name: str,
) -> None:
    conn.execute(
        f"""
        CREATE VIEW {windows_view_name} AS
        WITH as_of_dates AS (
            SELECT
                source,
                asset_type,
                interval,
                ticker,
                max(price_date) AS as_of_date
            FROM {prices_view_name}
            GROUP BY source, asset_type, interval, ticker
        ),
        windows(performance_window, sort_order) AS (
            VALUES
                ('1M', 1),
                ('3M', 2),
                ('6M', 3),
                ('YTD', 4),
                ('1Y', 5),
                ('3Y', 6),
                ('5Y', 7),
                ('10Y', 8),
                ('Max', 9)
        ),
        windowed_prices AS (
            SELECT
                p.*,
                w.performance_window,
                w.sort_order
            FROM {prices_view_name} AS p
            JOIN as_of_dates AS a
              ON p.source = a.source
             AND p.asset_type = a.asset_type
             AND p.interval = a.interval
             AND p.ticker = a.ticker
            CROSS JOIN windows AS w
            WHERE p.price_date <= a.as_of_date
              AND p.price_date >= CASE w.performance_window
                  WHEN '1M' THEN (a.as_of_date - INTERVAL '1 month')::DATE
                  WHEN '3M' THEN (a.as_of_date - INTERVAL '3 months')::DATE
                  WHEN '6M' THEN (a.as_of_date - INTERVAL '6 months')::DATE
                  WHEN 'YTD' THEN date_trunc('year', a.as_of_date)::DATE
                  WHEN '1Y' THEN (a.as_of_date - INTERVAL '1 year')::DATE
                  WHEN '3Y' THEN (a.as_of_date - INTERVAL '3 years')::DATE
                  WHEN '5Y' THEN (a.as_of_date - INTERVAL '5 years')::DATE
                  WHEN '10Y' THEN (a.as_of_date - INTERVAL '10 years')::DATE
                  ELSE DATE '0001-01-01'
              END
        ),
        ranked_prices AS (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY source, asset_type, interval, ticker, performance_window
                    ORDER BY price_date
                ) AS start_rank,
                row_number() OVER (
                    PARTITION BY source, asset_type, interval, ticker, performance_window
                    ORDER BY price_date DESC
                ) AS end_rank
            FROM windowed_prices
        ),
        rolled AS (
            SELECT
                ticker,
                asset_type,
                source,
                interval,
                performance_window,
                sort_order,
                max(CASE WHEN start_rank = 1 THEN price_date END) AS start_date,
                max(CASE WHEN end_rank = 1 THEN price_date END) AS end_date,
                count(*) AS trading_days,
                max(CASE WHEN start_rank = 1 THEN close END) AS start_close,
                max(CASE WHEN end_rank = 1 THEN close END) AS end_close,
                max(CASE WHEN start_rank = 1 THEN adj_close END) AS start_adj_close,
                max(CASE WHEN end_rank = 1 THEN adj_close END) AS end_adj_close
            FROM ranked_prices
            GROUP BY ticker, asset_type, source, interval, performance_window, sort_order
        )
        SELECT
            ticker,
            asset_type,
            source,
            interval,
            performance_window,
            sort_order,
            start_date,
            end_date,
            trading_days,
            start_close,
            end_close,
            start_adj_close,
            end_adj_close,
            (end_close / nullif(start_close, 0)) - 1 AS close_return,
            (end_adj_close / nullif(start_adj_close, 0)) - 1 AS adj_close_return
        FROM rolled
        ORDER BY ticker, sort_order
        """
    )


def refresh_duckdb_views(
    db_path: Path,
    prices_view: str,
    windows_view: str,
    lake_root: Path,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    prices_view_name = quote_identifier(prices_view)
    windows_view_name = quote_identifier(windows_view)
    parquet_glob = str(lake_root / "**" / "*.parquet")

    with duckdb.connect(str(db_path)) as conn:
        drop_relation_if_exists(conn, windows_view)
        drop_relation_if_exists(conn, prices_view)
        if not any(lake_root.rglob("*.parquet")):
            create_empty_prices_view(conn, prices_view_name)
            create_empty_performance_windows_view(conn, windows_view_name)
        else:
            create_parquet_prices_view(conn, prices_view_name, parquet_glob)
            create_performance_windows_view(conn, windows_view_name, prices_view_name)


def is_lock_error(exc: duckdb.Error) -> bool:
    return "Could not set lock on file" in str(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch ETF daily price history from yfinance into Parquet and DuckDB."
    )
    parser.add_argument("--tickers", type=Path, default=DEFAULT_TICKERS_PATH)
    parser.add_argument("--category", default="etf")
    parser.add_argument("--asset-type", default="etf")
    parser.add_argument("--source", default="yfinance")
    parser.add_argument("--lake-root", type=Path, default=DEFAULT_LAKE_ROOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--view", default=DEFAULT_VIEW)
    parser.add_argument("--windows-view", default=DEFAULT_WINDOWS_VIEW)
    parser.add_argument("--period", default="max")
    parser.add_argument("--interval", default="1d")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tickers = load_tickers(args.tickers, args.category)

    if not tickers:
        print(f"no tickers found in [{args.category}].tickers")
        return 0

    prices = fetch_history(
        tickers=tickers,
        period=args.period,
        interval=args.interval,
        source=args.source,
        asset_type=args.asset_type,
    )
    rows = write_silver_parquet(
        lake_root=args.lake_root,
        source=args.source,
        asset_type=args.asset_type,
        interval=args.interval,
        prices=prices,
    )

    try:
        refresh_duckdb_views(
            db_path=args.db,
            prices_view=args.view,
            windows_view=args.windows_view,
            lake_root=args.lake_root,
        )
    except duckdb.Error as exc:
        if is_lock_error(exc):
            print(
                f"stored {rows} Parquet rows, but could not refresh DuckDB views "
                f"{args.view} and {args.windows_view}: {args.db} is locked by another "
                "DuckDB process",
                file=sys.stderr,
            )
            return 1
        raise

    print(
        f"stored {rows} {args.interval} price rows for {len(tickers)} "
        f"{args.asset_type.upper()} tickers in {args.lake_root}; "
        f"refreshed DuckDB views {args.view} and {args.windows_view} in {args.db}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
