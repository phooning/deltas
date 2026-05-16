"""Signal contract shared by the trading desk UI pipeline.

The shell consumes this bundle in the persistent conviction panel and each page
contributes one or more fields as real engines replace the current stubs.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SignalBundle:
    """Composite state flowing from research pages into trade conviction."""

    ticker: str
    trend: Literal["up", "down", "sideways"]
    iv_rank: float
    regime: Literal["risk-on", "risk-off", "transitional"]
    catalyst_proximity: int
    fundamental_score: int
    conviction: float
    recommended_structure: str
