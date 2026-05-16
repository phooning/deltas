# Deltas (WIP)

A low rate, time-aware, recursively agentic AI architecture that leverages both local and cloud LLMs to compress global markets based off signals intelligence. Predicts market expectations by backtesting against a parallel world simulation model based on geopolitical, geospatial, and resource constrained economies of scale.

## Trading Strategy

For 1-week to 1-month trades, we are essentially trading Gamma and Vega.

### Volatility Surface Modeling (`core/pricing.py`)

1. In-Sample Excellence
2. In-Sample Permutation Test
3. Walk Forward Test
4. Walk Forward Permutation Test

- Moving Average Crossover

## Data Ingestion

Requirements:

- Point-in-Time (PIT) data.

Targets:

- ETFs: `yfinance` long-term daily bars.
- Options: historical chains

Lakehouse:

- Massive Parquet files partitioned out.
