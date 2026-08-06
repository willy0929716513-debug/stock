"""追蹤 pipeline 是否持續抓到新資料,連續 N 次沒有新資料就回報需要暫停排程。

背景:稽核發現 GitHub Actions 的排程在公開 repo / 免費方案上對高頻率排程
(原本 */5)不可靠,實際延遲到以小時計。除了排程本身的問題,也要防範另一種
「靜默失敗」——例如 Yahoo Finance 整批掛掉、或抓取邏輯在悄悄回傳跟上次一模
一樣的舊資料而不是真的報錯,導致資料長期沒有更新卻沒有任何警訊。連續多次
偵測不到新資料時,由呼叫端(GitHub Actions workflow)去停用排程,而不是
無限重試下去浪費資源、卻沒人發現系統早就壞了。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HEALTH_PATH = Path("docs/data/pipeline_health.json")
PAUSE_AFTER_CONSECUTIVE_FAILURES = 3


@dataclass
class HealthState:
    consecutive_no_update: int
    last_run_at: str
    last_signal_count: int

    def to_dict(self) -> dict:
        return {
            "consecutive_no_update": self.consecutive_no_update,
            "last_run_at": self.last_run_at,
            "last_signal_count": self.last_signal_count,
        }


def load_previous_count(path: Path = HEALTH_PATH) -> int:
    if not path.exists():
        return 0
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("consecutive_no_update", 0)
    except Exception:
        return 0


def compute_next_count(previous_count: int, signal_count: int, data_changed: bool) -> int:
    """判斷這次算不算「沒抓到新資料」:
    - 訊號數量是 0(整批抓取失敗),或
    - 這次輸出跟上次 commit 完全一樣(可疑——真實市場報價幾乎不可能連續
      好幾次都毫無變動,比較可能是抓取邏輯悄悄回傳了舊/快取資料而不是報錯)。
    符合任一種情況就算一次失敗,計數 +1;否則重置為 0。
    """
    no_update = signal_count == 0 or not data_changed
    return previous_count + 1 if no_update else 0


def update_health_file(signal_count: int, data_changed: bool, path: Path = HEALTH_PATH) -> int:
    """更新健康狀態檔並回傳新的連續失敗次數,供 workflow 判斷是否要停用排程。"""
    previous_count = load_previous_count(path)
    new_count = compute_next_count(previous_count, signal_count, data_changed)
    state = HealthState(
        consecutive_no_update=new_count,
        last_run_at=datetime.now(timezone.utc).isoformat(),
        last_signal_count=signal_count,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return new_count


def should_pause(consecutive_no_update: int) -> bool:
    return consecutive_no_update >= PAUSE_AFTER_CONSECUTIVE_FAILURES


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python -m src.pipeline.health_check <signal_count> <data_changed:0|1>", file=sys.stderr)
        sys.exit(1)
    signal_count = int(sys.argv[1])
    data_changed = sys.argv[2] == "1"
    new_count = update_health_file(signal_count, data_changed)
    print(new_count)


if __name__ == "__main__":
    main()
