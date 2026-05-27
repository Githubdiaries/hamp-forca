#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot\..

Write-Host "Starting PostgreSQL..."
docker compose up -d postgres

Write-Host "Running test suite in Docker..."
docker compose --profile test run --rm test
$exitCode = $LASTEXITCODE

Pop-Location
exit $exitCode
