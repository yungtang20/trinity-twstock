import { API_CONFIG } from '../config/apis';

async function fetchWithRetry(url: string, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (i === retries - 1) throw err;
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1))); // exponential backoff
    }
  }
}

export async function fetchTwseDailyQuote(dateStr: string) { // dateStr in YYYYMMDD
  const url = `${API_CONFIG.TWSE_BASE_URL}/exchangeReport/MI_INDEX?response=json&date=${dateStr}&type=ALLBUT0999`;
  return fetchWithRetry(url);
}

export async function fetchTwseInstitutional(dateStr: string) { // dateStr in YYYYMMDD
  const url = `${API_CONFIG.TWSE_BASE_URL}/fund/T86?response=json&date=${dateStr}&selectType=ALLBUT0999`;
  return fetchWithRetry(url);
}
