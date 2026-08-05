"""布林通道策略:價格觸及下軌視為買進,觸及上軌視為賣出。"""
from __future__ import annotations

import pandas as pd

from src.strategies.base import Strategy, StrategyResult


class BollingerBandStrategy(Strategy):
    name = "bollinger_band"

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        if len(df) < self.window:
            return StrategyResult(self.name, "hold", 0.0, "資料不足")

        close = df["Close"]
        mid = close.rolling(self.window).mean()
        std = close.rolling(self.window).std()
        upper = mid + self.num_std * std
        lower = mid - self.num_std * std

        price = close.iloc[-1]
        upper_now = upper.iloc[-1]
        lower_now = lower.iloc[-1]
        mid_now = mid.iloc[-1]

        if price <= lower_now:
            return StrategyResult(self.name, "buy", 0.5, f"價格 {price:.2f} 觸及下軌 {lower_now:.2f}")
        if price >= upper_now:
            return StrategyResult(self.name, "sell", 0.5, f"價格 {price:.2f} 觸及上軌 {upper_now:.2f}")

        band_width = upper_now - lower_now
        position = (price - mid_now) / (band_width / 2) if band_width else 0.0
        return StrategyResult(self.name, "hold", round(abs(position) * 0.2, 2), f"價格在通道內,相對位置={position:.2f}")
