"""均線交叉策略:短均線由下往上穿越長均線視為買進訊號,反之為賣出。"""
from __future__ import annotations

import pandas as pd

from src.strategies.base import Strategy, StrategyResult


class MovingAverageCrossStrategy(Strategy):
    name = "moving_average_cross"

    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        if len(df) < self.long_window + 1:
            return StrategyResult(self.name, "hold", 0.0, "資料不足")

        close = df["Close"]
        short_ma = close.rolling(self.short_window).mean()
        long_ma = close.rolling(self.long_window).mean()

        prev_diff = short_ma.iloc[-2] - long_ma.iloc[-2]
        curr_diff = short_ma.iloc[-1] - long_ma.iloc[-1]

        if prev_diff <= 0 and curr_diff > 0:
            return StrategyResult(self.name, "buy", 0.6, f"{self.short_window}日均線上穿{self.long_window}日均線")
        if prev_diff >= 0 and curr_diff < 0:
            return StrategyResult(self.name, "sell", 0.6, f"{self.short_window}日均線下穿{self.long_window}日均線")

        long_ma_now = long_ma.iloc[-1]
        # `if long_ma_now` 不能拿來擋 NaN——NaN 在 Python 是 truthy,算出來的
        # trend_strength 會是 NaN,寫進 JSON 時讓整個 pipeline 執行失敗
        # (json.dumps 的 allow_nan=False)。
        trend_strength = (
            min(abs(curr_diff) / long_ma_now, 0.05) / 0.05 * 0.4
            if long_ma_now and not pd.isna(long_ma_now) and not pd.isna(curr_diff)
            else 0.0
        )
        if curr_diff > 0:
            return StrategyResult(self.name, "hold", round(trend_strength, 2), "短均線在長均線之上,多頭排列但無交叉")
        return StrategyResult(self.name, "hold", round(trend_strength, 2), "短均線在長均線之下,空頭排列但無交叉")
