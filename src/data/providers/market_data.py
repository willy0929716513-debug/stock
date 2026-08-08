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


def fetch_history_batch(symbols: list[str], period: str = "6mo", interval: str = "1d") -> dict[str, pd.DataFrame]:
    """批次抓取多檔標的的歷史 K 線。

    追蹤清單擴大到上百檔之後,如果每檔都各別打一次 API,每次 pipeline 執行
    就是上百個 HTTP 請求,容易被 Yahoo Finance 限流(429)。改用 yfinance 的
    批次下載一次抓多檔,大幅減少請求數。批次下載中缺漏或整批失敗的標的,
    會退回逐檔呼叫 fetch_history() 重試一次,維持跟原本一樣「單一標的失敗
    不影響其他標的」的保證。
    """
    results: dict[str, pd.DataFrame] = {}
    if not symbols:
        return results

    try:
        data = yf.download(
            tickers=symbols,
            period=period,
            interval=interval,
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        logger.exception("batch history download failed for %d symbols, falling back to per-symbol fetch", len(symbols))
        data = None

    if data is not None and not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            top_level = set(data.columns.get_level_values(0))
            for symbol in symbols:
                if symbol in top_level:
                    df = data[symbol].dropna(how="all")
                    if not df.empty:
                        results[symbol] = df
        elif len(symbols) == 1:
            # yf.download 對單一標的可能回傳單層欄位(非 MultiIndex)
            df = data.dropna(how="all")
            if not df.empty:
                results[symbols[0]] = df

    missing = [s for s in symbols if s not in results]
    for symbol in missing:
        df = fetch_history(symbol, period=period, interval=interval)
        if not df.empty:
            results[symbol] = df
        else:
            logger.warning("no history data for %s (batch + per-symbol fallback both empty)", symbol)

    return results


def fetch_quote(symbol: str, history: Optional[pd.DataFrame] = None) -> Optional[Quote]:
    df = history if history is not None else fetch_history(symbol, period="5d", interval="1d")
    if df.empty:
        return None
    # 批次下載偶爾會讓最新一列的 Close 是 NaN(例如當天資料尚未完整結算),
    # 但其他欄位(Volume 等)仍有值,不會被上游的 dropna(how="all") 濾掉。
    # 沒濾掉的話 price/change_pct 會算出 NaN,而 Python 的 json.dumps 預設會
    # 把 NaN 原樣輸出成不合法的 JSON,導致整個 signals_latest.json 在瀏覽器
    # 解析失敗、全站掛掉(單一標的的資料問題波及全部標的)。
    df = df.dropna(subset=["Close"])
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
