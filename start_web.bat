@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Demarrage de ClaimGuard AI (React + FastAPI)...
".venv\Scripts\python.exe" scripts\run_web.py %*
echo.
echo Le serveur s est arrete. Lisez le message ci-dessus.
pause
