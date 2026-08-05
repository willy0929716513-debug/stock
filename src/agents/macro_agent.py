"""總經 Agent:依 FRED 總經數據判斷總體風險偏向,作為技術面訊號的加減分依據。

注意:這裡用的是簡化經驗法則(門檻式判斷),不是嚴謹的總經模型,
只作為多代理合議中的輔助修正項,權重也刻意設得比技術面低。
"""
from __future__ import annotations

from src.agents.technical_agent import AgentOpinion
from src.data.providers.fred_provider import MacroSeries

HIGH_YIELD_THRESHOLD = 4.5  # 10年期公債殖利率過高時偏保守(%)
HIGH_UNEMPLOYMENT_THRESHOLD = 5.0  # 失業率過高時偏保守(%)


class MacroAgent:
    name = "macro"

    def analyze(self, macro_series: list[MacroSeries]) -> AgentOpinion:
        if not macro_series:
            return AgentOpinion(self.name, "hold", 0.0, "無總經資料(FRED_API_KEY 未設定或抓取失敗)")

        by_id = {s.series_id: s for s in macro_series}
        reasons = []
        risk_score = 0.0

        yield10 = by_id.get("DGS10")
        if yield10 and yield10.latest_value is not None:
            if yield10.latest_value >= HIGH_YIELD_THRESHOLD:
                risk_score -= 0.3
                reasons.append(f"10年期公債殖利率偏高({yield10.latest_value}%),資金成本上升")
            else:
                reasons.append(f"10年期公債殖利率={yield10.latest_value}%")

        unrate = by_id.get("UNRATE")
        if unrate and unrate.latest_value is not None:
            if unrate.latest_value >= HIGH_UNEMPLOYMENT_THRESHOLD:
                risk_score -= 0.2
                reasons.append(f"失業率偏高({unrate.latest_value}%)")
            else:
                reasons.append(f"失業率={unrate.latest_value}%")

        if risk_score <= -0.3:
            signal = "sell"
        elif risk_score >= 0.3:
            signal = "buy"
        else:
            signal = "hold"

        return AgentOpinion(self.name, signal, round(abs(risk_score), 2), "; ".join(reasons))
