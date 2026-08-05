"""追蹤清單:以台股為主,輔以美股/ETF/黃金/原油/外匯/加密貨幣。

Symbol 格式沿用 yfinance 慣例(台股需帶 .TW / .TWO 後綴)。
"""
from __future__ import annotations

WATCHLIST: dict[str, dict[str, str]] = {
    "tw_stock": {
        "2330.TW": "台積電",
        "2317.TW": "鴻海",
        "2454.TW": "聯發科",
        "2308.TW": "台達電",
        "2412.TW": "中華電",
        "2882.TW": "國泰金",
        "2603.TW": "長榮",
        "3008.TW": "大立光",
        "2379.TW": "瑞昱",
        "0050.TW": "元大台灣50",
    },
    "us_stock": {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "TSLA": "Tesla",
        "GOOGL": "Alphabet",
    },
    "etf": {
        "SPY": "S&P 500 ETF",
        "QQQ": "Nasdaq 100 ETF",
    },
    "commodity": {
        "GC=F": "黃金期貨",
        "CL=F": "原油期貨",
    },
    "forex": {
        "TWD=X": "美元/新台幣",
        "JPY=X": "美元/日圓",
    },
    "crypto": {
        "BTC-USD": "比特幣",
        "ETH-USD": "以太幣",
    },
}


def all_symbols() -> list[str]:
    symbols: list[str] = []
    for group in WATCHLIST.values():
        symbols.extend(group.keys())
    return symbols


def symbol_name(symbol: str) -> str:
    for group in WATCHLIST.values():
        if symbol in group:
            return group[symbol]
    return symbol


def symbol_category(symbol: str) -> str:
    for category, group in WATCHLIST.items():
        if symbol in group:
            return category
    return "unknown"
