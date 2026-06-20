/**
 * Technical indicator calculations (browser-side)
 * Based on SPEC.md formulas
 */

export interface PriceData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** 移動平均線 */
export function calcMA(data: number[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j];
    return sum / period;
  });
}

/** EMA */
export function calcEMA(data: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const result: (number | null)[] = [];
  let ema = data[0];
  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      ema = data[i];
    } else {
      ema = data[i] * k + ema * (1 - k);
    }
    result.push(ema);
  }
  return result;
}

/** MACD */
export function calcMACD(data: number[]) {
  const ema12 = calcEMA(data, 12);
  const ema26 = calcEMA(data, 26);
  const dif: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (ema12[i] !== null && ema26[i] !== null) {
      dif.push((ema12[i] as number) - (ema26[i] as number));
    } else {
      dif.push(null);
    }
  }
  const difFiltered = dif.filter((d): d is number => d !== null);
  const deaRaw = calcEMA(difFiltered, 9);
  const dea = deaRaw.filter((d): d is number => d !== null);
  const macd: (number | null)[] = [];
  let deaIdx = 0;
  for (let i = 0; i < data.length; i++) {
    if (dif[i] !== null && dea[deaIdx] !== undefined) {
      macd.push(((dif[i] as number) - dea[deaIdx]) * 2);
      deaIdx++;
    } else {
      macd.push(null);
    }
  }
  return { dif, dea, macd };
}

/** RSI */
export function calcRSI(data: number[], period = 14): (number | null)[] {
  const result: (number | null)[] = [];
  if (data.length < period + 1) return data.map(() => null);
  let gains: number[] = [];
  let losses: number[] = [];
  for (let i = 1; i <= period; i++) {
    const diff = data[i] - data[i - 1];
    gains.push(Math.max(diff, 0));
    losses.push(Math.max(-diff, 0));
  }
  let avgGain = gains.reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.reduce((a, b) => a + b, 0) / period;
  result.push(null); // index 0
  for (let i = 1; i < period; i++) result.push(null);
  const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  result.push(100 - 100 / (1 + rs));
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i] - data[i - 1];
    const gain = Math.max(diff, 0);
    const loss = Math.max(-diff, 0);
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rs2 = avgLoss === 0 ? 100 : avgGain / avgLoss;
    result.push(100 - 100 / (1 + rs2));
  }
  return result;
}

/** KD */
export function calcKD(data: PriceData[], period = 9) {
  const kValues: (number | null)[] = [];
  const dValues: (number | null)[] = [];
  let prevK = 50;
  let prevD = 50;
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      kValues.push(null);
      dValues.push(null);
      continue;
    }
    let h9 = -Infinity, l9 = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      h9 = Math.max(h9, data[j].high);
      l9 = Math.min(l9, data[j].low);
    }
    const rsv = h9 === l9 ? 50 : ((data[i].close - l9) / (h9 - l9)) * 100;
    const k = (2 / 3) * prevK + (1 / 3) * rsv;
    const d = (2 / 3) * prevD + (1 / 3) * k;
    kValues.push(k);
    dValues.push(d);
    prevK = k;
    prevD = d;
  }
  return { k: kValues, d: dValues };
}

/** ATR */
export function calcATR(data: PriceData[], period = 14): (number | null)[] {
  const tr: number[] = [];
  for (let i = 1; i < data.length; i++) {
    const hl = data[i].high - data[i].low;
    const hc = Math.abs(data[i].high - data[i - 1].close);
    const lc = Math.abs(data[i].low - data[i - 1].close);
    tr.push(Math.max(hl, hc, lc));
  }
  const result: (number | null)[] = [null];
  if (tr.length < period) return data.map(() => null);
  let atr = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result.push(atr);
  for (let i = period; i < tr.length; i++) {
    atr = (atr * (period - 1) + tr[i]) / period;
    result.push(atr);
  }
  return result;
}

/** 扣抵分析 */
export function calcDeduction(data: number[], period: number) {
  if (data.length < period + 1) return { value: null, trend: '--' };
  const value = data[data.length - period];
  const isUp = data[data.length - 1] > value;
  return { value, trend: isUp ? '上揚' : '下彎' };
}