import { getDb } from '../db';
import { getTradingDays } from '../utils/dateUtils';
import { makeSeedRandom } from '../utils/dateUtils';

// ── Mock Data Generators ───────────────────────────────────

export function generateMockHistory(id: string, count: number) {
  const rand = makeSeedRandom(id);
  const basePrice = 40 + rand() * 850;
  let price = basePrice;
  const history = [];
  const dates = getTradingDays(count);

  for (let i = 0; i < count; i++) {
    const date = dates[i];
    const changePercent = (rand() - 0.485) * 0.038;
    const prevClose = price;
    price = parseFloat((price * (1 + changePercent)).toFixed(2));
    const spread = parseFloat((price * (rand() * 0.028)).toFixed(2));
    const open = parseFloat((prevClose + (rand() - 0.5) * (price * 0.012)).toFixed(2));
    const close = price;
    const high = parseFloat((Math.max(open, close) + rand() * (spread / 2)).toFixed(2));
    const low = parseFloat((Math.min(open, close) - rand() * (spread / 2)).toFixed(2));
    const volume = Math.floor(10000 + rand() * 190000);

    history.push({ date, open, high, low, close, volume });
  }
  return history;
}

export function generateMockInstitutional(id: string, count: number, dates: string[]) {
  const rand = makeSeedRandom(id + '_inst');
  const chipRows = [];
  for (let i = 0; i < count; i++) {
    const date = dates[i] || new Date().toISOString().split('T')[0];
    const foreign_net = Math.round((rand() - 0.49) * 22000);
    const trust_net = Math.round((rand() - 0.48) * 8500);
    const dealer_net = Math.round((rand() - 0.5) * 4500);
    chipRows.push({
      date,
      foreign_net,
      trust_net,
      dealer_net,
      institutional_net: foreign_net + trust_net + dealer_net,
    });
  }
  return chipRows;
}

export function generateMockShareholding(id: string, count: number, dates: string[]) {
  const rand = makeSeedRandom(id + '_tdcc');
  let whaleRatio = 35 + rand() * 50;
  const shareholdingRows = [];
  for (let i = 0; i < count; i++) {
    const date = dates[i] || new Date().toISOString().split('T')[0];
    whaleRatio = Math.min(98.5, Math.max(12.5, parseFloat((whaleRatio + (rand() - 0.495) * 0.4).toFixed(2))));
    const countWhales = Math.round(800 + rand() * 12000);
    const shares = Math.round(30000000 + rand() * 650000000);
    shareholdingRows.push({
      date,
      whale_ratio: whaleRatio,
      ratio: whaleRatio,
      count: countWhales,
      shares,
    });
  }
  return shareholdingRows;
}

// ── Technical Indicators ───────────────────────────────────

export function calcIndicators(
  prices: Array<{ date: string; open: number; high: number; low: number; close: number; volume: number }>
) {
  const closes = prices.map((p) => p.close);
  const n = closes.length;
  if (n < 2) return null;

  const ma = (period: number) => {
    if (n < period) return null;
    return parseFloat((closes.slice(-period).reduce((a, b) => a + b, 0) / period).toFixed(2));
  };
  const ma5 = ma(5),
    ma20 = ma(20),
    ma60 = ma(60),
    ma200 = ma(200);

  let rsi: number | null = null;
  if (n >= 15) {
    let gains = 0,
      losses = 0;
    for (let i = n - 14; i < n; i++) {
      const diff = closes[i] - closes[i - 1];
      if (diff > 0) gains += diff;
      else losses -= diff;
    }
    const avgGain = gains / 14,
      avgLoss = losses / 14;
    rsi = avgLoss === 0 ? 100 : parseFloat((100 - 100 / (1 + avgGain / avgLoss)).toFixed(2));
  }

  const recent20 = prices.slice(-20);
  const support = parseFloat(Math.min(...recent20.map((p) => p.low)).toFixed(2));
  const pressure = parseFloat(Math.max(...recent20.map((p) => p.high)).toFixed(2));

  return { ma5, ma20, ma60, ma200, rsi, support, pressure };
}
