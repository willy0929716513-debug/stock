from datetime import datetime, timezone

from src.pipeline.auto_trader import (
    INITIAL_CASH,
    REVERSAL_CONFIRMATIONS_REQUIRED,
    AutoTraderState,
    run_step,
)

MORNING_UTC = datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc)  # 台北時間 10:00,盤中
AFTER_CLOSE_UTC = datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc)  # 台北時間 14:00,已收盤


def test_opens_position_on_buy_signal_during_market_hours():
    state = AutoTraderState()
    signals = [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}]

    state = run_step(state, signals, MORNING_UTC)

    assert state.position is not None
    assert state.position.symbol == "2330.TW"
    assert state.position.direction == "buy"
    assert state.cash == INITIAL_CASH  # 現金尚未變動,只是開倉


def test_single_reversal_does_not_close_position():
    state = AutoTraderState()
    state = run_step(state, [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}], MORNING_UTC)

    state = run_step(state, [{"symbol": "2330.TW", "price": 990.0, "signal": "sell", "confidence": 0.5}], MORNING_UTC)

    assert state.position is not None
    assert state.position.reversal_count == 1


def test_consecutive_reversals_close_position():
    state = AutoTraderState()
    state = run_step(state, [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}], MORNING_UTC)

    for _ in range(REVERSAL_CONFIRMATIONS_REQUIRED):
        state = run_step(state, [{"symbol": "2330.TW", "price": 990.0, "signal": "sell", "confidence": 0.5}], MORNING_UTC)

    assert state.position is None
    assert len(state.trade_history) == 1
    assert state.trade_history[0]["close_reason"].startswith("訊號連續")


def test_signal_returning_to_original_direction_resets_reversal_count():
    state = AutoTraderState()
    state = run_step(state, [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}], MORNING_UTC)
    state = run_step(state, [{"symbol": "2330.TW", "price": 990.0, "signal": "sell", "confidence": 0.5}], MORNING_UTC)
    assert state.position.reversal_count == 1

    state = run_step(state, [{"symbol": "2330.TW", "price": 995.0, "signal": "buy", "confidence": 0.5}], MORNING_UTC)
    assert state.position.reversal_count == 0


def test_position_force_closed_after_market_close():
    state = AutoTraderState()
    state = run_step(state, [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}], MORNING_UTC)

    state = run_step(state, [{"symbol": "2330.TW", "price": 1010.0, "signal": "buy", "confidence": 0.5}], AFTER_CLOSE_UTC)

    assert state.position is None
    assert state.trade_history[0]["close_reason"] == "當沖收盤強制平倉"
    assert state.cash == INITIAL_CASH + (1010.0 - 1000.0) * 10


def test_no_position_opened_after_market_close():
    state = AutoTraderState()
    signals = [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}]

    state = run_step(state, signals, AFTER_CLOSE_UTC)

    assert state.position is None


def test_picks_highest_confidence_signal_when_multiple_candidates():
    state = AutoTraderState()
    signals = [
        {"symbol": "AAPL", "price": 200.0, "signal": "buy", "confidence": 0.3},
        {"symbol": "2330.TW", "price": 1000.0, "signal": "sell", "confidence": 0.8},
    ]

    state = run_step(state, signals, MORNING_UTC)

    assert state.position.symbol == "2330.TW"


def test_non_tw_symbol_can_open_position_after_tw_market_close():
    # 台股收盤後,美股/加密貨幣等非台股標的仍然可以開倉——
    # 這是稽核真實 production 資料後發現的問題:原本的規則不分資產類別,
    # 導致帳戶從上線以來因為每次執行都落在台灣晚上時段而完全沒進場過。
    state = AutoTraderState()
    signals = [{"symbol": "BTC-USD", "price": 100.0, "signal": "buy", "confidence": 0.5}]

    state = run_step(state, signals, AFTER_CLOSE_UTC)

    assert state.position is not None
    assert state.position.symbol == "BTC-USD"


def test_tw_stock_excluded_from_candidates_after_close_but_others_still_considered():
    state = AutoTraderState()
    signals = [
        {"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.9},  # 信心值最高但已收盤
        {"symbol": "AAPL", "price": 200.0, "signal": "buy", "confidence": 0.3},
    ]

    state = run_step(state, signals, AFTER_CLOSE_UTC)

    assert state.position is not None
    assert state.position.symbol == "AAPL"


def test_non_tw_position_not_force_closed_after_tw_market_close():
    state = AutoTraderState()
    state = run_step(state, [{"symbol": "BTC-USD", "price": 100.0, "signal": "buy", "confidence": 0.5}], MORNING_UTC)
    assert state.position is not None

    state = run_step(state, [{"symbol": "BTC-USD", "price": 60500.0, "signal": "buy", "confidence": 0.5}], AFTER_CLOSE_UTC)

    assert state.position is not None
    assert state.position.symbol == "BTC-USD"


def test_position_opens_with_stop_loss_and_take_profit_from_signal_risk_levels():
    state = AutoTraderState()
    signals = [{
        "symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5,
        "risk_levels": {"stop_loss": 950.0, "take_profit": 1100.0},
    }]

    state = run_step(state, signals, MORNING_UTC)

    assert state.position.stop_loss == 950.0
    assert state.position.take_profit == 1100.0


def test_position_without_risk_levels_has_no_stop_loss_or_take_profit():
    state = AutoTraderState()
    signals = [{"symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5}]

    state = run_step(state, signals, MORNING_UTC)

    assert state.position.stop_loss is None
    assert state.position.take_profit is None


def test_long_position_closes_when_price_drops_to_stop_loss():
    state = AutoTraderState()
    signals = [{
        "symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5,
        "risk_levels": {"stop_loss": 950.0, "take_profit": 1100.0},
    }]
    state = run_step(state, signals, MORNING_UTC)

    state = run_step(state, [{"symbol": "2330.TW", "price": 940.0, "signal": "hold", "confidence": 0.5}], MORNING_UTC)

    assert state.position is None
    assert state.trade_history[0]["close_reason"] == "觸發停損"
    assert state.trade_history[0]["exit_price"] == 940.0


def test_long_position_closes_when_price_rises_to_take_profit():
    state = AutoTraderState()
    signals = [{
        "symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5,
        "risk_levels": {"stop_loss": 950.0, "take_profit": 1100.0},
    }]
    state = run_step(state, signals, MORNING_UTC)

    state = run_step(state, [{"symbol": "2330.TW", "price": 1150.0, "signal": "hold", "confidence": 0.5}], MORNING_UTC)

    assert state.position is None
    assert state.trade_history[0]["close_reason"] == "觸發停利"


def test_short_position_closes_when_price_rises_to_stop_loss():
    state = AutoTraderState()
    signals = [{
        "symbol": "2330.TW", "price": 1000.0, "signal": "sell", "confidence": 0.5,
        "risk_levels": {"stop_loss": 1050.0, "take_profit": 900.0},
    }]
    state = run_step(state, signals, MORNING_UTC)

    state = run_step(state, [{"symbol": "2330.TW", "price": 1060.0, "signal": "hold", "confidence": 0.5}], MORNING_UTC)

    assert state.position is None
    assert state.trade_history[0]["close_reason"] == "觸發停損"


def test_stop_loss_takes_priority_over_reversal_count_on_same_step():
    # 現價同時觸發停損、訊號又反轉時,應該直接以停損出場,不必等反轉次數累積到門檻
    state = AutoTraderState()
    signals = [{
        "symbol": "2330.TW", "price": 1000.0, "signal": "buy", "confidence": 0.5,
        "risk_levels": {"stop_loss": 950.0, "take_profit": 1100.0},
    }]
    state = run_step(state, signals, MORNING_UTC)

    state = run_step(state, [{"symbol": "2330.TW", "price": 940.0, "signal": "sell", "confidence": 0.5}], MORNING_UTC)

    assert state.position is None
    assert state.trade_history[0]["close_reason"] == "觸發停損"
