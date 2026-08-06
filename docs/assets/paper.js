// 瀏覽器端模擬交易帳戶:純前端 localStorage,起始資金 NT$10,000,000。
// 刻意與伺服器端 24 小時自動跟單帳戶(NT$10,000 起始、當沖)不同:
// 這裡是「練習帳戶」,可以跨日持倉,預設由使用者自己手動下單,
// 也可以切換「自動模式」依訊號自動下單(但保留手動下單功能,兩者可並存)。
//
// 誠實限制:自動模式只會在「這個分頁保持開啟」時執行,不是真正的
// 24 小時背景自動交易——瀏覽器分頁關掉之後就不會有任何動作。真正
// 全天候自動化的是伺服器端 24 小時自動跟單帳戶(src/pipeline/auto_trader.py)。
const PAPER_TRADING = (() => {
  const STORAGE_KEY = "jpo_kbo_paper_account_v1";
  const INITIAL_CASH = 10_000_000;
  const AUTO_TRADE_MIN_CONFIDENCE = 0.3;
  const AUTO_TRADE_ALLOCATION_FRACTION = 0.05; // 自動買進時,每筆動用「目前現金」的比例
  const TAIPEI_MARKET_CLOSE_HOUR = 13;
  const TAIPEI_MARKET_CLOSE_MINUTE = 30; // TWSE 收盤時間,只套用在台股標的上,跟伺服器端 auto_trader.py 邏輯一致

  function isPastTaipeiMarketClose(date = new Date()) {
    // 用 Intl API 取台北時間,不依賴使用者瀏覽器/裝置的本地時區設定
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "Asia/Taipei",
      hour: "numeric",
      minute: "numeric",
      hour12: false,
    }).formatToParts(date);
    const hour = Number(parts.find((p) => p.type === "hour").value) % 24;
    const minute = Number(parts.find((p) => p.type === "minute").value);
    return hour > TAIPEI_MARKET_CLOSE_HOUR || (hour === TAIPEI_MARKET_CLOSE_HOUR && minute >= TAIPEI_MARKET_CLOSE_MINUTE);
  }

  function freshAccount() {
    return { cash: INITIAL_CASH, holdings: {}, transactions: [], autoMode: false, lastAutoProcessedAt: null };
  }

  function loadAccount() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return freshAccount();
      const parsed = JSON.parse(raw);
      if (typeof parsed.cash !== "number" || typeof parsed.holdings !== "object") return freshAccount();
      // 用 freshAccount() 補齊舊版帳戶資料缺少的欄位(例如舊帳戶沒有 autoMode)
      return { ...freshAccount(), ...parsed };
    } catch {
      return freshAccount();
    }
  }

  function saveAccount(account) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(account));
  }

  function resetAccount() {
    const account = freshAccount();
    saveAccount(account);
    return account;
  }

  function setAutoMode(account, enabled) {
    account.autoMode = enabled;
    saveAccount(account);
    return account;
  }

  function buy(account, symbol, name, qty, price, options = {}) {
    const cost = qty * price;
    if (qty <= 0) throw new Error("股數必須大於 0");
    if (cost > account.cash) throw new Error("現金不足,無法買進");

    const holding = account.holdings[symbol] || { name, qty: 0, avg_cost: 0 };
    const totalCost = holding.avg_cost * holding.qty + cost;
    const totalQty = holding.qty + qty;
    account.holdings[symbol] = { name, qty: totalQty, avg_cost: totalCost / totalQty };
    account.cash -= cost;

    account.transactions.push({
      symbol, name, side: "buy", qty, price, amount: cost, at: new Date().toISOString(), auto: !!options.auto,
    });
    saveAccount(account);
    return account;
  }

  function sell(account, symbol, name, qty, price, options = {}) {
    const holding = account.holdings[symbol];
    if (!holding || holding.qty < qty) throw new Error("持股不足,無法賣出");
    if (qty <= 0) throw new Error("股數必須大於 0");

    const proceeds = qty * price;
    const costBasis = holding.avg_cost * qty;
    const pnl = proceeds - costBasis;
    holding.qty -= qty;
    account.cash += proceeds;
    if (holding.qty <= 0) {
      delete account.holdings[symbol];
    } else {
      account.holdings[symbol] = holding;
    }

    account.transactions.push({
      symbol, name, side: "sell", qty, price, amount: proceeds, at: new Date().toISOString(), auto: !!options.auto,
      cost_basis: costBasis, pnl,
    });
    saveAccount(account);
    return account;
  }

  function portfolioValue(account, priceBySymbol) {
    let holdingsValue = 0;
    for (const [symbol, h] of Object.entries(account.holdings)) {
      const price = priceBySymbol[symbol] ?? h.avg_cost;
      holdingsValue += price * h.qty;
    }
    return account.cash + holdingsValue;
  }

  /**
   * 依目前訊號自動下單:
   * - 買進訊號且信心值達門檻、尚未持有該標的 -> 動用目前現金的一小部分開倉
   *   (已持有的標的不會重複加碼,避免每次重新整理就一直買同一檔)
   * - 賣出訊號且信心值達門檻、目前有持倉 -> 全部出清
   * - 同一批訊號(用 pipeline 的 generatedAt 判斷)只處理一次,避免分頁沒關、
   *   同一批資料被重複觸發交易。
   * - 台股標的(category === "tw_stock")在台股收盤後不下新單(買或賣都不執行),
   *   跟伺服器端 24 小時自動跟單帳戶用同一套規則;美股/ETF/商品期貨/外匯/
   *   加密貨幣不受這個時間限制。這是稽核伺服器端帳戶「上線以來因為規則沒分
   *   資產類別而完全沒進場過」的真因之後,一併套用到這裡的修正。
   *   跟伺服器端不同的是:這裡**不會**在收盤時強制平倉既有的台股持倉——
   *   這個練習帳戶本來就設計成可以跨日持倉,只是「新單」要遵守收盤時間。
   */
  function autoTrade(account, signals, generatedAt) {
    if (!account.autoMode) return { account, executed: [] };
    if (generatedAt && account.lastAutoProcessedAt === generatedAt) return { account, executed: [] };

    const marketClosed = isPastTaipeiMarketClose();
    const executed = [];
    for (const s of signals) {
      if (!s.price || s.price <= 0) continue;
      if (s.category === "tw_stock" && marketClosed) continue;

      if (s.signal === "buy" && s.confidence >= AUTO_TRADE_MIN_CONFIDENCE) {
        if (account.holdings[s.symbol]) continue;
        const budget = account.cash * AUTO_TRADE_ALLOCATION_FRACTION;
        const qty = Math.floor(budget / s.price);
        if (qty < 1) continue;
        try {
          buy(account, s.symbol, s.name, qty, s.price, { auto: true });
          executed.push({ symbol: s.symbol, side: "buy", qty, price: s.price });
        } catch {
          // 現金不足等情況直接跳過該標的,不中斷其他標的的自動下單
        }
      } else if (s.signal === "sell" && s.confidence >= AUTO_TRADE_MIN_CONFIDENCE) {
        const holding = account.holdings[s.symbol];
        if (!holding || holding.qty <= 0) continue;
        const sellQty = holding.qty; // sell() 會就地修改 holding.qty,要在呼叫前先記下來
        try {
          sell(account, s.symbol, s.name, sellQty, s.price, { auto: true });
          executed.push({ symbol: s.symbol, side: "sell", qty: sellQty, price: s.price });
        } catch {
          // 略過
        }
      }
    }

    if (generatedAt) account.lastAutoProcessedAt = generatedAt;
    saveAccount(account);
    return { account, executed };
  }

  return {
    STORAGE_KEY,
    INITIAL_CASH,
    AUTO_TRADE_MIN_CONFIDENCE,
    AUTO_TRADE_ALLOCATION_FRACTION,
    isPastTaipeiMarketClose,
    loadAccount,
    saveAccount,
    resetAccount,
    setAutoMode,
    buy,
    sell,
    portfolioValue,
    autoTrade,
  };
})();
