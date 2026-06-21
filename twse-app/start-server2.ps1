Start-Process -FilePath "npm" -ArgumentList "start" -WorkingDirectory "D:\twse\twse-app" -WindowStyle Hidden
Start-Sleep -Seconds 5
Write-Host "Server started, testing API..."
try {
    $response = Invoke-RestMethod -Uri 'http://localhost:3000/api/update' -Method Post -ContentType 'application/json' -Body '{}'
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response body: $responseBody"
    }
}
