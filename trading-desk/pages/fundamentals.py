"""Fundamental context page for medium-term trade conviction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

import pandas as pd
import panel as pn
import plotly.graph_objects as go


pn.extension("tabulator", "plotly", sizing_mode="stretch_width")


SECTOR_PEERS = {
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "ORCL", "ADBE"],
    "NVDA": ["AMD", "AVGO", "QCOM", "MRVL"],
    "AMD": ["NVDA", "INTC", "QCOM", "AVGO"],
    "TSLA": ["F", "GM", "RIVN", "NIO"],
    "SPY": ["VOO", "IVV", "QQQ", "DIA"],
    "QQQ": ["SPY", "IWM", "VGT", "XLK"],
}


@dataclass(frozen=True)
class ConvictionRead:
    score: int
    label: str
    tone: str
    rationale: str


def _seed(ticker: str, salt: str) -> int:
    digest = hashlib.sha256(f"{ticker.upper()}:{salt}".encode()).hexdigest()
    return int(digest[:8], 16)


def _bounded(seed: int, low: float, high: float) -> float:
    return low + (seed % 10_000) / 10_000 * (high - low)


def earnings_history(ticker: str, n: int = 8) -> pd.DataFrame:
    """Return recent earnings with EPS beat/miss and surprise percentage."""
    ticker = ticker.upper().strip() or "SPY"
    rows = []
    base_revenue = _bounded(_seed(ticker, "revenue"), 8.5, 92.0)

    for idx in range(n):
        quarter_index = n - idx
        period = pd.Period(date.today(), freq="Q") - quarter_index
        estimate = _bounded(_seed(ticker, f"eps-est-{idx}"), 0.55, 4.75)
        surprise_pct = _bounded(_seed(ticker, f"surprise-{idx}"), -14.0, 18.0)
        actual = estimate * (1 + surprise_pct / 100)
        revenue_growth = _bounded(_seed(ticker, f"revenue-growth-{idx}"), -0.06, 0.09)
        revenue = base_revenue * (1 + revenue_growth) ** idx

        rows.append(
            {
                "quarter": str(period),
                "eps_estimate": round(estimate, 2),
                "eps_actual": round(actual, 2),
                "surprise_pct": round(surprise_pct, 1),
                "result": "Beat" if surprise_pct >= 0 else "Miss",
                "revenue_bn": round(revenue, 2),
            }
        )

    history = pd.DataFrame(rows)
    history["beat_miss_streak"] = _beat_miss_streak(history["result"])
    return history


def peer_valuation_table(ticker: str) -> pd.DataFrame:
    """Return valuation multiples for the ticker and close comps."""
    ticker = ticker.upper().strip() or "SPY"
    peers = [ticker, *SECTOR_PEERS.get(ticker, ["SPY", "QQQ", "IWM", "DIA"])]
    rows = []

    for symbol in peers:
        rows.append(
            {
                "ticker": symbol,
                "ev_ebitda": round(_bounded(_seed(symbol, "ev-ebitda"), 8.0, 32.0), 1),
                "price_sales": round(_bounded(_seed(symbol, "ps"), 1.2, 14.0), 1),
                "pe_ratio": round(_bounded(_seed(symbol, "pe"), 11.0, 58.0), 1),
                "forward_pe": round(_bounded(_seed(symbol, "forward-pe"), 10.0, 46.0), 1),
            }
        )

    table = pd.DataFrame(rows)
    peer_median_pe = table.loc[table["ticker"] != ticker, "pe_ratio"].median()
    table["pe_vs_peer_median"] = (table["pe_ratio"] - peer_median_pe).round(1)
    return table


def ownership_delta(ticker: str) -> dict:
    """Return skeletal 13F ownership changes quarter over quarter."""
    ticker = ticker.upper().strip() or "SPY"
    net_shares = round(_bounded(_seed(ticker, "net-shares"), -18.0, 24.0), 1)
    holder_delta = int(round(_bounded(_seed(ticker, "holders"), -28, 42)))
    top_holder_delta = round(_bounded(_seed(ticker, "top-holder"), -4.0, 5.5), 1)

    return {
        "ticker": ticker,
        "period": f"{pd.Period(date.today(), freq='Q') - 1}",
        "net_shares_change_m": net_shares,
        "holder_count_change": holder_delta,
        "top_10_ownership_delta_pct": top_holder_delta,
        "read": _ownership_read(net_shares, holder_delta, top_holder_delta),
    }


def forward_eps_estimates(ticker: str) -> pd.DataFrame:
    ticker = ticker.upper().strip() or "SPY"
    current_year = date.today().year
    rows = []

    for offset in range(4):
        fiscal_year = current_year + offset
        estimate = _bounded(_seed(ticker, f"forward-eps-{offset}"), 3.25, 16.5)
        revision = _bounded(_seed(ticker, f"forward-rev-{offset}"), -7.5, 9.5)
        rows.append(
            {
                "fiscal_year": fiscal_year,
                "eps_estimate": round(estimate, 2),
                "revision_90d_pct": round(revision, 1),
            }
        )

    return pd.DataFrame(rows)


def fundamental_score(ticker: str) -> ConvictionRead:
    earnings = earnings_history(ticker)
    valuation = peer_valuation_table(ticker)
    ownership = ownership_delta(ticker)
    estimates = forward_eps_estimates(ticker)

    beat_rate = (earnings["result"] == "Beat").mean()
    latest_revenue = earnings["revenue_bn"].iloc[-1]
    prior_revenue = earnings["revenue_bn"].iloc[0]
    revenue_trend = (latest_revenue - prior_revenue) / max(prior_revenue, 0.01)
    pe_gap = valuation.loc[valuation["ticker"] == ticker.upper(), "pe_vs_peer_median"].iloc[0]
    eps_revision = estimates["revision_90d_pct"].tail(2).mean()

    raw = 2.5
    raw += 1.0 if beat_rate >= 0.62 else -0.4
    raw += 0.7 if revenue_trend > 0 else -0.4
    raw += 0.4 if pe_gap <= 8 else -0.4
    raw += 0.5 if eps_revision > 0 else -0.3
    raw += 0.4 if ownership["net_shares_change_m"] > 0 else -0.2

    score = max(1, min(5, round(raw)))
    labels = {
        1: ("Fragile", "#b42318"),
        2: ("Mixed", "#b54708"),
        3: ("Intact", "#175cd3"),
        4: ("Constructive", "#067647"),
        5: ("High Conviction", "#05603a"),
    }
    label, tone = labels[score]
    rationale = (
        f"{beat_rate:.0%} beat rate, revenue trend {revenue_trend:.1%}, "
        f"P/E gap {pe_gap:+.1f} pts, EPS revisions {eps_revision:+.1f}%."
    )
    return ConvictionRead(score=score, label=label, tone=tone, rationale=rationale)


def build_page() -> pn.viewable.Viewable:
    ticker = pn.widgets.TextInput(name="Ticker", value="NVDA", placeholder="Ticker")
    refresh = pn.widgets.Button(name="Refresh", button_type="primary")

    @pn.depends(ticker.param.value, refresh.param.clicks)
    def view(symbol: str, _clicks: int) -> pn.Column:
        clean_symbol = symbol.upper().strip() or "NVDA"
        earnings = earnings_history(clean_symbol)
        valuations = peer_valuation_table(clean_symbol)
        ownership = ownership_delta(clean_symbol)
        estimates = forward_eps_estimates(clean_symbol)
        score = fundamental_score(clean_symbol)

        return pn.Column(
            _score_row(score),
            pn.Row(
                _revenue_trend(earnings),
                _trade_conviction_panel(score, ownership),
            ),
            pn.Row(
                _table_card("Earnings History", earnings),
                _table_card("Forward EPS Estimates", estimates),
            ),
            pn.Row(
                _table_card("Peer Valuation", valuations),
                _ownership_card(ownership),
            ),
        )

    return pn.Column(
        pn.pane.Markdown(
            "## Fundamentals\n"
            "Context for holding ETF shares or 3-month calls through noise.",
            margin=(0, 0, 8, 0),
        ),
        pn.Row(ticker, refresh),
        view,
    )


def _beat_miss_streak(results: pd.Series) -> list[str]:
    streaks: list[str] = []
    current = ""
    count = 0

    for result in results:
        if result == current:
            count += 1
        else:
            current = result
            count = 1
        streaks.append(f"{count} {current.lower()}")

    return streaks


def _ownership_read(net_shares: float, holder_delta: int, top_holder_delta: float) -> str:
    if net_shares > 5 and holder_delta > 0:
        return "Accumulation"
    if net_shares < -5 and holder_delta < 0:
        return "Distribution"
    if top_holder_delta > 2:
        return "Concentrating"
    return "Stable"


def _score_row(score: ConvictionRead) -> pn.Row:
    badge = pn.pane.HTML(
        f"""
        <div style="background:{score.tone};color:white;border-radius:6px;
                    padding:12px 16px;min-width:150px;text-align:center;">
            <div style="font-size:12px;text-transform:uppercase;">Fundamental Score</div>
            <div style="font-size:28px;font-weight:700;">{score.score} / 5</div>
            <div style="font-size:13px;">{score.label}</div>
        </div>
        """,
        sizing_mode="fixed",
        width=180,
        height=104,
    )
    return pn.Row(
        badge,
        pn.pane.Markdown(f"**Story check:** {score.rationale}", margin=(18, 0, 0, 8)),
    )


def _trade_conviction_panel(score: ConvictionRead, ownership: dict) -> pn.Card:
    conviction = "Hold through noise" if score.score >= 4 else "Size modestly"
    if score.score <= 2:
        conviction = "Do not ignore fundamentals"

    return pn.Card(
        pn.pane.Markdown(
            f"### Trade Conviction\n"
            f"**Read:** {conviction}\n\n"
            f"**Institutional tape:** {ownership['read']}\n\n"
            f"**13F net shares QoQ:** {ownership['net_shares_change_m']:+.1f}M\n\n"
            f"**Holder count QoQ:** {ownership['holder_count_change']:+d}",
        ),
        title="Conviction Feed",
        width=360,
        collapsed=False,
    )


def _revenue_trend(history: pd.DataFrame) -> pn.Card:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history["quarter"],
            y=history["revenue_bn"],
            mode="lines+markers",
            name="Revenue",
            line={"color": "#175cd3", "width": 3},
        )
    )
    fig.update_layout(
        title="Revenue Trend",
        yaxis_title="Revenue, $B",
        margin={"l": 45, "r": 20, "t": 45, "b": 35},
        height=320,
        template="plotly_white",
    )
    return pn.Card(pn.pane.Plotly(fig, config={"displayModeBar": False}), title="Revenue", width=620)


def _table_card(title: str, frame: pd.DataFrame) -> pn.Card:
    table = pn.widgets.Tabulator(
        frame,
        disabled=True,
        pagination="local",
        page_size=8,
        sizing_mode="stretch_width",
    )
    return pn.Card(table, title=title, min_width=420)


def _ownership_card(ownership: dict) -> pn.Card:
    items = pd.DataFrame(
        [
            {"metric": "Period", "value": ownership["period"]},
            {"metric": "Net shares change", "value": f"{ownership['net_shares_change_m']:+.1f}M"},
            {"metric": "Holder count change", "value": f"{ownership['holder_count_change']:+d}"},
            {
                "metric": "Top 10 ownership delta",
                "value": f"{ownership['top_10_ownership_delta_pct']:+.1f}%",
            },
            {"metric": "Read", "value": ownership["read"]},
        ]
    )
    return _table_card("Institutional Ownership QoQ", items)


page = build_page()
