import express, { Router } from 'express';
import { initializeDatabase, getDb } from './server/db';

const router = Router();

// Inline the movers handler for testing
router.get('/movers', (_req, res) => {
  const db = getDb();
  if (!db) return res.json({ success: false, error: 'DB not connected' });

  try {
    const datesRow = db
      .prepare('SELECT DISTINCT date FROM stock_history ORDER BY date DESC LIMIT 2')
      .all() as { date: string }[];

    if (datesRow.length < 2) {
      return res.json({ success: true, date: '', gainers: [], losers: [] });
    }

    const latestDate = datesRow[0].date;
    const prevDate = datesRow[1].date;

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
      .all(prevDate, latestDate) as any[];

    const gainers = movers
      .filter((m: any) => m.change_pct > 0)
      .slice(0, 10)
      .map((m: any) => ({
        stock_id: m.stock_id,
        stock_name: m.stock_name,
        close: m.close,
        change: parseFloat((m.close - m.prev_close).toFixed(2)),
        changePercent: m.change_pct,
      }));

    const losers = movers
      .filter((m: any) => m.change_pct < 0)
      .sort((a: any, b: any) => a.change_pct - b.change_pct)
      .slice(0, 10)
      .map((m: any) => ({
        stock_id: m.stock_id,
        stock_name: m.stock_name,
        close: m.close,
        change: parseFloat((m.close - m.prev_close).toFixed(2)),
        changePercent: m.change_pct,
      }));

    res.json({ success: true, date: latestDate, gainers, losers });
  } catch (err: any) {
    res.json({ success: false, error: err.message });
  }
});

initializeDatabase();
const app = express();
app.use('/api', router);
const server = app.listen(3999, async () => {
  const res = await fetch('http://localhost:3999/api/movers');
  const data = await res.json();
  console.log('success:', data.success);
  console.log('date:', data.date);
  console.log('gainers count:', data.gainers?.length);
  console.log('losers count:', data.losers?.length);
  if (data.gainers?.length > 0) console.log('top gainer:', JSON.stringify(data.gainers[0]));
  if (data.losers?.length > 0) console.log('top loser:', JSON.stringify(data.losers[0]));
  server.close();
  process.exit(0);
});
