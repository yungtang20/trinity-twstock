import { Client } from "pg";
async function test() {
  const connectionString = "postgres://postgres:sk_54797faf7a65eee079b243b424e39f5e0347de0307b4a4735a970265d1a76f82@db.fpodvtaiugvgyfundequ.supabase.co:5432/postgres";
  const client = new Client({ connectionString });
  try {
    await client.connect();
    const res = await client.query('SELECT NOW()');
    console.log("Connected to postgres! Time:", res.rows[0]);
    await client.query(`
      CREATE TABLE IF NOT EXISTS stock_price (
        stock_id TEXT,
        date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume BIGINT,
        amount BIGINT,
        trade_count BIGINT,
        spread REAL,
        PRIMARY KEY(stock_id, date)
      );
      CREATE TABLE IF NOT EXISTS stock_institutional (
        stock_id TEXT,
        date TEXT,
        foreign_net BIGINT DEFAULT 0,
        trust_net BIGINT DEFAULT 0,
        dealer_net BIGINT DEFAULT 0,
        foreign_buy BIGINT DEFAULT 0,
        foreign_sell BIGINT DEFAULT 0,
        trust_buy BIGINT DEFAULT 0,
        trust_sell BIGINT DEFAULT 0,
        dealer_buy BIGINT DEFAULT 0,
        dealer_sell BIGINT DEFAULT 0,
        total_net BIGINT DEFAULT 0,
        PRIMARY KEY(stock_id, date)
      );
      CREATE TABLE IF NOT EXISTS stock_meta (
        stock_id TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL,
        industry_category TEXT,
        market TEXT,
        type TEXT,
        source TEXT,
        updated_at TIMESTAMPTZ DEFAULT now()
      );
      CREATE TABLE IF NOT EXISTS stock_features (
        stock_id TEXT,
        date TEXT,
        ma5 REAL,
        ma20 REAL,
        ma60 REAL,
        rsi14 REAL,
        macd REAL,
        macd_signal REAL,
        macd_hist REAL,
        volume_ma5 BIGINT,
        volume_ma20 BIGINT,
        bb_upper REAL,
        bb_middle REAL,
        bb_lower REAL,
        updated_at TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY(stock_id, date)
      );
      CREATE TABLE IF NOT EXISTS tdcc_shareholding (
        stock_id TEXT,
        date TEXT,
        total_shares BIGINT,
        whale_ratio REAL,
        retail_ratio REAL,
        source TEXT,
        updated_at TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY(stock_id, date)
      );
    `);
    console.log("Tables ensured.");
    await client.end();
  } catch (e) {
    console.error("Failed to connect:", e.message);
  }
}
test();
