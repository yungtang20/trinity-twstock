import { createClient } from "@supabase/supabase-js";
import fetch from "node-fetch";

const supabase = createClient(
  process.env.VITE_SUPABASE_URL as string,
  process.env.VITE_SUPABASE_ANON_KEY as string
);

// 轉化民國日期（動態取得今天日期）
const getLatestTradingDate = () => {
  const taipeiNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" }));
  const yyyy = taipeiNow.getFullYear();
  const mm = String(taipeiNow.getMonth() + 1).padStart(2, '0');
  const dd = String(taipeiNow.getDate()).padStart(2, '0');
  return `${yyyy}${mm}${dd}`;
};

const parseNum = (str: string) => {
  if (!str) return 0;
  const num = parseFloat(str.replace(/,/g, ""));
  return isNaN(num) ? 0 : num;
};

const parseSpread = (str: string) => {
  if (!str) return 0;
  let sign = 1;
  if (str.includes("green") || str.includes("-")) sign = -1;
  const text = str.replace(/<[^>]*>?/gm, "").trim();
  const num = parseFloat(text.replace(/,/g, ""));
  return isNaN(num) ? 0 : num * sign;
};

async function syncDailyPrices() {
  const dateStr = getLatestTradingDate();
  const taipeiNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" }));
  const isoDate = `${taipeiNow.getFullYear()}-${String(taipeiNow.getMonth() + 1).padStart(2, '0')}-${String(taipeiNow.getDate()).padStart(2, '0')}`;
  console.log(`[Sync] Fetching TWSE & TPEX data for ${dateStr}...`);

  const records: any[] = [];

  // TWSE
  try {
    const res = await fetch(`https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date=${dateStr}&type=ALLBUT0999`, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = await res.json() as any;
    const priceTable = json?.tables?.find((t: any) => t.title?.includes("行情"));
    
    if (priceTable?.data) {
      for (const row of priceTable.data) {
        const id = row[0];
        const volume = Math.min(parseNum(row[2]), 9999999999); // 成交股數
        const trade_count = parseNum(row[3]); // 成交筆數
        const amount = Math.min(parseNum(row[4]), 9999999999); // 成交金額
        const open = parseNum(row[5]);
        const high = parseNum(row[6]);
        const low = parseNum(row[7]);
        const close = parseNum(row[8]);
        const spread = parseSpread(row[9] + row[10]);

        if (volume > 0 && close > 0) {
          records.push({
            stock_id: id,
            date: isoDate,
            open, high, low, close, volume, amount, trade_count, spread,
            updated_at: new Date().toISOString()
          });
        }
      }
      console.log(`[Sync] TWSE table parsed, extracted ${priceTable.data.length} rows.`);
    }
  } catch (e: any) {
    console.error("TWSE Error", e.message);
  }

  // TPEX
  try {
    const tpexDate = `115/06/15`;
    const res = await fetch(`https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&d=${tpexDate}&se=EW`, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = await res.json() as any;
    if (json?.tables?.[0]?.data) {
      for (const row of json.tables[0].data) {
        const id = row[0];
        const close = parseNum(row[2]);
        const spread = parseSpread(row[3]);
        const open = parseNum(row[4]);
        const high = parseNum(row[5]);
        const low = parseNum(row[6]);
        const volume = Math.min(parseNum(row[7]), 9999999999);
        const amount = Math.min(parseNum(row[8]), 9999999999);
        const trade_count = parseNum(row[9]);

        if (volume > 0 && close > 0) {
          records.push({
            stock_id: id,
            date: isoDate,
            open, high, low, close, volume, amount, trade_count, spread,
            updated_at: new Date().toISOString()
          });
        }
      }
      console.log(`[Sync] TPEX table parsed, extracted ${json.tables[0].data.length} rows.`);
    }
  } catch (e: any) {
    console.error("TPEX Error", e.message);
  }

  console.log(`[Sync] Total valid records to insert: ${records.length}`);
  
  // Upsert in batches of 500
  let successCount = 0;
  for (let i = 0; i < records.length; i += 500) {
    const batch = records.slice(i, i + 500);
    const { error } = await supabase.from("stock_price").upsert(batch, { onConflict: "stock_id,date" });
    if (error) {
      console.error(`[Sync] Batch ${i} Error:`, error.message);
    } else {
      successCount += batch.length;
    }
  }
  
  console.log(`[Sync] Successfully upserted ${successCount} records to Supabase.`);

  // 總容量控制在 500MB 以內，約等於保留最近 512 個交易日
  // 我們透過查詢某檔每天都有交易的大型權值股 (例如 TSMC 2330)，
  // 取得其第 512 筆的日期作為 cutoffDate，將早於該日期的全庫交易紀錄刪除。
  const { data: dates } = await supabase
    .from("stock_price")
    .select("date")
    .eq("stock_id", "2330") // 台積電，通常天天交易
    .order("date", { ascending: false })
    .range(511, 511);

  if (dates && dates.length > 0) {
    const cutoffDate = dates[0].date;
    console.log("[Sync] Triggering cleanup for data older than: " + cutoffDate + " (keeping latest 512 days max)");
    const { error: cleanupErr } = await supabase
      .from("stock_price")
      .delete()
      .lt("date", cutoffDate);
      
    if (cleanupErr) {
      console.error("[Sync] Cleanup error:", cleanupErr.message);
    } else {
      console.log("[Sync] Cleanup complete, old data pruned.");
    }
  } else {
    console.log("[Sync] Total trading days < 512, no cleanup needed.");
  }
}

syncDailyPrices();
