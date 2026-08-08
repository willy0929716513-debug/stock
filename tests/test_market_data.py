import pandas as pd
import pytest

import src.data.providers.market_data as market_data


def _make_df(n=5, base=100.0):
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open": [base] * n,
        "High": [base + 1] * n,
        "Low": [base - 1] * n,
        "Close": [base] * n,
        "Volume": [1000] * n,
    }, index=dates)


def test_fetch_history_batch_empty_symbols_returns_empty_dict():
    assert market_data.fetch_history_batch([]) == {}


def test_fetch_history_batch_multiindex_success(monkeypatch):
    df_a = _make_df(base=100.0)
    df_b = _make_df(base=200.0)
    combined = pd.concat({"AAA": df_a, "BBB": df_b}, axis=1)

    monkeypatch.setattr(market_data.yf, "download", lambda **kwargs: combined)

    result = market_data.fetch_history_batch(["AAA", "BBB"])

    assert set(result.keys()) == {"AAA", "BBB"}
    assert result["AAA"]["Close"].iloc[0] == 100.0
    assert result["BBB"]["Close"].iloc[0] == 200.0


def test_fetch_history_batch_falls_back_for_missing_symbol(monkeypatch):
    df_a = _make_df(base=100.0)
    combined = pd.concat({"AAA": df_a}, axis=1)  # BBB missing from batch result

    monkeypatch.setattr(market_data.yf, "download", lambda **kwargs: combined)
    monkeypatch.setattr(market_data, "fetch_history", lambda symbol, **kwargs: _make_df(base=999.0) if symbol == "BBB" else pd.DataFrame())

    result = market_data.fetch_history_batch(["AAA", "BBB"])

    assert result["AAA"]["Close"].iloc[0] == 100.0
    assert result["BBB"]["Close"].iloc[0] == 999.0


def test_fetch_history_batch_falls_back_entirely_when_download_raises(monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("network boom")

    monkeypatch.setattr(market_data.yf, "download", _raise)
    monkeypatch.setattr(market_data, "fetch_history", lambda symbol, **kwargs: _make_df(base=42.0))

    result = market_data.fetch_history_batch(["AAA", "BBB"])

    assert result["AAA"]["Close"].iloc[0] == 42.0
    assert result["BBB"]["Close"].iloc[0] == 42.0


def test_fetch_history_batch_symbol_missing_everywhere_is_dropped(monkeypatch):
    monkeypatch.setattr(market_data.yf, "download", lambda **kwargs: pd.DataFrame())
    monkeypatch.setattr(market_data, "fetch_history", lambda symbol, **kwargs: pd.DataFrame())

    result = market_data.fetch_history_batch(["AAA"])

    assert result == {}


def test_fetch_quote_falls_back_to_last_row_with_valid_close():
    df = _make_df(n=3, base=100.0)
    df.loc[df.index[-1], "Close"] = float("nan")  # 最新一列 Close 是 NaN,其他欄位仍有值

    quote = market_data.fetch_quote("AAA", history=df)

    assert quote is not None
    assert quote.price == 100.0
    import math
    assert not math.isnan(quote.price)
    assert quote.change_pct is not None and not math.isnan(quote.change_pct)


def test_fetch_quote_returns_none_when_all_close_values_are_nan():
    df = _make_df(n=3, base=100.0)
    df["Close"] = float("nan")

    quote = market_data.fetch_quote("AAA", history=df)

    assert quote is None
