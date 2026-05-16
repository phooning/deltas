"""Shared presentation helpers for the Panel trading desk stubs.

These utilities keep page modules importable with no data side effects while
preserving the SignalBundle fields each page will eventually feed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import panel as pn
import param

from core.signals import SignalBundle


PALETTE = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "border": "#30363d",
    "text": "#c9d1d9",
    "muted": "#8b949e",
    "blue": "#58a6ff",
    "green": "#3fb950",
    "red": "#f85149",
    "amber": "#d29922",
}


class LocalState(param.Parameterized):
    """Minimal state object used when a page is imported standalone."""

    active_ticker = param.String(default="SPY")
    active_expiry = param.Date(default=date.today() + timedelta(days=45))
    active_tab = param.String(default="Options Calc")
    conviction = param.Number(default=0.62, bounds=(0, 1))
    regime = param.Selector(default="transitional", objects=["risk-on", "risk-off", "transitional"])
    vix_spot = param.Number(default=16.8)
    signal_bundle = param.Parameter(default=None, allow_None=True)

    def __init__(self, **params: Any) -> None:
        super().__init__(**params)
        if self.signal_bundle is None:
            self.update_signal_bundle()

    def update_signal_bundle(self, **overrides: Any) -> None:
        current = self.signal_bundle
        data = {
            "ticker": self.active_ticker,
            "trend": "up",
            "iv_rank": 54.0,
            "regime": self.regime,
            "catalyst_proximity": 12,
            "fundamental_score": 4,
            "conviction": self.conviction,
            "recommended_structure": "bull put spread",
        }
        if current is not None:
            data.update(current.__dict__)
        data.update(
            ticker=self.active_ticker,
            regime=self.regime,
            conviction=self.conviction,
        )
        data.update(overrides)
        self.signal_bundle = SignalBundle(**data)


def ensure_state(ticker: str, state: Any | None = None) -> Any:
    """Return the shared app state or a local standalone state."""

    if state is not None:
        return state
    return LocalState(active_ticker=(ticker or "SPY").upper())


def stable_seed(label: str) -> int:
    """Create a deterministic seed from display text."""

    return sum((index + 1) * ord(char) for index, char in enumerate(label)) % (2**32)


def stable_rng(label: str) -> np.random.Generator:
    return np.random.default_rng(stable_seed(label))


def sync_ticker_widget(widget: pn.widgets.TextInput, state: Any) -> None:
    """Wire a TextInput to state.active_ticker without creating feedback loops."""

    syncing = {"value": False}

    def push_to_state(event: param.parameterized.Event) -> None:
        if syncing["value"]:
            return
        value = (event.new or "").strip().upper()
        if value and value != state.active_ticker:
            state.active_ticker = value
            if hasattr(state, "update_signal_bundle"):
                state.update_signal_bundle(ticker=value)

    def pull_from_state(event: param.parameterized.Event) -> None:
        if widget.value == event.new:
            return
        syncing["value"] = True
        widget.value = event.new
        syncing["value"] = False

    widget.param.watch(push_to_state, "value")
    state.param.watch(pull_from_state, "active_ticker")


def sync_date_widget(widget: pn.widgets.DatePicker, state: Any) -> None:
    """Wire a DatePicker to state.active_expiry."""

    syncing = {"value": False}

    def push_to_state(event: param.parameterized.Event) -> None:
        if syncing["value"] or event.new is None:
            return
        if event.new != state.active_expiry:
            state.active_expiry = event.new

    def pull_from_state(event: param.parameterized.Event) -> None:
        if widget.value == event.new:
            return
        syncing["value"] = True
        widget.value = event.new
        syncing["value"] = False

    widget.param.watch(push_to_state, "value")
    state.param.watch(pull_from_state, "active_expiry")


def theme_plot(fig: Any, height: int = 280, showlegend: bool = False) -> Any:
    """Apply the app's dark, dense Plotly defaults."""

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=PALETTE["surface"],
        plot_bgcolor=PALETTE["surface"],
        height=height,
        margin={"l": 42, "r": 22, "t": 34, "b": 36},
        font={"family": "Inter, sans-serif", "color": PALETTE["text"], "size": 11},
        showlegend=showlegend,
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    fig.update_xaxes(gridcolor="#21262d", zerolinecolor=PALETTE["border"])
    fig.update_yaxes(gridcolor="#21262d", zerolinecolor=PALETTE["border"])
    return fig


def plotly_pane(fig: Any, height: int = 280) -> pn.pane.Plotly:
    """Create a responsive Plotly pane with modebar hidden."""

    return pn.pane.Plotly(
        theme_plot(fig, height=height),
        config={"displayModeBar": False, "responsive": True},
        sizing_mode="stretch_width",
        height=height,
    )


def pill_html(label: str, tone: str = "muted") -> str:
    colors = {
        "green": PALETTE["green"],
        "red": PALETTE["red"],
        "amber": PALETTE["amber"],
        "blue": PALETTE["blue"],
        "muted": PALETTE["muted"],
    }
    color = colors.get(tone, PALETTE["muted"])
    return (
        f"<span class='status-pill' style='border-color:{color};"
        f"color:{color};background:{color}1f'>{label}</span>"
    )


def metric_html(label: str, value: str, tone: str = "muted") -> pn.pane.HTML:
    return pn.pane.HTML(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value tone-{tone}">{value}</div>
        </div>
        """,
        sizing_mode="stretch_width",
    )
