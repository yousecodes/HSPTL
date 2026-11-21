@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment missing; run install_hsptl.bat
  goto :failed
)
.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto :failed
.venv\Scripts\python.exe scripts\verify_release.py
if errorlevel 1 (
  echo HSPTL release verification failed. Review the diagnostics above; do not package this build.
  goto :failed
)
echo All HSPTL release verification gates passed.
echo.
if not defined HSPTL_NO_PAUSE pause
exit /b 0

:failed
echo.
echo HSPTL checks failed. Review the error above.
if not defined HSPTL_NO_PAUSE pause
exit /b 1
