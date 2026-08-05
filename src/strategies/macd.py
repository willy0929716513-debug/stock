"""MACD 指標策略:MACD 柱狀體翻正/翻負視為黃金/死亡交叉。"""
from __future__ import annotations

import pandas as pd

from src.strategies.base import Strategy, StrategyResult


class MACDStrategy(Strategy):
    name = "macd"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        if len(df) < self.slow + self.signal:
            return StrategyResult(self.name, "hold", 0.0, "資料不足")

        close = df["Close"]
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
        hist = macd_line - signal_line

        prev_hist = hist.iloc[-2]
        curr_hist = hist.iloc[-1]

        if prev_hist <= 0 and curr_hist > 0:
            return StrategyResult(self.name, "buy", 0.55, "MACD 柱狀體翻正(黃金交叉)")
        if prev_hist >= 0 and curr_hist < 0:
            return StrategyResult(self.name, "sell", 0.55, "MACD 柱狀體翻負(死亡交叉)")
        return StrategyResult(self.name, "hold", 0.15, f"MACD 柱狀體={curr_hist:.3f},無交叉")
