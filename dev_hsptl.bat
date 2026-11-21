@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_hsptl.bat first.
  exit /b 1
)
start "HSPTL API" cmd /k "cd /d "%~dp0" ^&^& call run_hsptl_backend.bat"
cd frontend
npm run dev
