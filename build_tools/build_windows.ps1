param(
    [string]$PythonPath = "",
    [string]$OutputDirectory = ""
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $ProjectRoot "dist\RiverLakeCartography-Windows-x64"
}

# Build-time Python is needed only when rebuilding. Recipients use the bundled runtime.
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $LauncherCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $PythonPath = (& $PythonCommand.Source -c "import sys; print(sys.executable)").Trim()
    } elseif ($LauncherCommand) {
        $PythonPath = (& $LauncherCommand.Source -3 -c "import sys; print(sys.executable)").Trim()
    } else {
        throw "A build-time Python 3.10+ is required. Run with -PythonPath <full path to python.exe>."
    }
}
& $PythonPath -c "import sys; assert sys.version_info >= (3,10); print(sys.executable)"
if ($LASTEXITCODE -ne 0) { throw "Build-time Python check failed." }

$BuildEnv = Join-Path $ProjectRoot ".build-venv"
$BuildPython = Join-Path $BuildEnv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $BuildPython)) {
    & $PythonPath -m venv $BuildEnv
    if ($LASTEXITCODE -ne 0) { throw "Could not create isolated build environment." }
}
& $BuildPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update build pip." }

& $BuildPython (Join-Path $PSScriptRoot "assemble_windows.py") --output $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Windows portable assembly failed." }

$ExePath = Join-Path $OutputDirectory "RiverLakeCartography.exe"
$TestDirectory = Join-Path $ProjectRoot ("build_validation\windows-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $TestDirectory -Force | Out-Null
$Arguments = '--self-test --output-dir "' + $TestDirectory + '"'
$Process = Start-Process -FilePath $ExePath -ArgumentList $Arguments -Wait -PassThru
if ($Process.ExitCode -ne 0) {
    throw "The actual Windows executable failed its self-test. Inspect: $TestDirectory"
}
$ReportPath = Join-Path $TestDirectory "self_test_report.json"
if (-not (Test-Path -LiteralPath $ReportPath)) {
    throw "The executable did not produce its self-test report: $ReportPath"
}
$Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Report.status -ne "passed" -or @($Report.errors).Count -ne 0 -or $Report.platform -ne "win32") {
    throw "Native self-test report did not pass: $ReportPath"
}
$ExpectedPython = [System.IO.Path]::GetFullPath((Join-Path $OutputDirectory "runtime\python.exe"))
if ([System.IO.Path]::GetFullPath($Report.executable) -ine $ExpectedPython) {
    throw "The launcher did not use the bundled Python interpreter. Report: $ReportPath"
}
$EvidenceDirectory = Join-Path $OutputDirectory "validation\windows"
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
Copy-Item -LiteralPath $ReportPath -Destination (Join-Path $EvidenceDirectory "self_test_report.json") -Force
if ($Report.output_dir) {
    $QaPath = Join-Path $Report.output_dir "output\qa.json"
    if (Test-Path -LiteralPath $QaPath) {
        Copy-Item -LiteralPath $QaPath -Destination (Join-Path $EvidenceDirectory "qa.json") -Force
    }
}

$ManifestPath = Join-Path $OutputDirectory "BUILD_MANIFEST.json"
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Manifest.native_windows_test = "passed; actual executable self-test returned 0"
$Manifest | Add-Member -NotePropertyName native_windows_test_report -NotePropertyValue "validation/windows/self_test_report.json" -Force
$Manifest | Add-Member -NotePropertyName native_windows_test_time -NotePropertyValue (Get-Date -Format o) -Force
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($ManifestPath, ($Manifest | ConvertTo-Json -Depth 20), $Utf8NoBom)

$ZipPath = $OutputDirectory + ".zip"
Compress-Archive -LiteralPath $OutputDirectory -DestinationPath $ZipPath -Force
Write-Host "Windows portable build and self-test passed."
Write-Host "Download/share this complete ZIP: $ZipPath"
Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256 | Format-List
