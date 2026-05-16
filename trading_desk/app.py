"""Panel shell for the Deltas trading desk.

This entrypoint owns global app state, ticker routing, theme installation, and
the persistent conviction surface that consumes the SignalBundle.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import panel as pn
import param

from core.signals import SignalBundle


RAW_CSS = """
:root {
  --deltas-bg: #0d1117;
  --deltas-surface: #161b22;
  --deltas-border: #30363d;
  --deltas-text: #c9d1d9;
  --deltas-muted: #8b949e;
  --deltas-blue: #58a6ff;
  --deltas-green: #3fb950;
  --deltas-red: #f85149;
  --deltas-amber: #d29922;
}

html, body, .bk-root, .pn-template, .pn-template-main {
  background: var(--deltas-bg) !important;
  color: var(--deltas-text) !important;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.pn-template-header {
  border-bottom: 1px solid var(--deltas-border) !important;
  box-shadow: none !important;
}

.bk-input, input, textarea, select {
  background: #0d1117 !important;
  border-color: var(--deltas-border) !important;
  color: var(--deltas-text) !important;
  border-radius: 4px !important;
}

.bk-btn, button {
  border-radius: 4px !important;
  border-color: var(--deltas-border) !important;
  box-shadow: none !important;
  font-weight: 600 !important;
}

.bk-card, .desk-card, .metric-card {
  background: var(--deltas-surface) !important;
  border: 1px solid var(--deltas-border) !important;
  border-radius: 4px !important;
  box-shadow: none !important;
}

.bk-card-header {
  background: var(--deltas-surface) !important;
  border-bottom: 1px solid var(--deltas-border) !important;
  color: var(--deltas-text) !important;
  font-weight: 700 !important;
}

.bk-tab {
  background: #0d1117 !important;
  color: var(--deltas-muted) !important;
  border-color: var(--deltas-border) !important;
}

.bk-tab.bk-active {
  color: var(--deltas-blue) !important;
  border-bottom-color: var(--deltas-blue) !important;
}

.topbar {
  align-items: center;
  gap: 10px;
}

.topbar-label,
.metric-label,
.watchlist-label,
.compact-label,
.section-label {
  color: var(--deltas-muted);
  font-size: 11px;
  letter-spacing: 0;
  text-transform: uppercase;
}

.mono,
.metric-value,
.watchlist-table,
.numeric,
.status-pill {
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}

.metric-card {
  padding: 10px 12px;
  min-height: 66px;
}

.metric-value {
  color: var(--deltas-text);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
}

.tone-green { color: var(--deltas-green) !important; }
.tone-red { color: var(--deltas-red) !important; }
.tone-amber { color: var(--deltas-amber) !important; }
.tone-blue { color: var(--deltas-blue) !important; }
.tone-muted { color: var(--deltas-muted) !important; }

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(92px, 1fr));
  gap: 8px;
}

.signal-cell {
  border: 1px solid var(--deltas-border);
  border-radius: 4px;
  background: #0d1117;
  padding: 8px;
}

.progress-shell {
  height: 10px;
  width: 100%;
  border: 1px solid var(--deltas-border);
  border-radius: 999px;
  background: #0d1117;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
}

.watchlist-row {
  display: grid;
  grid-template-columns: 48px 1fr 58px;
  gap: 8px;
  padding: 7px 8px;
  border: 1px solid var(--deltas-border);
  border-radius: 4px;
  background: #0d1117;
  cursor: pointer;
}

.event-card {
  border: 1px solid var(--deltas-border);
  border-radius: 4px;
  background: var(--deltas-surface);
  padding: 10px;
}

.callout {
  border: 1px solid var(--deltas-blue);
  border-radius: 4px;
  background: #58a6ff14;
  padding: 12px;
  color: var(--deltas-text);
}
"""


class AppState(param.Parameterized):
    """Shared state that routes ticker, expiry, regime, and SignalBundle updates."""

    active_ticker = param.String(default="SPY")
    active_expiry = param.Date(default=date.today() + timedelta(days=45))
    active_tab = param.String(default="Macro")
    conviction = param.Number(default=0.62, bounds=(0, 1))
    regime = param.Selector(default="risk-on", objects=["risk-on", "risk-off", "transitional"])
    vix_spot = param.Number(default=16.8)
    signal_bundle = param.Parameter(
        default=SignalBundle(
            ticker="SPY",
            trend="up",
            iv_rank=54.0,
            regime="risk-on",
            catalyst_proximity=12,
            fundamental_score=4,
            conviction=0.62,
            recommended_structure="bull put spread",
        )
    )

    def update_signal_bundle(self, **overrides: Any) -> None:
        current = self.signal_bundle
        data = {
            "ticker": self.active_ticker,
            "trend": current.trend,
            "iv_rank": current.iv_rank,
            "regime": self.regime,
            "catalyst_proximity": current.catalyst_proximity,
            "fundamental_score": current.fundamental_score,
            "conviction": self.conviction,
            "recommended_structure": current.recommended_structure,
        }
        data.update(overrides)
        self.signal_bundle = SignalBundle(**data)


def _install_css() -> None:
    if RAW_CSS not in pn.config.raw_css:
        pn.config.raw_css.append(RAW_CSS)


def _compact_conviction(state: AppState) -> pn.Column:
    def render(value: float) -> pn.pane.HTML:
        score = int(round(value * 100))
        color = "#f85149" if score < 40 else "#d29922" if score < 70 else "#3fb950"
        return pn.pane.HTML(
            f"""
            <div class="desk-card" style="padding:10px;">
              <div class="compact-label">Active Conviction</div>
              <div class="metric-value" style="font-size:26px;color:{color};">{score}</div>
              <div class="progress-shell"><div class="progress-fill" style="width:{score}%;background:{color};"></div></div>
            </div>
            """,
            sizing_mode="stretch_width",
        )

    return pn.Column(pn.bind(render, state.param.conviction), sizing_mode="stretch_width")


def create_app(state: AppState | None = None) -> pn.template.FastListTemplate:
    """Build the complete Panel trading desk shell."""

    _install_css()

    from trading_desk.components.conviction_panel import create_conviction_panel
    from trading_desk.components.market_clock import create_market_header
    from trading_desk.components.watchlist import create_watchlist
    from trading_desk.pages import (
        backtests,
        catalysts,
        fundamentals,
        macro,
        options_calculator,
        strategy_lab,
    )

    state = state or AppState()

    def refresh_bundle(*_: Any) -> None:
        state.update_signal_bundle()

    state.param.watch(refresh_bundle, ["active_ticker", "conviction", "regime"])

    ticker_search = pn.widgets.TextInput(
        name="Ticker",
        value=state.active_ticker,
        placeholder="Search ticker",
        width=148,
        css_classes=["global-ticker-search"],
    )

    def push_ticker(event: param.parameterized.Event) -> None:
        value = (event.new or "").strip().upper()
        if value and value != state.active_ticker:
            state.active_ticker = value

    def pull_ticker(event: param.parameterized.Event) -> None:
        if ticker_search.value != event.new:
            ticker_search.value = event.new

    ticker_search.param.watch(push_ticker, "value")
    state.param.watch(pull_ticker, "active_ticker")

    tab_labels = [
        "Options Calc",
        "Strategy Lab",
        "Backtests",
        "Fundamentals",
        "Catalysts",
        "Macro",
    ]
    tabs_ref: dict[str, pn.Tabs | None] = {"tabs": None}

    def set_active_tab(label: str) -> None:
        if tabs_ref["tabs"] is None:
            return
        if label in tab_labels:
            tabs_ref["tabs"].active = tab_labels.index(label)
            state.active_tab = label

    tabs = pn.Tabs(
        ("Options Calc", options_calculator.create_panel(state.active_ticker, state=state, set_active_tab=set_active_tab)),
        ("Strategy Lab", strategy_lab.create_panel(state.active_ticker, state=state, set_active_tab=set_active_tab)),
        ("Backtests", backtests.create_panel(state.active_ticker, state=state, set_active_tab=set_active_tab)),
        ("Fundamentals", fundamentals.create_panel(state.active_ticker, state=state)),
        ("Catalysts", catalysts.create_panel(state.active_ticker, state=state)),
        ("Macro", macro.create_panel(state.active_ticker, state=state)),
        dynamic=True,
        sizing_mode="stretch_width",
        active=5,
    )
    tabs_ref["tabs"] = tabs

    def update_active_tab(event: param.parameterized.Event) -> None:
        state.active_tab = tab_labels[event.new]

    tabs.param.watch(update_active_tab, "active")

    nav_buttons = []
    for label in tab_labels:
        button = pn.widgets.Button(name=label, button_type="default", width=196)
        button.on_click(lambda _event, tab=label: set_active_tab(tab))
        nav_buttons.append(button)

    sidebar = pn.Column(
        pn.pane.Markdown("### Deltas", margin=(0, 0, 4, 0)),
        pn.pane.HTML("<div class='section-label'>Navigation</div>"),
        *nav_buttons,
        pn.Spacer(height=8),
        create_watchlist(state),
        pn.Spacer(height=8),
        _compact_conviction(state),
        sizing_mode="stretch_width",
    )

    main = pn.Column(
        tabs,
        create_conviction_panel(state, set_active_tab=set_active_tab),
        sizing_mode="stretch_width",
        margin=(8, 8, 16, 8),
    )

    return pn.template.FastListTemplate(
        title="Deltas Trading Desk",
        site="Deltas",
        header=[create_market_header(state, ticker_search)],
        sidebar=[sidebar],
        main=[main],
        sidebar_width=220,
        main_max_width="100%",
        theme="dark",
        theme_toggle=False,
        accent_base_color="#58a6ff",
        header_background="#0d1117",
        header_color="#c9d1d9",
        background_color="#0d1117",
        neutral_color="#30363d",
        corner_radius=4,
        shadow=False,
    )
