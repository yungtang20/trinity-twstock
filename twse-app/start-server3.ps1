Start-Process -FilePath "npm" -ArgumentList "start" -WorkingDirectory "D:\twse\twse-app" -WindowStyle Normal
Start-Sleep -Seconds 8
Write-Host "Server should be running now, testing API..."
try {
    $response = Invoke-RestMethod -Uri 'http://localhost:3000/api/update' -Method Post -ContentType 'application/json' -Body '{}'
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}
