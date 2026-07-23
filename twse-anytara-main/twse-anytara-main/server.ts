import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";
import { initDb } from "./server/db";
import { initMcp } from "./server/lib/mcpClient";
import { resumeInterruptedJobs } from "./server/lib/jobQueue";
import { startTdccScheduler } from "./server/lib/tdccScheduler";
import apiRouter from "./server/routes";
import { debugState, addLog } from "./server/services";

// Load environment variables from .env
dotenv.config({ override: true });

function getLatestTradingDayInTaipei(): string {
  // Get current date/time in Taipei
  const taipeiTimeStr = new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" });
  const taipeiDate = new Date(taipeiTimeStr);
  
  const y = taipeiDate.getFullYear();
  const m = String(taipeiDate.getMonth() + 1).padStart(2, '0');
  const d = String(taipeiDate.getDate()).padStart(2, '0');
  const todayStr = `${y}-${m}-${d}`;

  // Check day of week (0 = Sunday, 1 = Monday, ..., 6 = Saturday)
  const dayOfWeek = taipeiDate.getDay();
  const hour = taipeiDate.getHours();
  const minute = taipeiDate.getMinutes();

  // If weekday and after 14:30 (when TWSE/TPEX are guaranteed to be fully processed),
  // latest trading day should be today.
  // Otherwise, it should be the most recent weekday before today.
  if (dayOfWeek >= 1 && dayOfWeek <= 5) {
    if (hour > 14 || (hour === 14 && minute >= 30)) {
      return todayStr;
    }
  }

  // Find the previous weekday
  const tempDate = new Date(taipeiDate);
  do {
    tempDate.setDate(tempDate.getDate() - 1);
  } while (tempDate.getDay() === 0 || tempDate.getDay() === 6);

  const py = tempDate.getFullYear();
  const pm = String(tempDate.getMonth() + 1).padStart(2, '0');
  const pd = String(tempDate.getDate()).padStart(2, '0');
  return `${py}-${pm}-${pd}`;
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  // Initialize SQLite Database
  const db = initDb();

  // Trigger background sync if DB lacks historical data or is stale
  if (db) {
    try {
      const row = db.prepare("SELECT COUNT(DISTINCT date) as c FROM stock_price").get() as { c: number };
      const latestDbRow = db.prepare("SELECT MAX(date) as max_date FROM stock_price").get() as { max_date: string | null };
      const latestDbDate = latestDbRow?.max_date || "";
      const expectedLatestDate = getLatestTradingDayInTaipei();

      const isDBCriticalEmpty = row.c < 10;
      const isDBStale = !latestDbDate || latestDbDate < expectedLatestDate;

      if ((isDBCriticalEmpty || isDBStale) && process.env.VITE_SUPABASE_URL && process.env.VITE_SUPABASE_ANON_KEY) {
         const syncType = isDBCriticalEmpty ? "CRITICAL_RESTORE" : "STALE_UPDATE";
         console.log(`[SYNC] Triggering background sync (${syncType}). Local latest: ${latestDbDate || 'None'}, Expected: ${expectedLatestDate}`);

         // Reset status block
         debugState.activeSyncProcess.running = true;
         debugState.activeSyncProcess.startTime = new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" });
         debugState.activeSyncProcess.error = null;

         if (isDBCriticalEmpty) {
           debugState.activeSyncProcess.logs = [
             `[系統] ${new Date().toLocaleTimeString("zh-TW", { hour12: false })} [自動修復] 檢測到本地資料集嚴重缺失（僅 ${row.c} 天歷史），啟動極速恢復程序...`
           ];
         } else {
           debugState.activeSyncProcess.logs = [
             `[系統] ${new Date().toLocaleTimeString("zh-TW", { hour12: false })} [自動同步] 檢測到本地資料 (${latestDbDate}) 舊於最新交易日 (${expectedLatestDate})，啟動盤後自動補登更新...`
           ];
         }

         const { spawn } = await import("child_process");
         const webhookUrl = process.env.VITE_UPDATE_WEBHOOK_URL;

         if (webhookUrl && (webhookUrl.startsWith("http://") || webhookUrl.startsWith("https://"))) {
           debugState.activeSyncProcess.logs.push(`[系統] 偵測到遠端 Webhook，進行同步觸發: ${webhookUrl}`);
           try {
             await fetch(webhookUrl, {
               method: 'POST',
               signal: AbortSignal.timeout(4000)
             });
             debugState.activeSyncProcess.logs.push(`[系統] 遠端 Webhook 觸發成功。`);
           } catch (err: any) {
             debugState.activeSyncProcess.logs.push(`[系統] [警告] 遠端 Webhook 觸發未成功: ${err.message}`);
             console.warn(`[Webhook-Warning] Background remote webhook trigger failed: ${err.message}`);
           }
         }

         // For critical empty, we do fast_sync first. For stale, we do pull_from_supabase && complete_and_fetch_today.
         const cmd = isDBCriticalEmpty
           ? "npx tsx scripts/fast_sync.js && npx tsx scripts/pull_from_supabase.js"
           : "npx tsx scripts/pull_from_supabase.js && npx tsx scripts/complete_and_fetch_today.js";

         debugState.activeSyncProcess.logs.push(`[系統] 執行命令: ${cmd}`);

         const child = spawn(cmd, { shell: true });

         child.stdout.on("data", (data) => {
           const text = data.toString();
           const lines = text.split(/\r?\n/);
           for (const line of lines) {
             const trimmed = line.trim();
             if (trimmed) {
               const time = new Date().toLocaleTimeString("zh-TW", { hour12: false });
               debugState.activeSyncProcess.logs.push(`[${time}] ${trimmed}`);
               addLog('SYNC_STAGE', 'INFO', trimmed);
               if (trimmed.startsWith("[Sync-Info]") || trimmed.startsWith("[Sync-Error]")) {
                 console.log(trimmed);
               } else {
                 console.log(`[Sync-Info] ${trimmed}`);
               }
             }
           }
         });

         child.stderr.on("data", (data) => {
           const text = data.toString();
           const lines = text.split(/\r?\n/);
           for (const line of lines) {
             const trimmed = line.trim();
             if (trimmed) {
               const time = new Date().toLocaleTimeString("zh-TW", { hour12: false });
               debugState.activeSyncProcess.logs.push(`[${time}] [錯誤] ${trimmed}`);
               addLog('SYNC_STAGE', 'ERR', trimmed);
               if (trimmed.startsWith("[Sync-Info]") || trimmed.startsWith("[Sync-Error]")) {
                 console.error(trimmed);
               } else {
                 console.error(`[Sync-Error] ${trimmed}`);
               }
             }
           }
         });

         child.on("close", (code) => {
           debugState.activeSyncProcess.running = false;
           const time = new Date().toLocaleTimeString("zh-TW", { hour12: false });
           if (code !== 0) {
             debugState.activeSyncProcess.error = `處理程序異常終止 (代碼: ${code})`;
             debugState.activeSyncProcess.logs.push(`\n[${time}] ❌ 行程異常結束。錯誤代碼: ${code}`);
             addLog('SYNC', 'ERROR', `Background sync process exited with code ${code}`);
           } else {
             debugState.activeSyncProcess.logs.push(`\n[${time}] ✅ 行程順利完成！資料庫日期已與最新盤後資訊同步。`);
             addLog('SYNC', 'OK', 'Database synchronized successfully on server start.');
           }
         });
      }
    } catch (e: any) {
      console.error("Failed to check DB history state:", e.message);
    }
  }

  // Basic Middlewares with custom limits for CSV upload
  app.use(express.json({ limit: "50mb" }));
  app.use(express.urlencoded({ extended: true, limit: "50mb" }));

  // Mount API router
  app.use(apiRouter);

  // Vite Middleware for Development or Static Files for Production
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`[FULL-STACK] Express server running on http://localhost:${PORT}`);
    // MVP: 连 remote MCP server (失败不卡 server)
    initMcp().then((ok) => console.log(`[MVP] MCP init ${ok ? "OK" : "FAIL (server 仍可用)"}`));

    // 恢復未完成的 job (server 重啟後)
    try { resumeInterruptedJobs(); } catch (e: any) { console.warn("[jobQueue] resume 失敗:", e.message); }

    // TDCC 每周排程器
    try { startTdccScheduler(); } catch (e: any) { console.warn("[tdcc-scheduler] 啟動失敗:", e.message); }
  });
}

startServer();
