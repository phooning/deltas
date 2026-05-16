"""Fundamentals page for medium-term conviction.

This page contributes SignalBundle.fundamental_score by combining earnings
quality, valuation context, ownership momentum, and an analyst thesis surface.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import panel as pn
import plotly.graph_objects as go

from trading_desk.pages._common import (
    PALETTE,
    ensure_state,
    plotly_pane,
    stable_rng,
    sync_ticker_widget,
)


def _earnings(ticker: str, clicks: int) -> pd.DataFrame:
    rng = stable_rng(f"earnings-{ticker}-{clicks}")
    quarters = pd.period_range("2024Q2", periods=8, freq="Q").astype(str)
    estimate = np.round(rng.normal(2.1, 0.22, 8).cumsum() / 8 + np.linspace(1.8, 2.4, 8), 2)
    actual = np.round(estimate + rng.normal(0.07, 0.13, 8), 2)
    surprise = np.round((actual - estimate) / estimate * 100, 1)
    reaction = np.round(rng.normal(0.6, 2.8, 8) + surprise * 0.18, 1)
    return pd.DataFrame(
        {
            "Quarter": quarters,
            "EPS Est": estimate,
            "EPS Actual": actual,
            "Beat/Miss": np.where(actual >= estimate, "Beat", "Miss"),
            "Surprise %": surprise,
            "Next Day %": reaction,
        }
    )


def _eps_sparkline(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=df["Quarter"],
            y=df["EPS Actual"],
            mode="lines+markers",
            line={"color": PALETTE["green"], "width": 3},
        )
    )
    fig.update_layout(title="EPS Actual Trend")
    return fig


def _peers(ticker: str, clicks: int) -> pd.DataFrame:
    rng = stable_rng(f"peers-{ticker}-{clicks}")
    comps = [ticker, "AAPL", "MSFT", "NVDA", "AVGO"]
    return pd.DataFrame(
        {
            "Ticker": comps,
            "EV/EBITDA": np.round(rng.normal(18, 3.5, len(comps)), 1),
            "P/E": np.round(rng.normal(26, 5.5, len(comps)), 1),
            "P/S": np.round(rng.normal(8, 2.2, len(comps)), 1),
        }
    )


def _ownership(ticker: str, clicks: int) -> go.Figure:
    rng = stable_rng(f"ownership-{ticker}-{clicks}")
    funds = ["Top 10", "Long Only", "Hedge Funds", "Pensions", "Insiders"]
    delta = np.round(rng.normal(0.4, 1.4, len(funds)), 1)
    colors = [PALETTE["green"] if value >= 0 else PALETTE["red"] for value in delta]
    fig = go.Figure(go.Bar(x=funds, y=delta, marker_color=colors))
    fig.update_layout(title="Institutional Ownership Delta QoQ", yaxis_title="pp")
    return fig


def create_panel(ticker: str = "SPY", state: Any | None = None) -> pn.viewable.Viewable:
    """Return the fundamentals stub panel."""

    state = ensure_state(ticker, state)
    ticker_input = pn.widgets.TextInput(name="Ticker", value=state.active_ticker, width=120)
    sync_ticker_widget(ticker_input, state)
    load_button = pn.widgets.Button(name="Load", button_type="primary", width=80)
    agent_button = pn.widgets.Button(name="Run Analyst Agent", button_type="default", width=160)

    def score_badge(ticker_value: str, clicks: int) -> pn.pane.HTML:
        score = 3 + (stable_rng(f"score-{ticker_value}-{clicks}").integers(0, 3) // 2)
        if hasattr(state, "update_signal_bundle"):
            state.update_signal_bundle(fundamental_score=int(score))
        color = PALETTE["green"] if score >= 4 else PALETTE["amber"]
        return pn.pane.HTML(
            f"<div class='mono' style='color:{color};font-weight:800;'>FUNDAMENTAL SCORE {score}/5</div>",
            width=230,
        )

    def earnings_table(ticker_value: str, clicks: int) -> pn.widgets.Tabulator:
        return pn.widgets.Tabulator(
            _earnings(ticker_value, clicks),
            show_index=False,
            height=260,
            sizing_mode="stretch_width",
        )

    def eps_chart(ticker_value: str, clicks: int) -> pn.pane.Plotly:
        return plotly_pane(_eps_sparkline(_earnings(ticker_value, clicks)), height=210)

    def peer_table(ticker_value: str, clicks: int) -> pn.widgets.Tabulator:
        return pn.widgets.Tabulator(
            _peers(ticker_value, clicks),
            show_index=False,
            height=210,
            sizing_mode="stretch_width",
        )

    def ownership_chart(ticker_value: str, clicks: int) -> pn.pane.Plotly:
        return plotly_pane(_ownership(ticker_value, clicks), height=260)

    def thesis(clicks: int) -> pn.Column:
        running = clicks > 0 and clicks % 2 == 1
        text = (
            "Analyst thesis run is queued. The live agent will synthesize filings, "
            "earnings revisions, and catalyst context here."
            if running
            else "Analyst thesis will appear here after agent run."
        )
        return pn.Column(
            pn.Row(
                pn.indicators.LoadingSpinner(value=running, width=24, height=24),
                pn.pane.Markdown(text),
            ),
            sizing_mode="stretch_width",
        )

    return pn.Column(
        pn.Row(ticker_input, load_button, pn.bind(score_badge, ticker_input.param.value, load_button.param.clicks)),
        pn.Row(
            pn.Card(
                pn.bind(earnings_table, ticker_input.param.value, load_button.param.clicks),
                pn.bind(eps_chart, ticker_input.param.value, load_button.param.clicks),
                title="Earnings History",
                sizing_mode="stretch_width",
                css_classes=["desk-card"],
            ),
            pn.Card(
                pn.bind(peer_table, ticker_input.param.value, load_button.param.clicks),
                pn.bind(ownership_chart, ticker_input.param.value, load_button.param.clicks),
                title="Peer Valuation and Ownership",
                sizing_mode="stretch_width",
                css_classes=["desk-card"],
            ),
            sizing_mode="stretch_width",
        ),
        pn.Card(
            pn.Row(agent_button),
            pn.bind(thesis, agent_button.param.clicks),
            title="LLM Analyst Thesis",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        ),
        sizing_mode="stretch_width",
    )
