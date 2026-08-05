# JPO-KBO 量化交易訊號儀表板

以台股為主、輔以美股/ETF/黃金/原油/外匯/加密貨幣的量化訊號儀表板,部署在 GitHub Pages(純靜態網站)。
目標是提供實用、誠實(不誇大)的訊號參考,而不是保證獲利的黑盒子。

> 本專案原本開發於 `willy0929716513-debug/JPO-KBO`,現搬移並在 `willy0931926721-hub/stock`
> 重新實作核心架構(因搬移當下無法存取原 repo,採重新實作而非搬移 git 歷史)。

## 免責聲明

⚠️ 本站所有訊號、停損停利價位、AI 潛力股分析,都是根據歷史價格與公開新聞計算出的參考資訊,
**不構成投資建議**,不保證任何未來報酬。兩個模擬帳戶都是虛擬資金,不涉及真實下單。請自行承擔投資風險。

## 架構總覽

```
src/
  config.py                  # 環境變數與路徑設定
  watchlist.py                # 追蹤清單(台股/美股/ETF/商品/外匯/加密貨幣)
  data/providers/
    market_data.py            # yfinance 報價 + 新聞(含批次下載,降低大量標的的限流風險)
    twse_calendar.py          # 台股休市日偵測(手動維護清單,見下方「已知限制」)
    fred_provider.py          # FRED 總體經濟指標
    llm_provider.py           # Gemini AI 前瞻潛力股分析
  strategies/                 # 均線交叉 / RSI / MACD / 布林通道
  risk/stop_loss.py           # ATR 為基礎的停損停利計算
  agents/
    technical_agent.py        # 彙整多策略訊號
    macro_agent.py             # 總經風險修正(權重低,僅輔助)
    risk_agent.py               # 波動度風控(不表態方向,信心值把結果拉向中性)
    decision_engine.py          # 三個 Agent 加權合議 -> 最終訊號
  pipeline/
    daily_run.py               # 主要 pipeline 入口,產出 docs/data/signals_latest.json
    auto_trader.py              # 24 小時伺服器端自動跟單模擬帳戶

docs/                          # GitHub Pages 前端(純靜態,無建置流程)
  index.html                   # 今日建議首頁
  news.html                    # 📰 新聞熱門股
  top-picks.html               # 🚀 最強推薦(含 AI 潛力股)
  auto-trader.html             # 24 小時自動跟單帳戶
  paper-trading.html           # 瀏覽器模擬交易練習帳戶
  quotes.html                  # 即時報價
  assets/
    style.css / common.js       # 共用樣式與工具函式
    paper.js                    # 瀏覽器練習帳戶邏輯(純 localStorage)
  data/
    signals_latest.json         # pipeline 產出的公開資料(GitHub Actions 自動寫入)
    auto_trader_state.json      # 自動跟單帳戶狀態(GitHub Actions 自動寫入)

tests/                          # pytest 回歸測試
.github/workflows/
  pipeline.yml                  # 每 ~5 分鐘執行 pipeline,把結果 commit 回 docs/data/
  tests.yml                     # push / PR 時跑 pytest
```

## 多代理決策引擎

`DecisionEngine` 讓三個 Agent 加權合議產生最終訊號:

| Agent | 權重 | 職責 |
|---|---|---|
| 技術面(technical) | 0.6 | 彙整均線交叉、RSI、MACD、布林通道四個策略 |
| 總經(macro) | 0.15 | 依 FRED 公債殖利率 / 失業率做簡化風險修正,無 API key 時自動略過 |
| 風控(risk) | 0.25 | 依 ATR 波動度評估,只表態信心值(不表態方向),波動過大時把訊號拉向中性 |

這是刻意的簡化經驗法則,不是嚴謹的總經或選股模型,權重與門檻都可以在
`src/agents/decision_engine.py` 調整。

## 兩個模擬交易帳戶(刻意採用不同策略)

1. **24 小時伺服器端自動跟單**(`src/pipeline/auto_trader.py`)
   - 起始資金 NT$10,000
   - **當沖(只套用在台股標的)**:台股收盤前(台北時間 13:30)強制平倉、收盤後不開新倉,
     不留倉過夜。美股/ETF/商品期貨/外匯/加密貨幣**沒有**這個時間限制,隨時可以進出——
     這是 2026-08-05 稽核真實 production log 後發現並修正的:原本規則不分資產類別,
     導致帳戶從上線以來每次執行都落在台北時間傍晚/晚上(收盤後),一次都沒能進場過。
   - **Whipsaw 防護**:訊號需連續 2 次反轉才會真的平倉,單次反轉只累計次數、不平倉。
     這是為了避免單次雜訊來回抽單造成的手續費/滑價虧損。
   - 狀態存在 `docs/data/auto_trader_state.json`,由 GitHub Actions 定期更新並寫回 repo。

2. **瀏覽器端練習帳戶**(`docs/assets/paper.js`)
   - 起始資金 NT$10,000,000
   - 純前端 `localStorage`,不會同步到伺服器,換裝置/清瀏覽紀錄會遺失
   - 可跨日持倉,預設由使用者自己手動下單,也可以在頁面上開啟「🤖 自動交易模式」
     依訊號自動下單(買進訊號且信心值 ≥ 30%、尚未持有該標的時,動用目前現金 5%
     開倉;賣出訊號且有持倉時全部出清),手動下單功能在自動模式開啟時仍然可用,
     兩者不互斥。
   - **誠實限制**:自動模式只會在「這個瀏覽器分頁保持開啟」時執行(靠 60 秒一次
     的計時器重新檢查訊號),分頁關掉或裝置睡眠就不會有任何動作 —— 這**不是**
     真正的 24 小時背景自動交易,只有上面第 1 點的伺服器端帳戶才是全天候的。

## 🔮 AI 前瞻潛力股(除錯中的功能)

`src/data/providers/llm_provider.py` 用 Google Gemini 免費額度分析全部追蹤清單的新聞,
推論「因為其他標的/產業趨勢而未來可能受惠」的標的。

**誠實記錄目前的狀態:功能仍在除錯階段**,模型選擇沿革如下:

1. 一開始用 `gemini-2.0-flash` → 收到 429(額度用盡)
2. 查證後發現該模型已下架
3. 改用寫死的版本號 → 該版本也下架,收到 404
4. 改用 Google 官方滾動別名 `gemini-flash-lite-latest`,避免版本號寫死造成下架問題
5. 呼叫成功但可能出現「Gemini response wasn't in the expected format」解析失敗

目前已加上診斷紀錄(`finishReason`、原始回應片段前 2000 字),但**只寫進 `logger`,
只留在 GitHub Actions log,不會外洩到公開的 `signals_latest.json`**。下次若再解析失敗,
直接去對應那次 Actions run 的 log 找真因,不要憑感覺猜。

若 `GEMINI_API_KEY` 未設定或分析失敗,`potential_picks` 會是空陣列,前端會顯示提示文字,
不會讓整個 pipeline 掛掉。

## 已知限制(誠實記錄,不要刪掉)

- **台股休市日清單是手動維護的**(`src/data/providers/twse_calendar.py`),需要每年依證交所公告更新;
  颱風假等臨時公告無法預先寫死,需要另外查即時公告。
- **本次搬移是重新實作核心架構**,不是原 repo 的逐行搬移 —— 因為搬移當下沒有原 repo
  `willy0929716513-debug/JPO-KBO` 的存取權限。策略門檻、Agent 權重等參數是重新設計的
  簡化版本,還沒有經過原本專案的實際交易紀錄驗證,上線後應持續觀察並校正。
- **本 sandbox 開發環境無法連上 Yahoo Finance**(proxy 阻擋),所以 `market_data.py` 的
  實際抓取行為只能在 GitHub Actions 上驗證,不能在本機驗證。合併後已經驗證過:
  23 檔標的時全部成功、pipeline 全程約 8 秒;擴充到 121 檔後 `fetch_history_batch()`
  的批次下載也運作正常(全程約 20~25 秒),**沒有出現任何 429 限流訊息**,批次下載
  這個設計目前看起來是有效的。
- **台股清單(`WATCHLIST["tw_stock"]`)是人工整理的,不是即時抓取的**,approximate
  台灣50(0050)+中型100(0051)成分股,原因同樣是開發環境連不上 TWSE/Wikipedia
  等外部網站查證即時成分股。這兩個指數約每年 6 月、12 月會定期審核調整,清單可能
  已經過時,需要定期人工核對。若清單中有下市或改名的舊代號,pipeline 會在 log 印出
  `no history data for X` 警告並跳過,不會讓整條 pipeline 掛掉——2026-08-05 已經
  依照連續兩次真實執行的 log 校正過一次,移除了 5 個持續回傳 404 的代號(詳見
  `watchlist.py` 檔頭註解的完整記錄)。
- `docs/data/signals_latest.json`、`docs/data/auto_trader_state.json` 由 GitHub Actions 自動寫入,
  本地開發不需要、也不應該手動 commit 這兩個檔案的內容變動。

## 本機開發

```bash
pip install -r requirements.txt
python -m pytest tests/ -v          # 跑回歸測試(43 個測試,不需要網路或 API key)
python -m src.pipeline.daily_run    # 手動跑一次 pipeline(需要網路)
python -m src.pipeline.auto_trader  # 手動跑一次自動跟單(需要先有 signals_latest.json)
```

## 部署設定(一次性手動步驟)

1. **GitHub Pages**:Settings → Pages → Source 選擇 `Deploy from a branch`,
   Branch 選這個 repo 的預設分支、資料夾選 `/docs`。
2. **Secrets**(選填,不設定就自動降級,不影響其他功能):
   - `FRED_API_KEY`:[FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) 免費金鑰,沒設定時總經 Agent 自動略過。
   - `GEMINI_API_KEY`:[Google AI Studio](https://aistudio.google.com/) 免費金鑰,沒設定時 AI 潛力股功能自動略過。
3. `.github/workflows/pipeline.yml` 需要 `contents: write` 權限把資料寫回 repo,
   這已經在 workflow 檔案裡設定好,但如果 repo 的 Settings → Actions → General →
   Workflow permissions 被設為唯讀,還是要手動改成 `Read and write permissions`。

## 追蹤清單

目前 `src/watchlist.py` 涵蓋台股 103 檔(approximate 台灣50+中型100 成分股,見上方
「已知限制」的誠實說明)、美股 5 檔、2 檔 ETF、黃金/原油期貨、2 組外匯、2 種加密貨幣,
共 116 檔標的,可依需求增減。
