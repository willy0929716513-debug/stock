import numpy as np
import pandas as pd

from src.agents.decision_engine import DecisionEngine
from src.data.providers.fred_provider import MacroSeries


def _make_df(n=60, seed=1):
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


def test_decide_returns_all_three_agent_opinions():
    df = _make_df()
    result = DecisionEngine().decide("TEST", df, [])
    assert result.final_signal in ("buy", "sell", "hold")
    assert {o.agent for o in result.opinions} == {"technical", "macro", "risk"}


def test_decide_handles_missing_macro_data_gracefully():
    df = _make_df()
    result = DecisionEngine().decide("TEST", df, [])
    macro_opinion = next(o for o in result.opinions if o.agent == "macro")
    assert macro_opinion.signal == "hold"


def test_high_bond_yield_pulls_macro_agent_toward_sell():
    df = _make_df()
    macro_series = [MacroSeries(series_id="DGS10", name="美國10年期公債殖利率", latest_value=6.0, latest_date="2026-01-01")]
    result = DecisionEngine().decide("TEST", df, macro_series)
    macro_opinion = next(o for o in result.opinions if o.agent == "macro")
    assert macro_opinion.signal == "sell"
