// 共用工具函式:各頁面共用,負責抓資料、格式化顯示。
const JPO_KBO = (() => {
  const CATEGORY_LABELS = {
    tw_stock: "台股",
    us_stock: "美股",
    etf: "ETF",
    commodity: "商品期貨",
    forex: "外匯",
    crypto: "加密貨幣",
    unknown: "其他",
  };

  const SIGNAL_LABELS = { buy: "買進", sell: "賣出", hold: "觀望" };

  async function fetchJSON(path) {
    const res = await fetch(path + "?_=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error(`無法讀取 ${path}(HTTP ${res.status})`);
    return res.json();
  }

  async function loadSignals() {
    return fetchJSON("data/signals_latest.json");
  }

  async function loadAutoTraderState() {
    return fetchJSON("data/auto_trader_state.json");
  }

  function signalBadge(signal) {
    const label = SIGNAL_LABELS[signal] || signal;
    return `<span class="badge ${signal}">${label}</span>`;
  }

  function pctClass(pct) {
    if (pct == null) return "pct-flat";
    if (pct > 0) return "pct-up";
    if (pct < 0) return "pct-down";
    return "pct-flat";
  }

  function formatPct(pct) {
    if (pct == null) return "—";
    const sign = pct > 0 ? "+" : "";
    return `${sign}${pct.toFixed(2)}%`;
  }

  function formatPrice(price) {
    if (price == null) return "—";
    return price.toLocaleString("zh-TW", { maximumFractionDigits: 4 });
  }

  function formatMoney(amount) {
    if (amount == null) return "—";
    return "NT$" + Math.round(amount).toLocaleString("zh-TW");
  }

  function formatDateTime(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("zh-TW", { hour12: false });
    } catch {
      return iso;
    }
  }

  function categoryLabel(category) {
    return CATEGORY_LABELS[category] || category;
  }

  function setActiveNav() {
    const current = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll("nav.main-nav a").forEach((a) => {
      const href = a.getAttribute("href");
      if (href === current) a.classList.add("active");
    });
  }

  function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  return {
    CATEGORY_LABELS,
    SIGNAL_LABELS,
    fetchJSON,
    loadSignals,
    loadAutoTraderState,
    signalBadge,
    pctClass,
    formatPct,
    formatPrice,
    formatMoney,
    formatDateTime,
    categoryLabel,
    setActiveNav,
    escapeHTML,
  };
})();

document.addEventListener("DOMContentLoaded", () => JPO_KBO.setActiveNav());
