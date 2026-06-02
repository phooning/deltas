from dataclasses import dataclass
from typing import Literal


@dataclass
class SignalBundle:
    ticker: str
    trend: Literal["up", "down", "sideways"]
    iv_rank: float  # 0–100
    regime: str  # from macro.py
    catalyst_proximity: int  # days to nearest catalyst
    fundamental_score: int  # 1–5 from fundamentals.py
    conviction: float  # composite 0–1, drives size
    recommended_structure: str
