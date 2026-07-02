$file = 'C:\Users\yungtang\.claude\plugins\cache\superpowers-marketplace\superpowers\5.1.0\skills\brainstorming\SKILL.md'
$content = Get-Content $file -Raw -ErrorAction SilentlyContinue
$matches = [regex]::Matches($content, '.{0,30}superpowers.{0,30}')
foreach ($match in $matches) {
    Write-Host "MATCH: [$($match.Value)]"
}
