"""Sidebar watchlist component.

The watchlist is the primary cross-page ticker router and contributes the
SignalBundle.ticker field through the shared AppState.active_ticker parameter.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import panel as pn

from trading_desk.pages._common import PALETTE, stable_seed


WATCHLIST = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "TSLA", "AMD", "IWM"]


def _frame(active_ticker: str, tick: int = 0) -> pd.DataFrame:
    rows = []
    for ticker in WATCHLIST:
        rng = np.random.default_rng(stable_seed(f"{ticker}-{tick // 4}"))
        base = 95 + stable_seed(ticker) % 420
        drift = rng.normal(0, 0.55)
        pct = rng.normal(0.18, 1.15)
        rows.append(
            {
                "Ticker": ticker,
                "Price": f"{base + drift:,.2f}",
                "% Chg": f"{pct:+.2f}%",
                "Active": ">" if ticker == active_ticker else "",
            }
        )
    return pd.DataFrame(rows)


def create_watchlist(state: Any) -> pn.Column:
    """Create a selectable dummy watchlist that updates shared active ticker."""

    table = pn.widgets.Tabulator(
        _frame(state.active_ticker),
        show_index=False,
        selectable=1,
        height=250,
        widths={"Active": 22, "Ticker": 54, "Price": 68, "% Chg": 58},
        css_classes=["watchlist-table"],
        stylesheets=[
            f"""
            .tabulator {{
              background: {PALETTE['surface']};
              border: 1px solid {PALETTE['border']};
              color: {PALETTE['text']};
              font-size: 11px;
            }}
            .tabulator-row, .tabulator-cell {{
              background: {PALETTE['surface']};
              color: {PALETTE['text']};
              border-color: {PALETTE['border']};
            }}
            .tabulator-selected .tabulator-cell {{
              background: #58a6ff26 !important;
            }}
            """
        ],
    )

    tick = {"value": 0}

    def refresh() -> None:
        tick["value"] += 1
        table.value = _frame(state.active_ticker, tick["value"])

    def select_ticker(event: Any) -> None:
        if not event.new:
            return
        index = event.new[0]
        if 0 <= index < len(WATCHLIST):
            state.active_ticker = WATCHLIST[index]
            if hasattr(state, "update_signal_bundle"):
                state.update_signal_bundle(ticker=WATCHLIST[index])
            refresh()

    def sync_selection(event: Any) -> None:
        if event.new in WATCHLIST:
            table.selection = [WATCHLIST.index(event.new)]
            refresh()

    table.param.watch(select_ticker, "selection")
    state.param.watch(sync_selection, "active_ticker")
    pn.state.add_periodic_callback(refresh, period=3000)

    if state.active_ticker in WATCHLIST:
        table.selection = [WATCHLIST.index(state.active_ticker)]

    return pn.Column(
        pn.pane.HTML("<div class='section-label'>Watchlist</div>"),
        table,
        sizing_mode="stretch_width",
    )
