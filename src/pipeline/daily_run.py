"""JPO-KBO 主要 pipeline 入口。

由 GitHub Actions 每 ~5 分鐘執行一次:
1. 抓取追蹤清單的報價、歷史K線與新聞
2. 抓取總經資料(FRED)
3. 對每個標的跑多策略 + 多代理決策引擎,產生訊號
4. 呼叫 Gemini 分析潛力股(可失敗,不阻擋主流程)
5. 將結果寫入 docs/data/signals_latest.json(公開資料,前端直接讀取)
6. 觸發 24 小時自動跟單模擬帳戶更新
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.agents.decision_engine import DecisionEngine
from src.config import SIGNALS_LATEST_PATH
from src.data.providers.fred_provider import fetch_all_macro
from src.data.providers.llm_provider import analyze_potential_stocks
from src.data.providers.market_data import fetch_history_batch, fetch_news, fetch_quote
from src.data.providers.twse_calendar import is_trading_day
from src.risk.stop_loss import compute_risk_levels
from src.watchlist import all_symbols, symbol_category, symbol_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def build_signals() -> dict:
    engine = DecisionEngine()
    macro_series = fetch_all_macro()
    tw_trading_day = is_trading_day()

    signals = []
    news_by_symbol: dict[str, list[str]] = {}

    symbols = all_symbols()
    history_by_symbol = fetch_history_batch(symbols)
    logger.info("fetched history for %d/%d symbols", len(history_by_symbol), len(symbols))

    for symbol in symbols:
        df = history_by_symbol.get(symbol)
        news = fetch_news(symbol)
        news_by_symbol[symbol] = [n.title for n in news]

        if df is None or df.empty:
            logger.warning("skipping %s: no history data available", symbol)
            continue

        quote = fetch_quote(symbol, history=df)
        if quote is None:
            logger.warning("skipping %s: no quote available", symbol)
            continue

        decision = engine.decide(symbol, df, macro_series)

        risk_levels = None
        if decision.final_signal in ("buy", "sell"):
            levels = compute_risk_levels(df, direction=decision.final_signal)
            if levels is not None:
                risk_levels = {
                    "entry_price": levels.entry_price,
                    "stop_loss": levels.stop_loss,
                    "take_profit": levels.take_profit,
                    "atr": levels.atr,
                    "risk_reward_ratio": levels.risk_reward_ratio,
                }

        signals.append({
            "symbol": symbol,
            "name": symbol_name(symbol),
            "category": symbol_category(symbol),
            "price": quote.price,
            "change_pct": quote.change_pct,
            "volume": quote.volume,
            "signal": decision.final_signal,
            "confidence": decision.confidence,
            "opinions": [
                {"agent": o.agent, "signal": o.signal, "confidence": o.confidence, "rationale": o.rationale}
                for o in decision.opinions
            ],
            "risk_levels": risk_levels,
            "news": [{"title": n.title, "publisher": n.publisher, "link": n.link} for n in news[:3]],
        })

    potential_picks = []
    try:
        picks = analyze_potential_stocks(news_by_symbol)
        potential_picks = [
            {"symbol": p.symbol, "reason": p.reason, "beneficiary_of": p.beneficiary_of}
            for p in picks
        ]
    except Exception:
        logger.exception("potential-stock analysis failed, continuing without it")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tw_market_open_today": tw_trading_day,
        "macro": [
            {"series_id": m.series_id, "name": m.name, "value": m.latest_value, "date": m.latest_date}
            for m in macro_series
        ],
        "signals": signals,
        "potential_picks": potential_picks,
    }


def main() -> None:
    output = build_signals()
    output_path = Path(SIGNALS_LATEST_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False:寧可讓這次 pipeline 執行失敗、保留舊資料,也不要把 NaN
    # 寫進公開的 JSON——NaN 不是合法 JSON,瀏覽器解析會直接拋例外讓全站掛掉
    # (曾經發生過:0050.TW/0051.TW 的 price/change_pct 算出 NaN,寫進檔案後
    # 使用者在 Safari 看到「The string did not match the expected pattern.」)。
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    logger.info("wrote %d signals to %s", len(output["signals"]), output_path)


if __name__ == "__main__":
    main()
