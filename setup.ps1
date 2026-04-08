# setup.ps1
# Run this once from your repo root to organize all files correctly.
# Usage: .\setup.ps1

Write-Host "Creating folders..." -ForegroundColor Cyan

function Ensure-PackageDir {
    param(
        [Parameter(Mandatory=$true)][string]$DirName,
        [Parameter(Mandatory=$false)][string]$ExistingFileDest
    )

    if (Test-Path $DirName -PathType Leaf) {
        $tmp = "$DirName.__file"
        if (Test-Path $tmp) { Remove-Item -Force $tmp }
        Move-Item -Force $DirName $tmp

        New-Item -ItemType Directory -Force -Path $DirName | Out-Null

        if ($ExistingFileDest) {
            $destPath = Join-Path $DirName $ExistingFileDest
            if (Test-Path $destPath) { Remove-Item -Force $destPath }
            Move-Item -Force $tmp $destPath
        } else {
            # If we don't know what to name it, put it back.
            Move-Item -Force $tmp (Join-Path $DirName $DirName)
        }
        return
    }

    if (-not (Test-Path $DirName -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $DirName | Out-Null
    }
}

function Move-IfExists {
    param(
        [Parameter(Mandatory=$true)][string]$From,
        [Parameter(Mandatory=$true)][string]$ToDir
    )

    if (-not (Test-Path $From -PathType Leaf)) { return }
    if (-not (Test-Path $ToDir -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $ToDir | Out-Null
    }
    $dest = Join-Path $ToDir (Split-Path $From -Leaf)
    if (Test-Path $dest) { Remove-Item -Force $dest }
    Move-Item -Force $From $ToDir
}

# PowerShell needs folders created one at a time
Ensure-PackageDir "config"   "settings.py"
Ensure-PackageDir "scrapers" "base_scraper.py"
Ensure-PackageDir "api"      "endpoints.py"
Ensure-PackageDir "service"  "orchestrator.py"
Ensure-PackageDir "tests"    "test_parsers.py"

New-Item -ItemType Directory -Force -Path "models"   | Out-Null
New-Item -ItemType Directory -Force -Path "storage"  | Out-Null
New-Item -ItemType Directory -Force -Path "data"     | Out-Null
New-Item -ItemType Directory -Force -Path "logs"     | Out-Null

Write-Host "Moving files..." -ForegroundColor Cyan

# -- config/
Move-IfExists "settings.py" "config"
Move-IfExists "logging_setup.py" "config"

# -- models/
Move-IfExists "schemas.py" "models"

# -- scrapers/
Move-IfExists "base_scraper.py" "scrapers"
Move-IfExists "http_client.py" "scrapers"
Move-IfExists "nacional_scraper.py" "scrapers"
Move-IfExists "resultado_facil_scraper.py" "scrapers"

# -- storage/
Move-IfExists "storage_manager.py" "storage"
Move-IfExists "webhook_dispatcher.py" "storage"

# -- api/
Move-IfExists "endpoints.py" "api"

# -- service/
Move-IfExists "orchestrator.py" "service"

# -- tests/
Move-IfExists "test_parsers.py" "tests"

Write-Host "Creating __init__.py files..." -ForegroundColor Cyan

"" | Out-File -FilePath "config/__init__.py"   -Encoding utf8 -Force
"" | Out-File -FilePath "models/__init__.py"   -Encoding utf8 -Force
"" | Out-File -FilePath "scrapers/__init__.py" -Encoding utf8 -Force
"" | Out-File -FilePath "storage/__init__.py"  -Encoding utf8 -Force
"" | Out-File -FilePath "api/__init__.py"      -Encoding utf8 -Force
"" | Out-File -FilePath "service/__init__.py"  -Encoding utf8 -Force
"" | Out-File -FilePath "tests/__init__.py"    -Encoding utf8 -Force

Write-Host ""
Write-Host "Done! Final structure:" -ForegroundColor Green
Write-Host ""

Get-ChildItem -Recurse -Include "*.py" | 
    Where-Object { $_.FullName -notmatch "venv" } |
    Select-Object -ExpandProperty FullName |
    ForEach-Object { $_.Replace((Get-Location).Path + "\", "") } |
    Sort-Object

Write-Host ""
Write-Host "Now run: pip install -r requirements.txt" -ForegroundColor Yellow
Write-Host "Then:    pytest tests/ -v" -ForegroundColor Yellow
