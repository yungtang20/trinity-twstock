$skills = Get-ChildItem -Path 'C:\Users\yungtang\.claude\skills' -Directory
foreach ($dir in $skills) {
    $file = Join-Path $dir.FullName 'SKILL.md'
    if (Test-Path $file) {
        $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
        if ($content -match 'superpowers') {
            Write-Host "FOUND: $($dir.Name)"
        } else {
            Write-Host "OK: $($dir.Name)"
        }
    }
}
