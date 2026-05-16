"""Catalysts page for event-driven option setup.

This page contributes SignalBundle.catalyst_proximity by comparing nearby
events, expected move, and historical realized moves.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import panel as pn
import plotly.graph_objects as go

from trading_desk.pages._common import PALETTE, ensure_state, plotly_pane, stable_rng, sync_ticker_widget


EVENT_TYPES = ["Earnings", "FDA", "FOMC", "Product", "Index Rebalance"]


def _events(ticker: str, expiry_filter: str) -> pd.DataFrame:
    rng = stable_rng(f"events-{ticker}-{expiry_filter}")
    day_offsets = np.array([6, 13, 21, 35, 49])
    if expiry_filter == "Next 30D":
        day_offsets = day_offsets[day_offsets <= 30]
    elif expiry_filter == "Next 60D":
        day_offsets = day_offsets[day_offsets <= 60]
    rows = []
    for index, days_to in enumerate(day_offsets):
        expected = round(rng.uniform(2.4, 8.2), 1)
        spot = 100 + stable_rng(ticker).integers(80, 320)
        rows.append(
            {
                "type": EVENT_TYPES[index % len(EVENT_TYPES)],
                "name": f"{ticker} {EVENT_TYPES[index % len(EVENT_TYPES)]}",
                "date": date.today() + timedelta(days=int(days_to)),
                "days_to": int(days_to),
                "expected_pct": expected,
                "expected_dollars": round(spot * expected / 100, 2),
                "straddle_cost": round(spot * expected / 100 * 0.94, 2),
            }
        )
    return pd.DataFrame(rows)


def _timeline(df: pd.DataFrame, state: Any) -> pn.Column:
    if not df.empty and hasattr(state, "update_signal_bundle"):
        state.update_signal_bundle(catalyst_proximity=int(df["days_to"].min()))
    cards = []
    for row in df.itertuples(index=False):
        cards.append(
            pn.pane.HTML(
                f"""
                <div class="event-card">
                  <div style="display:grid;grid-template-columns:44px 1fr 72px;gap:10px;align-items:center;">
                    <div class="mono" style="color:{PALETTE['blue']};font-weight:800;">{row.type[:4].upper()}</div>
                    <div>
                      <div style="font-weight:800;">{row.name}</div>
                      <div class="metric-label">{row.date} | {row.days_to} days</div>
                    </div>
                    <div class="mono" style="text-align:right;color:{PALETTE['amber']};">
                      ${row.expected_dollars:.2f}<br>{row.expected_pct:.1f}%
                    </div>
                  </div>
                  <div class="metric-label" style="margin-top:6px;">ATM straddle: ${row.straddle_cost:.2f}</div>
                </div>
                """,
                sizing_mode="stretch_width",
            )
        )
    return pn.Column(*cards, sizing_mode="stretch_width")


def _history_chart(ticker: str, expiry_filter: str) -> go.Figure:
    rng = stable_rng(f"history-{ticker}-{expiry_filter}")
    labels = [f"E-{i}" for i in range(8, 0, -1)]
    expected = rng.uniform(3.2, 6.8, 8)
    actual = expected + rng.normal(0.7, 2.1, 8)
    colors = [PALETTE["green"] if actual[i] > expected[i] else PALETTE["red"] for i in range(8)]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=np.round(actual, 1), marker_color=colors, name="Actual Move %"))
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=np.round(expected, 1),
            mode="lines+markers",
            line={"color": PALETTE["blue"], "width": 3},
            name="Expected Move %",
        )
    )
    fig.update_layout(title="Historical Move vs Expected Move", yaxis_title="Move %")
    return fig


def create_panel(ticker: str = "SPY", state: Any | None = None) -> pn.viewable.Viewable:
    """Return the catalysts stub panel."""

    state = ensure_state(ticker, state)
    ticker_input = pn.widgets.TextInput(name="Ticker", value=state.active_ticker, width=120)
    sync_ticker_widget(ticker_input, state)
    expiry_filter = pn.widgets.Select(name="Expiry Filter", options=["Next 30D", "Next 60D", "All"], value="Next 60D", width=140)

    def timeline(ticker_value: str, selected_filter: str) -> pn.Column:
        return _timeline(_events(ticker_value, selected_filter), state)

    def chart(ticker_value: str, selected_filter: str) -> pn.pane.Plotly:
        return plotly_pane(_history_chart(ticker_value, selected_filter), height=300)

    callout = pn.pane.HTML(
        """
        <div class="callout">
          <div class="section-label">Decision Callout</div>
          <div style="font-weight:800;margin-top:4px;">
            Historical moves consistently EXCEED EM -> consider buying vol with a straddle or strangle.
          </div>
        </div>
        """,
        sizing_mode="stretch_width",
    )

    return pn.Column(
        pn.Row(ticker_input, expiry_filter, pn.Spacer(sizing_mode="stretch_width")),
        pn.Row(
            pn.Card(
                pn.bind(timeline, ticker_input.param.value, expiry_filter.param.value),
                title="Catalyst Timeline",
                width=380,
                css_classes=["desk-card"],
            ),
            pn.Column(
                pn.Card(
                    pn.bind(chart, ticker_input.param.value, expiry_filter.param.value),
                    title="Move History",
                    sizing_mode="stretch_width",
                    css_classes=["desk-card"],
                ),
                callout,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )
