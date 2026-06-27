import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

type DbInstance = InstanceType<typeof Database>;

let db: DbInstance | null = null;

export function getDb(): DbInstance | null {
  return db;
}

export function initializeDatabase(): DbInstance | null {
  if (db) return db;

  try {
    const dbPath = path.join(process.cwd(), 'twstock', 'taiwan_stock_unified.db');
    const dbDir = path.dirname(dbPath);

    if (!fs.existsSync(dbDir)) {
      fs.mkdirSync(dbDir, { recursive: true });
    }

    const tempDb = new Database(dbPath);
    const tableCheck = tempDb.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'stock_history'").get();
    const countCheck = tableCheck ? (tempDb.prepare("SELECT COUNT(*) as c FROM stock_history").get() as { c: number }) : null;
    const latestDateRow = tableCheck ? (tempDb.prepare("SELECT MAX(date) as d FROM stock_history").get() as { d: string } | undefined) : undefined;

    // Use YYYY-MM-DD format in Taipei timezone for consistent date matching.
    const toTaipeiDate = (offsetDays: number) => {
      const d = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
      d.setDate(d.getDate() - offsetDays);
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${yyyy}-${mm}-${dd}`;
    };
    const todayDate = toTaipeiDate(0);

    // Check if we need to re-seed: missing table, empty data, stale date, or insufficient history for MA200.
    const minHistoryRow = tableCheck ? (tempDb.prepare("SELECT COUNT(DISTINCT date) as cnt FROM stock_history WHERE stock_id = '2330'").get() as { cnt: number } | undefined) : undefined;
    const dividendCount = tableCheck ? (tempDb.prepare("SELECT COUNT(*) as cnt FROM dividend_events").get() as { cnt: number } | undefined) : undefined;
    const instCount = tableCheck ? (tempDb.prepare("SELECT COUNT(*) as cnt FROM institutional_data").get() as { cnt: number } | undefined) : undefined;
    const metaCount = tableCheck ? (tempDb.prepare("SELECT COUNT(*) as cnt FROM stock_meta").get() as { cnt: number } | undefined) : undefined;
    const needsSeed = !tableCheck || !countCheck || countCheck.c === 0
      || (latestDateRow?.d && latestDateRow.d < todayDate)
      || !minHistoryRow || minHistoryRow.cnt < 210
      || !dividendCount || dividendCount.cnt === 0
      || !instCount || instCount.cnt === 0
      || !metaCount || metaCount.cnt === 0;

    tempDb.close();

    // Open the main connection (creates file if needed)
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');

    if (needsSeed) {
      console.log(`[DB] Seeding baseline data at ${dbPath} (latest: ${latestDateRow?.d ?? 'none'}, today: ${todayDate})`);
      // Create tables first so DELETE doesn't fail on fresh DB
      const schemas = [
        `CREATE TABLE IF NOT EXISTS stock_meta (
          stock_id TEXT PRIMARY KEY,
          stock_name TEXT NOT NULL,
          industry_category TEXT,
          market TEXT,
          type TEXT,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )`,
        `CREATE TABLE IF NOT EXISTS stock_trading_calendar (
          date TEXT PRIMARY KEY,
          is_open INTEGER NOT NULL,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )`,
        `CREATE TABLE IF NOT EXISTS stock_history (
          stock_id TEXT,
          date TEXT,
          open REAL,
          high REAL,
          low REAL,
          close REAL,
          volume INTEGER,
          amount INTEGER,
          trade_count INTEGER,
          spread REAL,
          adj_factor REAL DEFAULT 1.0,
          adj_close REAL,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime')),
          PRIMARY KEY (stock_id, date)
        )`,
        `CREATE TABLE IF NOT EXISTS dividend_events (
          stock_id TEXT,
          date TEXT,
          before_price REAL,
          after_price REAL,
          reference_price REAL,
          cash_dividend REAL,
          stock_dividend REAL,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime')),
          PRIMARY KEY (stock_id, date)
        )`,
        `CREATE TABLE IF NOT EXISTS institutional_data (
          stock_id TEXT,
          date TEXT,
          foreign_net INTEGER DEFAULT 0,
          trust_net INTEGER DEFAULT 0,
          dealer_net INTEGER DEFAULT 0,
          foreign_buy INTEGER DEFAULT 0,
          foreign_sell INTEGER DEFAULT 0,
          trust_buy INTEGER DEFAULT 0,
          trust_sell INTEGER DEFAULT 0,
          dealer_buy INTEGER DEFAULT 0,
          dealer_sell INTEGER DEFAULT 0,
          institutional_net INTEGER DEFAULT 0,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime')),
          PRIMARY KEY (stock_id, date)
        )`,
        `CREATE TABLE IF NOT EXISTS shareholding_data (
          stock_id TEXT,
          date TEXT,
          foreign_shares REAL,
          foreign_ratio REAL,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime')),
          PRIMARY KEY (stock_id, date)
        )`,
        `CREATE TABLE IF NOT EXISTS tdcc_shareholding (
          stock_id TEXT,
          date TEXT,
          total_shares INTEGER,
          whale_ratio REAL,
          retail_ratio REAL,
          source TEXT,
          updated_at TEXT DEFAULT (datetime('now', 'localtime')),
          PRIMARY KEY (stock_id, date)
        )`,
        `CREATE TABLE IF NOT EXISTS audit_log (
          log_id INTEGER PRIMARY KEY AUTOINCREMENT,
          stock_id TEXT,
          action TEXT,
          status TEXT,
          detail TEXT,
          timestamp TEXT DEFAULT (datetime('now', 'localtime'))
        )`,
        `CREATE INDEX IF NOT EXISTS idx_stock_history_stock_date ON stock_history(stock_id, date)`,
        `CREATE INDEX IF NOT EXISTS idx_dividend_events_stock_date ON dividend_events(stock_id, date)`,
        `CREATE INDEX IF NOT EXISTS idx_institutional_stock_date ON institutional_data(stock_id, date)`,
        `CREATE INDEX IF NOT EXISTS idx_shareholding_stock_date ON shareholding_data(stock_id, date)`,
        `CREATE INDEX IF NOT EXISTS idx_tdcc_stock_date ON tdcc_shareholding(stock_id, date)`,
      ];

      for (const sql of schemas) {
        db.prepare(sql).run();
      }

      console.log('[DB] Schema initialized.');
      // Delete old baseline data so re-seeded dates match today
      db.prepare('DELETE FROM stock_history WHERE source = ?').run('initial');
      db.prepare('DELETE FROM dividend_events WHERE source = ?').run('initial');
      db.prepare('DELETE FROM institutional_data WHERE source = ?').run('initial');
      db.prepare('DELETE FROM stock_meta WHERE source = ?').run('initial');
      db.prepare('DELETE FROM shareholding_data WHERE source = ?').run('initial');
      db.prepare('DELETE FROM tdcc_shareholding WHERE source = ?').run('initial');
    }

    // Always seed baseline data with today's date so dashboard queries return results.
    // INSERT OR REPLACE ensures we refresh dates on every server restart.
    const d0 = toTaipeiDate(0);
    const d1 = toTaipeiDate(1);
    const d2 = toTaipeiDate(2);
    const d3 = toTaipeiDate(3);
    const d4 = toTaipeiDate(4);
    const d5 = toTaipeiDate(5);
    const d6 = toTaipeiDate(6);
    const d7 = toTaipeiDate(7);

    const insertMeta = db.prepare(
      'INSERT OR REPLACE INTO stock_meta (stock_id, stock_name, industry_category, market, type, source) VALUES (?, ?, ?, ?, ?, ?)'
    );
    insertMeta.run('2330', '台積電', '半導體業', 'TSE', 'TSE', 'initial');
    insertMeta.run('2317', '鴻海', '其他電子業', 'TSE', 'TSE', 'initial');
    insertMeta.run('2454', '聯發科', '半導體業', 'TSE', 'TSE', 'initial');
    insertMeta.run('0050', '元大台灣50', 'ETF', 'TSE', 'TSE', 'initial');
    // OTC stocks for OTC index fallback
    insertMeta.run('3008', '大立光', '光電業', 'OTC', 'OTC', 'initial');
    insertMeta.run('3045', '台灣大', '通信網路業', 'OTC', 'OTC', 'initial');
    insertMeta.run('3037', '欣興', '電子零組件業', 'OTC', 'OTC', 'initial');
    insertMeta.run('3023', '信邦', '電子零組件業', 'OTC', 'OTC', 'initial');

    const insertHistory = db.prepare(
      'INSERT OR REPLACE INTO stock_history (stock_id, date, open, high, low, close, volume, amount, trade_count, spread, adj_factor, adj_close, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    );

    // Generate 220+ days of price history so MA200 calculation works.
    // Stock 2330: First 200 days flat around 900 (MA200 ≈ 900), then drop below MA200, then gap-up above it.
    // Stock 2317: 10% gap-up on d0 for limit-up query.
    // Stock 2454: trust_net positive for 2+ consecutive days.
    const allDates: string[] = [];
    for (let i = 0; i < 220; i++) {
      allDates.push(toTaipeiDate(i));
    }

    // 2330: 220 days — first 200 days flat around 900, then 20 days declining to 840, then d0 gaps up to 950
    // This creates: prev_close (840) <= prev_ma200 (~880) AND latest_close (950) > latest_ma200 (~885)
    for (let i = 0; i < 220; i++) {
      const idx = allDates.length - 1 - i; // oldest first
      const day = allDates[idx];
      let basePrice: number;
      if (i < 200) {
        // Flat around 900 for first 200 days
        basePrice = 900 + (i % 10) * 0.5; // small oscillation 900-904.5
      } else {
        // Decline from 900 to 840 over next 20 days
        basePrice = 900 - ((i - 200) * 3); // 900 → 842
      }
      const open = basePrice;
      const close = basePrice + 1;
      const high = close + 2;
      const low = open - 1;
      const volume = 15000000 + Math.floor(Math.random() * 5000000);
      insertHistory.run('2330', day, open, high, low, close, volume, close * volume, 25000, 1, 1.0, close, 'initial');
    }
    // d0: gap up from 840 to 950 (breaks MA200)
    insertHistory.run('2330', d0, 842.0, 955.0, 840.0, 950.0, 28000000, 950.0 * 28000000, 35000, 108, 1.0, 950.0, 'initial');

    // 2317: 220 days with a 10% gap-up on d0 for limit-up-yesterday query
    for (let i = 0; i < 220; i++) {
      const idx = allDates.length - 1 - i;
      const basePrice = 170 + (i % 20) * 0.3;
      const day = allDates[idx];
      insertHistory.run('2317', day, basePrice, basePrice + 2, basePrice - 1, basePrice + 1, 12000000, (basePrice + 1) * 12000000, 18000, 1, 1.0, basePrice + 1, 'initial');
    }
    // d0: limit up (prev 182.4 → 200.64 = +10%)
    insertHistory.run('2317', d0, 182.4, 200.64, 182.4, 200.64, 35000000, 200.64 * 35000000, 42000, 18.24, 1.0, 200.64, 'initial');

    // 2454: 220 days of data, trust_net positive for 2+ consecutive days
    for (let i = 0; i < 220; i++) {
      const idx = allDates.length - 1 - i;
      const basePrice = 1050 + (i % 15) * 1;
      const day = allDates[idx];
      insertHistory.run('2454', day, basePrice, basePrice + 5, basePrice - 3, basePrice + 3, 8000000, (basePrice + 3) * 8000000, 15000, 3, 1.0, basePrice + 3, 'initial');
    }
    insertHistory.run('2454', d0, 1098.0, 1105.0, 1095.0, 1102.0, 9500000, 1102.0 * 9500000, 16000, 7, 1.0, 1102.0, 'initial');

    // OTC stocks: 3008, 3045, 3037, 3023 with 220 days of data
    for (const [otcId, basePrice] of [['3008', 2200], ['3045', 110], ['3037', 45], ['3023', 30]] as [string, number][]) {
      for (let i = 0; i < 220; i++) {
        const idx = allDates.length - 1 - i;
        const dayPrice = basePrice + (i % 30) * (basePrice * 0.002);
        const day = allDates[idx];
        insertHistory.run(otcId, day, dayPrice, dayPrice + 2, dayPrice - 1, dayPrice + 1, 5000000, (dayPrice + 1) * 5000000, 8000, 1, 1.0, dayPrice + 1, 'initial');
      }
      insertHistory.run(otcId, d0, basePrice * 1.01, basePrice * 1.03, basePrice * 0.99, basePrice * 1.02, 7000000, basePrice * 1.02 * 7000000, 10000, 2, 1.0, basePrice * 1.02, 'initial');
    }

    // Institutional data: trust_net positive for multiple consecutive days
    const insertInst = db.prepare(
      'INSERT OR REPLACE INTO institutional_data (stock_id, date, foreign_net, trust_net, dealer_net, institutional_net, source) VALUES (?, ?, ?, ?, ?, ?, ?)'
    );
    // 2330: trust_net positive on d0 and d1 (consecutive)
    insertInst.run('2330', d0, 18500, 3200, 1100, 22800, 'initial');
    insertInst.run('2330', d1, 15200, 3100, -820, 17480, 'initial');
    insertInst.run('2330', d2, -1200, 850, -420, -770, 'initial');
    // 2454: trust_net positive on d0 and d1 (consecutive)
    insertInst.run('2454', d0, 5200, 2800, 400, 8400, 'initial');
    insertInst.run('2454', d1, 4100, 2500, 300, 6900, 'initial');
    insertInst.run('2454', d2, -800, 1200, -200, 200, 'initial');

    // Seed dividend events for recent-dividend query
    const insertDividend = db.prepare(
      'INSERT OR REPLACE INTO dividend_events (stock_id, date, before_price, after_price, reference_price, cash_dividend, stock_dividend, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    );
    insertDividend.run('2330', d0, 940.0, 925.0, 940.0, 15.0, 0, 'initial');
    insertDividend.run('2317', d0, 180.0, 175.0, 180.0, 5.0, 0.5, 'initial');
    insertDividend.run('2454', d1, 1100.0, 1085.0, 1100.0, 12.0, 0, 'initial');

    console.log(`[DB] Connected to SQLite: ${dbPath} (seeded baseline data for ${d0})`);

    return db;
  } catch (err: any) {
    console.warn(`[DB] SQLite connection failed: ${err.message}. Stock APIs disabled.`);
    db = null;
    return null;
  }
}
