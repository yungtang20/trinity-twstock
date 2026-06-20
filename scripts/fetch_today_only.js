import { createClient } from "@supabase/supabase-js";
import Database from "better-sqlite3";
import path from "path";

const url = process.env.VITE_SUPABASE_URL;
const key = process.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.error("❌ Need VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY!");
  process.exit(1);
}

const supabase = createClient(url, key);
const dbPath = path.join(process.cwd(), "twstock", "taiwan_stock_unified.db");
const db = new Database(dbPath);

// Dynamic today's date in Taipei time
const taipeiNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" }));
const yyyy = taipeiNow.getFullYear();
const mm = String(taipeiNow.getMonth() + 1).padStart(2, '0');
const dd = String(taipeiNow.getDate()).padStart(2, '0');
const TODAY_DATE = `${yyyy}-${mm}-${dd}`;
const TODAY_ROC_DATE = `${yyyy - 1911}/${mm}/${dd}`;

function cleanFloat(v) {
  if (v === undefined || v === null) return null;
  const str = String(v).replace(/,/g, "").trim();
  if (str === "" || str === "--" || str === "---") return null;
  const val = parseFloat(str);
  return isNaN(val) ? null : val;
}

function cleanInt(v) {
  if (v === undefined || v === null) return null;
  const str = String(v).replace(/,/g, "").trim();
  if (str === "" || str === "--" || str === "---") return null;
  const val = parseInt(str, 10);
  return isNaN(val) ? null : val;
}

async function run() {
  console.log(`\n🕸️ Live-Crawling stock prices and volumes for TODAY: ${TODAY_DATE}...`);
  
  const todayPrices = [];
  const todayInsts = {};

  // 1. TWSE Quotes
  try {
    const twseUrl = `https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date=${yyyy}${mm}${dd}&type=ALL`;
    const res = await fetch(twseUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = await res.json();
    if (json.stat === "OK" && json.tables && json.tables[8]) {
      const dataRows = json.tables[8].data;
      console.log(`  TWSE online response is OK! Parsed ${dataRows.length} rows.`);
      for (const r of dataRows) {
        const id = String(r[0]).trim();
        if (id.length !== 4 || isNaN(Number(id))) continue;
        
        const close = cleanFloat(r[8]);
        if (!close || close <= 0) continue;
        
        const open = cleanFloat(r[5]) || close;
        const high = cleanFloat(r[6]) || close;
        const low = cleanFloat(r[7]) || close;
        const vol = cleanInt(r[2]) || 0;
        const amount = cleanInt(r[4]) || 0;
        const trades = cleanInt(r[3]) || 0;
        
        const polarity = String(r[9]).includes("red") ? 1 : String(r[9]).includes("green") ? -1 : 0;
        const spreadAmt = cleanFloat(r[10]) || 0;
        const spread = parseFloat((polarity * spreadAmt).toFixed(4));

        todayPrices.push({
          stock_id: id,
          date: TODAY_DATE,
          open, high, low, close,
          volume: vol,
          amount,
          trade_count: trades,
          spread,
          adj_factor: 1.0,
          adj_close: close,
          source: "TWSE_Crawler"
        });
      }
    }
  } catch (twseErr) {
    console.error("  ❌ TWSE error:", twseErr.message);
  }

  // 2. TPEx Quotes
  try {
    const tpexUrl = `https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&d=${TODAY_ROC_DATE}&se=AL&s=0,asc,0`;
    const res = await fetch(tpexUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = await res.json();
    const rows = json.aaData || (json.tables && json.tables[0] ? json.tables[0].data : null);
    if (rows) {
      console.log(`  TPEx online response is OK! Parsed ${rows.length} rows.`);
      for (const r of rows) {
        const id = String(r[0]).trim();
        if (id.length !== 4 || isNaN(Number(id))) continue;
        
        const close = cleanFloat(r[2]);
        if (!close || close <= 0) continue;
        
        const open = cleanFloat(r[4]) || close;
        const high = cleanFloat(r[5]) || close;
        const low = cleanFloat(r[6]) || close;
        const vol = cleanInt(r[7]) || 0;
        const amount = cleanInt(r[8]) || 0;
        
        todayPrices.push({
          stock_id: id,
          date: TODAY_DATE,
          open, high, low, close,
          volume: vol,
          amount,
          trade_count: null,
          spread: cleanFloat(r[3]) || 0.0,
          adj_factor: 1.0,
          adj_close: close,
          source: "TPEx_Crawler"
        });
      }
    }
  } catch (tpexErr) {
    console.error("  ❌ TPEx error:", tpexErr.message);
  }

  // 3. TWSE Institutional Buy/Sells
  try {
    const twseInstUrl = `https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=${yyyy}${mm}${dd}&selectType=ALLBUT0999`;
    const res = await fetch(twseInstUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = await res.json();
    if (json.stat === "OK" && json.data) {
      console.log(`  TWSE corporate response OK! Parsed ${json.data.length} records.`);
      for (const r of json.data) {
        const id = String(r[0]).trim();
        if (id.length !== 4 || isNaN(Number(id))) continue;
        
        const fb = cleanInt(r[2]) || 0;
        const fs = cleanInt(r[3]) || 0;
        const tb = cleanInt(r[11]) || 0;
        const ts = cleanInt(r[12]) || 0;
        
        todayInsts[id] = {
          stock_id: id,
          date: TODAY_DATE,
          foreign_net: fb - fs,
          trust_net: tb - ts,
          dealer_net: 0,
          foreign_buy: fb,
          foreign_sell: fs,
          trust_buy: tb,
          trust_sell: ts,
          dealer_buy: 0,
          dealer_sell: 0,
          source: "TWSE_Institutional_Crawler"
        };
      }
    }
  } catch (twInstErr) {
    console.error("  ❌ TWSE Corporate error:", twInstErr.message);
  }

  // 4. TPEx Institutional Buy/Sells
  try {
    const tpexInstUrl = `https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&t=D&d=${TODAY_ROC_DATE}`;
    const res = await fetch(tpexInstUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = await res.json();
    const rows = json.aaData || (json.tables && json.tables[0] ? json.tables[0].data : null);
    if (rows) {
      console.log(`  TPEx corporate response OK! Parsed ${rows.length} records.`);
      for (const r of rows) {
        const id = String(r[0]).trim();
        if (id.length !== 4 || isNaN(Number(id))) continue;
        
        let fb = 0, fs = 0, tb = 0, ts = 0;
        if (r.length > 18) {
          fb = cleanInt(r[2]) || 0; fs = cleanInt(r[3]) || 0;
          tb = cleanInt(r[11]) || 0; ts = cleanInt(r[12]) || 0;
        } else if (r.length > 9) {
          fb = cleanInt(r[2]) || 0; fs = cleanInt(r[3]) || 0;
          tb = cleanInt(r[5]) || 0; ts = cleanInt(r[6]) || 0;
        }
        
        todayInsts[id] = {
          stock_id: id,
          date: TODAY_DATE,
          foreign_net: fb - fs,
          trust_net: tb - ts,
          dealer_net: 0,
          foreign_buy: fb,
          foreign_sell: fs,
          trust_buy: tb,
          trust_sell: ts,
          dealer_buy: 0,
          dealer_sell: 0,
          source: "TPEx_Institutional_Crawler"
        };
      }
    }
  } catch (tpInstErr) {
    console.error("  ❌ TPEx Corporate error:", tpInstErr.message);
  }

  // Insert today's crawled stock_prices into Local SQLite
  if (todayPrices.length > 0) {
    console.log(`📥 Inserting ${todayPrices.length} close prices for ${TODAY_DATE} into SQLite...`);
    const insertPrice = db.prepare(`
      INSERT OR REPLACE INTO stock_history (stock_id, date, open, high, low, close, volume, amount, trade_count, spread, adj_factor, adj_close, source)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    db.transaction(() => {
      for (const p of todayPrices) {
        insertPrice.run(
          p.stock_id, p.date, p.open, p.high, p.low, p.close,
          p.volume, p.amount, p.trade_count, p.spread, p.adj_factor, p.adj_close, p.source
        );
      }
    })();
  }

  // Insert today's crawled institutional_data into Local SQLite
  const instList = Object.values(todayInsts);
  if (instList.length > 0) {
    console.log(`📥 Inserting ${instList.length} corporate networks for ${TODAY_DATE} into SQLite...`);
    const insertInst = db.prepare(`
      INSERT OR REPLACE INTO institutional_data (stock_id, date, foreign_net, trust_net, dealer_net, foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell, institutional_net, source)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    db.transaction(() => {
      for (const i of instList) {
        insertInst.run(
          i.stock_id, i.date, i.foreign_net, i.trust_net, i.dealer_net,
          i.foreign_buy, i.foreign_sell, i.trust_buy, i.trust_sell, i.dealer_buy, i.dealer_sell,
          i.foreign_net + i.trust_net + i.dealer_net, i.source
        );
      }
    })();
  }

  // Optional: Upload today's crawled prices to Supabase
  if (todayPrices.length > 0) {
    console.log(`📤 Upserting to Supabase...`);
    try {
      const bSize = 1000;
      for (let s = 0; s < todayPrices.length; s += bSize) {
        const batch = todayPrices.slice(s, s + bSize).map(p => ({
          stock_id: p.stock_id,
          date: p.date,
          open: p.open,
          high: p.high,
          low: p.low,
          close: p.close,
          volume: p.volume,
          amount: p.amount,
          trade_count: p.trade_count,
          spread: p.spread,
          adj_factor: p.adj_factor,
          source: p.source
        }));
        await supabase.from("stock_price").upsert(batch);
      }
      console.log("✅ Supabase stock_price updated with today's entries!");
    } catch (sbPriceErr) {
      console.warn("⚠️ Bypassed Supabase close price upload", sbPriceErr.message);
    }
  }

  if (instList.length > 0) {
    try {
      const bSize = 1000;
      for (let s = 0; s < instList.length; s += bSize) {
        const batch = instList.slice(s, s + bSize).map(i => ({
          stock_id: i.stock_id,
          date: i.date,
          foreign_net: i.foreign_net,
          trust_net: i.trust_net,
          dealer_net: i.dealer_net,
          foreign_buy: i.foreign_buy,
          foreign_sell: i.foreign_sell,
          trust_buy: i.trust_buy,
          trust_sell: i.trust_sell,
          dealer_buy: i.dealer_buy,
          dealer_sell: i.dealer_sell,
          source: i.source
        }));
        await supabase.from("stock_institutional").upsert(batch);
      }
      console.log("✅ Supabase stock_institutional updated with today's entries!");
    } catch (sbInstErr) {
      console.warn("⚠️ Bypassed Supabase institutional upload", sbInstErr.message);
    }
  }

  // Update calendar with unique dates including today's date
  console.log("📅 Refreshing stock_trading_calendar...");
  const dates = db.prepare("SELECT DISTINCT date FROM stock_history ORDER BY date ASC").all();
  db.prepare("DELETE FROM stock_trading_calendar").run();
  const insertCal = db.prepare(`
    INSERT INTO stock_trading_calendar (date, is_open, source)
    VALUES (?, 1, 'TWSE_Crawler')
  `);
  db.transaction(() => {
    for (const d of dates) {
      insertCal.run(d.date);
    }
  })();
  console.log(`✅ Loaded ${dates.length} unique trading days. Max date is ${dates[dates.length - 1]?.date}!`);
  
  console.log("\n🎉 ALL DONE! Today's stock data has been successfully crawling and synchronized!");
}

run().catch((err) => {
  console.error(err);
});
