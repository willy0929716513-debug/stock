from src.strategies.base import Signal, Strategy, StrategyResult
from src.strategies.bollinger import BollingerBandStrategy
from src.strategies.macd import MACDStrategy
from src.strategies.moving_average import MovingAverageCrossStrategy
from src.strategies.rsi import RSIStrategy

ALL_STRATEGIES: list[Strategy] = [
    MovingAverageCrossStrategy(),
    RSIStrategy(),
    MACDStrategy(),
    BollingerBandStrategy(),
]


def run_all(df) -> list[StrategyResult]:
    return [s.evaluate(df) for s in ALL_STRATEGIES]


__all__ = [
    "Signal",
    "Strategy",
    "StrategyResult",
    "ALL_STRATEGIES",
    "run_all",
    "MovingAverageCrossStrategy",
    "RSIStrategy",
    "MACDStrategy",
    "BollingerBandStrategy",
]
