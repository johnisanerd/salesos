$ErrorActionPreference = "Stop"

Write-Host "Checking SalesOS scaffold..."
docker compose config | Out-Null
Write-Host "Docker Compose configuration is valid."
