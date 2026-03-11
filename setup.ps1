# setup.ps1
# Run this once from your repo root to organize all files correctly.
# Usage: .\setup.ps1

Write-Host "Creating folders..." -ForegroundColor Cyan

# PowerShell needs folders created one at a time
New-Item -ItemType Directory -Force -Path "config"   | Out-Null
New-Item -ItemType Directory -Force -Path "models"   | Out-Null
New-Item -ItemType Directory -Force -Path "scrapers" | Out-Null
New-Item -ItemType Directory -Force -Path "storage"  | Out-Null
New-Item -ItemType Directory -Force -Path "api"      | Out-Null
New-Item -ItemType Directory -Force -Path "service"  | Out-Null
New-Item -ItemType Directory -Force -Path "tests"    | Out-Null
New-Item -ItemType Directory -Force -Path "data"     | Out-Null
New-Item -ItemType Directory -Force -Path "logs"     | Out-Null

Write-Host "Moving files..." -ForegroundColor Cyan

# -- config/
if (Test-Path "settings.py")      { Move-Item -Force "settings.py"      "config/" }
if (Test-Path "logging_setup.py") { Move-Item -Force "logging_setup.py" "config/" }

# -- models/
if (Test-Path "schemas.py")       { Move-Item -Force "schemas.py"       "models/" }

# -- scrapers/
if (Test-Path "base_scraper.py")              { Move-Item -Force "base_scraper.py"              "scrapers/" }
if (Test-Path "http_client.py")               { Move-Item -Force "http_client.py"               "scrapers/" }
if (Test-Path "nacional_scraper.py")          { Move-Item -Force "nacional_scraper.py"          "scrapers/" }
if (Test-Path "resultado_facil_scraper.py")   { Move-Item -Force "resultado_facil_scraper.py"   "scrapers/" }

# -- storage/
if (Test-Path "storage_manager.py")   { Move-Item -Force "storage_manager.py"   "storage/" }
if (Test-Path "webhook_dispatcher.py"){ Move-Item -Force "webhook_dispatcher.py" "storage/" }

# -- api/
if (Test-Path "endpoints.py") { Move-Item -Force "endpoints.py" "api/" }

# -- service/
if (Test-Path "orchestrator.py") { Move-Item -Force "orchestrator.py" "service/" }

# -- tests/
if (Test-Path "test_parsers.py") { Move-Item -Force "test_parsers.py" "tests/" }

Write-Host "Creating __init__.py files..." -ForegroundColor Cyan

"" | Out-File -FilePath "config/__init__.py"   -Encoding utf8
"" | Out-File -FilePath "models/__init__.py"   -Encoding utf8
"" | Out-File -FilePath "scrapers/__init__.py" -Encoding utf8
"" | Out-File -FilePath "storage/__init__.py"  -Encoding utf8
"" | Out-File -FilePath "api/__init__.py"      -Encoding utf8
"" | Out-File -FilePath "service/__init__.py"  -Encoding utf8
"" | Out-File -FilePath "tests/__init__.py"    -Encoding utf8

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
