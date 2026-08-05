"""yfinance 報價與新聞資料來源。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    symbol: str
    price: Optional[float]
    previous_close: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    as_of: str


@dataclass
class NewsItem:
    symbol: str
    title: str
    publisher: str
    link: str
    published_at: str


def fetch_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """抓取歷史 K 線。失敗時回傳空的 DataFrame 而非拋例外,讓 pipeline 能跳過單一標的繼續執行。"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            logger.warning("no history data for %s", symbol)
        return df
    except Exception:
        logger.exception("failed to fetch history for %s", symbol)
        return pd.DataFrame()


def fetch_quote(symbol: str, history: Optional[pd.DataFrame] = None) -> Optional[Quote]:
    df = history if history is not None else fetch_history(symbol, period="5d", interval="1d")
    if df.empty:
        return None
    last = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"] if len(df) >= 2 else last["Close"]
    change_pct = ((last["Close"] - prev_close) / prev_close * 100) if prev_close else None
    return Quote(
        symbol=symbol,
        price=round(float(last["Close"]), 4),
        previous_close=round(float(prev_close), 4),
        change_pct=round(float(change_pct), 2) if change_pct is not None else None,
        volume=int(last["Volume"]) if not pd.isna(last["Volume"]) else None,
        as_of=datetime.now(timezone.utc).isoformat(),
    )


def fetch_news(symbol: str, limit: int = 5) -> list[NewsItem]:
    """抓取個股新聞。yfinance 的 news schema 在不同版本間變動過,因此兩種格式都嘗試解析。"""
    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news or []
    except Exception:
        logger.exception("failed to fetch news for %s", symbol)
        return []

    items = []
    for entry in raw_news[:limit]:
        content = entry.get("content") if isinstance(entry.get("content"), dict) else entry
        title = content.get("title") or entry.get("title")
        if not title:
            continue

        provider = content.get("provider")
        publisher = provider.get("displayName") if isinstance(provider, dict) else content.get("publisher")

        canonical_url = content.get("canonicalUrl")
        link = canonical_url.get("url") if isinstance(canonical_url, dict) else content.get("link")

        published_at = content.get("pubDate") or entry.get("providerPublishTime")

        items.append(NewsItem(
            symbol=symbol,
            title=title,
            publisher=publisher or "",
            link=link or "",
            published_at=str(published_at) if published_at else "",
        ))
    return items
