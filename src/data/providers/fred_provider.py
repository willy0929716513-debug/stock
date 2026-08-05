"""FRED(聖路易聯邦準備銀行)總體經濟資料來源。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from src.config import FRED_API_KEY

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# 追蹤的總經指標:美國10年期公債殖利率、CPI、失業率
SERIES = {
    "DGS10": "美國10年期公債殖利率",
    "CPIAUCSL": "美國CPI",
    "UNRATE": "美國失業率",
}


@dataclass
class MacroSeries:
    series_id: str
    name: str
    latest_value: Optional[float]
    latest_date: Optional[str]


def fetch_series(series_id: str) -> Optional[MacroSeries]:
    name = SERIES.get(series_id, series_id)
    if not FRED_API_KEY:
        logger.info("FRED_API_KEY not set, skipping macro fetch for %s", series_id)
        return None
    try:
        resp = requests.get(
            FRED_BASE_URL,
            params={
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        observations = data.get("observations") or []
        if not observations:
            return None
        obs = observations[0]
        if obs.get("value") in (None, "."):
            return None
        return MacroSeries(series_id=series_id, name=name, latest_value=float(obs["value"]), latest_date=obs["date"])
    except Exception:
        logger.exception("failed to fetch FRED series %s", series_id)
        return None


def fetch_all_macro() -> list[MacroSeries]:
    results = []
    for series_id in SERIES:
        series = fetch_series(series_id)
        if series:
            results.append(series)
    return results
