<#
.SYNOPSIS
永久自動迭代直到 Playwright 測試通過，或連續失敗相同錯誤時退出。
#>

$MAX_CONSECUTIVE_SAME_ERROR = 5   # 連續幾次錯誤完全相同就放棄
$MAX_TURNS = 20                   # 每次 Claude 推理步數上限
$PROJECT_DIR = "d:\twse\twse-app" # 你的前端專案目錄
$RULES_FILE = "d:\twse\ai-rules.txt"
$API_EXAMPLE_FILE = "d:\twse\api-response-example.json"  # 如果有就放，沒有會跳過

Set-Location $PROJECT_DIR

# 確保 Git 可用
if (-not (Test-Path ".git")) {
    Write-Host "❌ 此目錄不是 Git 倉庫，請先初始化 Git。"
    exit 1
}

# 前置清除（保留手動修改的話可拿掉下面這行）
# git reset --hard HEAD

Write-Host "🚀 永久自動迭代模式啟動"
Write-Host "   卡死偵測：連續 $MAX_CONSECUTIVE_SAME_ERROR 次相同錯誤時自動停止"
Write-Host ""

$previousErrorHash = ""
$consecutiveCount = 0
$iteration = 0

while ($true) {
    $iteration++
    Write-Host "════════════════════════════════════"
    Write-Host "  第 $iteration 次檢查"
    Write-Host "════════════════════════════════════"

    # 執行 Playwright 測試，擷取完整輸出
    $output = & npx playwright test --reporter=line 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "✅ 所有測試通過！專案已可正常運作。"
        Write-Host "🎉 自動迭代完成，共進行 $iteration 次檢查。"
        exit 0
    }

    Write-Host "❌ 測試失敗，準備交由 Claude 修復..."

    # 計算本次錯誤雜湊（去除時間戳等變動部分，可自行調整）
    $errorBlock = ($output -join "`n") -replace '\d+:\d+:\d+',''  # 去除時間
    $errorHash = (Get-FileHash -InputStream ([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($errorBlock))) -Algorithm MD5).Hash

    # 卡死偵測
    if ($errorHash -eq $previousErrorHash) {
        $consecutiveCount++
        Write-Host "⚠️  連續相同錯誤次數: $consecutiveCount / $MAX_CONSECUTIVE_SAME_ERROR"
        if ($consecutiveCount -ge $MAX_CONSECUTIVE_SAME_ERROR) {
            Write-Host "⛔ 連續 $MAX_CONSECUTIVE_SAME_ERROR 次錯誤完全相同，判定為無法自動修復，請手動介入。"
            exit 1
        }
    } else {
        $consecutiveCount = 1
        $previousErrorHash = $errorHash
    }

    # 收集上下文：規則、錯誤、git diff、API 範例、相關檔案
    $rules = Get-Content $RULES_FILE -Raw

    $diff = git diff
    if (-not $diff) { $diff = "(無變更)" }

    $apiExample = ""
    if (Test-Path $API_EXAMPLE_FILE) {
        $apiExample = "`n=== 真實 API 回傳格式範例 ===`n" + (Get-Content $API_EXAMPLE_FILE -Raw)
    }

    # 嘗試抓取 src/api 目錄下的主要檔案，讓 Claude 更理解資料流
    $apiFilesContent = ""
    if (Test-Path "src/lib") {
        $apiFiles = Get-ChildItem "src/lib" -Filter *.ts -ErrorAction SilentlyContinue
        foreach ($f in $apiFiles) {
            $apiFilesContent += "`n=== ${f.Name} ===`n" + (Get-Content $f.FullName -Raw) + "`n"
        }
    }

    $prompt = @"
${rules}
${apiExample}

以下是執行 Playwright e2e 測試的錯誤訊息。請**直接修改前端程式碼**讓所有測試通過。
務必遵守鐵律：不使用任何假資料、Mock、Lorem ipsum。沒有資料時顯示對應的空狀態元件。
不要為了通過測試而修改測試檔案或移除 data-testid。

【測試錯誤訊息】
$output

【目前專案中相關的 API 檔案】
$apiFilesContent

【目前 Git 異動 (你已做的修改)】
$diff

請僅輸出你的修改摘要，並確實編輯對應的程式檔案。
"@

    # 將 prompt 透過標準輸入傳給 claude（避免長字串問題）
    $prompt | claude -p @- --allowedTools "Edit,Write,Bash(git diff:*,npx playwright test --reporter=line:*)" --output-format text --max-turns $MAX_TURNS

    Write-Host "📝 本次修改摘要 (git diff --stat):"
    git diff --stat

    # 短暫暫停
    Start-Sleep -Seconds 3
}
