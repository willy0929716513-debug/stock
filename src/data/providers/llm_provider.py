"""Google Gemini AI 前瞻潛力股分析。

用免費額度分析全部追蹤清單的新聞,推論「因為其他標的/產業趨勢而未來受惠」的標的。

模型選擇沿革(除錯過程,誠實記錄勿刪):
  1. 一開始用 gemini-2.0-flash -> 收到 429(額度用盡)
  2. 查證後發現該模型已下架
  3. 改用寫死的版本號 -> 該版本也下架,收到 404
  4. 改用 Google 官方滾動別名 gemini-flash-lite-latest,避免版本號寫死造成的下架問題
  5. 呼叫成功但出現「Gemini response wasn't in the expected format」解析失敗,
     已加上下方的診斷紀錄(finishReason、原始回應片段)方便下次直接看 Actions log 抓真因。
     診斷紀錄只寫進 logger(留在 GitHub Actions log),不會寫入公開的 signals_latest.json。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import requests

from src.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-flash-lite-latest"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


@dataclass
class PotentialPick:
    symbol: str
    reason: str
    beneficiary_of: str  # 因為哪個標的/趨勢而受惠


def _build_prompt(news_by_symbol: dict[str, list[str]]) -> str:
    lines = [
        "以下是各標的最近的新聞標題,請找出「因為其他標的或產業趨勢而可能未來受惠」的標的。",
        "只根據提供的新聞內容推論,不要編造未提及的事實。",
        "請用 JSON 陣列格式回答,每個元素包含 symbol, reason, beneficiary_of 三個欄位,"
        "沒有適合的就回傳空陣列 []。不要加上任何 JSON 以外的文字。",
        "",
    ]
    for symbol, titles in news_by_symbol.items():
        if not titles:
            continue
        lines.append(f"[{symbol}]")
        lines.extend(f"- {t}" for t in titles[:5])
    return "\n".join(lines)


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            first_line, rest = text.split("\n", 1)
            text = rest if first_line.strip().lower() in ("json", "") else text
    return text.strip()


def analyze_potential_stocks(news_by_symbol: dict[str, list[str]]) -> list[PotentialPick]:
    if not GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set, skipping potential-stock analysis")
        return []

    has_news = any(news_by_symbol.values())
    if not has_news:
        logger.info("no news available, skipping potential-stock analysis")
        return []

    prompt = _build_prompt(news_by_symbol)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        resp = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Gemini API request failed (model=%s)", GEMINI_MODEL)
        return []

    data = resp.json()
    try:
        candidates = data.get("candidates") or []
        if not candidates:
            logger.warning(
                "Gemini returned no candidates: promptFeedback=%s raw=%s",
                data.get("promptFeedback"), json.dumps(data, ensure_ascii=False)[:2000],
            )
            return []

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)

        if not text:
            logger.warning(
                "Gemini response wasn't in the expected format: finishReason=%s raw=%s",
                finish_reason, json.dumps(data, ensure_ascii=False)[:2000],
            )
            return []

        picks_raw = json.loads(_extract_json_text(text))
        return [
            PotentialPick(symbol=p["symbol"], reason=p.get("reason", ""), beneficiary_of=p.get("beneficiary_of", ""))
            for p in picks_raw
            if "symbol" in p
        ]
    except Exception:
        logger.exception("failed to parse Gemini response: raw=%s", json.dumps(data, ensure_ascii=False)[:2000])
        return []
