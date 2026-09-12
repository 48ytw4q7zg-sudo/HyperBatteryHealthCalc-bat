[CmdletBinding()]
param(
    [string]$Python = 'C:\Python314\python.exe',
    [string]$Node = 'node'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$buildRoot = Join-Path $projectRoot '.build'
$distRoot = Join-Path $projectRoot 'dist'

function Assert-OwnedPath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    $inside = $false
    foreach ($base in @($buildRoot, $distRoot)) {
        if ($full.StartsWith($base + '\', [System.StringComparison]::OrdinalIgnoreCase)) { $inside = $true }
    }
    if (-not $inside) { throw "Path is outside build/dist children: $full" }
    $cursor = $full
    while ($cursor -and $cursor -ne $projectRoot) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Reparse point not allowed: $cursor" }
        }
        $cursor = [System.IO.Path]::GetDirectoryName($cursor)
    }
    return $full
}

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with code $LASTEXITCODE" }
}

if ($env:OS -ne 'Windows_NT') { throw 'Build on Windows x64.' }
Invoke-Checked $Python @('-c', "import struct,sys,tkinter; assert sys.platform == 'win32' and struct.calcsize('P') == 8; print(sys.version)")
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$job = Assert-OwnedPath (Join-Path $buildRoot ('windows-' + $stamp))
$release = Assert-OwnedPath (Join-Path $job 'release')
$venv = Assert-OwnedPath (Join-Path $job 'venv')
$evidence = Assert-OwnedPath (Join-Path $job 'evidence')
New-Item -ItemType Directory -Path $release, $evidence -Force | Out-Null
$venvPython = Join-Path $venv 'Scripts\python.exe'
$sourceFiles = @(
    'HyperBatteryHealthCalc-bat\battery_core.py', 'HyperBatteryHealthCalc-bat\battery_gui.py',
    'HyperBatteryHealthCalc-bat\battery_calc.py', 'HyperBatteryHealthCalc-bat\portable_entry.py',
    'HyperBatteryHealthCalc-bat\report_io.py', 'HyperBatteryHealthCalc-bat\battery_smoke.py',
    'packaging\windows.spec', 'packaging\requirements-build.txt',
    'packaging\test_portable.py', 'packaging\test_gui_export.py', 'packaging\verify_portable.py',
    'packaging\PORTABLE_README.txt', 'packaging\BUILD_WINDOWS.md', 'build_windows.ps1',
    'test_battery_core.py', 'test_functional_completion.py', 'test_web_logic.cjs',
    'index.html', 'HyperBatteryHealthCalc-bat\index.html', 'LICENSE'
)
$sourceHashes = @{}
foreach ($name in $sourceFiles) {
    $sourceHashes[$name] = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $projectRoot $name)).Hash
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $evidence 'source-hashes.json'), ($sourceHashes | ConvertTo-Json), $utf8)
$previousCache = $env:PYINSTALLER_CONFIG_DIR
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
try {
    $env:PYINSTALLER_CONFIG_DIR = Assert-OwnedPath (Join-Path $job 'pyinstaller-cache')
    $env:TEMP = $env:TMP = Assert-OwnedPath (Join-Path $job 'temp')
    New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
    Write-Output "Build workspace: $job"
    Invoke-Checked $Python @('-m', 'venv', $venv)
    Invoke-Checked $venvPython @('-m', 'pip', '--isolated', '--disable-pip-version-check', 'install', '--require-virtualenv', '--no-cache-dir', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple', '-r', (Join-Path $projectRoot 'packaging\requirements-build.txt'))
    $resolved = & $venvPython -m pip --isolated freeze --all
    if ($LASTEXITCODE -ne 0) { throw 'Unable to record build dependencies' }
    [System.IO.File]::WriteAllText((Join-Path $evidence 'requirements-resolved.txt'), ($resolved -join "`n") + "`n", $utf8)
    Invoke-Checked $venvPython @((Join-Path $projectRoot 'packaging\verify_portable.py'), '--source-only', '--work-dir', (Join-Path $evidence 'source'), '--node', $Node)
    Invoke-Checked $venvPython @('-m', 'PyInstaller', '--noconfirm', '--distpath', $release, '--workpath', (Join-Path $job 'pyinstaller-work'), (Join-Path $projectRoot 'packaging\windows.spec'))
    $bundle = Assert-OwnedPath (Join-Path $release 'HyperBatteryHealthCalc')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'packaging\PORTABLE_README.txt') -Destination (Join-Path $bundle 'README.txt')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination (Join-Path $bundle 'LICENSE.txt')
    New-Item -ItemType Directory -Path (Join-Path $bundle 'input'), (Join-Path $bundle 'reports') -Force | Out-Null
    $archive = Assert-OwnedPath (Join-Path $release 'HyperBatteryHealthCalc-Windows-x64.zip')
    Invoke-Checked $venvPython @((Join-Path $projectRoot 'packaging\verify_portable.py'), '--bundle', $bundle, '--archive', $archive, '--work-dir', (Join-Path $evidence 'bundle'))
    foreach ($name in $sourceFiles) {
        $current = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $projectRoot $name)).Hash
        if ($current -ne $sourceHashes[$name]) { throw "Source changed during build; candidate is not published: $name" }
    }
    $verification = Get-Content -LiteralPath (Join-Path $evidence 'bundle\bundle-verification.json') -Raw | ConvertFrom-Json
    $sums = @($verification.inventory.files | ForEach-Object { $_.sha256 + '  HyperBatteryHealthCalc/' + $_.path })
    $sums += $verification.zip.sha256 + '  ' + $verification.zip.name
    [System.IO.File]::WriteAllText((Join-Path $release 'SHA256SUMS.txt'), ($sums -join "`n") + "`n", $utf8)
    $final = Assert-OwnedPath (Join-Path $distRoot ('HyperBatteryHealthCalc-Windows-x64-' + $stamp))
    New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
    if (Test-Path -LiteralPath $final) { throw "Destination already exists: $final" }
    # Both absolute roots were checked; each publication has a unique destination.
    $null = Assert-OwnedPath $release
    $null = Assert-OwnedPath $final
    Move-Item -LiteralPath $release -Destination $final
    $summary = [ordered]@{
        status = 'verified-preparation-pending-parent-review'
        release = $final
        bundle = Join-Path $final 'HyperBatteryHealthCalc'
        archive = Join-Path $final 'HyperBatteryHealthCalc-Windows-x64.zip'
        archive_sha256 = $verification.zip.sha256
        archive_bytes = $verification.zip.bytes
        bundle_bytes = $verification.inventory.total_bytes
        bundle_files = $verification.inventory.file_count
        tested_host = $verification.host
        evidence = $evidence
    }
    $summaryJson = $summary | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText((Join-Path $evidence 'build-result.json'), $summaryJson, $utf8)
    Write-Output $summaryJson
}
finally {
    $env:PYINSTALLER_CONFIG_DIR = $previousCache
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
}
