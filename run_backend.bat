@echo off
cd /d "%~dp0"
if not defined HSPTL_HOME set "HSPTL_HOME=%USERPROFILE%\HSPTL"
set "HSPTL_HOME=%USERPROFILE%\HSPTL"
for /f "usebackq delims=" %%P in (`".venv\Scripts\python.exe" scripts\check_port.py`) do set "HSPTL_RESOLVED_PORT=%%P"
if not defined HSPTL_RESOLVED_PORT (
  echo HSPTL failed to resolve a usable port.
  exit /b 1
)
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port %HSPTL_RESOLVED_PORT% --workers 1
