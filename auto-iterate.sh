#!/bin/bash
set -e

# ===== 設定區 =====
MAX_ITERATIONS=5                # 最多修幾次
CHECK_COMMAND="npx playwright test --reporter=line"  # 使用 e2e 測試
PROJECT_DIR="$(pwd)"            # 自動取當前目錄，亦可手動指定
RULES_FILE="$PROJECT_DIR/ai-rules.txt"

# Claude Code 安全限制
ALLOWED_TOOLS="Edit,Write,Bash(git diff:*)"
MAX_TURNS=12                    # 每次修復允許的推理步數上限

# ===== 前置檢查 =====
if ! command -v claude &> /dev/null; then
  echo "❌ 請先安裝 Claude Code: npm install -g @anthropic-ai/claude-code"
  exit 1
fi

if [ ! -f "$RULES_FILE" ]; then
  echo "❌ 缺少規則檔案 $RULES_FILE，請先建立。"
  exit 1
fi

cd "$PROJECT_DIR"

# 確保工作目錄乾淨 (可註解掉這行如果你想保留手動修改)
git add -A && git reset --hard HEAD

echo "🚀 開始自動迭代修復，最多 $MAX_ITERATIONS 次"

# ===== 迭代迴圈 =====
for i in $(seq 1 $MAX_ITERATIONS); do
  echo ""
  echo "════════════════════════════════════"
  echo "  第 $i / $MAX_ITERATIONS 次檢查"
  echo "════════════════════════════════════"

  # 執行檢查，擷取輸出與 exit code
  set +e
  OUTPUT=$($CHECK_COMMAND 2>&1)
  EXIT_CODE=$?
  set -e

  if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 所有測試通過！專案已可正常運作。"
    exit 0
  fi

  echo "❌ 測試失敗，錯誤訊息如下："
  echo "----------------------------------------"
  echo "$OUTPUT"
  echo "----------------------------------------"

  # 組合鐵律 + 錯誤訊息，寫入暫存檔供 prompt 使用
  COMBINED_PROMPT="/tmp/ai_fix_prompt_$i.txt"
  cat "$RULES_FILE" > "$COMBINED_PROMPT"
  echo "" >> "$COMBINED_PROMPT"
  echo "以下是執行 \`$CHECK_COMMAND\` 的錯誤訊息，請直接修改專案內的程式碼來修復所有問題。" >> "$COMBINED_PROMPT"
  echo "修完後不需要再執行檢查，我會自己再跑一次。" >> "$COMBINED_PROMPT"
  echo "" >> "$COMBINED_PROMPT"
  echo "錯誤訊息：" >> "$COMBINED_PROMPT"
  echo '```' >> "$COMBINED_PROMPT"
  echo "$OUTPUT" >> "$COMBINED_PROMPT"
  echo '```' >> "$COMBINED_PROMPT"

  echo "🧠 交由 Claude Code 修復中 (最多 $MAX_TURNS 步) ..."

  # 執行 Claude Code (非互動模式)
  claude -p "$(cat "$COMBINED_PROMPT")" \
    --allowedTools "$ALLOWED_TOOLS" \
    --output-format text \
    --max-turns $MAX_TURNS

  # 顯示異動摘要
  echo ""
  echo "📝 本次修改檔案："
  git diff --stat

  # 短暫暫停，避免瞬間請求過於密集
  sleep 2
done

echo ""
echo "⚠️ 已達最大迭代次數 ($MAX_ITERATIONS)，仍有測試未通過。"
echo "請手動檢查剩餘錯誤，或調高 MAX_ITERATIONS。"
exit 1
