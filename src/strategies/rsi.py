"""RSI 相對強弱指標策略:超賣視為買進訊號,超買視為賣出訊號。"""
from __future__ import annotations

import pandas as pd

from src.strategies.base import Strategy, StrategyResult


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    # avg_loss.replace(0, nan) 讓「連續上漲、完全無跌」的區間被除法吃成 nan,
    # 若直接 fillna(50) 會把應該是 RSI=100(極端超買)的區間誤判成中性,
    # 因此這三種邊界情況(全漲/全跌/完全平盤)要分開明確處理。
    all_gains_no_losses = (avg_loss == 0) & (avg_gain > 0)
    all_losses_no_gains = (avg_gain == 0) & (avg_loss > 0)
    flat = (avg_gain == 0) & (avg_loss == 0)

    rsi = rsi.mask(all_gains_no_losses, 100.0)
    rsi = rsi.mask(all_losses_no_gains, 0.0)
    rsi = rsi.mask(flat, 50.0)
    return rsi.fillna(50.0)


class RSIStrategy(Strategy):
    name = "rsi"

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        if len(df) < self.period + 1:
            return StrategyResult(self.name, "hold", 0.0, "資料不足")

        rsi = compute_rsi(df["Close"], self.period)
        latest = rsi.iloc[-1]

        if latest <= self.oversold:
            confidence = min((self.oversold - latest) / self.oversold, 1.0)
            return StrategyResult(self.name, "buy", round(0.4 + confidence * 0.4, 2), f"RSI={latest:.1f} 進入超賣區")
        if latest >= self.overbought:
            confidence = min((latest - self.overbought) / (100 - self.overbought), 1.0)
            return StrategyResult(self.name, "sell", round(0.4 + confidence * 0.4, 2), f"RSI={latest:.1f} 進入超買區")
        return StrategyResult(self.name, "hold", 0.1, f"RSI={latest:.1f} 中性區間")
