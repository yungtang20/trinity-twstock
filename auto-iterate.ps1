# ===== 設定區 =====
$MAX_ITERATIONS = 5                # 最多修幾次
$CHECK_COMMAND = "npx playwright test --reporter=line"
$RULES_FILE = Join-Path $PSScriptRoot "ai-rules.txt"
$MAX_TURNS = 12

# ===== 前置檢查 =====
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "請先安裝 Claude Code: npm install -g @anthropic-ai/claude-code" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $RULES_FILE)) {
    Write-Host "缺少規則檔案 $RULES_FILE，請先建立。" -ForegroundColor Red
    exit 1
}

Set-Location $PSScriptRoot

# 確保工作目錄乾淨
git add -A
git reset --hard HEAD

Write-Host "開始自動迭代修復，最多 $MAX_ITERATIONS 次" -ForegroundColor Cyan

# ===== 迭代迴圈 =====
for ($i = 1; $i -le $MAX_ITERATIONS; $i++) {
    Write-Host ""
    Write-Host "════════════════════════════════════" -ForegroundColor Yellow
    Write-Host "  第 $i / $MAX_ITERATIONS 次檢查" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════" -ForegroundColor Yellow

    # 執行檢查
    $OUTPUT = & npx playwright test --reporter=line 2>&1
    $EXIT_CODE = $LASTEXITCODE

    if ($EXIT_CODE -eq 0) {
        Write-Host "所有測試通過！專案已可正常運作。" -ForegroundColor Green
        exit 0
    }

    Write-Host "測試失敗，錯誤訊息如下：" -ForegroundColor Red
    Write-Host "----------------------------------------" -ForegroundColor Gray
    $OUTPUT | ForEach-Object { Write-Host $_ }
    Write-Host "----------------------------------------" -ForegroundColor Gray

    # 組合鐵律 + 錯誤訊息
    $COMBINED_PROMPT = Join-Path $TEMP "ai_fix_prompt_$i.txt"
    Get-Content $RULES_FILE | Out-File -FilePath $COMBINED_PROMPT -Encoding utf8
    "" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    "以下是執行 ``$CHECK_COMMAND`` 的錯誤訊息，請直接修改專案內的程式碼來修復所有問題。" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    "修完後不需要再執行檢查，我會自己再跑一次。" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    "" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    "錯誤訊息：" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    "```" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    $OUTPUT | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8
    "```" | Out-File -FilePath $COMBINED_PROMPT -Append -Encoding utf8

    Write-Host "交由 Claude Code 修復中 (最多 $MAX_TURNS 步) ..." -ForegroundColor Magenta

    # 執行 Claude Code
    $PROMPT = Get-Content $COMBINED_PROMPT -Raw
    claude -p $PROMPT `
        --allowedTools "Edit,Write,Bash(git diff:*)" `
        --output-format text `
        --max-turns $MAX_TURNS

    # 顯示異動摘要
    Write-Host ""
    Write-Host "本次修改檔案：" -ForegroundColor Cyan
    git diff --stat

    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "已達最大迭代次數 ($MAX_ITERATIONS)，仍有測試未通過。" -ForegroundColor Yellow
Write-Host "請手動檢查剩餘錯誤，或調高 MAX_ITERATIONS。" -ForegroundColor Yellow
exit 1
