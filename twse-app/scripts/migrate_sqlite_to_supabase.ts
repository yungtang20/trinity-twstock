import Database from 'better-sqlite3';
import { createClient } from '@supabase/supabase-js';
import path from 'path';

const supabaseUrl = process.env.VITE_SUPABASE_URL!;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

const dbPath = path.join(process.cwd(), 'twstock', 'taiwan_stock_unified.db');

async function migrate() {
  console.log('🚀 開始遷移 SQLite → Supabase...\n');

  const db = new Database(dbPath);

  // 1. 遷移 stock_meta
  console.log('📦 迁移 stock_meta...');
  const metaRows = db.prepare('SELECT * FROM stock_meta').all();
  if (metaRows.length > 0) {
    const { error } = await supabase.from('stock_meta').upsert(metaRows);
    if (error) console.error('  ❌ 失敗:', error.message);
    else console.log(`  ✅ ${metaRows.length} 筆`);
  }

  // 2. 遷移 stock_price
  console.log('📦 遷移 stock_price...');
  const priceCount = db.prepare('SELECT COUNT(*) as c FROM stock_price').get() as { c: number };
  console.log(`  總筆數: ${priceCount.c}`);

  const batchSize = 1000;
  let offset = 0;
  let totalMigrated = 0;

  while (true) {
    const rows = db.prepare('SELECT * FROM stock_price LIMIT ? OFFSET ?').all(batchSize, offset);
    if (rows.length === 0) break;

    const { error } = await supabase.from('stock_price').upsert(rows);
    if (error) {
      console.error(`  ❌ 批次 ${offset} 失敗:`, error.message);
      break;
    }

    totalMigrated += rows.length;
    offset += batchSize;
    process.stdout.write(`\r  進度: ${totalMigrated}/${priceCount.c}`);
  }

  console.log(`\n  ✅ ${totalMigrated} 筆\n`);

  // 3. 遷移 institutional_data
  console.log('📦 遷移 stock_institutional...');
  const instRows = db.prepare('SELECT * FROM institutional_data').all();
  if (instRows.length > 0) {
    const { error } = await supabase.from('stock_institutional').upsert(instRows);
    if (error) console.error('  ❌ 失敗:', error.message);
    else console.log(`  ✅ ${instRows.length} 筆`);
  }

  // 4. 遷移 dividend_events
  console.log('📦 遷移 dividend_events...');
  const divRows = db.prepare('SELECT * FROM dividend_events').all();
  if (divRows.length > 0) {
    const { error } = await supabase.from('dividend_events').upsert(divRows);
    if (error) console.error('  ❌ 失敗:', error.message);
    else console.log(`  ✅ ${divRows.length} 筆`);
  }

  // 5. 遷移 tdcc_shareholding
  console.log('📦 遷移 tdcc_shareholding...');
  const tdccRows = db.prepare('SELECT * FROM tdcc_shareholding').all();
  if (tdccRows.length > 0) {
    // 欄位名稱不同，需要轉換
    const mappedRows = tdccRows.map((r: any) => ({
      stock_id: r.stock_id,
      date: r.date,
      total_shares: r.total_shares,
      whale_ratio: r.whale_ratio,
      retail_ratio: r.retail_ratio,
      source: r.source,
    }));
    const { error } = await supabase.from('stock_features').upsert(mappedRows);
    if (error) console.error('  ❌ 失敗:', error.message);
    else console.log(`  ✅ ${tdccRows.length} 筆`);
  }

  db.close();

  console.log('\n🎉 遷移完成！');
}

migrate().catch(console.error);
