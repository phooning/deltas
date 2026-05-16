"""Strategy Lab page for ranked short-term spread candidates.

This page contributes SignalBundle.recommended_structure and SignalBundle.conviction
by generating three spread proposals and exposing manual conviction inputs.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import panel as pn
import plotly.graph_objects as go

from core.strategies import select_spreads
from trading_desk.pages._common import (
    PALETTE,
    ensure_state,
    pill_html,
    plotly_pane,
    sync_date_widget,
    sync_ticker_widget,
)


def _iv_rank(ticker: str, clicks: int) -> float:
    return float(35 + (sum(ord(char) for char in ticker) + clicks * 7) % 46)


def _proposal_payoff(name: str, index: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.linspace(420, 550, 80)
    if "Bull" in name:
        y = np.clip((x - 462) * 2.5, -380, 118)
    elif "Bear" in name:
        y = np.clip((516 - x) * 2.1, -406, 94)
    else:
        y = 162 - np.maximum(np.abs(x - 490) - 24, 0) * 15
        y = np.clip(y, -338, 162)
    return x, y + index * 4


def _sparkline(name: str, index: int) -> pn.pane.Plotly:
    x, y = _proposal_payoff(name, index)
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line={"color": PALETTE["green"] if y[-1] > y[0] else PALETTE["amber"], "width": 2},
        )
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return plotly_pane(fig, height=120)


def create_panel(
    ticker: str = "SPY",
    state: Any | None = None,
    set_active_tab: Callable[[str], None] | None = None,
) -> pn.viewable.Viewable:
    """Return the strategy lab stub panel."""

    state = ensure_state(ticker, state)
    ticker_input = pn.widgets.TextInput(name="Ticker", value=state.active_ticker, width=120)
    sync_ticker_widget(ticker_input, state)
    expiry = pn.widgets.DatePicker(name="Expiry", value=state.active_expiry)
    sync_date_widget(expiry, state)
    generate = pn.widgets.Button(name="Generate Spreads", button_type="primary", width=150)
    toggles = pn.widgets.CheckButtonGroup(
        name="Overlay",
        options=["Bull Put Spread", "Bear Call Spread", "Iron Condor"],
        value=["Bull Put Spread", "Bear Call Spread", "Iron Condor"],
        button_type="default",
    )

    trend_slider = pn.widgets.FloatSlider(name="Trend", start=0, end=100, value=68, step=1)
    iv_slider = pn.widgets.FloatSlider(name="IV Setup", start=0, end=100, value=62, step=1)
    catalyst_slider = pn.widgets.FloatSlider(name="Catalyst", start=0, end=100, value=57, step=1)
    risk_slider = pn.widgets.FloatSlider(name="Risk Fit", start=0, end=100, value=61, step=1)

    @pn.depends(
        trend_slider.param.value,
        iv_slider.param.value,
        catalyst_slider.param.value,
        risk_slider.param.value,
        watch=True,
    )
    def update_conviction(trend: float, iv_setup: float, catalyst: float, risk_fit: float) -> None:
        conviction = (trend * 0.3 + iv_setup * 0.3 + catalyst * 0.2 + risk_fit * 0.2) / 100
        state.conviction = conviction
        if hasattr(state, "update_signal_bundle"):
            state.update_signal_bundle(conviction=conviction)

    update_conviction(trend_slider.value, iv_slider.value, catalyst_slider.value, risk_slider.value)

    def iv_badge(ticker_value: str, clicks: int) -> pn.pane.HTML:
        rank = _iv_rank(ticker_value, clicks)
        if hasattr(state, "update_signal_bundle"):
            state.update_signal_bundle(iv_rank=rank)
        tone = "green" if rank < 70 else "amber" if rank < 85 else "red"
        return pn.pane.HTML(pill_html(f"IV RANK {rank:.0f}", tone), width=120)

    def proposals(ticker_value: str, expiry_value: Any, clicks: int) -> list[dict[str, object]]:
        return select_spreads(ticker_value, expiry_value, _iv_rank(ticker_value, clicks))

    def proposal_cards(ticker_value: str, expiry_value: Any, clicks: int) -> pn.FlexBox:
        cards = []
        for index, proposal in enumerate(proposals(ticker_value, expiry_value, clicks)):
            tone = "green" if proposal["direction"] == "Bullish" else "red" if proposal["direction"] == "Bearish" else "amber"
            open_button = pn.widgets.Button(name="Open in Calculator", button_type="default", width=150)

            def open_calc(_event: Any, structure: str = str(proposal["structure"])) -> None:
                if hasattr(state, "update_signal_bundle"):
                    state.update_signal_bundle(recommended_structure=structure.lower())
                if set_active_tab is not None:
                    set_active_tab("Options Calc")

            open_button.on_click(open_calc)
            cards.append(
                pn.Card(
                    pn.pane.HTML(
                        f"""
                        <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;">
                          <div>
                            <div class="metric-label">Structure</div>
                            <div style="font-weight:800;">{proposal['structure']}</div>
                          </div>
                          {pill_html(str(proposal['direction']).upper(), tone)}
                        </div>
                        """
                    ),
                    pn.Row(
                        pn.pane.HTML(f"<div class='metric-label'>Entry</div><div class='mono'>${proposal['entry_cost']}</div>"),
                        pn.pane.HTML(f"<div class='metric-label'>Max Profit</div><div class='mono tone-green'>${proposal['max_profit']}</div>"),
                        pn.pane.HTML(f"<div class='metric-label'>Max Loss</div><div class='mono tone-red'>${proposal['max_loss']}</div>"),
                    ),
                    pn.Row(
                        pn.pane.HTML(f"<div class='metric-label'>POP</div><div class='mono'>{proposal['probability_of_profit']}%</div>"),
                        pn.pane.HTML(f"<div class='metric-label'>B/E</div><div class='mono'>{proposal['breakevens']}</div>"),
                    ),
                    pn.Row(
                        pn.pane.HTML(f"<div class='metric-label'>Req Move</div><div class='mono'>{proposal['required_move_pct']}%</div>"),
                        pn.pane.HTML(f"<div class='metric-label'>Exp Move</div><div class='mono'>{proposal['expected_move_pct']}%</div>"),
                    ),
                    _sparkline(str(proposal["structure"]), index),
                    pn.pane.Markdown(str(proposal["short_note"])),
                    open_button,
                    title=f"Rank {index + 1}",
                    width=320,
                    css_classes=["desk-card"],
                )
            )
        return pn.FlexBox(*cards, flex_wrap="wrap", gap="12px", sizing_mode="stretch_width")

    def overlay(selected: list[str], ticker_value: str, expiry_value: Any, clicks: int) -> pn.pane.Plotly:
        del expiry_value
        fig = go.Figure()
        for index, proposal in enumerate(proposals(ticker_value, state.active_expiry, clicks)):
            name = str(proposal["structure"])
            if name not in selected:
                continue
            x, y = _proposal_payoff(name, index)
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name, line={"width": 3}))
        fig.update_layout(title="Spread Payoff Overlay", xaxis_title="Underlying", yaxis_title="P/L")
        return plotly_pane(fig, height=320)

    controls = pn.Row(
        ticker_input,
        expiry,
        generate,
        pn.bind(iv_badge, ticker_input.param.value, generate.param.clicks),
        pn.Spacer(sizing_mode="stretch_width"),
    )

    conviction_inputs = pn.Card(
        trend_slider,
        iv_slider,
        catalyst_slider,
        risk_slider,
        title="Conviction Overrides",
        width=300,
        css_classes=["desk-card"],
    )

    return pn.Column(
        controls,
        pn.bind(proposal_cards, ticker_input.param.value, expiry.param.value, generate.param.clicks),
        pn.Row(
            pn.Card(
                toggles,
                pn.bind(overlay, toggles.param.value, ticker_input.param.value, expiry.param.value, generate.param.clicks),
                title="Shared Payoff Overlay",
                sizing_mode="stretch_width",
                css_classes=["desk-card"],
            ),
            conviction_inputs,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )
