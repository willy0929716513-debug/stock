"""24 小時伺服器端自動跟單模擬帳戶。

策略特性(刻意與瀏覽器練習帳戶不同,見 docs/assets/paper.js):
- 起始資金 NT$10,000
- 當沖:收盤前強制平倉,不留倉過夜
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

logger = logging.getLogger(__name__)

TAIPEI_TZ = timezone(timedelta(hours=8))
INITIAL_CASH = 10_000.0
MARKET_CLOSE_TIME = time(13, 30)  # TWSE 收盤時間
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


def _find_signal(signals: list[dict], symbol: str) -> Optional[dict]:
    for s in signals:
        if s["symbol"] == symbol:
            return s
    return None


def _pick_best_signal(signals: list[dict]) -> Optional[dict]:
    candidates = [s for s in signals if s.get("signal") in ("buy", "sell") and s.get("price")]
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


def run_step(state: AutoTraderState, signals: list[dict], now: datetime) -> AutoTraderState:
    """依最新訊號更新自動跟單狀態(單一持倉,當沖規則)。

    決策順序:
    1. 若已收盤且仍有持倉 -> 強制平倉(當沖規則)
    2. 若有持倉且新訊號與持倉方向相反 -> 累計反轉次數,達到門檻才平倉
    3. 若有持倉且新訊號與持倉方向相同或為 hold -> 重置反轉次數,續抱
    4. 若無持倉、未收盤,選信心最高的 buy/sell 訊號開倉
    """
    if state.position is not None:
        current = _find_signal(signals, state.position.symbol)

        if is_past_market_close(now):
            exit_price = current["price"] if current else state.position.entry_price
            _close_position(state, exit_price, now, "當沖收盤強制平倉")
            return state

        if current is None:
            return state

        is_reversal = current["signal"] != "hold" and current["signal"] != state.position.direction
        if is_reversal:
            state.position.reversal_count += 1
            if state.position.reversal_count >= REVERSAL_CONFIRMATIONS_REQUIRED:
                _close_position(state, current["price"], now, f"訊號連續{REVERSAL_CONFIRMATIONS_REQUIRED}次反轉")
        else:
            state.position.reversal_count = 0
        return state

    if is_past_market_close(now):
        return state

    best = _pick_best_signal(signals)
    if best is None:
        return state

    price = best["price"]
    qty = state.cash // price if price and price > 0 else 0
    if qty > 0:
        state.position = Position(
            symbol=best["symbol"],
            direction=best["signal"],
            entry_price=price,
            qty=qty,
            opened_at=now.isoformat(),
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
