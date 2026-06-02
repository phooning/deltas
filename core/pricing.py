from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.stats import norm


MIN_VOL = 1e-8
MIN_T = 1e-8
ATM_EPS = 1e-7


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


@dataclass(frozen=True)
class SABRParams:
    alpha: float
    beta: float
    rho: float
    nu: float
    rmse: float | None = None
    observations: int = 0
    success: bool = True


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    expiry: date | datetime | str
    implied_vol: float
    flag: str = "c"
    time_to_expiry: float | None = None


@dataclass(frozen=True)
class OptionChain:
    quotes: pd.DataFrame | Sequence[OptionQuote]
    underlying_price: float
    risk_free_rate: float = 0.0
    valuation_date: date | datetime | str | None = None


def _normalize_flag(flag: str) -> str:
    normalized = flag.lower()[0]
    if normalized not in {"c", "p"}:
        raise ValueError("flag must be 'c'/'call' or 'p'/'put'")
    return normalized


def _as_years(expiry: object, valuation_date: object | None) -> float:
    if isinstance(expiry, (int, float, np.number)):
        return float(expiry)

    if valuation_date is None:
        raise ValueError("valuation_date is required when expiry is not already a year fraction")

    expiry_ts = pd.Timestamp(expiry)
    valuation_ts = pd.Timestamp(valuation_date)
    return max((expiry_ts - valuation_ts).days / 365.25, 0.0)


def _chain_frame(chain: OptionChain) -> pd.DataFrame:
    if isinstance(chain.quotes, pd.DataFrame):
        frame = chain.quotes.copy()
    else:
        frame = pd.DataFrame([quote.__dict__ for quote in chain.quotes])

    rename_map = {
        "K": "strike",
        "Strike": "strike",
        "expiration": "expiry",
        "expiration_date": "expiry",
        "iv": "implied_vol",
        "IV": "implied_vol",
        "impliedVolatility": "implied_vol",
        "T": "time_to_expiry",
        "time_to_maturity": "time_to_expiry",
    }
    frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})

    required = {"strike", "implied_vol"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"option chain is missing required columns: {sorted(missing)}")

    if "time_to_expiry" not in frame.columns:
        if "expiry" not in frame.columns:
            raise ValueError("option chain must include expiry or time_to_expiry")
        frame["time_to_expiry"] = frame["expiry"].map(
            lambda expiry: _as_years(expiry, chain.valuation_date)
        )

    if "expiry" not in frame.columns:
        frame["expiry"] = frame["time_to_expiry"]

    if "flag" not in frame.columns:
        frame["flag"] = "c"

    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    frame["implied_vol"] = pd.to_numeric(frame["implied_vol"], errors="coerce")
    frame["time_to_expiry"] = pd.to_numeric(frame["time_to_expiry"], errors="coerce")

    return frame.dropna(subset=["strike", "implied_vol", "time_to_expiry"])


def bs_price(S, K, T, r, sigma, flag) -> float:
    flag = _normalize_flag(flag)
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)

    if S <= 0 or K <= 0:
        raise ValueError("S and K must be positive")

    if T <= 0:
        return max(S - K, 0.0) if flag == "c" else max(K - S, 0.0)

    if sigma <= 0:
        forward_intrinsic = max(S - K * np.exp(-r * T), 0.0)
        return forward_intrinsic if flag == "c" else max(K * np.exp(-r * T) - S, 0.0)

    sqrt_t = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    if flag == "c":
        return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def bs_greeks(S, K, T, r, sigma, flag) -> Greeks:
    flag = _normalize_flag(flag)
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)

    if S <= 0 or K <= 0:
        raise ValueError("S and K must be positive")

    if T <= 0 or sigma <= 0:
        if flag == "c":
            delta = 1.0 if S > K else 0.0
        else:
            delta = -1.0 if S < K else 0.0
        return Greeks(delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)

    sqrt_t = np.sqrt(T)
    discount = np.exp(-r * T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    pdf_d1 = norm.pdf(d1)

    gamma = pdf_d1 / (S * sigma * sqrt_t)
    vega = S * pdf_d1 * sqrt_t

    if flag == "c":
        delta = norm.cdf(d1)
        theta = -(S * pdf_d1 * sigma) / (2 * sqrt_t) - r * K * discount * norm.cdf(d2)
        rho = K * T * discount * norm.cdf(d2)
    else:
        delta = norm.cdf(d1) - 1
        theta = -(S * pdf_d1 * sigma) / (2 * sqrt_t) + r * K * discount * norm.cdf(-d2)
        rho = -K * T * discount * norm.cdf(-d2)

    return Greeks(
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
        rho=float(rho),
    )


def sabr_vol(F, K, T, alpha, beta, rho, nu) -> float:
    F = float(F)
    K = float(K)
    T = float(T)
    alpha = float(alpha)
    beta = float(beta)
    rho = float(rho)
    nu = float(nu)

    if F <= 0 or K <= 0:
        raise ValueError("F and K must be positive")
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    if not 0 <= beta <= 1:
        raise ValueError("beta must be in [0, 1]")
    if not -1 < rho < 1:
        raise ValueError("rho must be in (-1, 1)")
    if nu < 0:
        raise ValueError("nu must be non-negative")

    T = max(T, MIN_T)
    one_minus_beta = 1.0 - beta
    fk_beta = (F * K) ** (0.5 * one_minus_beta)
    log_fk = np.log(F / K)

    correction = (
        (one_minus_beta**2 * alpha**2) / (24.0 * fk_beta**2)
        + (rho * beta * nu * alpha) / (4.0 * fk_beta)
        + ((2.0 - 3.0 * rho**2) * nu**2) / 24.0
    ) * T

    if abs(log_fk) < ATM_EPS:
        return float((alpha / (F ** one_minus_beta)) * (1.0 + correction))

    z = (nu / alpha) * fk_beta * log_fk if nu > 0 else 0.0
    if abs(z) < ATM_EPS:
        z_over_x = 1.0
    else:
        x_z = np.log((np.sqrt(1.0 - 2.0 * rho * z + z**2) + z - rho) / (1.0 - rho))
        z_over_x = z / x_z

    denominator = fk_beta * (
        1.0
        + (one_minus_beta**2 / 24.0) * log_fk**2
        + (one_minus_beta**4 / 1920.0) * log_fk**4
    )
    return float((alpha / denominator) * z_over_x * (1.0 + correction))


def calibrate_sabr(chain: OptionChain) -> SABRParams:
    frame = _chain_frame(chain)
    frame = frame[
        (frame["strike"] > 0)
        & (frame["implied_vol"] > MIN_VOL)
        & (frame["time_to_expiry"] > MIN_T)
    ].copy()

    if len(frame) < 4:
        raise ValueError("at least four valid option quotes are required to calibrate SABR")

    strikes = frame["strike"].to_numpy(dtype=float)
    expiries = frame["time_to_expiry"].to_numpy(dtype=float)
    observed_vols = frame["implied_vol"].to_numpy(dtype=float)
    forwards = chain.underlying_price * np.exp(chain.risk_free_rate * expiries)

    median_t = float(np.median(expiries))
    atm_idx = int(np.argmin(np.abs(strikes - np.median(forwards))))
    beta_guess = 0.5
    alpha_guess = max(
        observed_vols[atm_idx] * (forwards[atm_idx] ** (1.0 - beta_guess)),
        0.01,
    )
    nu_guess = 0.5
    x0 = np.array([alpha_guess, beta_guess, -0.2, nu_guess], dtype=float)

    def residuals(params: np.ndarray) -> np.ndarray:
        alpha, beta, rho, nu = params
        modeled = np.array(
            [
                sabr_vol(F, K, T, alpha, beta, rho, nu)
                for F, K, T in zip(forwards, strikes, expiries, strict=True)
            ]
        )
        weights = np.sqrt(np.maximum(median_t, MIN_T) / np.maximum(expiries, MIN_T))
        return (modeled - observed_vols) * weights

    result = least_squares(
        residuals,
        x0=x0,
        bounds=([MIN_VOL, 0.0, -0.999, 0.0], [10.0, 1.0, 0.999, 10.0]),
        max_nfev=2_000,
    )
    rmse = float(np.sqrt(np.mean(residuals(result.x) ** 2)))
    alpha, beta, rho, nu = result.x

    return SABRParams(
        alpha=float(alpha),
        beta=float(beta),
        rho=float(rho),
        nu=float(nu),
        rmse=rmse,
        observations=len(frame),
        success=bool(result.success),
    )


def vol_surface(chain: OptionChain) -> xr.DataArray:
    import xarray as xr

    frame = _chain_frame(chain)
    surface = (
        frame.pivot_table(
            values="implied_vol",
            index="strike",
            columns="expiry",
            aggfunc="mean",
        )
        .sort_index()
        .sort_index(axis=1)
    )

    return xr.DataArray(
        surface.to_numpy(dtype=float),
        coords={
            "strike": surface.index.to_numpy(dtype=float),
            "expiry": surface.columns.to_numpy(),
        },
        dims=("strike", "expiry"),
        name="implied_volatility",
    )
