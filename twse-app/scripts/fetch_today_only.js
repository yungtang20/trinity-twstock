#!/usr/bin/env node
/**
 * fetch_today_only.js — 抓取今日資料（骨架）
 *
 * 此腳本供 server.ts 的 /api/trigger-update 端點呼叫。
 * 實際邏輯已移至 twstock/main.py，此檔案保留作為備用入口。
 *
 * 用法：
 *   node scripts/fetch_today-only.js
 */

const { execFile } = require('child_process');
const path = require('path');
const { promisify } = require('util');

const execFileAsync = promisify(execFile);

async function main() {
  console.log('[fetchToday] 開始抓取今日資料...');

  // twstock/main.py 的絕對路徑
  const twstockRoot = path.resolve(__dirname, '..', '..', 'twstock');
  const mainPy = path.join(twstockRoot, 'main.py');

  const args = ['official', '--days', '1', '--with-tdcc'];

  console.log(`[fetchToday] 執行: python ${mainPy} ${args.join(' ')}`);

  try {
    const { stdout, stderr } = await execFileAsync('python', [mainPy, ...args], {
      cwd: twstockRoot,
      timeout: 300_000,
    });
    console.log(stdout);
    if (stderr) console.warn(stderr);
    console.log('[fetchToday] 抓取完成');
  } catch (err) {
    console.error(`[fetchToday] 失敗: ${err.message}`);
    process.exit(1);
  }
}

main();
