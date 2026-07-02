$skills = Get-ChildItem -Path 'C:\Users\yungtang\.claude\plugins\cache\superpowers-marketplace\superpowers\5.1.0\skills' -Directory
foreach ($dir in $skills) {
    $file = Join-Path $dir.FullName 'SKILL.md'
    if (Test-Path $file) {
        $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
        if ($content -match 'superpowers') {
            Write-Host "FOUND: $($dir.Name)"
            $idx = $content.IndexOf('superpowers')
            $start = [Math]::Max(0, $idx - 30)
            $len = [Math]::Min(60, $content.Length - $start)
            Write-Host "  ...$($content.Substring($start, $len))..."
        } else {
            Write-Host "OK: $($dir.Name)"
        }
    }
}
