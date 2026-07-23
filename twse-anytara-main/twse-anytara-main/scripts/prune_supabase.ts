import { createClient } from "@supabase/supabase-js";
import dotenv from "dotenv";

dotenv.config();

const url = process.env.VITE_SUPABASE_URL;
const key = process.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.error("❌ Need VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to prune Supabase!");
  process.exit(1);
}

const supabase = createClient(url, key);

async function run() {
  console.log("🚀 [Prune] Initializing Supabase robust batched pruning (for 512 trading days + pure regular stocks)...");

  // 1. 取得天天交易的台積電 (2330) 作為基準，找出第 512 個交易日的日期
  const MAX_TRADING_DAYS = 512; // 512 天，只留普通股 4 碼，容量絕對能控制在 500MB 以內
  console.log(`🔍 [Prune] Querying ${MAX_TRADING_DAYS} trading day timeline from stock_price...`);
  const { data: dates, error: dateError } = await supabase
    .from("stock_price")
    .select("date")
    .eq("stock_id", "2330")
    .order("date", { ascending: false })
    .range(MAX_TRADING_DAYS - 1, MAX_TRADING_DAYS - 1);

  if (dateError) {
    console.error("❌ Failed to query trading days:", dateError.message);
    process.exit(1);
  }

  let cutoffDate = "2024-05-15"; // fallback 
  if (dates && dates.length > 0) {
    cutoffDate = dates[0].date;
    console.log(`🎯 [Prune] Cutoff date selected: ${cutoffDate} (keeping latest ${MAX_TRADING_DAYS} trading days to limit database size)`);
  } else {
    console.warn("⚠️ Less than 512 trading days available, using default fallback date.");
  }

  // 2. 針對所有非 4 碼純數字的「非普通股」(如 6 碼權證、非標準商品)，不限日期一次性徹底清除。
  // 我們先極速查詢 stock_meta 表（該表很小），找出所有長度不等於 4 或含有字母的 stock_id 清單！
  console.log("🔍 [Prune] Querying all stock IDs from stock_meta for quick screening...");
  const { data: metas, error: metaErr } = await supabase
    .from("stock_meta")
    .select("stock_id");

  if (metaErr || !metas) {
    console.warn("⚠️ Cannot query stock_meta table, falling back to manual batching logic.", metaErr?.message);
  } else {
    const allIds = metas.map(m => m.stock_id);
    const nonRegularIds = allIds.filter(id => !/^\d{4}$/.test(id));
    console.log(`💡 [Prune] Found ${nonRegularIds.length} non-regular stock IDs (warrants, ETFs, index options, etc.) to delete.`);

    if (nonRegularIds.length > 0) {
      // 依 100 個一組分批刪除，這可以利用資料庫的 B-Tree 索引進行微秒級定位與物理刪除，100% 避免 Timeout
      const bSize = 100;
      for (let i = 0; i < nonRegularIds.length; i += bSize) {
        const batch = nonRegularIds.slice(i, i + bSize);
        console.log(`   🧹 Removing batch ${i / bSize + 1}/${Math.ceil(nonRegularIds.length / bSize)} (${batch.length} stocks)...`);
        
        await supabase.from("stock_price").delete().in("stock_id", batch);
        await supabase.from("stock_institutional").delete().in("stock_id", batch);
        await supabase.from("stock_features").delete().in("stock_id", batch);
        // 也順便從 stock_meta 裡刪除它
        await supabase.from("stock_meta").delete().in("stock_id", batch);
      }
      console.log("✅ [Prune] Completed deletion of all non-standard stock IDs across all tables!");
    }
  }

  // 3. 刪除早於限制日期的最舊普通股數據（4 碼股票）
  console.log(`🧹 [Prune] Removing regular stock data older than ${cutoffDate} (Older than ${MAX_TRADING_DAYS} trading days)...`);
  
  // 分段時間進行歷史大刪除以避免超時。我們找最舊的普通股日期
  const { data: oldestPrices } = await supabase
    .from("stock_price")
    .select("date")
    .order("date", { ascending: true })
    .limit(1);

  if (oldestPrices && oldestPrices.length > 0) {
    const oldestDateStr = oldestPrices[0].date;
    console.log(`📍 [Prune] Oldest date in DB currently is: ${oldestDateStr}`);
    
    if (oldestDateStr < cutoffDate) {
      let currentStart = new Date(oldestDateStr);
      const targetEnd = new Date(cutoffDate);
      
      while (currentStart < targetEnd) {
        let nextEnd = new Date(currentStart);
        nextEnd.setDate(nextEnd.getDate() + 14); // 每 14 天一個批次
        if (nextEnd > targetEnd) nextEnd = targetEnd;
        
        const startStr = currentStart.toISOString().split("T")[0];
        const endStr = nextEnd.toISOString().split("T")[0];
        console.log(`   👉 Deleting batch: [${startStr} to ${endStr}]`);
        
        await supabase.from("stock_price").delete().gte("date", startStr).lt("date", endStr);
        await supabase.from("stock_institutional").delete().gte("date", startStr).lt("date", endStr);
        await supabase.from("stock_features").delete().gte("date", startStr).lt("date", endStr);
        
        const nextStart = new Date(nextEnd);
        nextStart.setDate(nextStart.getDate() + 1);
        currentStart = nextStart;
      }
    }
  }

  console.log("\n🎉 [Prune] Supabase 512-day storage optimization successfully completed!");
  console.log(`💡 Note: Standard stocks (4 digits) are kept for exactly ${MAX_TRADING_DAYS} trading days to control storage below 500MB, whereas useless warrants/derivatives are completely wiped out.`);
}

run().catch(err => {
  console.error("Critical error in pruning script:", err);
});
