param(
    [switch]$InstallDeps,
    [switch]$RunTests,
    [switch]$RunCrawl,
    [switch]$RunReport,
    [switch]$RunExport
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
}

$python = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found at .\.venv\Scripts\python.exe"
}

if (-not ($InstallDeps -or $RunTests -or $RunCrawl -or $RunReport -or $RunExport)) {
    $InstallDeps = $true
    $RunTests = $true
    $RunReport = $true
    $RunExport = $true
}

if ($InstallDeps) {
    Invoke-Step "Install runtime and test dependencies" {
        & $python -m pip install -r requirements-dev.txt
    }
}

if ($RunTests) {
    Invoke-Step "Run unit and regression tests" {
        & $python -m pytest
    }
}

if ($RunCrawl) {
    Invoke-Step "Run NewsNow crawl" {
        & $python -m src.main
    }
}

if ($RunReport) {
    Invoke-Step "Generate NewsNow report" {
        & $python -m src.main_report_newsnow
    }
}

if ($RunExport) {
    Invoke-Step "Export observed evaluation set" {
        & $python -m src.main_export_evaluation_set
    }
}

Write-Host ""
Write-Host "Verification flow completed." -ForegroundColor Green
