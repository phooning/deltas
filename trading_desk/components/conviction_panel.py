"""Persistent trade conviction component.

The panel consumes SignalBundle fields from all pages and exposes a manual
conviction slider so the MVP can verify color and sizing transitions.
"""

from __future__ import annotations

from typing import Any, Callable

import panel as pn

from trading_desk.pages._common import PALETTE, pill_html


def _score_color(score: int) -> str:
    if score < 40:
        return PALETTE["red"]
    if score < 70:
        return PALETTE["amber"]
    return PALETTE["green"]


def _source_grid(bundle: Any) -> str:
    trend_tone = "green" if bundle.trend == "up" else "red" if bundle.trend == "down" else "amber"
    iv_tone = "green" if 35 <= bundle.iv_rank <= 70 else "amber" if bundle.iv_rank < 80 else "red"
    regime_tone = "green" if bundle.regime == "risk-on" else "red" if bundle.regime == "risk-off" else "amber"
    catalyst_tone = "green" if bundle.catalyst_proximity <= 14 else "amber"
    fundamental_tone = "green" if bundle.fundamental_score >= 4 else "amber" if bundle.fundamental_score == 3 else "red"
    signal_tone = "green" if bundle.conviction >= 0.7 else "amber" if bundle.conviction >= 0.4 else "red"
    cells = [
        ("Trend", bundle.trend.upper(), trend_tone),
        ("IV Rank", f"{bundle.iv_rank:.0f}", iv_tone),
        ("Regime", bundle.regime.upper(), regime_tone),
        ("Catalyst", f"{bundle.catalyst_proximity}D", catalyst_tone),
        ("Fund", f"{bundle.fundamental_score}/5", fundamental_tone),
        ("Signal", f"{bundle.conviction * 100:.0f}", signal_tone),
    ]
    body = "".join(
        f"""
        <div class="signal-cell">
          <div class="metric-label">{label}</div>
          <div style="margin-top:6px;">{pill_html(value, tone)}</div>
        </div>
        """
        for label, value, tone in cells
    )
    return f"<div class='signal-grid'>{body}</div>"


def create_conviction_panel(
    state: Any,
    set_active_tab: Callable[[str], None] | None = None,
) -> pn.Card:
    """Create the persistent SignalBundle summary and routing actions."""

    slider = pn.widgets.FloatSlider(
        name="Manual Conviction",
        start=0,
        end=100,
        value=round(state.conviction * 100),
        step=1,
        width=260,
    )

    def slider_to_state(event: Any) -> None:
        value = max(0, min(100, event.new)) / 100
        if value != state.conviction:
            state.conviction = value
            if hasattr(state, "update_signal_bundle"):
                state.update_signal_bundle(conviction=value)

    def state_to_slider(event: Any) -> None:
        score = round(event.new * 100)
        if slider.value != score:
            slider.value = score

    slider.param.watch(slider_to_state, "value")
    state.param.watch(state_to_slider, "conviction")

    def summary(bundle: Any) -> pn.pane.HTML:
        score = int(round(bundle.conviction * 100))
        color = _score_color(score)
        size = 1 if score < 40 else 2 if score < 70 else 3
        return pn.pane.HTML(
            f"""
            <div style="display:grid;grid-template-columns:220px 1fr 220px;gap:14px;align-items:center;">
              <div>
                <div class="metric-label">Active Ticker</div>
                <div class="metric-value" style="font-size:30px;">{bundle.ticker}</div>
              </div>
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <div class="metric-label">Conviction Score</div>
                  <div class="mono" style="color:{color};font-size:22px;font-weight:800;">{score}/100</div>
                </div>
                <div class="progress-shell" style="margin-top:6px;">
                  <div class="progress-fill" style="width:{score}%;background:{color};"></div>
                </div>
              </div>
              <div>
                <div class="metric-label">Recommendation</div>
                <div class="mono" style="font-weight:800;color:{PALETTE['blue']};">{bundle.recommended_structure.upper()}</div>
                <div class="metric-label" style="margin-top:4px;">Suggested Size: {size} contracts</div>
              </div>
            </div>
            """,
            sizing_mode="stretch_width",
        )

    def grid(bundle: Any) -> pn.pane.HTML:
        return pn.pane.HTML(_source_grid(bundle), sizing_mode="stretch_width")

    strategy_button = pn.widgets.Button(name="Send to Strategy Lab", button_type="primary", width=170)
    calculator_button = pn.widgets.Button(name="Send to Calculator", button_type="default", width=170)

    if set_active_tab is not None:
        strategy_button.on_click(lambda _event: set_active_tab("Strategy Lab"))
        calculator_button.on_click(lambda _event: set_active_tab("Options Calc"))

    return pn.Card(
        pn.Column(
            pn.bind(summary, state.param.signal_bundle),
            pn.Row(slider, pn.Spacer(sizing_mode="stretch_width"), strategy_button, calculator_button),
            pn.bind(grid, state.param.signal_bundle),
            sizing_mode="stretch_width",
        ),
        title="Trade Conviction",
        sizing_mode="stretch_width",
        css_classes=["desk-card"],
        collapsed=False,
    )
