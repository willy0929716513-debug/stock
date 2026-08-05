import numpy as np
import pandas as pd

from src.strategies.bollinger import BollingerBandStrategy
from src.strategies.macd import MACDStrategy
from src.strategies.moving_average import MovingAverageCrossStrategy
from src.strategies.rsi import RSIStrategy


def _make_df(prices):
    n = len(prices)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open": prices,
        "High": [p + 1 for p in prices],
        "Low": [p - 1 for p in prices],
        "Close": prices,
        "Volume": [1000] * n,
    }, index=dates)


def test_moving_average_insufficient_data_returns_hold():
    df = _make_df([100] * 5)
    result = MovingAverageCrossStrategy(short_window=5, long_window=20).evaluate(df)
    assert result.signal == "hold"
    assert result.confidence == 0.0


def test_moving_average_detects_golden_cross():
    # 前段下降趨勢(短均線在長均線之下),最後一天急拉,讓短均線由下往上穿越長均線
    down = [130 - i for i in range(24)]
    df = _make_df(down + [160])
    result = MovingAverageCrossStrategy(short_window=5, long_window=20).evaluate(df)
    assert result.signal == "buy"


def test_rsi_oversold_triggers_buy():
    prices = [100 - i for i in range(20)]  # 連續下跌
    df = _make_df(prices)
    result = RSIStrategy().evaluate(df)
    assert result.signal == "buy"


def test_rsi_overbought_triggers_sell():
    prices = [100 + i for i in range(20)]  # 連續上漲
    df = _make_df(prices)
    result = RSIStrategy().evaluate(df)
    assert result.signal == "sell"


def test_macd_insufficient_data_returns_hold():
    df = _make_df([100] * 10)
    result = MACDStrategy().evaluate(df)
    assert result.signal == "hold"
    assert result.confidence == 0.0


def test_bollinger_price_below_lower_band_triggers_buy():
    prices = [100.0] * 20 + [80.0]  # 末筆價格大幅低於通道
    df = _make_df(prices)
    result = BollingerBandStrategy(window=20).evaluate(df)
    assert result.signal == "buy"


def test_bollinger_price_above_upper_band_triggers_sell():
    prices = [100.0] * 20 + [120.0]
    df = _make_df(prices)
    result = BollingerBandStrategy(window=20).evaluate(df)
    assert result.signal == "sell"
