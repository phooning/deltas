"""Options calculator page for a single structured trade.

This page contributes SignalBundle.recommended_structure and short-term option
shape by recomputing payoff, Greeks, break-evens, and scenarios from inputs.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import panel as pn
import plotly.graph_objects as go

from core.pricing import bs_greeks, build_payoff
from trading_desk.pages._common import (
    PALETTE,
    ensure_state,
    plotly_pane,
    sync_date_widget,
    sync_ticker_widget,
)


STRUCTURES = [
    "Long Call",
    "Long Put",
    "Bull Put Spread",
    "Bear Call Spread",
    "Iron Condor",
    "Calendar",
    "Strangle",
]


def _payoff_chart(
    structure: str,
    strike: float,
    expiry: Any,
    iv_percent: float,
    underlying: float,
    risk_free: float,
) -> go.Figure:
    payoff = build_payoff(structure, strike, expiry, iv_percent, underlying, risk_free)
    x = payoff["underlying"]
    y = payoff["pnl"]
    colors = np.where(y >= 0, PALETTE["green"], PALETTE["red"])
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line={"color": PALETTE["blue"], "width": 3},
            name="P/L at Expiry",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=np.zeros_like(x),
            mode="lines",
            line={"color": PALETTE["border"], "width": 1},
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Bar(x=x[::6], y=y[::6], marker_color=colors[::6], opacity=0.24, showlegend=False)
    )
    for breakeven in payoff["breakevens"]:
        fig.add_vline(x=breakeven, line_dash="dot", line_color=PALETTE["amber"])
        fig.add_annotation(
            x=breakeven,
            y=max(y) * 0.88,
            text=f"BE {breakeven:.2f}",
            showarrow=False,
            font={"color": PALETTE["amber"], "size": 10},
        )
    fig.update_layout(title=f"{structure} Payoff", xaxis_title="Underlying", yaxis_title="P/L")
    return fig


def _greeks_table(
    structure: str,
    strike: float,
    expiry: Any,
    iv_percent: float,
    underlying: float,
    risk_free: float,
) -> pn.widgets.Tabulator:
    greeks = bs_greeks(structure, strike, expiry, iv_percent, underlying, risk_free)
    df = pd.DataFrame({"Greek": list(greeks), "Value": list(greeks.values())})
    return pn.widgets.Tabulator(df, show_index=False, height=190, sizing_mode="stretch_width")


def _scenario_heatmap(
    structure: str,
    strike: float,
    expiry: Any,
    iv_percent: float,
    underlying: float,
    risk_free: float,
) -> pn.pane.Plotly:
    vol_shocks = np.array([-30, -15, 0, 15, 30])
    spot_shocks = np.array([-8, -4, 0, 4, 8])
    base = build_payoff(structure, strike, expiry, iv_percent, underlying, risk_free)
    matrix = []
    for vol in vol_shocks:
        row = []
        for spot in spot_shocks:
            shocked_spot = underlying * (1 + spot / 100)
            scenario = build_payoff(
                structure,
                strike,
                expiry,
                max(1, iv_percent + vol),
                shocked_spot,
                risk_free,
            )
            closest = np.argmin(np.abs(scenario["underlying"] - shocked_spot))
            row.append(float(scenario["pnl"][closest] - np.mean(base["pnl"]) * 0.04))
        matrix.append(row)
    fig = go.Figure(
        go.Heatmap(
            z=np.round(matrix, 1),
            x=[f"{value:+.0f}%" for value in spot_shocks],
            y=[f"{value:+.0f} vol" for value in vol_shocks],
            colorscale=[[0, PALETTE["red"]], [0.5, PALETTE["surface"]], [1, PALETTE["green"]]],
            zmid=0,
            colorbar={"title": "P/L"},
        )
    )
    fig.update_layout(title="Scenario Grid", xaxis_title="Spot Shock", yaxis_title="Vol Shock")
    return plotly_pane(fig, height=260)


def create_panel(
    ticker: str = "SPY",
    state: Any | None = None,
    set_active_tab: Callable[[str], None] | None = None,
) -> pn.viewable.Viewable:
    """Return the options calculator stub panel."""

    state = ensure_state(ticker, state)
    ticker_input = pn.widgets.TextInput(name="Ticker", value=state.active_ticker, disabled=True)
    sync_ticker_widget(ticker_input, state)
    structure = pn.widgets.Select(name="Structure", options=STRUCTURES, value="Long Call")
    strike = pn.widgets.FloatInput(name="Strike", value=485.0, step=1.0)
    expiry = pn.widgets.DatePicker(name="Expiry", value=state.active_expiry)
    sync_date_widget(expiry, state)
    iv = pn.widgets.FloatSlider(name="IV Override %", start=0, end=200, value=34, step=1)
    underlying = pn.widgets.FloatInput(name="Underlying", value=492.0, step=0.5)
    risk_free = pn.widgets.FloatInput(name="Risk-free Rate %", value=4.35, step=0.05)
    send_button = pn.widgets.Button(name="Open in Strategy Lab", button_type="primary")

    def update_structure(event: Any) -> None:
        if hasattr(state, "update_signal_bundle"):
            state.update_signal_bundle(recommended_structure=event.new.lower())

    structure.param.watch(update_structure, "value")

    def open_strategy(_event: Any) -> None:
        state.active_expiry = expiry.value
        if set_active_tab is not None:
            set_active_tab("Strategy Lab")

    send_button.on_click(open_strategy)

    inputs = pn.Card(
        ticker_input,
        structure,
        strike,
        expiry,
        iv,
        underlying,
        risk_free,
        send_button,
        title="Trade Inputs",
        width=300,
        css_classes=["desk-card"],
    )

    payoff = pn.bind(
        lambda s, k, e, v, u, r: plotly_pane(_payoff_chart(s, k, e, v, u, r), height=360),
        structure.param.value,
        strike.param.value,
        expiry.param.value,
        iv.param.value,
        underlying.param.value,
        risk_free.param.value,
    )
    greeks = pn.bind(
        _greeks_table,
        structure.param.value,
        strike.param.value,
        expiry.param.value,
        iv.param.value,
        underlying.param.value,
        risk_free.param.value,
    )
    scenarios = pn.bind(
        _scenario_heatmap,
        structure.param.value,
        strike.param.value,
        expiry.param.value,
        iv.param.value,
        underlying.param.value,
        risk_free.param.value,
    )

    outputs = pn.Column(
        pn.Card(payoff, title="Payoff and Break-Evens", sizing_mode="stretch_width", css_classes=["desk-card"]),
        pn.Row(
            pn.Card(greeks, title="Greeks", sizing_mode="stretch_width", css_classes=["desk-card"]),
            pn.Card(scenarios, title="Scenario Heat Map", sizing_mode="stretch_width", css_classes=["desk-card"]),
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )

    return pn.Row(inputs, outputs, sizing_mode="stretch_width")
