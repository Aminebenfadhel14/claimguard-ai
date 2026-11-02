$ErrorActionPreference = 'Stop'
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Write-Host 'Installation terminée. Lancez .\.venv\Scripts\python.exe -m pytest -q'
