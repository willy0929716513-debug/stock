import numpy as np
import pandas as pd

from src.pipeline import daily_run


def _trending_df(n=40, seed=2):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    price = 100 + np.cumsum(rng.normal(0.5, 1, n))  # 帶上升偏態,較容易出現 buy 訊號
    return pd.DataFrame({
        "Open": price,
        "High": price + 1,
        "Low": price - 1,
        "Close": price,
        "Volume": rng.integers(1000, 5000, n),
    }, index=dates)


def test_build_signals_produces_expected_shape(monkeypatch):
    fake_df = _trending_df()

    monkeypatch.setattr(daily_run, "fetch_history_batch", lambda symbols, **kwargs: {s: fake_df for s in symbols})
    monkeypatch.setattr(daily_run, "fetch_news", lambda symbol, **kwargs: [])
    monkeypatch.setattr(daily_run, "fetch_all_macro", lambda: [])
    monkeypatch.setattr(daily_run, "analyze_potential_stocks", lambda news_by_symbol: [])
    monkeypatch.setattr(daily_run, "is_trading_day", lambda: True)

    output = daily_run.build_signals()

    assert output["tw_market_open_today"] is True
    assert "generated_at" in output
    assert len(output["signals"]) == len(daily_run.all_symbols())

    for signal in output["signals"]:
        assert signal["signal"] in ("buy", "sell", "hold")
        if signal["signal"] in ("buy", "sell"):
            # 帶方向性的訊號應該要有風控停損停利價位(資料充足時)
            assert signal["risk_levels"] is not None
            assert signal["risk_levels"]["stop_loss"] != signal["risk_levels"]["take_profit"]
        else:
            assert signal["risk_levels"] is None


def test_build_signals_skips_symbols_with_no_history(monkeypatch):
    monkeypatch.setattr(daily_run, "fetch_history_batch", lambda symbols, **kwargs: {})
    monkeypatch.setattr(daily_run, "fetch_news", lambda symbol, **kwargs: [])
    monkeypatch.setattr(daily_run, "fetch_all_macro", lambda: [])
    monkeypatch.setattr(daily_run, "analyze_potential_stocks", lambda news_by_symbol: [])
    monkeypatch.setattr(daily_run, "is_trading_day", lambda: True)

    output = daily_run.build_signals()

    assert output["signals"] == []


def test_build_signals_continues_when_potential_stock_analysis_raises(monkeypatch):
    fake_df = _trending_df()

    monkeypatch.setattr(daily_run, "fetch_history_batch", lambda symbols, **kwargs: {s: fake_df for s in symbols})
    monkeypatch.setattr(daily_run, "fetch_news", lambda symbol, **kwargs: [])
    monkeypatch.setattr(daily_run, "fetch_all_macro", lambda: [])

    def _raise(news_by_symbol):
        raise RuntimeError("Gemini boom")

    monkeypatch.setattr(daily_run, "analyze_potential_stocks", _raise)
    monkeypatch.setattr(daily_run, "is_trading_day", lambda: True)

    output = daily_run.build_signals()

    assert output["potential_picks"] == []
    assert len(output["signals"]) > 0
