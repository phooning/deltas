"""Top-bar market context component.

This component contributes live market-clock awareness, the VIX spot badge, and
the current regime pill that ultimately feeds SignalBundle.regime.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import panel as pn

from trading_desk.pages._common import PALETTE, pill_html


def _clock_html() -> str:
    now = datetime.now(ZoneInfo("America/New_York"))
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    is_session = now.weekday() < 5 and market_open <= now <= market_close
    tone = PALETTE["green"] if is_session else PALETTE["amber"]
    label = "OPEN" if is_session else "CLOSED"
    return (
        "<div class='mono' style='display:flex;gap:8px;align-items:center;'>"
        f"<span style='color:{PALETTE['muted']};'>NYSE</span>"
        f"<span style='color:{tone};font-weight:800;'>{label}</span>"
        f"<span>{now.strftime('%H:%M:%S ET')}</span>"
        "</div>"
    )


def create_market_header(
    state: Any,
    ticker_input: pn.widgets.TextInput | None = None,
) -> pn.Row:
    """Create the global ticker search, live clock, VIX badge, and regime pill."""

    ticker_input = ticker_input or pn.widgets.TextInput(
        name="Ticker",
        value=state.active_ticker,
        placeholder="Search ticker",
        width=148,
    )
    clock = pn.pane.HTML(_clock_html(), width=210)

    def tick() -> None:
        clock.object = _clock_html()

    pn.state.add_periodic_callback(tick, period=1000)

    def vix_badge(value: float) -> pn.pane.HTML:
        tone = "green" if value < 18 else "amber" if value < 24 else "red"
        return pn.pane.HTML(
            f"<div class='mono'>{pill_html(f'VIX {value:.1f}', tone)}</div>",
            width=92,
        )

    def regime_badge(regime: str) -> pn.pane.HTML:
        tone = "green" if regime == "risk-on" else "red" if regime == "risk-off" else "amber"
        return pn.pane.HTML(pill_html(regime.upper(), tone), width=132)

    bell = pn.pane.HTML(
        f"""
        <div class="mono" style="border:1px solid {PALETTE['border']};border-radius:4px;
        width:34px;height:30px;display:flex;align-items:center;justify-content:center;color:{PALETTE['blue']};">
        03
        </div>
        """,
        width=38,
    )

    return pn.Row(
        pn.pane.HTML("<div class='topbar-label'>Ticker</div>", width=46),
        ticker_input,
        pn.Spacer(width=16),
        clock,
        pn.Spacer(width=10),
        pn.bind(vix_badge, state.param.vix_spot),
        pn.bind(regime_badge, state.param.regime),
        pn.Spacer(sizing_mode="stretch_width"),
        pn.pane.HTML("<div class='topbar-label'>Alerts</div>", width=48),
        bell,
        sizing_mode="stretch_width",
        css_classes=["topbar"],
        margin=(0, 8, 0, 8),
    )
