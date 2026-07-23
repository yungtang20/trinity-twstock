// Pure-Node TDCC open-data downloader.  No Python dependency.
// Weekly CSV source: https://opendata.tdcc.com.tw/getOD.ashx?id=1-5  (~2.3MB)
import { getDb } from "../db";
import { supabase, addLog } from "../services";

export interface TdccRecord {
  stock_id: string;
  date: string;
  total_shares: number;
  whale_ratio: number;
  retail_ratio: number;
}

const OPEN_DATA_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5";

export async function downloadTdccCSV(): Promise<string> {
  const res = await fetch(OPEN_DATA_URL, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      Accept: "*/*",
    },
  });
  if (!res.ok) throw new Error(`TDCC open data HTTP ${res.status}`);
  const text = await res.text();
  if (!text || text.length < 100) throw new Error("TDCC response empty");
  return text;
}

// Parse CSV with columns: 資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%
// Aggregate by (stock_id, date):  total_shares = all-whare (level 17 if present, else sum of 1..17)
// whale_shares = sum of shares where level >= 12 (1000+張大股東 level)
// retail_shares = sum of shares where level <= 5
export function parseTdccCSV(csvText: string): { records: TdccRecord[]; date: string } {
  const lines = csvText.replace(/^﻿/, "").trim().split(/\r?\n/);
  const levelMap: Record<string, Record<number, number>> = {}; // date -> level -> shares
  const levelPeopleMap: Record<string, Record<number, number>> = {};
  let theDate = "";

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line || line.includes("資料日期")) continue;
    const parts = line.split(",").map((s) => s.trim());
    if (parts.length < 6) continue;
    const rawDate = parts[0];
    const stockId = parts[1];
    const level = parseInt(parts[2], 10);
    const people = parseInt(parts[3], 10) || 0;
    const shares = parseFloat(parts[4]) || 0;
    if (isNaN(level) || isNaN(shares)) continue;
    if (!/^\d{4,8}$/.test(rawDate)) continue;
    theDate = rawDate.length === 8
      ? `${rawDate.slice(0, 4)}-${rawDate.slice(4, 6)}-${rawDate.slice(6, 8)}`
      : rawDate.replace(/-/g, "-");
    const key = `${stockId}_${theDate}`;
    if (!levelMap[key]) levelMap[key] = {};
    if (!levelPeopleMap[key]) levelPeopleMap[key] = {};
    levelMap[key][level] = (levelMap[key][level] || 0) + shares;
    levelPeopleMap[key][level] = (levelPeopleMap[key][level] || 0) + people;
  }

  const records: TdccRecord[] = [];
  for (const [key, sharesByLevel] of Object.entries(levelMap)) {
    const stockId = key.split("_")[0];
    const date = key.slice(stockId.length + 1);
    let totalShares = sharesByLevel[17] || 0;
    if (!totalShares) {
      // fallback: sum all levels
      totalShares = Object.values(sharesByLevel).reduce((a, b) => a + b, 0);
    }
    // whale = level 12-16 (大型持碼人 + 1000+張); level 15 in some APIs is 1000+
    let whaleShares = 0;
    let retailShares = 0;
    for (const [lvlStr, shares] of Object.entries(sharesByLevel)) {
      const lvl = parseInt(lvlStr, 10);
      if (lvl >= 12 && lvl <= 16) whaleShares += shares;
      if (lvl >= 1 && lvl <= 6) retailShares += shares;
    }
    if (!totalShares) continue;
    records.push({
      stock_id: stockId,
      date,
      total_shares: Math.round(totalShares),
      whale_ratio: Math.round((whaleShares / totalShares) * 10000) / 100,
      retail_ratio: Math.round((retailShares / totalShares) * 10000) / 100,
    });
  }

  return { records, date: theDate };
}

export async function saveTdccToSQLite(records: TdccRecord[]): Promise<number> {
  const db = getDb();
  const tx = db.transaction((recs: TdccRecord[]) => {
    // one row per (stock_id, date); whale/retail ratio latest per stock
    const seen = new Set<string>();
    let n = 0;
    for (const r of recs) {
      const key = `${r.stock_id}_${r.date}`;
      if (seen.has(key)) continue;
      seen.add(key);
      db.prepare(
        `INSERT OR REPLACE INTO tdcc_shareholding
          (stock_id, date, total_shares, whale_ratio, retail_ratio, source, updated_at)
         VALUES (?, ?, ?, ?, ?, 'opendata', datetime('now'))`
      ).run(r.stock_id, r.date, r.total_shares, r.whale_ratio, r.retail_ratio);
      n++;
    }
    return n;
  });
  return tx(records);
}

export async function saveTdccToSupabase(records: TdccRecord[]): Promise<void> {
  if (!supabase) return;
  try {
    const rows = records.map((r) => ({
      stock_id: r.stock_id,
      date: r.date,
      total_shares: r.total_shares,
      whale_ratio: r.whale_ratio,
      retail_ratio: r.retail_ratio,
      source: "opendata",
    }));
    const CHUNK = 500;
    for (let i = 0; i < rows.length; i += CHUNK) {
      const { error } = await supabase.from("tdcc_shareholding").upsert(rows.slice(i, i + CHUNK), {
        onConflict: "stock_id,date",
      });
      if (error) console.warn("[tdcc] supabase upsert partial:", error.message);
    }
    addLog("TDCC_SUPABASE", "OK", `synced ${rows.length} TDCC rows`);
  } catch (e: any) {
    console.warn("[tdcc] supabase upsert failed:", e.message);
  }
}

export function getTdccSqliteStatus(): { latest: string | null; totalDistinctStocks: number; totalRows: number } {
  try {
    const db = getDb();
    const r1 = db.prepare(`SELECT MAX(date) as latest FROM tdcc_shareholding`).get() as any;
    const r2 = db.prepare(`SELECT COUNT(DISTINCT stock_id) as c FROM tdcc_shareholding`).get() as any;
    const r3 = db.prepare(`SELECT COUNT(*) as c FROM tdcc_shareholding`).get() as any;
    return { latest: r1?.latest || null, totalDistinctStocks: r2?.c || 0, totalRows: r3?.c || 0 };
  } catch { return { latest: null, totalDistinctStocks: 0, totalRows: 0 }; }
}

// Master sync flow
export async function syncTdcc(opts: { toSqlite?: boolean; toSupabase?: boolean; log?: (m: string) => void } = {}): Promise<{ count: number; date: string }> {
  const log = opts.log || ((m: string) => console.log("[tdcc]", m));
  const toSqlite = opts.toSqlite !== false;
  const toSupabase = opts.toSupabase !== false;

  log("下載 TDCC 每周 open data...");
  const csv = await downloadTdccCSV();
  log(`下載完成 (${(csv.length / 1024).toFixed(0)} KB)`);
  const { records, date } = parseTdccCSV(csv);
  log(`解析完成 ${records.length} 股 (每周基準日 ${date})`);

  let inserted = 0;
  if (toSqlite) {
    inserted = await saveTdccToSQLite(records);
    log(`SQLite 入庫 ${inserted} 筆`);
  }
  if (toSupabase) {
    await saveTdccToSupabase(records);
    log("Supabase 同步完成 (best-effort)");
  }
  return { count: inserted, date };
}
