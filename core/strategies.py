"""Stub spread selection contract for Strategy Lab.

The MVP returns deterministic proposal dictionaries that match the future
selection engine surface without making data, broker, or database calls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np


@dataclass(frozen=True)
class SpreadProposal:
    structure: str
    direction: str
    entry_cost: float
    max_profit: float
    max_loss: float
    probability_of_profit: float
    breakevens: str
    required_move_pct: float
    expected_move_pct: float
    short_note: str


def _seed(label: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(label)) % (2**32)


def select_spreads(
    ticker: str,
    expiry: date | str | None,
    iv_rank: float = 54,
) -> list[dict[str, object]]:
    """Return three ranked spread candidates for the supplied ticker and expiry."""

    del expiry
    rng = np.random.default_rng(_seed(ticker.upper()))
    em = round(4.5 + (iv_rank / 100) * 6 + rng.normal(0, 0.25), 1)
    proposals = [
        SpreadProposal(
            "Bull Put Spread",
            "Bullish",
            -1.18,
            118,
            382,
            round(64 + rng.normal(0, 2), 1),
            "468 / 463",
            round(em * 0.72, 1),
            em,
            "Defined-risk income under support.",
        ),
        SpreadProposal(
            "Bear Call Spread",
            "Bearish",
            -0.94,
            94,
            406,
            round(58 + rng.normal(0, 2), 1),
            "514 / 519",
            round(em * 0.84, 1),
            em,
            "Fade upside into resistance.",
        ),
        SpreadProposal(
            "Iron Condor",
            "Neutral",
            -1.62,
            162,
            338,
            round(61 + rng.normal(0, 2), 1),
            "466 / 516",
            round(em * 1.08, 1),
            em,
            "Sell rich range premium.",
        ),
    ]
    return [asdict(proposal) for proposal in proposals]
