@echo off
echo Starting SkyGuard API...
cd /d "%~dp0"
set ALLOWED_ORIGINS=http://localhost:5173
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
