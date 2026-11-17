param([ValidateRange(1024,65535)][int]$Port = 8501, [string]$Profile = '')
$ErrorActionPreference = 'Stop'
$claimRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $claimRoot
$claimPython = Join-Path $claimRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $claimPython)) { throw 'Environnement absent. Exécutez scripts/setup.ps1.' }
if (-not $Profile) { $Profile = (Get-Content -LiteralPath 'configs/retrieval.json' -Raw | ConvertFrom-Json).default }
$claimProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
try { $claimProbe.Start() }
catch { throw "Le port $Port est occupé ou indisponible. Ouvrez http://localhost:$Port ou choisissez -Port 8502." }
finally { $claimProbe.Stop() }
& $claimPython scripts/doctor.py --profile $Profile --require-ready
if ($LASTEXITCODE -ne 0) { throw 'Préparez les modèles avec python scripts/prepare_models.py.' }
$env:CLAIMGUARD_PROFILE = $Profile
& $claimPython -m streamlit run app/Home.py --server.address 127.0.0.1 --server.port $Port
