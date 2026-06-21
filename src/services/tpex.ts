import { API_CONFIG } from '../config/apis';

async function fetchWithRetry(url: string, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (i === retries - 1) throw err;
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
    }
  }
}

// dateStr format: ROC Year/MM/DD (e.g. 115/06/15)
export async function fetchTpexDailyQuote(rocDateStr: string) { 
  const url = `${API_CONFIG.TPEX_BASE_URL}/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&d=${rocDateStr}&se=EW`;
  return fetchWithRetry(url);
}

// dateStr format: ROC Year/MM/DD (e.g. 115/06/15)
export async function fetchTpexInstitutional(rocDateStr: string) {
  const url = `${API_CONFIG.TPEX_BASE_URL}/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&se=AL&t=D&d=${rocDateStr}`;
  return fetchWithRetry(url);
}
