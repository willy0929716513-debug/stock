"""風控 Agent:依 ATR 波動度評估風險,不表態方向,只用信心值修正合議結果。

高信心值代表「波動過大、建議保守」,在多代理加權平均時會把最終訊號往中性拉,
藉此避免在劇烈震盪時盲目跟單技術面訊號。
"""
from __future__ import annotations

import pandas as pd

from src.agents.technical_agent import AgentOpinion
from src.risk.stop_loss import compute_atr

HIGH_VOLATILITY_RATIO = 0.05  # ATR 佔股價比例超過此門檻視為波動過大


class RiskAgent:
    name = "risk"

    def analyze(self, df: pd.DataFrame) -> AgentOpinion:
        if len(df) < 15:
            return AgentOpinion(self.name, "hold", 0.0, "資料不足,無法評估波動風險")

        atr_series = compute_atr(df)
        atr = atr_series.iloc[-1]
        price = df["Close"].iloc[-1]

        if pd.isna(atr) or price <= 0:
            return AgentOpinion(self.name, "hold", 0.0, "無法計算 ATR")

        volatility_ratio = float(atr) / float(price)

        if volatility_ratio >= HIGH_VOLATILITY_RATIO:
            confidence = min(volatility_ratio / HIGH_VOLATILITY_RATIO - 1.0, 1.0)
            return AgentOpinion(
                self.name, "hold", round(confidence, 2),
                f"波動度過高(ATR/價格={volatility_ratio:.2%}),建議降低部位或觀望",
            )
        return AgentOpinion(self.name, "hold", 0.0, f"波動度正常(ATR/價格={volatility_ratio:.2%})")
