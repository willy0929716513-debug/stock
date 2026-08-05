"""偵測台股是否為交易日(週末 + 公告休市日)。"""
from __future__ import annotations

import datetime as dt

TAIPEI_TZ = dt.timezone(dt.timedelta(hours=8))

# 台灣證券交易所公告之休市日(國定假日等),需每年依證交所公告更新。
# 來源:證交所年度「上市有價證券當日沖銷交易標的及應行注意事項」/
#       「上市上櫃有價證券買賣日曆表」公告。
# 誠實說明:此表為手動維護,颱風假等臨時公告無法預先寫死,
# 需要另外查即時公告;若表格未及時更新,交易日判斷可能有誤。
TWSE_HOLIDAYS_2026 = {
    "2026-01-01",  # 元旦
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-02-19",
    "2026-02-20",  # 農曆春節(含彈性放假,以證交所公告為準)
    "2026-02-27",  # 228 和平紀念日調整假
    "2026-04-03",
    "2026-04-06",  # 清明節
    "2026-05-01",  # 勞動節
    "2026-06-19",  # 端午節
    "2026-09-25",  # 中秋節
    "2026-10-09",  # 國慶日調整假
}


def is_trading_day(date: dt.date | None = None, holidays: set[str] | None = None) -> bool:
    """回傳指定日期(預設今天,台北時區)是否為台股交易日。"""
    if date is None:
        date = dt.datetime.now(TAIPEI_TZ).date()
    if holidays is None:
        holidays = TWSE_HOLIDAYS_2026
    if date.weekday() >= 5:  # 週六=5, 週日=6
        return False
    if date.isoformat() in holidays:
        return False
    return True
