# HAE + Lightning Azent: local synthetic-only Windows launcher.
# From repository root: .\apps\ax-flow\run-integrated.ps1 -Smoke
# Or: .\apps\ax-flow\run-integrated.ps1 -LaCheckout C:\path\to\LA-worktree
param(
    [string]$LaCheckout = "",
    [string]$DemoRoot = (Join-Path $env:TEMP 'hae-la-synthetic'),
    [int]$Port = 8765,
    [string]$DbvoraUrl = "",
    [string]$SoviaRoot = "",
    [switch]$Smoke
)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be in 1..65535.' }

$AppRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $AppRoot '..\..')).Path
$BundledLa = Join-Path $RepoRoot 'packages\lightning-azent'
$LaMarker = 'packages\lightning-azent\lightning_azent\__init__.py'
$ExplicitCheckout = -not [string]::IsNullOrWhiteSpace($LaCheckout)
if ($ExplicitCheckout) {
    if (-not (Test-Path -LiteralPath $LaCheckout -PathType Container)) {
        throw 'The supplied Lightning Azent checkout directory does not exist.'
    }
    $LaCheckout = (Resolve-Path -LiteralPath $LaCheckout).Path
} elseif (Test-Path -LiteralPath (Join-Path $BundledLa 'lightning_azent\__init__.py') -PathType Leaf) {
    # Offline/CI staged LA package: do not call Git or touch the network.
    $LaCheckout = $RepoRoot
} else {
    $LaCheckout = Join-Path $DemoRoot 'lightning-source'
    if (-not (Test-Path -LiteralPath (Join-Path $LaCheckout $LaMarker) -PathType Leaf)) {
        if (Test-Path -LiteralPath $LaCheckout) {
            throw 'An incomplete LA worktree already exists. Supply a valid -LaCheckout.'
        }
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw 'LA is not staged. Install Git or supply an existing -LaCheckout.'
        }
        New-Item -ItemType Directory -Force -Path $DemoRoot | Out-Null
        $GitRepo = $null
        try {
            $GitRepo = (& git -C $RepoRoot rev-parse --show-toplevel 2>$null)
            if ($LASTEXITCODE -ne 0) { $GitRepo = $null }
        } catch {
            $GitRepo = $null  # Source ZIP: clone instead of creating a worktree.
        }
        if ($GitRepo) {
            & git -C $RepoRoot fetch origin '+refs/heads/feature/lightning-azent:refs/remotes/origin/feature/lightning-azent'
            if ($LASTEXITCODE -ne 0) { throw 'LA branch fetch failed; supply -LaCheckout.' }
            $LaCommit = ((& git -C $RepoRoot rev-parse 'refs/remotes/origin/feature/lightning-azent') | Out-String).Trim()
            if ($LASTEXITCODE -ne 0 -or $LaCommit -notmatch '^[a-fA-F0-9]{40}$') {
                throw 'LA branch commit could not be verified.'
            }
            & git -C $RepoRoot worktree add --detach $LaCheckout $LaCommit
            if ($LASTEXITCODE -ne 0) { throw 'LA worktree creation failed; supply -LaCheckout.' }
        } else {
            & git clone --quiet --single-branch --branch feature/lightning-azent 'https://github.com/hibi89/HAE.git' $LaCheckout
            if ($LASTEXITCODE -ne 0) { throw 'LA clone failed; supply a local -LaCheckout.' }
        }
    }
}
$LaPackage = Join-Path $LaCheckout 'packages\lightning-azent'
if (-not (Test-Path -LiteralPath (Join-Path $LaPackage 'lightning_azent\__init__.py') -PathType Leaf)) {
    throw 'Lightning Azent package missing in checkout (expected packages/lightning-azent).'
}

$InputRoot = Join-Path $DemoRoot 'input'
New-Item -ItemType Directory -Force -Path $InputRoot | Out-Null
$Sample = Join-Path $InputRoot 'contacts.csv'
if (-not (Test-Path -LiteralPath $Sample)) {
    [System.IO.File]::WriteAllText($Sample, "id,name`n11,Alice`n12,Bob`n", (New-Object System.Text.UTF8Encoding($false)))
}
$OldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$AppRoot;$LaPackage"
    if ($OldPythonPath) { $env:PYTHONPATH += ";$OldPythonPath" }

    # This checks the real LA package handshake without touching SQLite.
    & python -c "from axflow.planner import plan_request; from axflow.la_adapter import inspect_backend; p=plan_request('Import this CSV into local SQLite', 'contacts.csv'); b=inspect_backend(p); assert b['api_version']=='azent.api.v0' and b['preflight']['executes_workflow'] is False; print('HAE-LA preflight OK')"
    if ($LASTEXITCODE -ne 0) { throw 'HAE-LA compatibility preflight failed; refusing to start.' }

    if ($Smoke) {
        # The real integration test imports LA from the repo's packages path.
        $ExpectedLa = Join-Path $BundledLa 'lightning_azent\__init__.py'
        if (-not (Test-Path -LiteralPath $ExpectedLa -PathType Leaf)) {
            New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot 'packages') | Out-Null
            if (([System.IO.Path]::GetFullPath($LaPackage)) -ne ([System.IO.Path]::GetFullPath($BundledLa))) {
                Copy-Item -LiteralPath $LaPackage -Destination $BundledLa -Recurse -Force
            }
        }
        if (-not (Test-Path -LiteralPath $ExpectedLa -PathType Leaf)) {
            throw 'Cannot stage LA; integration tests must not be skipped.'
        }
        Push-Location $AppRoot
        try {
            & python -m unittest discover -s tests -p test_la_adapter.py -v
            if ($LASTEXITCODE -ne 0) { throw 'HAE-LA integration smoke failed.' }
        } finally {
            Pop-Location
        }
        Write-Host 'HAE-LA HTTP integration smoke passed.'
    } else {
        Write-Host "HAE + Lightning Azent: http://127.0.0.1:$Port/"
        Write-Host "Synthetic CSV: $Sample"
        Write-Host 'Synthetic fixtures only. SQLite writes require explicit UI approval.'
        $LaunchArgs = @(
            'serve', '--input-root', $InputRoot,
            '--state', (Join-Path $DemoRoot 'state.db'),
            '--data', (Join-Path $DemoRoot 'business.db'),
            '--synthetic', '--engine-backend', 'lightning-azent', '--port', "$Port"
        )
        if ($DbvoraUrl) { $LaunchArgs += @('--dbvora-url', $DbvoraUrl) }
        if ($SoviaRoot) { $LaunchArgs += @('--sovia-root', $SoviaRoot) }
        & python -m axflow @LaunchArgs
        if ($LASTEXITCODE -ne 0) { throw 'HAE-LA server exited unsuccessfully.' }
    }
} finally {
    $env:PYTHONPATH = $OldPythonPath
}
