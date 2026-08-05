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
