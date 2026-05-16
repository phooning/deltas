"""Backtests page for walk-forward validation.

This page contributes evidence for SignalBundle.conviction by stress-testing a
selected structure under regime filters with deterministic fake trades.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import panel as pn
import plotly.graph_objects as go

from trading_desk.pages._common import PALETTE, ensure_state, metric_html, plotly_pane, stable_seed


REGIME_FILTERS = ["All", "High IV", "Low IV", "Trending Up", "Trending Down", "Pre-Earnings"]


def _fake_trades(strategy: str, lookback: int, regimes: list[str], clicks: int) -> pd.DataFrame:
    seed = stable_seed(f"{strategy}-{lookback}-{','.join(regimes)}-{clicks}")
    rng = np.random.default_rng(seed)
    count = 50
    end_dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=count, freq="3D")
    pnl = rng.normal(42, 145, count)
    if "High IV" in regimes:
        pnl += rng.normal(28, 45, count)
    if "Trending Down" in regimes:
        pnl -= rng.normal(18, 35, count)
    entry_cost = np.round(rng.uniform(80, 240, count), 2)
    exit_value = np.round(entry_cost + pnl, 2)
    return pd.DataFrame(
        {
            "Entry Date": end_dates - pd.Timedelta(days=14),
            "Exit Date": end_dates,
            "Structure": strategy,
            "Entry Cost": entry_cost,
            "Exit Value": exit_value,
            "P&L": np.round(pnl, 2),
            "Regime at Entry": rng.choice(REGIME_FILTERS[1:], count),
        }
    )


def _metrics(df: pd.DataFrame) -> dict[str, float]:
    pnl = df["P&L"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()
    sharpe = 0.0 if pnl.std() == 0 else pnl.mean() / pnl.std() * np.sqrt(252 / 14)
    return {
        "Win Rate": len(wins) / len(pnl) * 100,
        "Avg Win": wins.mean() if len(wins) else 0,
        "Avg Loss": losses.mean() if len(losses) else 0,
        "Sharpe": sharpe,
        "Max DD": drawdown.min(),
        "Total Trades": float(len(df)),
    }


def _equity_curve(df: pd.DataFrame) -> go.Figure:
    equity = df["P&L"].cumsum()
    max_dd = (equity - equity.cummax()).min()
    fig = go.Figure(
        go.Scatter(
            x=df["Exit Date"],
            y=equity,
            mode="lines",
            line={"color": PALETTE["blue"], "width": 3},
            name="Equity",
        )
    )
    fig.add_annotation(
        x=df["Exit Date"].iloc[int(np.argmin(equity - equity.cummax()))],
        y=equity.min(),
        text=f"Max DD ${max_dd:,.0f}",
        showarrow=True,
        arrowcolor=PALETTE["red"],
        font={"color": PALETTE["red"]},
    )
    fig.update_layout(title="Walk-forward Equity Curve", yaxis_title="Cumulative P/L")
    return fig


def create_panel(
    ticker: str = "SPY",
    state: Any | None = None,
    set_active_tab: Callable[[str], None] | None = None,
) -> pn.viewable.Viewable:
    """Return the backtests stub panel."""

    del ticker, set_active_tab
    state = ensure_state("SPY", state)
    strategy = pn.widgets.Select(
        name="Strategy Template",
        options=["Bull Put Spread", "Bear Call Spread", "Iron Condor", "Long Call"],
        value="Bull Put Spread",
        width=170,
    )
    lookback = pn.widgets.Select(name="Lookback", options=[30, 90, 252, 504], value=252, width=110)
    regimes = pn.widgets.MultiChoice(name="Regime Filter", options=REGIME_FILTERS, value=["All"], width=300)
    run = pn.widgets.Button(name="Run Backtest", button_type="primary", width=130)

    def trades(strategy_value: str, lookback_value: int, regime_values: list[str], clicks: int) -> pd.DataFrame:
        values = regime_values or ["All"]
        df = _fake_trades(strategy_value, lookback_value, values, clicks)
        metrics = _metrics(df)
        conviction = min(0.92, max(0.18, 0.45 + metrics["Win Rate"] / 250 + metrics["Sharpe"] / 10))
        state.conviction = conviction
        if hasattr(state, "update_signal_bundle"):
            state.update_signal_bundle(conviction=conviction, recommended_structure=strategy_value.lower())
        return df

    def curve(strategy_value: str, lookback_value: int, regime_values: list[str], clicks: int) -> pn.pane.Plotly:
        df = trades(strategy_value, lookback_value, regime_values, clicks)
        return plotly_pane(_equity_curve(df), height=330)

    def metric_strip(strategy_value: str, lookback_value: int, regime_values: list[str], clicks: int) -> pn.Row:
        df = trades(strategy_value, lookback_value, regime_values, clicks)
        metrics = _metrics(df)
        return pn.Row(
            metric_html("Win Rate", f"{metrics['Win Rate']:.0f}%", "green" if metrics["Win Rate"] >= 55 else "amber"),
            metric_html("Avg Win", f"${metrics['Avg Win']:,.0f}", "green"),
            metric_html("Avg Loss", f"${metrics['Avg Loss']:,.0f}", "red"),
            metric_html("Sharpe", f"{metrics['Sharpe']:.2f}", "blue" if metrics["Sharpe"] > 1 else "amber"),
            metric_html("Max DD", f"${metrics['Max DD']:,.0f}", "red"),
            metric_html("Trades", f"{metrics['Total Trades']:.0f}", "muted"),
            sizing_mode="stretch_width",
        )

    def trade_table(strategy_value: str, lookback_value: int, regime_values: list[str], clicks: int) -> pn.widgets.Tabulator:
        df = trades(strategy_value, lookback_value, regime_values, clicks)
        return pn.widgets.Tabulator(df, show_index=False, height=310, sizing_mode="stretch_width")

    return pn.Column(
        pn.Row(strategy, lookback, regimes, run, pn.Spacer(sizing_mode="stretch_width")),
        pn.Card(
            pn.bind(curve, strategy.param.value, lookback.param.value, regimes.param.value, run.param.clicks),
            title="Equity Curve",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        ),
        pn.bind(metric_strip, strategy.param.value, lookback.param.value, regimes.param.value, run.param.clicks),
        pn.Card(
            pn.bind(trade_table, strategy.param.value, lookback.param.value, regimes.param.value, run.param.clicks),
            title="Per-trade P&L",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        ),
        sizing_mode="stretch_width",
    )
