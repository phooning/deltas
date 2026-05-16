"""Stub pricing contract for the options calculator MVP shell.

The functions here intentionally use deterministic dummy math while preserving
the shape expected from Black-Scholes, Greeks, payoff, and scenario workflows.
"""

from __future__ import annotations

from datetime import date, datetime
from math import exp, log, sqrt
from statistics import NormalDist
from typing import Any

import numpy as np


def _years_to_expiry(expiry: date | datetime | str | None) -> float:
    if expiry is None:
        return 45 / 365
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry).date()
    if isinstance(expiry, datetime):
        expiry = expiry.date()
    return max((expiry - date.today()).days, 1) / 365


def _call_price(spot: float, strike: float, rate: float, vol: float, years: float) -> float:
    if spot <= 0 or strike <= 0 or vol <= 0 or years <= 0:
        return max(spot - strike, 0)
    normal = NormalDist()
    d1 = (log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * sqrt(years))
    d2 = d1 - vol * sqrt(years)
    return spot * normal.cdf(d1) - strike * exp(-rate * years) * normal.cdf(d2)


def _put_price(spot: float, strike: float, rate: float, vol: float, years: float) -> float:
    call = _call_price(spot, strike, rate, vol, years)
    return call - spot + strike * exp(-rate * years)


def bs_greeks(
    structure_type: str,
    strike: float,
    expiry: date | datetime | str | None,
    iv_percent: float,
    underlying_price: float,
    risk_free_rate: float,
) -> dict[str, float]:
    """Return deterministic, realistic-looking Greeks for a selected structure."""

    vol = max(iv_percent / 100, 0.01)
    rate = risk_free_rate / 100
    years = _years_to_expiry(expiry)
    normal = NormalDist()
    spot = max(underlying_price, 0.01)
    strike = max(strike, 0.01)
    d1 = (log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * sqrt(years))
    base_delta = normal.cdf(d1)
    gamma = normal.pdf(d1) / (spot * vol * sqrt(years))
    vega = spot * normal.pdf(d1) * sqrt(years) / 100
    theta = -(spot * normal.pdf(d1) * vol) / (2 * sqrt(years) * 365)
    rho = strike * years * exp(-rate * years) * normal.cdf(d1 - vol * sqrt(years)) / 100

    multipliers: dict[str, tuple[float, float, float, float, float]] = {
        "Long Call": (1.0, 1.0, 1.0, 1.0, 1.0),
        "Long Put": (-1.0, 1.0, 1.0, 1.0, -1.0),
        "Bull Put Spread": (0.35, -0.35, -0.45, -0.5, -0.35),
        "Bear Call Spread": (-0.35, -0.35, -0.45, -0.5, 0.35),
        "Iron Condor": (0.03, -0.55, 0.9, -0.75, 0.02),
        "Calendar": (0.08, 0.25, -0.2, 1.25, 0.08),
        "Strangle": (0.0, 0.75, -1.0, 1.65, 0.0),
    }
    d_mult, g_mult, t_mult, v_mult, r_mult = multipliers.get(
        structure_type, (1.0, 1.0, 1.0, 1.0, 1.0)
    )

    return {
        "delta": round((base_delta - 0.5) * 2 * d_mult, 3),
        "gamma": round(gamma * g_mult, 4),
        "theta": round(theta * t_mult, 3),
        "vega": round(vega * v_mult, 3),
        "rho": round(rho * r_mult, 3),
    }


def build_payoff(
    structure_type: str,
    strike: float,
    expiry: date | datetime | str | None,
    iv_percent: float,
    underlying_price: float,
    risk_free_rate: float,
    points: int = 121,
) -> dict[str, Any]:
    """Return a payoff curve and break-evens for the selected stub structure."""

    del expiry, risk_free_rate
    spot = max(underlying_price, 1)
    strike = max(strike, 1)
    iv = max(iv_percent / 100, 0.01)
    x = np.linspace(spot * 0.65, spot * 1.35, points)
    premium = max(spot * iv * 0.08, 0.75)
    width = max(spot * 0.05, 2.5)

    if structure_type == "Long Put":
        pnl = np.maximum(strike - x, 0) - premium
        breakevens = [strike - premium]
    elif structure_type == "Bull Put Spread":
        short_put = np.maximum(strike - x, 0)
        long_put = np.maximum(strike - width - x, 0)
        credit = width * 0.32
        pnl = credit - short_put + long_put
        breakevens = [strike - credit]
    elif structure_type == "Bear Call Spread":
        short_call = np.maximum(x - strike, 0)
        long_call = np.maximum(x - strike - width, 0)
        credit = width * 0.31
        pnl = credit - short_call + long_call
        breakevens = [strike + credit]
    elif structure_type == "Iron Condor":
        low_short = strike - width
        high_short = strike + width
        spread_width = width * 0.8
        credit = spread_width * 0.42
        pnl = (
            credit
            - np.maximum(low_short - x, 0)
            + np.maximum(low_short - spread_width - x, 0)
            - np.maximum(x - high_short, 0)
            + np.maximum(x - high_short - spread_width, 0)
        )
        breakevens = [low_short - credit, high_short + credit]
    elif structure_type == "Calendar":
        pnl = np.exp(-((x - strike) / (spot * 0.075)) ** 2) * premium * 3 - premium
        breakevens = [strike - spot * 0.08, strike + spot * 0.08]
    elif structure_type == "Strangle":
        put_strike = strike - width
        call_strike = strike + width
        debit = premium * 1.45
        pnl = np.maximum(put_strike - x, 0) + np.maximum(x - call_strike, 0) - debit
        breakevens = [put_strike - debit, call_strike + debit]
    else:
        pnl = np.maximum(x - strike, 0) - premium
        breakevens = [strike + premium]

    return {
        "underlying": x,
        "pnl": pnl,
        "breakevens": [round(value, 2) for value in breakevens],
        "premium": round(float(premium), 2),
    }
