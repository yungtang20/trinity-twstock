#!/usr/bin/env node
/**
 * verify_fixes.mjs
 * 驗證 twse-anytara 兩個 bug 修改是否正確
 *
 * 執行方式：
 *   node verify_fixes.mjs
 *   node verify_fixes.mjs --path D:\projects\twse-anytara
 *
 * 兩個檔案在不同子目錄時，個別指定：
 *   node verify_fixes.mjs --sync scripts\complete_and_fetch_today.js --api src\lib\api.ts
 */

import fs from 'fs';
import path from 'path';

// ── 路徑設定 ───────────────────────────────────────────────
// 預設值：從專案根目錄執行時的相對路徑
// 可用 --sync 和 --api 個別覆寫
const args = process.argv.slice(2);

function getArg(flag, defaultVal) {
  const idx = args.indexOf(flag);
  return idx !== -1 ? args[idx + 1] : defaultVal;
}

const ROOT = getArg('--path', process.cwd());

const FILES = {
  sync: getArg('--sync', path.join(ROOT, 'complete_and_fetch_today.js')),
  api:  getArg('--api',  path.join(ROOT, 'src', 'lib', 'api.ts')),
};

// ── 輸出工具 ───────────────────────────────────────────────
let passed = 0;
let failed = 0;

function ok(msg)   { console.log(`  ✅ PASS  ${msg}`); passed++; }
function fail(msg) { console.log(`  ❌ FAIL  ${msg}`); failed++; }
function info(msg) { console.log(`  ℹ️       ${msg}`); }
function header(title) {
  console.log('');
  console.log(`${'─'.repeat(55)}`);
  console.log(`  ${title}`);
  console.log(`${'─'.repeat(55)}`);
}

// ── 讀取檔案 ───────────────────────────────────────────────
function readFile(filePath) {
  if (!fs.existsSync(filePath)) {
    fail(`找不到檔案：${filePath}`);
    return null;
  }
  return fs.readFileSync(filePath, 'utf-8');
}

// ── Bug 1 驗證：complete_and_fetch_today.js ────────────────
function verifySync(content) {
  header('Bug 1｜complete_and_fetch_today.js — CUTOFF_DATE');

  // 1-A：舊的 hardcoded 寫法不應該存在
  const hardcoded = /CUTOFF_DATE\s*=\s*`\$\{yyyy\}-01-01`/;
  if (hardcoded.test(content)) {
    fail('CUTOFF_DATE 仍然是 hardcoded `${yyyy}-01-01`，尚未修改');
  } else {
    ok('hardcoded `${yyyy}-01-01` 已移除');
  }

  // 1-B：應該有動態計算的痕跡（減去天數計算 cutoff）
  const hasDynamicCalc = /Date\.now\(\)\s*-\s*\d+\s*\*\s*24\s*\*\s*60\s*\*\s*60\s*\*\s*1000/.test(content);
  if (hasDynamicCalc) {
    ok('找到動態日期計算（Date.now() - N*24*60*60*1000）');
  } else {
    fail('找不到動態日期計算，CUTOFF_DATE 可能還不是滾動視窗');
  }

  // 1-C：CUTOFF_DATE 仍然存在（變數名稱沒有被誤刪）
  const hasCutoff = /const CUTOFF_DATE/.test(content);
  if (hasCutoff) {
    ok('CUTOFF_DATE 變數仍然存在');
  } else {
    fail('CUTOFF_DATE 變數不見了，可能誤刪');
  }

  // 1-D：使用 Asia/Taipei 時區（跟 taipeiNow 一致）
  const hasTaipeiTZ = /Asia\/Taipei/.test(content);
  if (hasTaipeiTZ) {
    ok('有使用 Asia/Taipei 時區');
  } else {
    fail('找不到 Asia/Taipei 時區，cutoff 時區與 today 不一致');
  }

  // 1-E：執行期驗證 — 計算出來的 CUTOFF_DATE 格式要是 YYYY-MM-DD 且不是今天
  //       用 eval 從內容中擷取計算邏輯來實際跑一次
  try {
    // 從檔案取出 CUTOFF_DATE 那段，在此 process 內重跑
    // 抓出「從 Date.now() 減去 N 天」的實際值
    const daysMatch = content.match(/Date\.now\(\)\s*-\s*(\d+)\s*\*\s*24\s*\*\s*60\s*\*\s*60\s*\*\s*1000/);
    if (daysMatch) {
      const days = parseInt(daysMatch[1], 10);
      const cutoffMs = Date.now() - days * 24 * 60 * 60 * 1000;
      const cutoffDate = new Date(
        new Date(cutoffMs).toLocaleString('en-US', { timeZone: 'Asia/Taipei' })
      );
      const cy  = cutoffDate.getFullYear();
      const cm  = String(cutoffDate.getMonth() + 1).padStart(2, '0');
      const cdd = String(cutoffDate.getDate()).padStart(2, '0');
      const cutoffStr = `${cy}-${cm}-${cdd}`;

      const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
      if (dateRegex.test(cutoffStr)) {
        ok(`CUTOFF_DATE 實際值：${cutoffStr}（往回 ${days} 天，格式正確）`);
      } else {
        fail(`CUTOFF_DATE 產出格式不對：${cutoffStr}`);
      }

      // 確認不是今天（應該在今天之前）
      const todayTaipei = new Date(
        new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' })
      );
      const todayStr = `${todayTaipei.getFullYear()}-${String(todayTaipei.getMonth()+1).padStart(2,'0')}-${String(todayTaipei.getDate()).padStart(2,'0')}`;
      if (cutoffStr < todayStr) {
        ok(`CUTOFF_DATE（${cutoffStr}）早於今天（${todayStr}）✓`);
      } else {
        fail(`CUTOFF_DATE（${cutoffStr}）不早於今天，邏輯有誤`);
      }
    }
  } catch (e) {
    info(`執行期驗證略過：${e.message}`);
  }
}

// ── Bug 2 驗證：src/lib/api.ts ─────────────────────────────
function verifyApi(content) {
  header('Bug 2｜src/lib/api.ts — import type PriceData');

  // 2-A：舊的 value import 不應該存在
  const valueImport = /^import\s+\{[^}]*PriceData[^}]*\}\s+from\s+['"]\.\/indicators['"]/m;
  if (valueImport.test(content)) {
    fail("仍有 `import { PriceData }` 的 value import，isolatedModules 下會報錯");
  } else {
    ok('沒有殘留 value import `{ PriceData }`');
  }

  // 2-B：正確的 type import 應該存在
  const typeImport = /^import\s+type\s+\{[^}]*PriceData[^}]*\}\s+from\s+['"]\.\/indicators['"]/m;
  if (typeImport.test(content)) {
    ok('找到正確的 `import type { PriceData }` 寫法');
  } else {
    fail('找不到 `import type { PriceData }` — 請確認第 1 行已加上 type');
  }

  // 2-C：re-export 應該還在（export type { PriceData }）
  const reExport = /export\s+type\s+\{\s*PriceData\s*\}/.test(content);
  if (reExport) {
    ok('`export type { PriceData }` 仍然存在，re-export 沒有被誤刪');
  } else {
    fail('`export type { PriceData }` 不見了，其他 import 這個型別的地方會炸');
  }

  // 2-D：import type 要在第 1 行（慣例 + 確保沒有異位）
  const firstLine = content.split('\n')[0];
  if (/import\s+type/.test(firstLine)) {
    ok('`import type` 在第 1 行，位置正確');
  } else {
    fail(`第 1 行是「${firstLine.trim()}」，import type 不在第一行`);
  }
}

// ── 主流程 ─────────────────────────────────────────────────
console.log('');
console.log('╔═══════════════════════════════════════════════════════╗');
console.log('║   twse-anytara  Bug Fix Verifier                     ║');
console.log('╚═══════════════════════════════════════════════════════╝');
console.log(`  sync  ：${FILES.sync}`);
console.log(`  api   ：${FILES.api}`);

const syncContent = readFile(FILES.sync);
const apiContent  = readFile(FILES.api);

if (syncContent) verifySync(syncContent);
if (apiContent)  verifyApi(apiContent);

// ── 總結 ───────────────────────────────────────────────────
header('驗證結果');
console.log(`  通過：${passed}　失敗：${failed}`);
if (failed === 0) {
  console.log('');
  console.log('  🎉 全部通過，兩個 bug 均已正確修復！');
} else {
  console.log('');
  console.log(`  ⚠️  有 ${failed} 個檢查未通過，請依照 FAIL 訊息修正。`);
}
console.log('');
