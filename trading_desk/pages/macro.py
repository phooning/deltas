"""Macro regime page for trade sizing context.

This page contributes SignalBundle.regime by translating VIX structure, yield
curve shape, Fed path, and sector rotation into a risk-on/off/transitional label.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import panel as pn
import plotly.graph_objects as go

from trading_desk.pages._common import PALETTE, ensure_state, metric_html, pill_html, plotly_pane


SCENARIO_TO_REGIME = {
    "Contango": "risk-on",
    "Flat": "transitional",
    "Backwardation": "risk-off",
}


def _term_structure(scenario: str) -> go.Figure:
    labels = ["VIX", "VX1", "VX2", "VX3"]
    if scenario == "Backwardation":
        values = [24.8, 23.4, 22.1, 21.5]
        color = PALETTE["red"]
    elif scenario == "Flat":
        values = [18.9, 19.1, 19.0, 19.3]
        color = PALETTE["amber"]
    else:
        values = [15.9, 16.7, 17.5, 18.2]
        color = PALETTE["green"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=values,
            mode="lines+markers",
            line={"color": color, "width": 3},
            marker={"size": 9},
            name="Vol term",
        )
    )
    fig.update_layout(title="VIX Term Structure")
    return fig


def _yield_curve(scenario: str) -> tuple[go.Figure, float]:
    ten_year = 4.23 if scenario != "Backwardation" else 3.84
    two_year = 4.08 if scenario == "Contango" else 4.34 if scenario == "Flat" else 4.55
    yields = {"2Y": two_year, "5Y": 4.02, "10Y": ten_year, "30Y": 4.44}
    spread = ten_year - two_year
    colors = [PALETTE["red"] if name == "2Y" and spread < 0 else PALETTE["blue"] for name in yields]
    fig = go.Figure(go.Bar(x=list(yields.values()), y=list(yields.keys()), orientation="h", marker_color=colors))
    fig.update_layout(title="Treasury Curve", xaxis_title="Yield %")
    return fig, spread


def _fed_path(scenario: str) -> go.Figure:
    meetings = [date.today() + timedelta(days=days) for days in [32, 74, 119, 165, 214]]
    base = 4.55 if scenario == "Backwardation" else 4.35 if scenario == "Flat" else 4.15
    rates = [base, base - 0.05, base - 0.2, base - 0.32, base - 0.45]
    fig = go.Figure(
        go.Scatter(
            x=meetings,
            y=rates,
            mode="lines+markers",
            line={"shape": "hv", "color": PALETTE["blue"], "width": 3},
            marker={"size": 8},
        )
    )
    fig.update_layout(title="Implied Fed Path", yaxis_title="Rate %")
    return fig


def _sector_heatmap(scenario: str) -> go.Figure:
    sectors = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU"]
    windows = ["1D", "1W", "1M"]
    tilt = {"Contango": 0.7, "Flat": 0.0, "Backwardation": -0.75}[scenario]
    values = np.array(
        [
            [1.0, 2.1, 4.2],
            [0.2, 1.4, 2.7],
            [-0.3, 0.6, 1.8],
            [0.1, 0.3, 1.1],
            [0.6, 1.8, 3.5],
            [-0.1, 0.2, 0.8],
            [0.4, 1.1, 2.0],
            [-0.2, 0.1, 0.9],
            [-0.4, -0.7, -1.2],
        ]
    ) + tilt
    fig = go.Figure(
        go.Heatmap(
            z=values,
            x=windows,
            y=sectors,
            colorscale=[[0, PALETTE["red"]], [0.5, PALETTE["surface"]], [1, PALETTE["green"]]],
            zmid=0,
            colorbar={"title": "%"},
        )
    )
    fig.update_layout(title="Sector Rotation")
    return fig


def create_panel(ticker: str = "SPY", state: Any | None = None) -> pn.viewable.Viewable:
    """Return the macro regime stub panel."""

    state = ensure_state(ticker, state)
    scenario = pn.widgets.Select(name="Regime Scenario", options=list(SCENARIO_TO_REGIME), value="Contango", width=180)

    def apply_scenario(event: Any) -> None:
        regime = SCENARIO_TO_REGIME[event.new]
        state.regime = regime
        state.vix_spot = 24.8 if event.new == "Backwardation" else 18.9 if event.new == "Flat" else 15.9
        if hasattr(state, "update_signal_bundle"):
            state.update_signal_bundle(regime=regime)

    scenario.param.watch(apply_scenario, "value")

    def vix_panel(value: str) -> pn.Card:
        regime = SCENARIO_TO_REGIME[value]
        tone = "green" if regime == "risk-on" else "red" if regime == "risk-off" else "amber"
        return pn.Card(
            plotly_pane(_term_structure(value), height=250),
            pn.pane.HTML(f"<div class='section-label'>Current Regime</div>{pill_html(regime.upper(), tone)}"),
            title="Volatility",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        )

    def yield_panel(value: str) -> pn.Card:
        fig, spread = _yield_curve(value)
        tone = "red" if spread < 0 else "green"
        return pn.Card(
            plotly_pane(fig, height=250),
            metric_html("2s10s Spread", f"{spread * 100:+.0f} bp", tone),
            title="Yield Curve",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        )

    def fed_panel(value: str) -> pn.Card:
        return pn.Card(
            plotly_pane(_fed_path(value), height=250),
            pn.pane.HTML(pill_html("NEXT FOMC 32D", "blue")),
            title="Fed Path",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        )

    def heatmap(value: str) -> pn.pane.Plotly:
        return plotly_pane(_sector_heatmap(value), height=290)

    def regime_output(regime: str) -> pn.pane.HTML:
        tone = "green" if regime == "risk-on" else "red" if regime == "risk-off" else "amber"
        return pn.pane.HTML(
            f"<div class='callout'><span class='section-label'>SignalBundle.regime</span><br>{pill_html(regime.upper(), tone)}</div>",
            sizing_mode="stretch_width",
        )

    return pn.Column(
        pn.Row(scenario, pn.Spacer(sizing_mode="stretch_width")),
        pn.Row(
            pn.bind(vix_panel, scenario.param.value),
            pn.bind(yield_panel, scenario.param.value),
            pn.bind(fed_panel, scenario.param.value),
            sizing_mode="stretch_width",
        ),
        pn.Card(
            pn.bind(heatmap, scenario.param.value),
            title="Sector Rotation Heat Map",
            sizing_mode="stretch_width",
            css_classes=["desk-card"],
        ),
        pn.bind(regime_output, state.param.regime),
        sizing_mode="stretch_width",
    )
