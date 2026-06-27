import { Router } from 'express';
import { getTwseStats, getOtcStats } from '../services/marketDataService';
import { getDb } from '../db';

const router = Router();

router.get('/twse-stats', async (_req, res) => {
  const data = await getTwseStats();
  res.json(data);
});

router.get('/otc-stats', async (_req, res) => {
  const data = await getOtcStats();
  res.json(data);
});

router.get('/health', (_req, res) => {
  res.json({
    success: true,
    sqlite: !!getDb(),
    time: new Date().toISOString(),
  });
});

// ── Movers (Top gainers/losers) ────────────────────────────

router.get('/movers', (_req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });

  try {
    // Get latest 2 dates
    const datesRow = db
      .prepare('SELECT DISTINCT date FROM stock_history ORDER BY date DESC LIMIT 2')
      .all() as { date: string }[];

    if (datesRow.length < 2) {
      return res.json({ success: true, date: '', gainers: [], losers: [] });
    }

    const latestDate = datesRow[0].date;
    const prevDate = datesRow[1].date;

    // Join today's close with yesterday's close to compute change percent
    const movers = db
      .prepare(`
        SELECT
          curr.stock_id,
          COALESCE(m.stock_name, curr.stock_id) AS stock_name,
          curr.close,
          curr.volume,
          prev.close AS prev_close,
          ROUND((curr.close - prev.close) / prev.close * 100, 2) AS change_pct
        FROM stock_history curr
        JOIN stock_history prev ON curr.stock_id = prev.stock_id AND prev.date = ?
        LEFT JOIN stock_meta m ON curr.stock_id = m.stock_id
        WHERE curr.date = ? AND prev.close > 0
        ORDER BY change_pct DESC
      `)
      .all(prevDate, latestDate) as {
        stock_id: string;
        stock_name: string;
        close: number;
        volume: number;
        prev_close: number;
        change_pct: number;
      }[];

    const gainers = movers
      .filter((m) => m.change_pct > 0)
      .slice(0, 10)
      .map((m) => ({
        stock_id: m.stock_id,
        stock_name: m.stock_name,
        close: m.close,
        change: parseFloat((m.close - m.prev_close).toFixed(2)),
        changePercent: m.change_pct,
      }));

    const losers = movers
      .filter((m) => m.change_pct < 0)
      .sort((a, b) => a.change_pct - b.change_pct)
      .slice(0, 10)
      .map((m) => ({
        stock_id: m.stock_id,
        stock_name: m.stock_name,
        close: m.close,
        change: parseFloat((m.close - m.prev_close).toFixed(2)),
        changePercent: m.change_pct,
      }));

    res.json({
      success: true,
      date: latestDate,
      gainers,
      losers,
    });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

export default router;
