@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose up -d qdrant
".venv\Scripts\python.exe" -m claimguard serve %*
pause
