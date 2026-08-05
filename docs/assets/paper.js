// 瀏覽器端模擬交易帳戶:純前端 localStorage,起始資金 NT$10,000,000。
// 刻意與伺服器端 24 小時自動跟單帳戶(NT$10,000 起始、當沖)不同:
// 這裡是「練習帳戶」,可以跨日持倉,由使用者自己手動下單。
const PAPER_TRADING = (() => {
  const STORAGE_KEY = "jpo_kbo_paper_account_v1";
  const INITIAL_CASH = 10_000_000;

  function loadAccount() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return freshAccount();
      const parsed = JSON.parse(raw);
      if (typeof parsed.cash !== "number" || typeof parsed.holdings !== "object") return freshAccount();
      return parsed;
    } catch {
      return freshAccount();
    }
  }

  function freshAccount() {
    return { cash: INITIAL_CASH, holdings: {}, transactions: [] };
  }

  function saveAccount(account) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(account));
  }

  function resetAccount() {
    const account = freshAccount();
    saveAccount(account);
    return account;
  }

  function buy(account, symbol, name, qty, price) {
    const cost = qty * price;
    if (qty <= 0) throw new Error("股數必須大於 0");
    if (cost > account.cash) throw new Error("現金不足,無法買進");

    const holding = account.holdings[symbol] || { name, qty: 0, avg_cost: 0 };
    const totalCost = holding.avg_cost * holding.qty + cost;
    const totalQty = holding.qty + qty;
    account.holdings[symbol] = { name, qty: totalQty, avg_cost: totalCost / totalQty };
    account.cash -= cost;

    account.transactions.push({
      symbol, name, side: "buy", qty, price, amount: cost, at: new Date().toISOString(),
    });
    saveAccount(account);
    return account;
  }

  function sell(account, symbol, name, qty, price) {
    const holding = account.holdings[symbol];
    if (!holding || holding.qty < qty) throw new Error("持股不足,無法賣出");
    if (qty <= 0) throw new Error("股數必須大於 0");

    const proceeds = qty * price;
    holding.qty -= qty;
    account.cash += proceeds;
    if (holding.qty <= 0) {
      delete account.holdings[symbol];
    } else {
      account.holdings[symbol] = holding;
    }

    account.transactions.push({
      symbol, name, side: "sell", qty, price, amount: proceeds, at: new Date().toISOString(),
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

  return { STORAGE_KEY, INITIAL_CASH, loadAccount, saveAccount, resetAccount, buy, sell, portfolioValue };
})();
