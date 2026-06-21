Get-Process -Name 'node' -ErrorAction SilentlyContinue | ForEach-Object {
    $id = $_.Id
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
}
Write-Host "Done"
