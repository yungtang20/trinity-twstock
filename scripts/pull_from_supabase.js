import { createClient } from "@supabase/supabase-js";
import Database from "better-sqlite3";
import path from "path";

const url = process.env.VITE_SUPABASE_URL;
const key = process.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.error("❌ Need VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to pull from Supabase!");
  process.exit(1);
}

const supabase = createClient(url, key);
const dbPath = path.join(process.cwd(), "twstock", "taiwan_stock_unified.db");

console.log("📍 SQLite DB Path:", dbPath);
const db = new Database(dbPath);

// Fast download filter: 2026-06-01 to present (~110 trading days, very light & fast, finishes in ~10 seconds)
const CUTOFF_DATE = "2026-06-01";

async function run() {
  console.log(`⏳ Beginning lightning-fast Supabase -> SQLite restoration (>= ${CUTOFF_DATE})...`);

  // 1. Sync stock_meta
  console.log("\n🔄 Pulling stock_meta...");
  db.prepare("DELETE FROM stock_meta").run();
  
  let rangeStart = 0;
  const batchSize = 1000;
  let hasMore = true;
  let totalMeta = 0;
  
  const insertMeta = db.prepare(`
    INSERT INTO stock_meta (stock_id, stock_name, market, industry_category, type, source, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  while (hasMore) {
    const { data: metas, error } = await supabase
      .from("stock_meta")
      .select("*")
      .range(rangeStart, rangeStart + batchSize - 1);
      
    if (error) {
      console.error("❌ Failed to query stock_meta:", error.message);
      break;
    }
    
    if (!metas || metas.length === 0) {
      hasMore = false;
      break;
    }
    
    db.transaction(() => {
      for (const m of metas) {
        insertMeta.run(
          m.stock_id,
          m.stock_name,
          m.market || "TSE",
          m.industry_category || null,
          m.type || null,
          m.source || null,
          m.updated_at || null
        );
      }
    })();
    
    totalMeta += metas.length;
    if (metas.length < batchSize) {
      hasMore = false;
    } else {
      rangeStart += batchSize;
    }
  }
  console.log(`✅ stock_meta restored! Total: ${totalMeta} stocks`);

  // Helper for parallel chunks fetching
  async function fetchAndInsertTable(supabaseTable, sqliteTable, insertStmt, transformer) {
    console.log(`\n🔄 Restoring ${sqliteTable} from Supabase ${supabaseTable}...`);
    db.prepare(`DELETE FROM ${sqliteTable}`).run();
    
    // Use exact count where possible, but if it fails fallback to a large number
    let count = 0;
    const { count: exactCount, error: countErr } = await supabase
      .from(supabaseTable)
      .select("*", { count: "exact", head: true })
      .gte("date", CUTOFF_DATE);
      
    if (countErr) {
      console.error(`⚠️ Can't get total rows for ${supabaseTable}, fallback to scanning:`, countErr.message);
      // Hardcode a large enough number for recent days
      count = 300000;
    } else {
      count = exactCount;
    }
    
    console.log(`  Total rows since ${CUTOFF_DATE} in ${supabaseTable}: ${count}. Restoring using parallel batches...`);
    
    const pageSize = 1000;
    const totalPages = Math.ceil(count / pageSize);
    let completedRows = 0;
    
    // Process pages in parallel concurrent chunks (15 at a time)
    const concurrency = 15;
    for (let i = 0; i < totalPages; i += concurrency) {
      const pageBatch = [];
      const endPage = Math.min(i + concurrency, totalPages);
      
      for (let p = i; p < endPage; p++) {
        const rStart = p * pageSize;
        const rEnd = rStart + pageSize - 1;
        
        pageBatch.push(
          supabase
            .from(supabaseTable)
            .select("*")
            .gte("date", CUTOFF_DATE)
            .order("date", { ascending: false })
            .range(rStart, rEnd)
            .then(({ data, error }) => {
              if (error) {
                console.error(`❌ Page ${p} query failed:`, error.message);
                return null;
              }
              return data;
            })
        );
      }
      
      const results = await Promise.all(pageBatch);
      
      db.transaction(() => {
        for (const data of results) {
          if (!data) continue;
          for (const item of data) {
            try {
              transformer(insertStmt, item);
              completedRows++;
            } catch (err) {
              // Ignore constraints
            }
          }
        }
      })();
      
      console.log(`  Progress: ${completedRows} / ${count} rows`);
    }
    console.log(`✅ ${sqliteTable} restored successfully! Total: ${completedRows} rows`);
  }

  // 2. Sync stock_price -> stock_history
  const insertPrice = db.prepare(`
    INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount, trade_count, spread, adj_factor, adj_close, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  await fetchAndInsertTable(
    "stock_price",
    "stock_history",
    insertPrice,
    (stmt, p) => {
      stmt.run(
        p.stock_id,
        p.date,
        p.open !== undefined ? p.open : null,
        p.high !== undefined ? p.high : null,
        p.low !== undefined ? p.low : null,
        p.close !== undefined ? p.close : null,
        p.volume !== undefined ? p.volume : null,
        p.amount !== undefined ? p.amount : null,
        p.trade_count !== undefined ? p.trade_count : null,
        p.spread !== undefined ? p.spread : null,
        p.adj_factor !== undefined ? p.adj_factor : 1.0,
        p.adj_close !== undefined ? p.adj_close : p.close,
        p.source || "supabase"
      );
    }
  );

  // 3. Sync stock_institutional -> institutional_data
  const insertInst = db.prepare(`
    INSERT INTO institutional_data (stock_id, date, foreign_net, trust_net, dealer_net, foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell, institutional_net, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  await fetchAndInsertTable(
    "stock_institutional",
    "institutional_data",
    insertInst,
    (stmt, i) => {
      stmt.run(
        i.stock_id,
        i.date,
        i.foreign_net || 0,
        i.trust_net || 0,
        i.dealer_net || 0,
        i.foreign_buy || 0,
        i.foreign_sell || 0,
        i.trust_buy || 0,
        i.trust_sell || 0,
        i.dealer_buy || 0,
        i.dealer_sell || 0,
        (i.foreign_net || 0) + (i.trust_net || 0) + (i.dealer_net || 0),
        i.source || "supabase"
      );
    }
  );

  // 4. Sync stock_features -> tdcc_shareholding
  const insertFeat = db.prepare(`
    INSERT INTO tdcc_shareholding (stock_id, date, total_shares, whale_ratio, retail_ratio, source)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  await fetchAndInsertTable(
    "stock_features",
    "tdcc_shareholding",
    insertFeat,
    (stmt, f) => {
      stmt.run(
        f.stock_id,
        f.date,
        f.total_shares || 0,
        f.whale_ratio || 0.0,
        f.retail_ratio || 0.0,
        f.source || "supabase"
      );
    }
  );

  // 5. Build Calendar from unique trade dates
  console.log("\n📅 Generating stock_trading_calendar from history...");
  const dates = db.prepare("SELECT DISTINCT date FROM stock_history ORDER BY date ASC").all();
  db.prepare("DELETE FROM stock_trading_calendar").run();
  const insertCal = db.prepare(`
    INSERT INTO stock_trading_calendar (date, is_open, source)
    VALUES (?, 1, 'supabase')
  `);
  db.transaction(() => {
    for (const d of dates) {
      insertCal.run(d.date);
    }
  })();
  console.log(`✅ Loaded ${dates.length} unique trading days into calendar!`);

  console.log("\n🎉 ALL DONE! Local SQLite database fully reconstructed.");
}

run().catch((err) => {
  console.error("Critical error:", err);
});
