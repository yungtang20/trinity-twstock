import { createClient } from "@supabase/supabase-js";
import dotenv from "dotenv";
dotenv.config();

const url = process.env.VITE_SUPABASE_URL;
const key = process.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.log("❌ Missing Supabase credentials in .env");
  process.exit(1);
}

const supabase = createClient(url, key);

async function check() {
  console.log("--- Supabase Database Status Check ---");
  
  // 1. Check stock_price max date & count
  const { data: maxPrice, error: priceErr } = await supabase
    .from("stock_price")
    .select("date")
    .order("date", { ascending: false })
    .limit(1);
    
  const { count: priceCount, error: countErr } = await supabase
    .from("stock_price")
    .select("*", { count: "exact", head: true });
    
  if (priceErr || countErr) {
    console.error("❌ Error fetching stock_price info:", priceErr?.message || countErr?.message);
  } else {
    console.log(`📈 Table [stock_price]: Total rows = ${priceCount}, Latest date = ${maxPrice?.[0]?.date || "None"}`);
  }

  // Check specific dates
  const targetDates = ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"];
  for (const d of targetDates) {
    const { count, error } = await supabase
      .from("stock_price")
      .select("*", { count: "exact", head: true })
      .eq("date", d);
    console.log(`   -> Price count for ${d}: ${count ?? 0} (Error: ${error?.message || "none"})`);
  }

  // 2. Check stock_institutional max date & count
  const { data: maxInst, error: instErr } = await supabase
    .from("stock_institutional")
    .select("date")
    .order("date", { ascending: false })
    .limit(1);
    
  const { count: instCount, error: instCountErr } = await supabase
    .from("stock_institutional")
    .select("*", { count: "exact", head: true });
    
  if (instErr || instCountErr) {
    console.error("❌ Error fetching stock_institutional info:", instErr?.message || instCountErr?.message);
  } else {
    console.log(`👥 Table [stock_institutional]: Total rows = ${instCount}, Latest date = ${maxInst?.[0]?.date || "None"}`);
  }

  for (const d of targetDates) {
    const { count, error } = await supabase
      .from("stock_institutional")
      .select("*", { count: "exact", head: true })
      .eq("date", d);
    console.log(`   -> Institutional count for ${d}: ${count ?? 0} (Error: ${error?.message || "none"})`);
  }

  // 3. Check stock_features (TDCC) max date & count
  const { data: maxFeats, error: featErr } = await supabase
    .from("stock_features")
    .select("date")
    .order("date", { ascending: false })
    .limit(1);
    
  const { count: featCount, error: featCountErr } = await supabase
    .from("stock_features")
    .select("*", { count: "exact", head: true });
    
  if (featErr || featCountErr) {
    console.error("❌ Error fetching stock_features info:", featErr?.message || featCountErr?.message);
  } else {
    console.log(`🐋 Table [stock_features]: Total rows = ${featCount}, Latest date = ${maxFeats?.[0]?.date || "None"}`);
  }

  // 4. Check stock_meta count
  const { count: metaCount, error: metaErr } = await supabase
    .from("stock_meta")
    .select("*", { count: "exact", head: true });
    
  if (metaErr) {
    console.error("❌ Error fetching stock_meta info:", metaErr.message);
  } else {
    console.log(`🏷️ Table [stock_meta]: Total rows = ${metaCount}`);
  }
}

check();
