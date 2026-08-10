"""24 小時伺服器端自動跟單模擬帳戶。

策略特性(刻意與瀏覽器練習帳戶不同,見 docs/assets/paper.js):
- 起始資金 NT$10,000
- 當沖:**只有台股標的**收盤前強制平倉,不留倉過夜。美股/ETF/商品期貨/外匯/
  加密貨幣沒有這個時間限制,隨時可以進出——這是因為 2026-08-05 稽核真實
  production 資料時發現,上線以來每一次執行(不管是排程還是手動觸發)全部
  落在台北時間傍晚/晚上(收盤後),導致帳戶從上線到現在一次都沒能進場。
  原本的規則不分資產類別,一律套用台股收盤時間,等於直接把美股/外匯/
  加密貨幣的候選訊號也一起鎖死了,不符合「24小時」的設計初衷,所以改成
  只對台股標的套用當沖規則。
- Whipsaw 防護:訊號需「連續 2 次」出現反向,才會真的平倉。
  這是稽核實際自動跟單交易紀錄後找到的真因 —
  單次訊號反轉常常只是雜訊來回抽動(whipsaw),連續兩次反向出現時
  才視為趨勢真的轉向,可大幅減少來回進出造成的手續費與滑價虧損。
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.watchlist import symbol_category

logger = logging.getLogger(__name__)

TAIPEI_TZ = timezone(timedelta(hours=8))
INITIAL_CASH = 10_000.0
MARKET_CLOSE_TIME = time(13, 30)  # TWSE 收盤時間,只套用在台股標的上
REVERSAL_CONFIRMATIONS_REQUIRED = 2

STATE_PATH = Path("docs/data/auto_trader_state.json")
SIGNALS_PATH = Path("docs/data/signals_latest.json")


@dataclass
class Position:
    symbol: str
    direction: str  # "buy"(做多) or "sell"(放空)
    entry_price: float
    qty: float
    opened_at: str
    reversal_count: int = 0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class AutoTraderState:
    cash: float = INITIAL_CASH
    position: Optional[Position] = None
    trade_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cash": self.cash,
            "position": asdict(self.position) if self.position else None,
            "trade_history": self.trade_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AutoTraderState":
        position = Position(**data["position"]) if data.get("position") else None
        return cls(cash=data.get("cash", INITIAL_CASH), position=position, trade_history=data.get("trade_history", []))


def load_state(path: Path = STATE_PATH) -> AutoTraderState:
    if not path.exists():
        return AutoTraderState()
    try:
        return AutoTraderState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        logger.exception("failed to load auto trader state, starting fresh")
        return AutoTraderState()


def save_state(state: AutoTraderState, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def is_past_market_close(now: datetime) -> bool:
    local = now.astimezone(TAIPEI_TZ)
    return local.time() >= MARKET_CLOSE_TIME


def _is_tw_stock(symbol: str) -> bool:
    return symbol_category(symbol) == "tw_stock"


def _find_signal(signals: list[dict], symbol: str) -> Optional[dict]:
    for s in signals:
        if s["symbol"] == symbol:
            return s
    return None


def _pick_best_signal(signals: list[dict], now: datetime) -> Optional[dict]:
    market_closed = is_past_market_close(now)
    candidates = [
        s for s in signals
        if s.get("signal") in ("buy", "sell")
        and s.get("price")
        and not (market_closed and _is_tw_stock(s["symbol"]))  # 收盤後台股不開新倉,其他資產不受限
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s["confidence"])


def _close_position(state: AutoTraderState, exit_price: float, now: datetime, reason: str) -> None:
    pos = state.position
    if pos is None:
        return
    direction_sign = 1 if pos.direction == "buy" else -1
    pnl = direction_sign * (exit_price - pos.entry_price) * pos.qty
    state.cash += pnl
    state.trade_history.append({
        "symbol": pos.symbol,
        "direction": pos.direction,
        "entry_price": pos.entry_price,
        "exit_price": exit_price,
        "qty": pos.qty,
        "pnl": round(pnl, 2),
        "opened_at": pos.opened_at,
        "closed_at": now.isoformat(),
        "close_reason": reason,
    })
    state.position = None


def _check_risk_exit(position: Position, price: float) -> Optional[str]:
    """檢查現價是否觸發持倉的停損/停利價位,回傳平倉原因,沒觸發則回傳 None。

    在這之前,持倉完全沒有停損/停利保護——只有「台股收盤」或「訊號連續反轉
    兩次」會平倉,如果訊號一直沒反轉,部位會不管虧損多少都一直抱著,實際
    production 就發生過一筆外匯部位卡了好幾天沒動。停損/停利價位在開倉當下
    直接沿用 daily_run.py 已經算好的 ATR 風控價位(src/risk/stop_loss.py),
    不重新計算。
    """
    if position.direction == "buy":
        if position.stop_loss is not None and price <= position.stop_loss:
            return "觸發停損"
        if position.take_profit is not None and price >= position.take_profit:
            return "觸發停利"
    else:
        if position.stop_loss is not None and price >= position.stop_loss:
            return "觸發停損"
        if position.take_profit is not None and price <= position.take_profit:
            return "觸發停利"
    return None


def run_step(state: AutoTraderState, signals: list[dict], now: datetime) -> AutoTraderState:
    """依最新訊號更新自動跟單狀態(單一持倉,台股當沖規則)。

    決策順序:
    1. 若持倉是台股標的、且已收盤 -> 強制平倉(當沖規則)。非台股標的沒有這條規則。
    2. 若現價觸發開倉時設定的停損/停利價位 -> 平倉
    3. 若有持倉且新訊號與持倉方向相反 -> 累計反轉次數,達到門檻才平倉
    4. 若有持倉且新訊號與持倉方向相同或為 hold -> 重置反轉次數,續抱
    5. 若無持倉,選信心最高的 buy/sell 訊號開倉(停損/停利價位取自該訊號的
       風控計算)——已收盤的台股標的不列入候選,但美股/ETF/商品期貨/外匯/
       加密貨幣不受收盤時間限制,隨時可以開倉
    """
    if state.position is not None:
        current = _find_signal(signals, state.position.symbol)

        if _is_tw_stock(state.position.symbol) and is_past_market_close(now):
            exit_price = current["price"] if current else state.position.entry_price
            _close_position(state, exit_price, now, "當沖收盤強制平倉")
            return state

        if current is None:
            return state

        price = current.get("price")
        if price:
            risk_exit_reason = _check_risk_exit(state.position, price)
            if risk_exit_reason:
                _close_position(state, price, now, risk_exit_reason)
                return state

        is_reversal = current["signal"] != "hold" and current["signal"] != state.position.direction
        if is_reversal:
            state.position.reversal_count += 1
            if state.position.reversal_count >= REVERSAL_CONFIRMATIONS_REQUIRED:
                _close_position(state, current["price"], now, f"訊號連續{REVERSAL_CONFIRMATIONS_REQUIRED}次反轉")
        else:
            state.position.reversal_count = 0
        return state

    best = _pick_best_signal(signals, now)
    if best is None:
        return state

    price = best["price"]
    qty = state.cash // price if price and price > 0 else 0
    if qty > 0:
        risk_levels = best.get("risk_levels") or {}
        state.position = Position(
            symbol=best["symbol"],
            direction=best["signal"],
            entry_price=price,
            qty=qty,
            opened_at=now.isoformat(),
            stop_loss=risk_levels.get("stop_loss"),
            take_profit=risk_levels.get("take_profit"),
        )
    return state


def main() -> None:
    if not SIGNALS_PATH.exists():
        logger.warning("%s not found, run daily_run first", SIGNALS_PATH)
        return

    data = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
    signals = data.get("signals", [])

    state = load_state()
    now = datetime.now(timezone.utc)
    state = run_step(state, signals, now)
    save_state(state)

    position_desc = state.position.symbol if state.position else "無持倉"
    logger.info("auto trader: cash=%.2f position=%s", state.cash, position_desc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
