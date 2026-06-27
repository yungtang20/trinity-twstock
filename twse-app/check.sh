#!/bin/bash
# twse-app 自動驗收腳本
# 執行方式: bash check.sh  或  chmod +x check.sh && ./check.sh
# 需要 server 在 localhost:3000 運行（npm run dev）

set -e

PASS=0
FAIL=0
ERRORS=""

check() {
  local desc="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo "  ✅ $desc"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $desc"
    FAIL=$((FAIL + 1))
    ERRORS="${ERRORS}\n  - ${desc}"
  fi
}

echo ""
echo "═══════════════════════════════════════"
echo "  twse-app 自動驗收"
echo "═══════════════════════════════════════"
echo ""

# ── 1. TypeScript 編譯 ─────────────────────────────────────
echo "📦 TypeScript 型別檢查"
check "tsc --noEmit 無新增錯誤" "! npx tsc --noEmit 2>&1 | grep -v 'db.ts' | grep -q 'error'"

# ── 2. 資料庫 seed ──────────────────────────────────────────
echo ""
echo "🗄️  資料庫檢查"
DB_SCRIPT=$(cat << 'EOF'
const Database = require('better-sqlite3');
const db = new Database('twstock/taiwan_stock_unified.db');
const checks = [
  db.prepare('SELECT COUNT(*) c FROM stock_history').get().c >= 100,
  db.prepare('SELECT COUNT(*) c FROM stock_meta').get().c >= 8,
  db.prepare('SELECT COUNT(*) c FROM institutional_data').get().c >= 3,
  db.prepare('SELECT COUNT(*) c FROM dividend_events').get().c >= 3,
  db.prepare("SELECT COUNT(*) c FROM stock_history WHERE stock_id='2330'").get().c >= 210,
  db.prepare("SELECT COUNT(*) c FROM stock_history WHERE stock_id='2317'").get().c >= 210,
];
db.close();
if (!checks.every(Boolean)) process.exit(1);
EOF
)
check "資料庫 seed 完整" "node -e \"$DB_SCRIPT\""

# ── 3. API 端點回應格式 ────────────────────────────────────
echo ""
echo "🌐 API 端點檢查"

api_success() {
  local path="$1"
  curl -s "http://localhost:3000${path}" 2>/dev/null | grep -q '"success":true'
}

api_data_not_null() {
  local path="$1"
  local data
  data=$(curl -s "http://localhost:3000${path}" 2>/dev/null | node -e "
    const d=require('fs').readFileSync('/dev/stdin','utf8');
    try{const j=JSON.parse(d);process.stdout.write(j.data===null||j.data===undefined?'null':'hasdata')}catch(e){process.stdout.write('null')}
  " 2>/dev/null)
  [ "$data" = "hasdata" ]
}

check "GET /api/twse-stats" "api_success '/api/twse-stats'"
check "GET /api/otc-stats" "api_success '/api/otc-stats'"
check "GET /api/stock/search?q=2330" "api_success '/api/stock/search?q=2330'"
check "GET /api/stock/2330/history" "api_success '/api/stock/2330/history?days=30'"
check "GET /api/stock/2330/indicators" "api_success '/api/stock/2330/indicators'"
check "GET /api/stock/2330/institutional" "api_success '/api/stock/2330/institutional'"
check "GET /api/stock/2330/quote" "api_success '/api/stock/2330/quote'"
check "GET /api/stock/2330/sr-analysis" "api_success '/api/stock/2330/sr-analysis'"
check "GET /api/stock/2330/ma-analysis" "api_success '/api/stock/2330/ma-analysis'"
check "GET /api/stock/2330/chips-analysis" "api_success '/api/stock/2330/chips-analysis'"
check "GET /api/stock/2330/prediction-analysis" "api_success '/api/stock/2330/prediction-analysis'"
check "GET /api/stock/2330/pattern-analysis" "api_success '/api/stock/2330/pattern-analysis'"
check "GET /api/movers" "api_success '/api/movers'"
check "GET /api/movers 有資料" "curl -s 'http://localhost:3000/api/movers' 2>/dev/null | node -e \"const d=require('fs').readFileSync('/dev/stdin','utf8');try{const j=JSON.parse(d);process.stdout.write(j.gainers&&j.gainers.length>0?'hasdata':'empty')}catch(e){process.stdout.write('empty')}\" | grep -q 'hasdata'"
check "GET /api/strategy/sr-scan" "api_success '/api/strategy/sr-scan?min_volume=0'"
check "GET /api/strategy/ma-scan" "api_success '/api/strategy/ma-scan'"
check "GET /api/strategy/chips-scan" "api_success '/api/strategy/chips-scan'"
check "GET /api/strategy/prediction-scan" "api_success '/api/strategy/prediction-scan'"
check "GET /api/strategy/pattern-scan" "api_success '/api/strategy/pattern-scan'"
check "GET /api/dashboard/recent-dividend" "api_success '/api/dashboard/recent-dividend'"
check "GET /api/dashboard/trust-buy-2day" "api_success '/api/dashboard/trust-buy-2day'"
check "GET /api/dashboard/break-ma200" "api_success '/api/dashboard/break-ma200'"
check "GET /api/dashboard/limit-up-yesterday" "api_success '/api/dashboard/limit-up-yesterday'"
check "GET /api/sync-status" "api_success '/api/sync-status'"
check "GET /api/settings" "api_success '/api/settings'"

# ── 4. 假資料關鍵字檢查（只檢查渲染文字，不檢查變數名）────
echo ""
echo "🔍 假資料關鍵字檢查（UI 渲染文字）"
# 檢查 src/ 中是否有 "Mock" 出現在字串Literal 中（排除變數名 isDataMock/isMock）
check "src/ 渲染文字不含 'Mock'" "! grep -r '\"[^\"]*Mock' src/ --include='*.tsx' --include='*.ts' | grep -v 'isMock' | grep -v 'isDataMock'"
check "src/ 渲染文字不含 'Test Data'" "! grep -r 'Test Data' src/ --include='*.tsx' --include='*.ts'"

# ── 5. data-testid 存在性 ───────────────────────────────────
echo ""
echo "🏷️  E2E test ID 檢查"
check "dashboard-view" "grep -r 'data-testid=\"dashboard-view\"' src/"
check "main-content" "grep -r 'data-testid=\"main-content\"' src/"
check "error-display" "grep -r 'data-testid=\"error-display\"' src/"
check "retry-button" "grep -r 'data-testid=\"retry-button\"' src/"

# ── 總結 ────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════"
echo "  結果：✅ $PASS | ❌ $FAIL"
echo "═══════════════════════════════════════"

if [ $FAIL -gt 0 ]; then
  echo ""
  echo "失敗項目："
  echo -e "$ERRORS"
  echo ""
  echo "請修正後重新執行 check.sh"
  exit 1
else
  echo ""
  echo "🟢 全部通過！"
  exit 0
fi
