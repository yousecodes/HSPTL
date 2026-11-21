@echo off
setlocal
cd /d "%~dp0"
rem Set the data home before *any* Python process imports application settings.
if not defined HSPTL_HOME set "HSPTL_HOME=%USERPROFILE%\HSPTL"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_hsptl.bat first.
  goto :failed
)
if not exist "frontend\dist\index.html" (
  echo Frontend production build is missing. Run install_hsptl.bat first.
  goto :failed
)
rem Exercise the exact backend import and all startup migrations before opening a browser.
.venv\Scripts\python.exe scripts\startup_preflight.py
if errorlevel 1 goto :failed
set "HSPTL_RESOLVED_PORT="
for /f "usebackq delims=" %%P in (`".venv\Scripts\python.exe" scripts\check_port.py`) do set "HSPTL_RESOLVED_PORT=%%P"
if not defined HSPTL_RESOLVED_PORT goto :failed
start "HSPTL" http://127.0.0.1:%HSPTL_RESOLVED_PORT%
call run_hsptl_backend.bat
if errorlevel 1 goto :failed
echo.
echo HSPTL backend stopped.
if not defined HSPTL_NO_PAUSE pause
exit /b 0
:failed
echo.
echo HSPTL failed to start. The startup preflight above should identify the failing import or migration.
if not defined HSPTL_NO_PAUSE pause
exit /b 1
