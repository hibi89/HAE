# HAE + Lightning Azent local synthetic integration launcher.
# Run from an HAE checkout: powershell -ExecutionPolicy Bypass -File .\apps\ax-flow\run-integrated.ps1 -LaCheckout C:\path\to\HAE-LA
param(
    [string]$LaCheckout = "",
    [string]$DemoRoot = (Join-Path $env:TEMP 'hae-la-synthetic'),
    [int]$Port = 8765,
    [string]$DbvoraUrl = "",
    [string]$SoviaRoot = "",
    [switch]$Smoke
)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be 1..65535' }
$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot '.')).Path
if (-not $LaCheckout) {
    $LaCheckout = Join-Path $DemoRoot 'lightning-source'
    if (-not (Test-Path (Join-Path $LaCheckout 'packages\lightning-azent\lightning_azent\__init__.py') -PathType Leaf)) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required to fetch Lightning Azent. Install Git or pass -LaCheckout.' }
        New-Item -ItemType Directory -Force -Path $DemoRoot | Out-Null
        $RepoRoot = $null
        try {
            $RepoRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null)
            if ($LASTEXITCODE -ne 0) { $RepoRoot = $null }
        } catch {
            # Source ZIPs are valid inputs: use the remote LA checkout below.
            $RepoRoot = $null
        }
        if ($RepoRoot) {
            # Resolve LA by its remote-tracking ref: FETCH_HEAD may be overwritten
            # by concurrent Git commands in this shared repository.
            & git -C $RepoRoot fetch origin '+refs/heads/feature/lightning-azent:refs/remotes/origin/feature/lightning-azent'
            if ($LASTEXITCODE -ne 0) { throw 'Unable to fetch current LA branch; pass a verified -LaCheckout.' }
            & git -C $RepoRoot worktree add --detach $LaCheckout refs/remotes/origin/feature/lightning-azent
            if ($LASTEXITCODE -ne 0) { throw 'Unable to create LA worktree; pass -LaCheckout.' }
        }
        if (-not (Test-Path (Join-Path $LaCheckout 'packages\lightning-azent\lightning_azent\__init__.py') -PathType Leaf)) {
            if (Test-Path $LaCheckout) {
                throw 'LA checkout incomplete. Remove the incomplete lightning-source folder or pass -LaCheckout.'
            }
            & git clone --quiet --single-branch --branch feature/lightning-azent https://github.com/hibi89/HAE.git $LaCheckout
            if ($LASTEXITCODE -ne 0) { throw 'Could not fetch Lightning Azent. Pass an existing checkout with -LaCheckout.' }
        }
    }
}
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
$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$AppRoot;$LaPackage"
if ($OldPythonPath) { $env:PYTHONPATH += ";$OldPythonPath" }
& python -c "from axflow.planner import plan_request; from axflow.la_adapter import inspect_backend; from axflow.web import create_server; p=plan_request('Import this CSV into local SQLite', 'contacts.csv'); b=inspect_backend(p); assert b['api_version']=='azent.api.v0'; assert b['preflight']['executes_workflow'] is False; print('HAE-LA plan-only compatibility preflight OK')"
if ($LASTEXITCODE -ne 0) { throw 'HAE / Lightning Azent plan-only compatibility check failed; refusing to start.' }
if ($Smoke) {
    $RepoRootForTests = (Resolve-Path (Join-Path $AppRoot '..\..')).Path
    $ExpectedLa = Join-Path $RepoRootForTests 'packages\lightning-azent\lightning_azent\__init__.py'
    if (-not (Test-Path $ExpectedLa -PathType Leaf)) {
        $StagedParent = Join-Path $RepoRootForTests 'packages'
        New-Item -ItemType Directory -Force -Path $StagedParent | Out-Null
        if ((Resolve-Path $LaPackage).Path -ne (Join-Path $StagedParent 'lightning-azent')) {
            Copy-Item -Recurse -Force -Path $LaPackage -Destination $StagedParent
        }
    }
    if (-not (Test-Path $ExpectedLa -PathType Leaf)) {
        throw 'Unable to stage LA for integration smoke; refusing skipped tests.'
    }
    Push-Location $AppRoot
    try {
        & python -m unittest discover -s tests -p test_la_adapter.py -v
        if ($LASTEXITCODE -ne 0) { throw 'HAE-LA HTTP integration smoke tests failed.' }
    } finally {
        Pop-Location
    }
    Write-Host 'HAE-LA HTTP integration smoke tests passed.'
    exit 0
}
Write-Host "HAE + Lightning Azent: http://127.0.0.1:$Port/"
Write-Host "Synthetic CSV: $Sample"
Write-Host 'Use only synthetic fixtures. SQLite writes require UI approval.'
$LaunchArgs = @('serve', '--input-root', $InputRoot, '--state', (Join-Path $DemoRoot 'state.db'), '--data', (Join-Path $DemoRoot 'business.db'), '--synthetic', '--engine-backend', 'lightning-azent', '--port', "$Port")
if ($DbvoraUrl) { $LaunchArgs += @('--dbvora-url', $DbvoraUrl) }
if ($SoviaRoot) { $LaunchArgs += @('--sovia-root', $SoviaRoot) }
& python -m axflow @LaunchArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
