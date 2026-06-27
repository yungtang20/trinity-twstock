import Database from 'better-sqlite3';
type Db = InstanceType<typeof Database>;

// ── Types ──────────────────────────────────────────────────

interface PriceRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface SRLevel {
  price: number;
  strength: number;
  dates: string[];
}

interface SRAnalysisResult {
  supports: SRLevel[];
  resistances: SRLevel[];
  currentPrice: number;
  analysis: string;
}

interface MAAnalysisResult {
  ma5: number | null;
  ma20: number | null;
  ma60: number | null;
  ma200: number | null;
  arrangement: string;
  arrangementLabel: string;
  crossovers: { type: string; short: string; long: string; date: string; price: number }[];
  priceRelation: { ma: string; position: string; distance: number }[];
  summary: string;
}

interface ChipsAnalysisResult {
  foreign: { today: number; days5: number; days10: number; days20: number; consecutiveBuy: number; consecutiveSell: number; trend: string };
  trust: { today: number; days5: number; days10: number; days20: number; consecutiveBuy: number; consecutiveSell: number; trend: string };
  dealer: { today: number; days5: number; days10: number; days20: number; consecutiveBuy: number; consecutiveSell: number; trend: string };
  summary: string;
}

interface PredictionAnalysisResult {
  indicators: { rsi: number; macdDif: number; macdSignal: number; macdHistogram: number; k: number; d: number; atr: number };
  score: number;
  maxScore: number;
  direction: string;
  directionLabel: string;
  prediction: { target: number; rangeLow: number; rangeHigh: number; days: number };
  signals: { name: string; value: string; signal: string; label: string }[];
  summary: string;
}

interface PatternResult {
  type: string;
  name: string;
  confidence: number;
  startDate: string;
  endDate: string;
  keyPoints: { date: string; price: number; label: string }[];
  target: number;
  description: string;
}

interface PatternAnalysisResult {
  patterns: PatternResult[];
  summary: string;
}

// ── Shared helpers ─────────────────────────────────────────

function getStockHistory(db: Db, stockId: string, days = 250): PriceRow[] {
  return db
    .prepare('SELECT date, open, high, low, close, volume FROM stock_history WHERE stock_id = ? ORDER BY date ASC LIMIT ?')
    .all(stockId, days) as PriceRow[];
}

function getStockName(db: Db, stockId: string): string {
  const row = db.prepare('SELECT stock_name FROM stock_meta WHERE stock_id = ?').get(stockId) as { stock_name: string } | undefined;
  return row?.stock_name || stockId;
}

// ── MA ─────────────────────────────────────────────────────

function calcMA(data: number[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j];
    return sum / period;
  });
}

function calcEMA(data: number[], period: number): number[] {
  const k = 2 / (period + 1);
  const result: number[] = [];
  let ema = data[0];
  for (let i = 0; i < data.length; i++) {
    ema = i === 0 ? data[i] : data[i] * k + ema * (1 - k);
    result.push(ema);
  }
  return result;
}

function calcMACD(data: number[]) {
  const ema12 = calcEMA(data, 12);
  const ema26 = calcEMA(data, 26);
  const dif = data.map((_, i) => ema12[i] - ema26[i]);
  const dea = calcEMA(dif, 9);
  const macd = dif.map((d, i) => (d - dea[i]) * 2);
  return { dif, dea, macd };
}

function calcRSI(data: number[], period = 14): (number | null)[] {
  if (data.length < period + 1) return data.map(() => null);
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = data[i] - data[i - 1];
    if (diff > 0) gains += diff; else losses -= diff;
  }
  let avgGain = gains / period, avgLoss = losses / period;
  const result: (number | null)[] = [];
  for (let i = 0; i < period; i++) result.push(null);
  result.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i] - data[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    result.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  }
  return result;
}

function calcKD(data: PriceRow[], period = 9) {
  const kArr: number[] = [], dArr: number[] = [];
  let prevK = 50, prevD = 50;
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { kArr.push(0); dArr.push(0); continue; }
    let h9 = -Infinity, l9 = Infinity;
    for (let j = i - period + 1; j <= i; j++) { h9 = Math.max(h9, data[j].high); l9 = Math.min(l9, data[j].low); }
    const rsv = h9 === l9 ? 50 : ((data[i].close - l9) / (h9 - l9)) * 100;
    prevK = (2 / 3) * prevK + (1 / 3) * rsv;
    prevD = (2 / 3) * prevD + (1 / 3) * prevK;
    kArr.push(prevK); dArr.push(prevD);
  }
  return { k: kArr, d: dArr };
}

function calcATR(data: PriceRow[], period = 14): number[] {
  if (data.length < 2) return [];
  const tr: number[] = [];
  for (let i = 1; i < data.length; i++) {
    tr.push(Math.max(data[i].high - data[i].low, Math.abs(data[i].high - data[i - 1].close), Math.abs(data[i].low - data[i - 1].close)));
  }
  if (tr.length < period) return [];
  let atr = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
  const result: number[] = [atr];
  for (let i = period; i < tr.length; i++) {
    atr = (atr * (period - 1) + tr[i]) / period;
    result.push(atr);
  }
  return result;
}

// ── Support / Resistance ───────────────────────────────────

function findLocalExtremes(closes: number[], window: number) {
  const lows: { idx: number; price: number }[] = [];
  const highs: { idx: number; price: number }[] = [];
  for (let i = window; i < closes.length - window; i++) {
    let isLow = true, isHigh = true;
    for (let j = i - window; j <= i + window; j++) {
      if (j === i) continue;
      if (closes[j] <= closes[i]) isLow = false;
      if (closes[j] >= closes[i]) isHigh = false;
    }
    if (isLow) lows.push({ idx: i, price: closes[i] });
    if (isHigh) highs.push({ idx: i, price: closes[i] });
  }
  return { lows, highs };
}

function mergeLevels(levels: { price: number; idx: number; dates: string[] }[], threshold = 0.02): SRLevel[] {
  if (levels.length === 0) return [];
  const sorted = [...levels].sort((a, b) => a.price - b.price);
  const groups: { sum: number; count: number; dates: string[] }[] = [];
  let cur = { sum: sorted[0].price, count: 1, dates: [...sorted[0].dates] };
  for (let i = 1; i < sorted.length; i++) {
    const mean = cur.sum / cur.count;
    if (Math.abs(sorted[i].price - mean) / mean <= threshold) {
      cur.sum += sorted[i].price; cur.count++; cur.dates.push(...sorted[i].dates);
    } else {
      groups.push({ ...cur }); cur = { sum: sorted[i].price, count: 1, dates: [...sorted[i].dates] };
    }
  }
  groups.push({ ...cur });
  return groups.sort((a, b) => b.count - a.count).map((g) => ({ price: parseFloat((g.sum / g.count).toFixed(2)), strength: g.count, dates: g.dates }));
}

// ── Public: SR Analysis ────────────────────────────────────

export function getSRAnalysis(db: Db, stockId: string): SRAnalysisResult | null {
  const rows = getStockHistory(db, stockId, 120);
  if (rows.length < 30) return null;
  const closes = rows.map((r) => r.close);
  const dates = rows.map((r) => r.date);
  const currentPrice = closes[closes.length - 1];
  const { lows, highs } = findLocalExtremes(closes, 5);
  const supports = mergeLevels(lows.map((l) => ({ price: l.price, idx: l.idx, dates: [dates[l.idx]] })))
    .filter((s) => s.price < currentPrice).slice(0, 3);
  const resistances = mergeLevels(highs.map((h) => ({ price: h.price, idx: h.idx, dates: [dates[h.idx]] })))
    .filter((r) => r.price > currentPrice).slice(0, 3);
  return { supports, resistances, currentPrice, analysis: `${stockId} 目前價格 ${currentPrice.toFixed(2)}，支撐 ${supports.map((s) => s.price).join('/') || '無'}，壓力 ${resistances.map((r) => r.price).join('/') || '無'}` };
}

// ── Public: MA Analysis ────────────────────────────────────

export function getMAAnalysis(db: Db, stockId: string): MAAnalysisResult | null {
  const rows = getStockHistory(db, stockId, 250);
  if (rows.length < 20) return null;
  const closes = rows.map((r) => r.close);
  const dates = rows.map((r) => r.date);
  const ma5 = calcMA(closes, 5); const ma20 = calcMA(closes, 20); const ma60 = calcMA(closes, 60); const ma200 = calcMA(closes, 200);
  const last = closes.length - 1;
  const v5 = ma5[last]; const v20 = ma20[last]; const v60 = ma60[last]; const v200 = ma200[last];
  let arrangement = 'mixed', arrangementLabel = '整理';
  if (v5 && v20 && v60 && v200) {
    if (v5 > v20 && v20 > v60 && v60 > v200) { arrangement = 'bullish'; arrangementLabel = '多頭排列'; }
    else if (v5 < v20 && v20 < v60 && v60 < v200) { arrangement = 'bearish'; arrangementLabel = '空頭排列'; }
  }
  const crossovers: MAAnalysisResult['crossovers'] = [];
  for (let i = 1; i < closes.length; i++) {
    const pDiff = (ma5[i - 1] as number) - (ma20[i - 1] as number);
    const cDiff = (ma5[i] as number) - (ma20[i] as number);
    if (pDiff < 0 && cDiff > 0) crossovers.push({ type: 'golden', short: 'MA5', long: 'MA20', date: dates[i], price: closes[i] });
    else if (pDiff > 0 && cDiff < 0) crossovers.push({ type: 'death', short: 'MA5', long: 'MA20', date: dates[i], price: closes[i] });
  }
  const price = closes[last];
  const priceRelation = ['MA5', 'MA20', 'MA60', 'MA200'].map((label, idx) => {
    const v = [v5, v20, v60, v200][idx] as number;
    return { ma: label, position: price > v ? 'above' : 'below', distance: v ? parseFloat((((price - v) / v) * 100).toFixed(2)) : 0 };
  });
  const name = getStockName(db, stockId);
  return {
    ma5: v5 ? parseFloat(v5.toFixed(2)) : null, ma20: v20 ? parseFloat(v20.toFixed(2)) : null,
    ma60: v60 ? parseFloat(v60.toFixed(2)) : null, ma200: v200 ? parseFloat(v200.toFixed(2)) : null,
    arrangement, arrangementLabel, crossovers: crossovers.slice(-3), priceRelation,
    summary: `${name}(${stockId}) ${arrangementLabel}，MA5=${v5?.toFixed(1) ?? 'N/A'} MA20=${v20?.toFixed(1) ?? 'N/A'} MA60=${v60?.toFixed(1) ?? 'N/A'} MA200=${v200?.toFixed(1) ?? 'N/A'}`,
  };
}

// ── Public: Chips Analysis ─────────────────────────────────

export function getChipsAnalysis(db: Db, stockId: string): ChipsAnalysisResult | null {
  const instRows = db.prepare('SELECT date, foreign_net, trust_net, dealer_net FROM institutional_data WHERE stock_id = ? ORDER BY date DESC LIMIT 20')
    .all(stockId) as { date: string; foreign_net: number; trust_net: number; dealer_net: number }[];
  if (instRows.length === 0) return null;
  const sorted = [...instRows].reverse();
  const cum = (field: 'foreign_net' | 'trust_net' | 'dealer_net', n: number) => sorted.slice(-n).reduce((s, r) => s + (r[field] || 0), 0);
  const consec = (field: 'foreign_net' | 'trust_net' | 'dealer_net') => {
    let buy = 0, sell = 0;
    for (let i = sorted.length - 1; i >= 0; i--) {
      const v = sorted[i][field];
      if (v > 0) { buy = buy >= 0 ? buy + 1 : 1; sell = 0; }
      else if (v < 0) { sell = sell >= 0 ? sell + 1 : 1; buy = 0; }
      else break;
    }
    return { consecutiveBuy: buy, consecutiveSell: sell };
  };
  const fC = consec('foreign_net'); const tC = consec('trust_net'); const dC = consec('dealer_net');
  const name = getStockName(db, stockId);
  return {
    foreign: { today: sorted[sorted.length - 1]?.foreign_net || 0, days5: cum('foreign_net', 5), days10: cum('foreign_net', 10), days20: cum('foreign_net', 20), ...fC, trend: fC.consecutiveBuy > 0 ? 'buying' : fC.consecutiveSell > 0 ? 'selling' : 'neutral' },
    trust: { today: sorted[sorted.length - 1]?.trust_net || 0, days5: cum('trust_net', 5), days10: cum('trust_net', 10), days20: cum('trust_net', 20), ...tC, trend: tC.consecutiveBuy > 0 ? 'buying' : tC.consecutiveSell > 0 ? 'selling' : 'neutral' },
    dealer: { today: sorted[sorted.length - 1]?.dealer_net || 0, days5: cum('dealer_net', 5), days10: cum('dealer_net', 10), days20: cum('dealer_net', 20), ...dC, trend: dC.consecutiveBuy > 0 ? 'buying' : dC.consecutiveSell > 0 ? 'selling' : 'neutral' },
    summary: `${name}(${stockId}) 外資${fC.consecutiveBuy > 0 ? '連買' + fC.consecutiveBuy + '日' : fC.consecutiveSell > 0 ? '連賣' + fC.consecutiveSell + '日' : '中性'}，投信${tC.consecutiveBuy > 0 ? '連買' + tC.consecutiveBuy + '日' : tC.consecutiveSell > 0 ? '連賣' + tC.consecutiveSell + '日' : '中性'}`,
  };
}

// ── Public: Prediction Analysis ────────────────────────────

export function getPredictionAnalysis(db: Db, stockId: string): PredictionAnalysisResult | null {
  const rows = getStockHistory(db, stockId, 60);
  if (rows.length < 30) return null;
  const closes = rows.map((r) => r.close);
  const rsiArr = calcRSI(closes, 14);
  const { dif, dea, macd } = calcMACD(closes);
  const { k, d } = calcKD(rows, 9);
  const atrArr = calcATR(rows, 14);
  const last = closes.length - 1;
  const rsi = rsiArr[last];
  if (rsi === null || dif[last] === undefined || dea[last] === undefined || macd[last] === undefined || k[last] === 0 || d[last] === 0 || atrArr.length === 0) return null;
  const macdDif = dif[last], macdSignal = dea[last], macdHistogram = macd[last];
  const kVal = k[last], dVal = d[last], atr = atrArr[atrArr.length - 1];

  let score = 0;
  const signals: PredictionAnalysisResult['signals'] = [];
  if (rsi > 70) { score -= 1; signals.push({ name: 'RSI', value: rsi.toFixed(1), signal: 'overbought', label: '偏高' }); }
  else if (rsi < 30) { score += 1; signals.push({ name: 'RSI', value: rsi.toFixed(1), signal: 'oversold', label: '偏低' }); }
  else { signals.push({ name: 'RSI', value: rsi.toFixed(1), signal: 'neutral', label: '中性' }); }
  if (macdDif > macdSignal && macdHistogram > 0) { score += 1; signals.push({ name: 'MACD', value: 'DIF > Signal', signal: 'bullish', label: '多頭' }); }
  else if (macdDif < macdSignal && macdHistogram < 0) { score -= 1; signals.push({ name: 'MACD', value: 'DIF < Signal', signal: 'bearish', label: '空頭' }); }
  else { signals.push({ name: 'MACD', value: 'Mixed', signal: 'neutral', label: '中性' }); }
  if (kVal > dVal && kVal < 80) { score += 1; signals.push({ name: 'KD', value: 'K > D', signal: 'bullish', label: '偏多' }); }
  else if (kVal < dVal && kVal > 20) { score -= 1; signals.push({ name: 'KD', value: 'K < D', signal: 'bearish', label: '偏空' }); }
  else { signals.push({ name: 'KD', value: kVal.toFixed(1), signal: 'neutral', label: '中性' }); }

  const maxScore = 3;
  const direction = score > 0 ? 'bullish' : score < 0 ? 'bearish' : 'neutral';
  const directionLabel = score > 0 ? '偏多' : score < 0 ? '偏空' : '中性';
  const price = closes[last];
  const target = parseFloat((price + score * atr * 0.5).toFixed(2));
  const name = getStockName(db, stockId);
  return {
    indicators: { rsi: parseFloat(rsi.toFixed(1)), macdDif: parseFloat(macdDif.toFixed(2)), macdSignal: parseFloat(macdSignal.toFixed(2)), macdHistogram: parseFloat(macdHistogram.toFixed(2)), k: parseFloat(kVal.toFixed(1)), d: parseFloat(dVal.toFixed(1)), atr: parseFloat(atr.toFixed(2)) },
    score, maxScore, direction, directionLabel,
    prediction: { target, rangeLow: parseFloat((price - 1.5 * atr).toFixed(2)), rangeHigh: parseFloat((price + 1.5 * atr).toFixed(2)), days: 5 },
    signals,
    summary: `${name}(${stockId}) 綜合評分 ${score}/${maxScore}，${directionLabel}，預測 5 日目標價 ${target}`,
  };
}

// ── Public: Pattern Analysis ───────────────────────────────

export function getPatternAnalysis(db: Db, stockId: string): PatternAnalysisResult | null {
  const rows = getStockHistory(db, stockId, 60);
  if (rows.length < 20) return null;
  const lows = rows.map((r) => r.low);
  const highs = rows.map((r) => r.high);
  const closes = rows.map((r) => r.close);
  const dates = rows.map((r) => r.date);
  const patterns: PatternResult[] = [];

  // Double bottom: two similar lows
  const window = 5;
  const localLows: { idx: number; price: number }[] = [];
  for (let i = window; i < closes.length - window; i++) {
    let isLow = true;
    for (let j = i - window; j <= i + window; j++) {
      if (j !== i && lows[j] <= lows[i]) { isLow = false; break; }
    }
    if (isLow) localLows.push({ idx: i, price: lows[i] });
  }
  if (localLows.length >= 2) {
    let found = false;
    for (let i = 0; i < localLows.length - 1 && !found; i++) {
      for (let j = i + 1; j < localLows.length && !found; j++) {
        const a = localLows[i].price, b = localLows[j].price;
        if (Math.abs(a - b) / ((a + b) / 2) < 0.02) {
          const between = highs.slice(localLows[i].idx, localLows[j].idx + 1);
          const neckline = Math.max(...between);
          const neckIdx = localLows[i].idx + between.indexOf(neckline);
          const target = parseFloat((neckline + (neckline - a)).toFixed(2));
          patterns.push({
            type: 'double_bottom', name: '雙重底', confidence: 0.75,
            startDate: dates[localLows[i].idx], endDate: dates[localLows[j].idx],
            keyPoints: [{ date: dates[localLows[i].idx], price: a, label: '第一底' }, { date: dates[neckIdx], price: neckline, label: '頸線' }, { date: dates[localLows[j].idx], price: b, label: '第二底' }],
            target, description: `雙重底型態確認，頸線 ${neckline.toFixed(2)}，目標價 ${target.toFixed(2)}`,
          });
          found = true;
        }
      }
    }
  }

  // Three white soldiers
  for (let i = 2; i < closes.length; i++) {
    const c1 = closes[i - 2], c2 = closes[i - 1], c3 = closes[i];
    const o1 = rows[i - 2].open, o2 = rows[i - 1].open, o3 = rows[i].open;
    if (c1 > o1 && c2 > o2 && c3 > o3 && c2 > c1 && c3 > c2 && o2 > o1 && o3 > o2) {
      patterns.push({
        type: 'three_white_soldiers', name: '三紅兵', confidence: 0.7,
        startDate: dates[i - 2], endDate: dates[i],
        keyPoints: [{ date: dates[i - 2], price: c1, label: '第一根' }, { date: dates[i - 1], price: c2, label: '第二根' }, { date: dates[i], price: c3, label: '第三根' }],
        target: parseFloat((c3 + (c3 - c1) * 0.5).toFixed(2)),
        description: `三紅兵型態，連續三根陽線，目標價 ${c3 + (c3 - c1) * 0.5}`,
      });
    }
  }

  const name = getStockName(db, stockId);
  const summary = patterns.length > 0
    ? `${name}(${stockId}) 偵測到 ${patterns.length} 個型態：${patterns.map((p) => p.name).join(', ')}`
    : `${name}(${stockId}) 未偵測到明顯型態`;

  return { patterns, summary };
}