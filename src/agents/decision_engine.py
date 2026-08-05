"""多代理決策引擎:技術面/總經/風控 Agent 加權合議,產生最終訊號。"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.agents.macro_agent import MacroAgent
from src.agents.risk_agent import RiskAgent
from src.agents.technical_agent import AgentOpinion, TechnicalAgent
from src.data.providers.fred_provider import MacroSeries

# 各 Agent 的合議權重:技術面為主要依據,總經與風控用來修正,加總為 1.0。
AGENT_WEIGHTS = {
    "technical": 0.6,
    "macro": 0.15,
    "risk": 0.25,
}

BUY_THRESHOLD = 0.15
SELL_THRESHOLD = -0.15


@dataclass
class DecisionResult:
    symbol: str
    final_signal: str
    confidence: float
    opinions: list[AgentOpinion] = field(default_factory=list)


class DecisionEngine:
    def __init__(self):
        self.technical_agent = TechnicalAgent()
        self.macro_agent = MacroAgent()
        self.risk_agent = RiskAgent()

    def decide(self, symbol: str, df: pd.DataFrame, macro_series: list[MacroSeries]) -> DecisionResult:
        opinions = [
            self.technical_agent.analyze(df),
            self.macro_agent.analyze(macro_series),
            self.risk_agent.analyze(df),
        ]

        score = 0.0
        for opinion in opinions:
            direction = {"buy": 1, "sell": -1, "hold": 0}[opinion.signal]
            weight = AGENT_WEIGHTS.get(opinion.agent, 0.0)
            score += direction * opinion.confidence * weight

        if score > BUY_THRESHOLD:
            final_signal = "buy"
        elif score < SELL_THRESHOLD:
            final_signal = "sell"
        else:
            final_signal = "hold"

        return DecisionResult(
            symbol=symbol,
            final_signal=final_signal,
            confidence=round(min(abs(score), 1.0), 2),
            opinions=opinions,
        )
