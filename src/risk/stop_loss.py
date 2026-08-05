"""ATR(平均真實區間)為基礎的停損停利計算。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class RiskLevels:
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float
    risk_reward_ratio: float


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def compute_risk_levels(
    df: pd.DataFrame,
    direction: str = "buy",
    atr_period: int = 14,
    stop_multiplier: float = 1.5,
    profit_multiplier: float = 2.5,
) -> Optional[RiskLevels]:
    """依 ATR 計算停損停利價位。direction 為 'buy'(做多)或 'sell'(做空)。"""
    if len(df) < atr_period + 1:
        return None

    atr_series = compute_atr(df, atr_period)
    atr = atr_series.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return None

    entry_price = float(df["Close"].iloc[-1])

    if direction == "buy":
        stop_loss = entry_price - atr * stop_multiplier
        take_profit = entry_price + atr * profit_multiplier
    else:
        stop_loss = entry_price + atr * stop_multiplier
        take_profit = entry_price - atr * profit_multiplier

    return RiskLevels(
        entry_price=round(entry_price, 4),
        stop_loss=round(float(stop_loss), 4),
        take_profit=round(float(take_profit), 4),
        atr=round(float(atr), 4),
        risk_reward_ratio=round(profit_multiplier / stop_multiplier, 2),
    )
