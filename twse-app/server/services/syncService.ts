import { spawn } from 'child_process';

interface SyncProcess {
  running: boolean;
  logs: string[];
  startTime: string | null;
  error: string | null;
}

let activeSyncProcess: SyncProcess = {
  running: false,
  logs: [],
  startTime: null,
  error: null,
};

export const getSyncStatus = () => activeSyncProcess;

export const startBackgroundSync = async (webhookUrl?: string) => {
  if (activeSyncProcess.running) {
    return { alreadyRunning: true };
  }

  activeSyncProcess.running = true;
  activeSyncProcess.logs = [
    `[系統] ${new Date().toLocaleTimeString('zh-TW', { hour12: false })} 開始大盤行情同步程序...`,
  ];
  activeSyncProcess.startTime = new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' });
  activeSyncProcess.error = null;

  // Run asynchronously
  (async () => {
    if (webhookUrl && (webhookUrl.startsWith('http://') || webhookUrl.startsWith('https://'))) {
      activeSyncProcess.logs.push(`[系統] 偵測到遠端 Webhook，進行同步觸發: ${webhookUrl}`);
      try {
        await fetch(webhookUrl, { method: 'POST', signal: AbortSignal.timeout(4000) });
        activeSyncProcess.logs.push(`[系統] 遠端 Webhook 觸發成功。`);
      } catch (err: any) {
        activeSyncProcess.logs.push(`[系統] [警告] 遠端 Webhook 觸發未成功: ${err.message}`);
      }
    }

    activeSyncProcess.logs.push(`[系統] 啟動本地爬蟲對接。`);
    const child = spawn('npx tsx scripts/pull_from_supabase.js && npx tsx scripts/fetch_today_only.js', {
      shell: true,
    });

    child.stdout.on('data', (data) => {
      const text = data.toString();
      const lines = text.split(/\r?\n/);
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed) {
          const time = new Date().toLocaleTimeString('zh-TW', { hour12: false });
          activeSyncProcess.logs.push(`[${time}] ${trimmed}`);
        }
      }
    });

    child.stderr.on('data', (data) => {
      const text = data.toString();
      const lines = text.split(/\r?\n/);
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed) {
          const time = new Date().toLocaleTimeString('zh-TW', { hour12: false });
          activeSyncProcess.logs.push(`[${time}] [錯誤] ${trimmed}`);
        }
      }
    });

    child.on('close', (code) => {
      activeSyncProcess.running = false;
      const time = new Date().toLocaleTimeString('zh-TW', { hour12: false });
      if (code !== 0) {
        activeSyncProcess.error = `處理程序異常終止 (代碼: ${code})`;
        activeSyncProcess.logs.push(`\n[${time}] ❌ 行程異常結束。錯誤代碼: ${code}`);
      } else {
        activeSyncProcess.logs.push(`\n[${time}] ✅ 大盤實時爬蟲同步完成！`);
      }
    });
  })();

  return { alreadyRunning: false };
};
