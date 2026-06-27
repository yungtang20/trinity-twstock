import { Request, Response } from 'express';
import { getDb } from '../db';
import { getTradingDays } from '../utils/dateUtils';
import { generateMockHistory, generateMockInstitutional, generateMockShareholding, calcIndicators } from '../services/stockService';

export const searchStocks = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const q = String(req.query.q || '').trim();
  if (!q) return res.json({ success: true, data: [] });

  try {
    const rows = db
      .prepare(
        "SELECT stock_id, stock_name, market, industry_category FROM stock_meta WHERE (stock_id LIKE ? OR stock_name LIKE ?) AND length(stock_id) = 4 AND stock_id NOT GLOB '*[A-Z]*' LIMIT 10"
      )
      .all(`%${q}%`, `%${q}%`);
    res.json({ success: true, data: rows });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

export const getHistory = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const id = req.params.id;
  const days = Math.min(parseInt(String(req.query.days || '120')), 1000);

  try {
    let meta = db.prepare('SELECT stock_id, stock_name, market FROM stock_meta WHERE stock_id = ?').get(id);
    if (!meta) {
      const names: Record<string, string> = {
        '2330': '台積電', '2317': '鴻海', '2454': '聯發科', '2603': '長榮', '3231': '緯創',
        '2382': '廣達', '2308': '台達電', '2881': '富邦金', '2882': '國泰金', '0050': '元大台灣50',
      };
      meta = { stock_id: id, stock_name: names[id] || `股票(${id})`, market: 'TSE' };
    }

    let rows = db
      .prepare('SELECT date, open, high, low, close, volume FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT ?')
      .all(id, days);

    let isMock = false;
    if (rows.length < 10) {
      rows = generateMockHistory(id, days).reverse();
      isMock = true;
    }

    res.json({
      success: true,
      data: rows.reverse(),
      isMock,
      meta,
      source: meta?.market === 'TSE' ? 'twse' : 'tpex',
    });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

export const getIndicators = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const id = req.params.id;

  try {
    let rows = db
      .prepare('SELECT date, open, high, low, close, volume FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 250')
      .all(id);

    if (rows.length < 10) {
      rows = generateMockHistory(id, 250).reverse();
    }

    const indicators = calcIndicators(rows.reverse());
    res.json({ success: true, data: indicators });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

export const getInstitutional = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const id = req.params.id;

  try {
    let rows = db
      .prepare('SELECT date, foreign_net, trust_net, dealer_net, institutional_net FROM institutional_data WHERE stock_id = ? ORDER BY date DESC LIMIT 250')
      .all(id);

    let isMock = false;
    if (rows.length < 10) {
      const dates = getTradingDays(250).reverse();
      rows = generateMockInstitutional(id, 250, dates);
      isMock = true;
    }

    res.json({ success: true, data: rows, isMock });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

export const getShareholding = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const id = req.params.id;

  try {
    let rows = db
      .prepare('SELECT date, whale_ratio as ratio, NULL as count, total_shares as shares FROM tdcc_shareholding WHERE stock_id = ? ORDER BY date DESC LIMIT 250')
      .all(id);

    let isMock = false;
    if (rows.length < 10) {
      const dates = getTradingDays(250).reverse();
      rows = generateMockShareholding(id, 250, dates);
      isMock = true;
    }

    res.json({ success: true, data: rows, isMock });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

export const getQuote = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  const id = req.params.id;

  try {
    const meta = db.prepare('SELECT * FROM stock_meta WHERE stock_id = ?').get(id);
    if (!meta) return res.json({ success: false, error: 'Stock not found' });

    const latest = db.prepare('SELECT * FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 1').get(id);
    if (!latest) return res.json({ success: false, error: 'No price data' });

    const prev = db.prepare('SELECT * FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 1 OFFSET 1').get(id);
    const hist = db
      .prepare('SELECT date, open, high, low, close, volume FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 250')
      .all(id)
      .reverse();
    const indicators = calcIndicators(hist);
    const inst = db
      .prepare('SELECT date, foreign_net, trust_net FROM institutional_data WHERE stock_id = ? ORDER BY date DESC LIMIT 10')
      .all(id);
    const shareholding = db
      .prepare('SELECT date, whale_ratio, retail_ratio FROM tdcc_shareholding WHERE stock_id = ? ORDER BY date DESC LIMIT 1')
      .get(id);

    const change = prev ? parseFloat((latest.close - prev.close).toFixed(2)) : 0;
    const changePercent = prev && prev.close > 0 ? parseFloat(((change / prev.close) * 100).toFixed(2)) : 0;

    res.json({
      success: true,
      data: {
        stock_id: meta.stock_id,
        name: meta.stock_name,
        market: meta.market,
        industry: meta.industry_category,
        date: latest.date,
        open: latest.open,
        high: latest.high,
        low: latest.low,
        close: latest.close,
        volume: latest.volume,
        change,
        changePercent,
        prevClose: prev ? prev.close : null,
        indicators,
        institutional: inst,
        shareholding: shareholding || null,
      },
    });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

// ── Analysis endpoints (real implementation) ────────────────

import {
  getSRAnalysis as analyzeSR,
  getMAAnalysis as analyzeMA,
  getChipsAnalysis as analyzeChips,
  getPredictionAnalysis as analyzePrediction,
  getPatternAnalysis as analyzePattern,
} from '../services/technicalAnalysisService';

// Re-export the analysis functions as route handlers
const getSRAnalysis = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  try {
    res.json({ success: true, data: analyzeSR(db, req.params.id) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

const getMAAnalysis = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  try {
    res.json({ success: true, data: analyzeMA(db, req.params.id) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

const getChipsAnalysis = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  try {
    res.json({ success: true, data: analyzeChips(db, req.params.id) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

const getPredictionAnalysis = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  try {
    res.json({ success: true, data: analyzePrediction(db, req.params.id) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

const getPatternAnalysis = (req: Request, res: Response) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });
  try {
    res.json({ success: true, data: analyzePattern(db, req.params.id) });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
};

export {
  getSRAnalysis,
  getMAAnalysis,
  getChipsAnalysis,
  getPredictionAnalysis,
  getPatternAnalysis,
};
