Get-ChildItem -Path 'C:\Users\yungtang\.claude\skills' -Directory | ForEach-Object {
    $path = Join-Path $_.FullName 'SKILL.md'
    $lines = Get-Content $path -TotalCount 15 -ErrorAction SilentlyContinue
    $desc = $lines | Select-String '^description' | ForEach-Object { $_.Line }
    if ($desc -match 'superpowers') {
        Write-Host "FOUND: $($_.Name)"
        Write-Host "  $desc"
    } else {
        Write-Host "OK: $($_.Name)"
    }
}
