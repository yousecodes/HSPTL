@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_hsptl.bat first.
  exit /b 1
)
.venv\Scripts\python.exe scripts\run_ucks_scheduler.py --loop --interval-minutes 15
