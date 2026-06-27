import { Router } from 'express';
import { getDb } from '../db';

const router = Router();

// ── Recent Dividend ────────────────────────────────────────

router.get('/recent-dividend', async (_req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });

  try {
    // Use Taipei timezone for consistent date matching with seeded data
    const taipeiNow = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
    const yyyy = taipeiNow.getFullYear();
    const mm = String(taipeiNow.getMonth() + 1).padStart(2, '0');
    const dd = String(taipeiNow.getDate()).padStart(2, '0');
    const todayStr = `${yyyy}-${mm}-${dd}`;

    // Check for any dividend events in current year (dynamic, not hardcoded)
    const yearPrefix = `${yyyy}-`;
    const row = db.prepare("SELECT COUNT(*) as count FROM dividend_events WHERE date LIKE ?").get(`${yearPrefix}%`) as { count: number };
    if (row.count === 0) {
      return res.json({ success: true, data: [] });
    }

    // Query events from today forward (next 7 days)
    // Use LEFT JOIN to avoid losing events if stock_meta is missing
    const events = db
      .prepare(
        `
        SELECT d.stock_id, COALESCE(m.stock_name, d.stock_id) as stock_name, d.date, d.cash_dividend, d.stock_dividend
        FROM dividend_events d
        LEFT JOIN stock_meta m ON d.stock_id = m.stock_id
        WHERE d.date >= ?
        ORDER BY d.date ASC
        LIMIT 10
      `
      )
      .all(todayStr) as any[];

    res.json({ success: true, data: events });
  } catch (err: any) {
    res.json({ success: false, error: err.message, data: [] });
  }
});

// ── Trust Buy 2 Day ────────────────────────────────────────

router.get('/trust-buy-2day', (_req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });

  try {
    const datesRow = db
      .prepare(
        `
        SELECT DISTINCT date FROM stock_history
        ORDER BY date DESC LIMIT 10
      `
      )
      .all() as { date: string }[];

    if (datesRow.length < 2) {
      return res.json({ success: true, data: [] });
    }

    const trustBuyStocks = db
      .prepare(
        `
        SELECT i.stock_id, COALESCE(m.stock_name, i.stock_id) as stock_name,
               h.close, h.volume, h_prev.close as prev_close, h_prev.volume as prev_volume,
               i.trust_net as latest_trust_net
        FROM institutional_data i
        JOIN institutional_data i_prev ON i.stock_id = i_prev.stock_id AND i_prev.date = ?
        LEFT JOIN stock_meta m ON i.stock_id = m.stock_id
        LEFT JOIN stock_history h ON i.stock_id = h.stock_id AND h.date = i.date
        LEFT JOIN stock_history h_prev ON i.stock_id = h_prev.stock_id AND h_prev.date = i_prev.date
        WHERE i.date = ? AND i.trust_net > 0 AND i_prev.trust_net > 0
        ORDER BY i.trust_net DESC
        LIMIT 50
      `
      )
      .all(datesRow[1].date, datesRow[0].date);

    const formatted = trustBuyStocks.map((s: any) => {
      const close = s.close || 0;
      const prev_close = s.prev_close || close;
      const change_pct = prev_close > 0 ? parseFloat(((close - prev_close) / prev_close * 100).toFixed(2)) : 0;
      const volume = s.volume || 0;
      const prev_volume = s.prev_volume || volume;
      const volume_change_pct = prev_volume > 0 ? parseFloat(((volume - prev_volume) / prev_volume * 100).toFixed(2)) : 0;

      return {
        stock_id: s.stock_id,
        stock_name: s.stock_name,
        volume: Math.floor(volume / 1000),
        amount: parseFloat(((s.close * s.volume) / 1e8).toFixed(2)),
        trust_days: 2,
        close,
        prev_close,
        change_pct,
        volume_change_pct,
      };
    });

    res.json({ success: true, data: formatted });
  } catch (err: any) {
    res.json({ success: false, error: err.message, data: [] });
  }
});

// ── Break MA200 ─────────────────────────────────────────────

router.get('/break-ma200', (_req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });

  try {
    const datesRow = db
      .prepare(
        `
        SELECT DISTINCT date FROM stock_history
        ORDER BY date DESC LIMIT 2
      `
      )
      .all() as { date: string }[];

    if (datesRow.length < 2) {
      return res.json({ success: true, data: [] });
    }

    const candidates = db
      .prepare(
        `
        SELECT h.stock_id, m.stock_name, h.close, h.volume, h_prev.close as prev_close
        FROM stock_history h
        JOIN stock_meta m ON h.stock_id = m.stock_id
        LEFT JOIN stock_history h_prev ON h.stock_id = h_prev.stock_id AND h_prev.date = ?
        WHERE h.date = ? AND h.volume >= 500000
        ORDER BY h.volume DESC
        LIMIT 150
      `
      )
      .all(datesRow[1].date, datesRow[0].date);

    const results: any[] = [];
    const getHistoryStmt = db.prepare('SELECT close FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 202');

    for (const c of candidates) {
      const history = getHistoryStmt.all(c.stock_id) as { close: number }[];
      if (history.length < 21) continue;

      const maPeriod = history.length >= 201 ? 200 : history.length >= 61 ? 60 : 20;
      if (history.length < maPeriod + 1) continue;

      const latest_close = history[0].close;
      const prev_close = history[1].close;
      const latest_ma = history.slice(0, maPeriod).reduce((sum, r) => sum + r.close, 0) / maPeriod;
      const prev_ma = history.slice(1, maPeriod + 1).reduce((sum, r) => sum + r.close, 0) / maPeriod;

      if (prev_close <= prev_ma && latest_close > latest_ma) {
        const change_pct = prev_close > 0 ? parseFloat(((latest_close - prev_close) / prev_close * 100).toFixed(2)) : 0;
        results.push({
          stock_id: c.stock_id,
          stock_name: c.stock_name,
          prev_close,
          latest_close,
          prev_ma200: parseFloat(prev_ma.toFixed(2)),
          latest_ma200: parseFloat(latest_ma.toFixed(2)),
          volume: Math.floor((c.volume || 0) / 1000),
          close: c.close,
          change_pct,
          volume_change_pct: 0,
        });
      }
    }

    res.json({ success: true, data: results.slice(0, 50) });
  } catch (err: any) {
    res.json({ success: false, error: err.message, data: [] });
  }
});

// ── Limit Up Yesterday ─────────────────────────────────────

router.get('/limit-up-yesterday', (_req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });

  try {
    const datesRow = db
      .prepare(
        `
        SELECT DISTINCT date FROM stock_history
        ORDER BY date DESC LIMIT 2
      `
      )
      .all() as { date: string }[];

    if (datesRow.length < 2) {
      return res.json({ success: true, data: [] });
    }

    const limitUpStocks = db
      .prepare(
        `
        SELECT h.stock_id, m.stock_name, h.close, h.volume, h_prev.close as prev_close
        FROM stock_history h
        JOIN stock_meta m ON h.stock_id = m.stock_id
        LEFT JOIN stock_history h_prev ON h.stock_id = h_prev.stock_id AND h_prev.date = ?
        WHERE h.date = ? AND h.stock_id GLOB '[1-9][0-9][0-9][0-9]'
          AND h_prev.close > 0
          AND (h.close - h_prev.close) / h_prev.close >= 0.085
        ORDER BY (h.close - h_prev.close) / h_prev.close DESC
        LIMIT 50
      `
      )
      .all(datesRow[1].date, datesRow[0].date);

    const formatted = limitUpStocks.map((s: any) => {
      const close = s.close || 0;
      const prev_close = s.prev_close || close;
      const change_pct = prev_close > 0 ? parseFloat(((close - prev_close) / prev_close * 100).toFixed(2)) : 0;
      const volume = s.volume || 0;
      const prev_volume = s.prev_volume || volume;
      const volume_change_pct = prev_volume > 0 ? parseFloat(((volume - prev_volume) / prev_volume * 100).toFixed(2)) : 0;

      return {
        stock_id: s.stock_id,
        stock_name: s.stock_name,
        close,
        prev_close,
        change_pct,
        volume: Math.floor(volume / 1000),
        vol_explosion_pct: 0,
        volume_change_pct,
      };
    });

    res.json({ success: true, data: formatted });
  } catch (err: any) {
    res.json({ success: false, error: err.message, data: [] });
  }
});

export default router;
