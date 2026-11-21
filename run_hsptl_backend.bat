@echo off
cd /d "%~dp0"
if not defined HSPTL_HOME set "HSPTL_HOME=%USERPROFILE%\HSPTL"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_hsptl.bat first.
  exit /b 1
)
rem Resolve the port (HSPTL_PORT, default 8000) and confirm it is free, so a
rem clash is reported here instead of as a bare uvicorn bind error.
rem The check is by variable, not errorlevel: `set` inside for /f resets
rem errorlevel, so it would not reflect check_port.py's exit code.
set "HSPTL_RESOLVED_PORT="
for /f "usebackq delims=" %%P in (`".venv\Scripts\python.exe" scripts\check_port.py`) do set "HSPTL_RESOLVED_PORT=%%P"
if not defined HSPTL_RESOLVED_PORT (
  rem check_port.py already printed the reason to stderr.
  exit /b 1
)
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port %HSPTL_RESOLVED_PORT% --workers 1
