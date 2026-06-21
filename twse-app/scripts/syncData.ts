/**
 * syncData.ts — 每日資料同步腳本（骨架）
 *
 * 此腳本供 server.ts 的 /api/update 端點呼叫。
 * 實際邏輯已移至 twstock/main.py，此檔案保留作為備用入口。
 *
 * 用法：
 *   npx tsx scripts/syncData.ts [options]
 *
 * 選項：
 *   --days <N>     下載幾個交易日（預設 5）
 *   --with-tdcc    自動更新 TDCC 集保資料
 */

import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

interface SyncOptions {
  days: number;
  withTdcc: boolean;
}

function parseArgs(): SyncOptions {
  const args = process.argv.slice(2);
  const opts: SyncOptions = { days: 5, withTdcc: false };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--days' && args[i + 1]) {
      opts.days = parseInt(args[++i], 10);
    } else if (args[i] === '--with-tdcc') {
      opts.withTdcc = true;
    }
  }
  return opts;
}

async function main() {
  const opts = parseArgs();
  console.log(`[syncData] 開始同步: days=${opts.days}, withTdcc=${opts.withTdcc}`);

  // twstock/main.py 的絕對路徑
  const twstockRoot = path.resolve(__dirname, '..', '..', 'twstock');
  const mainPy = path.join(twstockRoot, 'main.py');

  const args = ['official', `--days`, String(opts.days)];
  if (opts.withTdcc) args.push('--with-tdcc');

  console.log(`[syncData] 執行: python ${mainPy} ${args.join(' ')}`);

  try {
    const { stdout, stderr } = await execFileAsync('python', [mainPy, ...args], {
      cwd: twstockRoot,
      timeout: 300_000,
    });
    console.log(stdout);
    if (stderr) console.warn(stderr);
    console.log('[syncData] 同步完成');
  } catch (err: any) {
    console.error(`[syncData] 失敗: ${err.message}`);
    process.exit(1);
  }
}

main();
