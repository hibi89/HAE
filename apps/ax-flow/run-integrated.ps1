# HAE + Lightning Azent local synthetic integration launcher.
# Run from an HAE checkout: powershell -ExecutionPolicy Bypass -File .\apps\ax-flow\run-integrated.ps1 -LaCheckout C:\path\to\HAE-LA
param(
    [Parameter(Mandatory=$true)][string]$LaCheckout,
    [string]$DemoRoot = (Join-Path $env:TEMP 'hae-la-synthetic'),
    [int]$Port = 8765
)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be 1..65535' }
$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot '.')).Path
$LaPackage = Join-Path $LaCheckout 'packages\lightning-azent'
if (-not (Test-Path (Join-Path $LaPackage 'lightning_azent\__init__.py') -PathType Leaf)) {
    throw 'Lightning Azent source not found. Pass a checkout of feature/lightning-azent using -LaCheckout.'
}
$InputRoot = Join-Path $DemoRoot 'input'
New-Item -ItemType Directory -Force -Path $InputRoot | Out-Null
$Sample = Join-Path $InputRoot 'contacts.csv'
if (-not (Test-Path $Sample)) {
    [System.IO.File]::WriteAllText($Sample, "id,name`n11,Alice`n12,Bob`n", (New-Object System.Text.UTF8Encoding($false)))
}
$env:PYTHONPATH = "$AppRoot;$LaPackage"
Write-Host "HAE + Lightning Azent: http://127.0.0.1:$Port/"
Write-Host "Synthetic CSV: $Sample"
Write-Host 'Use only synthetic fixtures. SQLite writes require UI approval.'
& python -m axflow serve --input-root $InputRoot --state (Join-Path $DemoRoot 'state.db') --data (Join-Path $DemoRoot 'business.db') --synthetic --engine-backend lightning-azent --port $Port
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
