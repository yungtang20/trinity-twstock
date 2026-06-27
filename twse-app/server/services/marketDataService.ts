import { getDb } from '../db';
import { fetchFollowRedirects } from '../utils/httpUtils';
import { formatDateStr, formatTpexDateStr } from '../utils/dateUtils';
import { parseTwseIndex, parseTwseUpDown, parseTpexIndex, parseNum } from '../utils/parsingUtils';

const fallbackTwseData = {
  success: false,
  index: 0,
  change: 0,
  changePercent: 0,
  amount: 0,
  limitUp: 0,
  up: 0,
  flat: 0,
  down: 0,
  limitDown: 0,
  error: 'No data for 8 days',
};

const fallbackOtcData = {
  success: false,
  index: 0,
  change: 0,
  changePercent: 0,
  amount: 0,
  limitUp: 0,
  up: 0,
  flat: 0,
  down: 0,
  limitDown: 0,
  error: 'No data for 8 days',
};

// ── DB-based fallback for TWSE stats ─────────────────────────
// Computes index from average of TSE stock prices when external API fails
const getTwseStatsFromDb = () => {
  const db = getDb();
  if (!db) return null;
  try {
    // Get latest 2 dates with data
    const datesRow = db.prepare(
      `SELECT DISTINCT date FROM stock_history ORDER BY date DESC LIMIT 2`
    ).all() as { date: string }[];
    if (datesRow.length < 1) return null;

    const latestDate = datesRow[0].date;
    const prevDate = datesRow.length > 1 ? datesRow[1].date : latestDate;

    // Get all stocks with valid 4-digit IDs (TSE stocks) latest close and previous close
    // Use GLOB to filter TSE stock IDs (4 digits, starting with 1-9) - avoids JOIN with stock_meta
    const stocks = db.prepare(`
      SELECT h.stock_id, h.close, h.volume, h.amount,
             h_prev.close as prev_close
      FROM stock_history h
      LEFT JOIN stock_history h_prev ON h.stock_id = h_prev.stock_id AND h_prev.date = ?
      WHERE h.date = ? AND h.stock_id GLOB '[1-9][0-9][0-9][0-9]' AND h.close > 0
    `).all(prevDate, latestDate) as { stock_id: string; close: number; volume: number; amount: number; prev_close: number }[];

    if (stocks.length === 0) return null;

    // Compute index as average close (simple average as fallback)
    const index = stocks.reduce((sum, s) => sum + s.close, 0) / stocks.length;
    const prevIndex = stocks.reduce((sum, s) => sum + (s.prev_close || s.close), 0) / stocks.length;
    const change = index - prevIndex;
    const changePercent = prevIndex > 0 ? parseFloat(((change / prevIndex) * 100).toFixed(2)) : 0;

    // Compute up/down/flat counts
    let limitUp = 0, up = 0, flat = 0, down = 0, limitDown = 0;
    for (const s of stocks) {
      const prev = s.prev_close || s.close;
      const pct = prev > 0 ? (s.close - prev) / prev : 0;
      if (pct >= 0.098) limitUp++;
      else if (pct > 0) up++;
      else if (pct === 0) flat++;
      else if (pct <= -0.098) limitDown++;
      else down++;
    }

    // Total amount
    const totalAmount = stocks.reduce((sum, s) => sum + (s.amount || 0), 0) / 1e8;

    return {
      index: parseFloat(index.toFixed(2)),
      change: parseFloat(change.toFixed(2)),
      changePercent,
      amount: parseFloat(totalAmount.toFixed(2)),
      limitUp, up, flat, down, limitDown,
    };
  } catch {
    return null;
  }
};

// ── DB-based fallback for OTC stats ─────────────────────────
// Computes index from average of OTC stock prices when external API fails
const getOtcStatsFromDb = () => {
  const db = getDb();
  if (!db) return null;
  try {
    // Get latest 2 dates with data
    const datesRow = db.prepare(
      `SELECT DISTINCT date FROM stock_history ORDER BY date DESC LIMIT 2`
    ).all() as { date: string }[];
    if (datesRow.length < 1) return null;

    const latestDate = datesRow[0].date;
    const prevDate = datesRow.length > 1 ? datesRow[1].date : latestDate;

    // Get all OTC stocks latest close and previous close
    // OTC stocks have 4-digit IDs starting with 3 or 4 (e.g., 3008, 3045, 4301)
    // Use GLOB to filter - avoids JOIN with stock_meta
    const stocks = db.prepare(`
      SELECT h.stock_id, h.close, h.volume, h.amount,
             h_prev.close as prev_close
      FROM stock_history h
      LEFT JOIN stock_history h_prev ON h.stock_id = h_prev.stock_id AND h_prev.date = ?
      WHERE h.date = ? AND (h.stock_id GLOB '3[0-9][0-9][0-9]' OR h.stock_id GLOB '4[0-9][0-9][0-9]') AND h.close > 0
    `).all(prevDate, latestDate) as { stock_id: string; close: number; volume: number; amount: number; prev_close: number }[];

    if (stocks.length === 0) return null;

    // Compute index as average close
    const index = stocks.reduce((sum, s) => sum + s.close, 0) / stocks.length;
    const prevIndex = stocks.reduce((sum, s) => sum + (s.prev_close || s.close), 0) / stocks.length;
    const change = index - prevIndex;
    const changePercent = prevIndex > 0 ? parseFloat(((change / prevIndex) * 100).toFixed(2)) : 0;

    // Compute up/down/flat counts
    let limitUp = 0, up = 0, flat = 0, down = 0, limitDown = 0;
    for (const s of stocks) {
      const prev = s.prev_close || s.close;
      const pct = prev > 0 ? (s.close - prev) / prev : 0;
      if (pct >= 0.098) limitUp++;
      else if (pct > 0) up++;
      else if (pct === 0) flat++;
      else if (pct <= -0.098) limitDown++;
      else down++;
    }

    // Total amount
    const totalAmount = stocks.reduce((sum, s) => sum + (s.amount || 0), 0) / 1e8;

    return {
      index: parseFloat(index.toFixed(2)),
      change: parseFloat(change.toFixed(2)),
      changePercent,
      amount: parseFloat(totalAmount.toFixed(2)),
      limitUp, up, flat, down, limitDown,
    };
  } catch {
    return null;
  }
};

// ── OTC DB helper: up/down counts from stock_meta joined tables ──
// Returns only up/down/flat/limit counts + total_amount (used as supplement when live quotes fail)
function getOtcUpDownFromDb(dateStr?: string) {
  const db = getDb();
  if (!db) return null;
  try {
    const normalized = dateStr ? dateStr.replace(/\//g, '') : '';
    let activeDate = normalized ? `${normalized.slice(0, 4)}-${normalized.slice(4, 6)}-${normalized.slice(6, 8)}` : '';
    const activeDateRow = db
      .prepare(
        `SELECT date FROM stock_history WHERE date <= ? AND stock_id IN (SELECT stock_id FROM stock_meta WHERE market='OTC') GROUP BY date HAVING COUNT(*) > 50 ORDER BY date DESC LIMIT 1`
      )
      .get(activeDate);
    if (activeDateRow?.date) activeDate = activeDateRow.date;
    else {
      const maxDateRow = db
        .prepare("SELECT MAX(date) as d FROM stock_history WHERE stock_id IN (SELECT stock_id FROM stock_meta WHERE market='OTC')")
        .get();
      if (maxDateRow?.d) activeDate = maxDateRow.d;
    }
    const prevDateRow = db
      .prepare(
        "SELECT date FROM stock_history WHERE date < ? AND stock_id IN (SELECT stock_id FROM stock_meta WHERE market='OTC') GROUP BY date HAVING COUNT(*) > 50 ORDER BY date DESC LIMIT 1"
      )
      .get(activeDate);
    const prevDate = prevDateRow?.date;
    if (!prevDate) return null;
    const row = db
      .prepare(
        `
        SELECT
          SUM(CASE WHEN (curr.close - prev.close)/prev.close >= 0.098 THEN 1 ELSE 0 END) as limit_up,
          SUM(CASE WHEN (curr.close - prev.close)/prev.close <= -0.098 THEN 1 ELSE 0 END) as limit_down,
          SUM(CASE WHEN curr.close > prev.close AND (curr.close - prev.close)/prev.close < 0.098 THEN 1 ELSE 0 END) as up,
          SUM(CASE WHEN curr.close < prev.close AND (curr.close - prev.close)/prev.close > -0.098 THEN 1 ELSE 0 END) as down,
          SUM(CASE WHEN curr.close = prev.close THEN 1 ELSE 0 END) as flat,
          SUM(curr.amount)/100000000.0 as total_amount
        FROM stock_history curr
        JOIN stock_history prev ON curr.stock_id = prev.stock_id
        JOIN stock_meta m ON curr.stock_id = m.stock_id
        WHERE m.market = 'OTC' AND curr.date = ? AND prev.date = ? AND prev.close > 0
      `
      )
      .get(activeDate, prevDate);
    if (!row) return null;
    return {
      limit_up: row.limit_up || 0,
      limit_down: row.limit_down || 0,
      up: row.up || 0,
      down: row.down || 0,
      flat: row.flat || 0,
      total_amount: parseFloat((row.total_amount || 0).toFixed(2)),
    };
  } catch {
    return null;
  }
};

export const getTwseStats = async () => {
  let date = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));

  for (let attempts = 0; attempts < 8; attempts++) {
    const targetDate = new Date(date);
    if (attempts > 0) targetDate.setDate(targetDate.getDate() - attempts);
    const dateStr = formatDateStr(targetDate);
    try {
      const indexUrl = `https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date=${dateStr}&type=ALL`;
      const indexRes = await fetch(indexUrl, {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        signal: AbortSignal.timeout(10000),
      });
      if (!indexRes.ok) throw new Error(`TWSE API error: ${indexRes.status}`);
      const indexJson = await indexRes.json();
      const parsedIndex = parseTwseIndex(indexJson);
      if (!parsedIndex) throw new Error('Cannot parse TWSE index');

      let amount = 0;
      try {
        const amountUrl = `https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date=${dateStr}`;
        const amountRes = await fetch(amountUrl, {
          headers: { 'User-Agent': 'Mozilla/5.0' },
          signal: AbortSignal.timeout(5000),
        });
        if (amountRes.ok) {
          const amountJson = await amountRes.json();
          const lastRow = amountJson?.data?.[amountJson.data.length - 1];
          const latestAmount = lastRow?.[2]?.replace(/,/g, '');
          amount = latestAmount ? parseFloat(latestAmount) / 100_000_000 : 0;
        }
      } catch {
        /* ignore */
      }

      let upDown = { limitUp: 0, up: 0, flat: 0, down: 0, limitDown: 0 };
      const parsedUpDown = parseTwseUpDown(indexJson);
      if (parsedUpDown) upDown = parsedUpDown;

      return {
        success: true,
        date: `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`,
        index: parsedIndex.index,
        change: parsedIndex.change,
        changePercent: parsedIndex.changePercent,
        amount: parseFloat(amount.toFixed(2)),
        ...upDown,
      };
    } catch {
      /* try next day */
    }
  }

  // Fallback: compute from DB
  const dbStats = getTwseStatsFromDb();
  if (dbStats) {
    return { success: true, date: new Date().toISOString().slice(0, 10), ...dbStats };
  }

  return { ...fallbackTwseData };
};

export const getOtcStats = async () => {
  let date = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));

  for (let attempts = 0; attempts < 8; attempts++) {
    const targetDate = new Date(date);
    if (attempts > 0) targetDate.setDate(targetDate.getDate() - attempts);
    const yyyy = targetDate.getFullYear();
    const mm = String(targetDate.getMonth() + 1).padStart(2, '0');
    const dd = String(targetDate.getDate()).padStart(2, '0');
    const dateStr = `${yyyy}/${mm}/${dd}`;

    try {
      const indexUrl = `https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_index/st41_result.php?l=zh-tw&d=${dateStr}`;
      const indexRes = await fetchFollowRedirects(indexUrl);
      if (!indexRes.ok) throw new Error(`TPEX API error: ${indexRes.status}`);
      const indexJson = await indexRes.json();
      const parsedIndex = parseTpexIndex(indexJson);
      if (!parsedIndex) throw new Error('Cannot parse TPEX index');

      let upDown = { limitUp: 0, up: 0, flat: 0, down: 0, limitDown: 0 };
      let hasLiveUpDown = false;
      try {
        const quotesUrl = `https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&d=${dateStr}&se=EW&s=0,asc,0`;
        const quotesRes = await fetchFollowRedirects(quotesUrl);
        if (quotesRes.ok) {
          const quotesJson = await quotesRes.json();
          const quotesData = quotesJson?.tables?.[0]?.data || quotesJson?.aaData || [];
          if (quotesData.length > 0) {
            let lUp = 0,
              u = 0,
              f = 0,
              d = 0,
              lDn = 0;
            quotesData.forEach((r: any) => {
              const id = String(r[0] || '');
              if (id.length > 6) return;
              const changeStr = String(r[3] || '');
              const changeVal = parseNum(changeStr);
              const closeVal = parseNum(r[2]);

              if (changeVal === 0) f++;
              else if (changeVal > 0) {
                const prevClose = closeVal - changeVal;
                const percent = prevClose > 0 ? changeVal / prevClose : 0;
                if (percent >= 0.0975) lUp++;
                else u++;
              } else {
                const prevClose = closeVal + Math.abs(changeVal);
                const percent = prevClose > 0 ? Math.abs(changeVal) / prevClose : 0;
                if (percent >= 0.0975) lDn++;
                else d++;
              }
            });
            upDown = { limitUp: lUp, up: u, flat: f, down: d, limitDown: lDn };
            hasLiveUpDown = true;
          }
        }
      } catch {
        /* ignore */
      }

      let amount = 0;
      const dbUpDown = getOtcUpDownFromDb(dateStr);
      if (!hasLiveUpDown && dbUpDown) {
        upDown = {
          limitUp: dbUpDown.limit_up,
          up: dbUpDown.up,
          flat: dbUpDown.flat,
          down: dbUpDown.down,
          limitDown: dbUpDown.limit_down,
        };
        amount = dbUpDown.total_amount;
      }

      return {
        success: true,
        date: `${yyyy}-${mm}-${dd}`,
        index: parsedIndex.index,
        change: parsedIndex.change,
        changePercent: parsedIndex.changePercent,
        amount,
        ...upDown,
      };
    } catch {
      /* try next day */
    }
  }

  // Fallback: compute from DB
  const dbStats = getOtcStatsFromDb();
  if (dbStats) {
    return { success: true, date: new Date().toISOString().slice(0, 10), ...dbStats };
  }

  return { ...fallbackOtcData };
};
