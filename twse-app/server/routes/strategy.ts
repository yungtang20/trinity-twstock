import { Router } from 'express';
import { getDb } from '../db';
import { getPredictionAnalysis } from '../services/technicalAnalysisService';

const router = Router();

// ── Helper: get all stock IDs with sufficient history ────────

function getQualifiedStocks(db: any, minVolume: number): { stock_id: string; stock_name: string }[] {
  return db.prepare(`
    SELECT DISTINCT h.stock_id, COALESCE(m.stock_name, h.stock_id) AS stock_name
    FROM stock_history h
    LEFT JOIN stock_meta m ON h.stock_id = m.stock_id
    WHERE h.date = (SELECT MAX(date) FROM stock_history)
      AND h.volume >= ?
  `).all(minVolume) as { stock_id: string; stock_name: string }[];
}

// ── Helper: get history for a stock ─────────────────────────

function getHistory(db: any, stockId: string): any[] {
  return db.prepare(
    'SELECT date, open, high, low, close, volume FROM stock_history WHERE stock_id = ? ORDER BY date ASC'
  ).all(stockId);
}

// ── Helper: compute simple MA ───────────────────────────────

function simpleMA(closes: number[], period: number): number | null {
  if (closes.length < period) return null;
  const slice = closes.slice(-period);
  return slice.reduce((a, b) => a + b, 0) / period;
}

// ── Helper: consecutive buy days ────────────────────────────

function consecutiveDays(values: number[], positive = true): number {
  let count = 0;
  for (let i = values.length - 1; i >= 0; i--) {
    if (positive ? values[i] > 0 : values[i] < 0) count++;
    else break;
  }
  return count;
}

// ── 3A. SR Scan ─────────────────────────────────────────────

router.get('/sr-scan', (req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const minVolume = parseInt(String(req.query.min_volume || '500')) || 500;
  const sort = String(req.query.sort || '1');

  try {
    const stocks = getQualifiedStocks(db, minVolume);
    const results: any[] = [];

    for (const s of stocks) {
      const history = getHistory(db, s.stock_id);
      if (history.length < 30) continue;
      const closes = history.map((r: any) => r.close);
      const lastClose = closes[closes.length - 1];

      // Find local lows as support candidates
      const window = 5;
      const supports: number[] = [];
      for (let i = window; i < closes.length - window; i++) {
        let isLow = true;
        for (let j = i - window; j <= i + window; j++) {
          if (j !== i && closes[j] <= closes[i]) { isLow = false; break; }
        }
        if (isLow && closes[i] < lastClose) supports.push(closes[i]);
      }

      if (supports.length === 0) continue;
      const nearestSupport = Math.max(...supports);
      const supportDistance = parseFloat(((lastClose - nearestSupport) / nearestSupport * 100).toFixed(2));

      results.push({
        stock_id: s.stock_id,
        stock_name: s.stock_name,
        close: lastClose,
        changePercent: 0,
        volume: history[history.length - 1].volume,
        support: parseFloat(nearestSupport.toFixed(2)),
        supportDistance,
        position: supportDistance < 2 ? 'near_support' : 'mid',
      });
    }

    if (sort === '1') results.sort((a, b) => a.supportDistance - b.supportDistance);
    else results.sort((a, b) => b.volume - a.volume);

    res.json({ success: true, data: results.slice(0, 50) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

// ── 3B. MA Scan ─────────────────────────────────────────────

router.get('/ma-scan', (req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const minVolume = parseInt(String(req.query.min_volume || '500')) || 500;
  const arrangement = String(req.query.arrangement || 'all');

  try {
    const stocks = getQualifiedStocks(db, minVolume);
    const results: any[] = [];

    for (const s of stocks) {
      const history = getHistory(db, s.stock_id);
      if (history.length < 60) continue;
      const closes = history.map((r: any) => r.close);
      const ma5 = simpleMA(closes, 5);
      const ma20 = simpleMA(closes, 20);
      const ma60 = simpleMA(closes, 60);
      if (!ma5 || !ma20 || !ma60) continue;

      let arrLabel = '整理';
      if (ma5 > ma20 && ma20 > ma60) arrLabel = '多頭排列';
      else if (ma5 < ma20 && ma20 < ma60) arrLabel = '空頭排列';

      if (arrangement !== 'all' && ((arrangement === 'bullish' && arrLabel !== '多頭排列') || (arrangement === 'bearish' && arrLabel !== '空頭排列'))) continue;

      results.push({
        stock_id: s.stock_id,
        stock_name: s.stock_name,
        close: closes[closes.length - 1],
        changePercent: 0,
        volume: history[history.length - 1].volume,
        ma5: parseFloat(ma5.toFixed(2)),
        ma20: parseFloat(ma20.toFixed(2)),
        ma60: parseFloat(ma60.toFixed(2)),
        arrangement: arrLabel,
      });
    }

    res.json({ success: true, data: results.slice(0, 50) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

// ── 3C. Chips Scan ──────────────────────────────────────────

router.get('/chips-scan', (req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const minConsecutive = parseInt(String(req.query.min_consecutive || '3')) || 3;

  try {
    const stocks = db.prepare('SELECT DISTINCT stock_id FROM institutional_data').all() as { stock_id: string }[];
    const results: any[] = [];

    for (const s of stocks) {
      const rows = db.prepare(
        'SELECT date, foreign_net, trust_net, dealer_net FROM institutional_data WHERE stock_id = ? ORDER BY date DESC LIMIT 20'
      ).all(s.stock_id) as any[];
      if (rows.length < minConsecutive) continue;

      const foreignValues = rows.map((r: any) => r.foreign_net || 0);
      const trustValues = rows.map((r: any) => r.trust_net || 0);

      const foreignBuy = consecutiveDays(foreignValues, true);
      const foreignSell = consecutiveDays(foreignValues, false);
      const trustBuy = consecutiveDays(trustValues, true);
      const trustSell = consecutiveDays(trustValues, false);

      const maxConsecutive = Math.max(foreignBuy, foreignSell, trustBuy, trustSell);
      if (maxConsecutive < minConsecutive) continue;

      const meta = db.prepare('SELECT stock_name FROM stock_meta WHERE stock_id = ?').get(s.stock_id) as any;
      results.push({
        stock_id: s.stock_id,
        stock_name: meta?.stock_name || s.stock_id,
        close: 0,
        changePercent: 0,
        volume: 0,
        foreignConsecutiveBuy: foreignBuy,
        foreignConsecutiveSell: foreignSell,
        trustConsecutiveBuy: trustBuy,
        trustConsecutiveSell: trustSell,
        signal: `外資${foreignBuy > 0 ? '連買' + foreignBuy + '日' : '連賣' + foreignSell + '日'}，投信${trustBuy > 0 ? '連買' + trustBuy + '日' : '連賣' + trustSell + '日'}`,
      });
    }

    res.json({ success: true, data: results });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

// ── 3D. Prediction Scan ─────────────────────────────────────

router.get('/prediction-scan', (req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const minVolume = parseInt(String(req.query.min_volume || '500')) || 500;
  const direction = String(req.query.direction || 'all');
  const minScore = parseInt(String(req.query.min_score || '2')) || 2;

  try {
    const stocks = getQualifiedStocks(db, minVolume);
    const results: any[] = [];

    for (const s of stocks) {
      const analysis = getPredictionAnalysis(db, s.stock_id);
      if (!analysis) continue;
      if (analysis.score < minScore) continue;
      if (direction !== 'all' && analysis.direction !== direction) continue;

      results.push({
        stock_id: s.stock_id,
        stock_name: s.stock_name,
        close: 0,
        changePercent: 0,
        volume: 0,
        score: analysis.score,
        maxScore: analysis.maxScore,
        direction: analysis.direction,
        directionLabel: analysis.directionLabel,
        rsi: analysis.indicators.rsi,
        macdSignal: analysis.signals.find((sig: any) => sig.name === 'MACD')?.label || '中性',
        target: analysis.prediction.target,
        upside: 0,
      });
    }

    results.sort((a, b) => b.score - a.score);
    res.json({ success: true, data: results });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

// ── 3E. Pattern Scan ────────────────────────────────────────

router.get('/pattern-scan', (req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const minVolume = parseInt(String(req.query.min_volume || '500')) || 500;
  const minConfidence = parseFloat(String(req.query.min_confidence || '0.5')) || 0.5;

  try {
    const stocks = getQualifiedStocks(db, minVolume);
    const results: any[] = [];

    for (const s of stocks) {
      const history = getHistory(db, s.stock_id);
      if (history.length < 20) continue;
      const closes = history.map((r: any) => r.close);

      // Simple pattern: three white soldiers
      let patternFound = false;
      for (let i = 2; i < closes.length && !patternFound; i++) {
        const c1 = closes[i - 2], c2 = closes[i - 1], c3 = closes[i];
        const o1 = history[i - 2].open, o2 = history[i - 1].open, o3 = history[i].open;
        if (c1 > o1 && c2 > o2 && c3 > o3 && c2 > c1 && c3 > c2) {
          const confidence = 0.7;
          if (confidence >= minConfidence) {
            results.push({
              stock_id: s.stock_id,
              stock_name: s.stock_name,
              close: closes[closes.length - 1],
              changePercent: 0,
              volume: history[history.length - 1].volume,
              patternType: 'three_white_soldiers',
              patternName: '三紅兵',
              confidence,
              target: parseFloat((c3 + (c3 - c1) * 0.5).toFixed(2)),
              upside: parseFloat((((c3 + (c3 - c1) * 0.5) - c3) / c3 * 100).toFixed(2)),
            });
            patternFound = true;
          }
        }
      }
    }

    res.json({ success: true, data: results });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

export default router;
