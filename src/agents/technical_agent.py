"""技術面 Agent:彙整多個技術策略的訊號,產生單一技術面意見。"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies import ALL_STRATEGIES, StrategyResult


@dataclass
class AgentOpinion:
    agent: str
    signal: str  # buy / sell / hold
    confidence: float
    rationale: str


class TechnicalAgent:
    name = "technical"

    def analyze(self, df: pd.DataFrame) -> AgentOpinion:
        results: list[StrategyResult] = [s.evaluate(df) for s in ALL_STRATEGIES]

        score = 0.0
        total_weight = 0.0
        reasons = []
        for r in results:
            weight = max(r.confidence, 0.05)
            direction = {"buy": 1, "sell": -1, "hold": 0}[r.signal]
            score += direction * weight
            total_weight += weight
            if r.signal != "hold":
                reasons.append(f"{r.strategy}:{r.signal}({r.detail})")

        normalized = score / total_weight if total_weight else 0.0

        if normalized > 0.2:
            signal = "buy"
        elif normalized < -0.2:
            signal = "sell"
        else:
            signal = "hold"

        confidence = min(abs(normalized), 1.0)
        rationale = "; ".join(reasons) if reasons else "各策略皆無明確訊號"
        return AgentOpinion(self.name, signal, round(confidence, 2), rationale)
