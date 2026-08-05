"""策略基底類別與共用型別。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

Signal = Literal["buy", "sell", "hold"]


@dataclass
class StrategyResult:
    strategy: str
    signal: Signal
    confidence: float  # 0~1
    detail: str


class Strategy:
    name = "base"

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        raise NotImplementedError
