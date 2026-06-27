#!/bin/bash

MAX_CONSECUTIVE_SAME_ERROR=5
MAX_TURNS=20
PROJECT_DIR="d:/twse/twse-app"          # 請改成你的實際路徑，或用 $(pwd)
RULES_FILE="$PROJECT_DIR/../ai-rules.txt"
API_EXAMPLE_FILE="$PROJECT_DIR/../api-response-example.json"

cd "$PROJECT_DIR" || exit 1

if [ ! -d ".git" ]; then
  echo "❌ 此目錄不是 Git 倉庫，請先初始化 Git。"
  exit 1
fi

# git reset --hard HEAD  # 視需求開啟

echo "🚀 永久自動迭代模式啟動"
echo "   卡死偵測：連續 $MAX_CONSECUTIVE_SAME_ERROR 次相同錯誤時自動停止"
echo ""

previous_error_hash=""
consecutive_count=0
iteration=0

while true; do
  iteration=$((iteration + 1))
  echo "════════════════════════════════════"
  echo "  第 $iteration 次檢查"
  echo "════════════════════════════════════"

  # 執行測試，保留完整輸出
  output=$(npx playwright test --reporter=line 2>&1)
  exit_code=$?

  if [ $exit_code -eq 0 ]; then
    echo "✅ 所有測試通過！專案已可正常運作。"
    echo "🎉 自動迭代完成，共進行 $iteration 次檢查。"
    exit 0
  fi

  echo "❌ 測試失敗，準備交由 Claude 修復..."

  # 計算錯誤雜湊（移除時間戳）
  error_block=$(echo "$output" | sed 's/[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}//g')
  error_hash=$(echo "$error_block" | md5sum | awk '{print $1}')

  if [ "$error_hash" = "$previous_error_hash" ]; then
    consecutive_count=$((consecutive_count + 1))
    echo "⚠️  連續相同錯誤次數: $consecutive_count / $MAX_CONSECUTIVE_SAME_ERROR"
    if [ $consecutive_count -ge $MAX_CONSECUTIVE_SAME_ERROR ]; then
      echo "⛔ 連續 $MAX_CONSECUTIVE_SAME_ERROR 次錯誤完全相同，判定為無法自動修復，請手動介入。"
      exit 1
    fi
  else
    consecutive_count=1
    previous_error_hash="$error_hash"
  fi

  # 收集上下文
  rules=$(cat "$RULES_FILE")
  diff_output=$(git diff)
  [ -z "$diff_output" ] && diff_output="(無變更)"

  api_example=""
  if [ -f "$API_EXAMPLE_FILE" ]; then
    api_example="
=== 真實 API 回傳格式範例 ===
$(cat "$API_EXAMPLE_FILE")"
  fi

  # API 檔案內容
  api_files_content=""
  if [ -d "src/lib" ]; then
    for f in src/lib/*.ts; do
      [ -f "$f" ] && api_files_content+="
=== ${f##*/} ===
$(cat "$f")
"
    done
  fi

  prompt="${rules}
${api_example}

以下是執行 Playwright e2e 測試的錯誤訊息。請**直接修改前端程式碼**讓所有測試通過。
務必遵守鐵律：不使用任何假資料、Mock、Lorem ipsum。沒有資料時顯示對應的空狀態元件。
不要為了通過測試而修改測試檔案或移除 data-testid。

【測試錯誤訊息】
$output

【目前專案中相關的 API 檔案】
$api_files_content

【目前 Git 異動 (你已做的修改)】
$diff_output

請僅輸出你的修改摘要，並確實編輯對應的程式檔案。
"

  # 透過 stdin 傳遞 prompt 避免跳脫問題
  echo "$prompt" | claude -p @- \
    --allowedTools "Edit,Write,Bash(git diff:*,npx playwright test --reporter=line:*)" \
    --output-format text \
    --max-turns $MAX_TURNS

  echo "📝 本次修改摘要 (git diff --stat):"
  git diff --stat

  sleep 3
done
