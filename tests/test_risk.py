import numpy as np
import pandas as pd

from src.risk.stop_loss import compute_atr, compute_risk_levels


def _make_df(n=30, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    price = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "Open": price,
        "High": price + 1,
        "Low": price - 1,
        "Close": price,
        "Volume": rng.integers(1000, 5000, n),
    }, index=dates)


def test_compute_atr_is_positive_after_warmup():
    df = _make_df()
    atr = compute_atr(df, period=14)
    assert atr.iloc[-1] > 0


def test_compute_risk_levels_insufficient_data_returns_none():
    df = _make_df(n=5)
    assert compute_risk_levels(df) is None


def test_compute_risk_levels_buy_direction():
    df = _make_df()
    levels = compute_risk_levels(df, direction="buy")
    assert levels is not None
    assert levels.stop_loss < levels.entry_price < levels.take_profit
    assert levels.risk_reward_ratio > 1


def test_compute_risk_levels_sell_direction():
    df = _make_df()
    levels = compute_risk_levels(df, direction="sell")
    assert levels is not None
    assert levels.take_profit < levels.entry_price < levels.stop_loss
