@echo off
setlocal
cd /d "%~dp0"

rem Prefer 64-bit Python 3.13; Python 3.12 is also supported.
set "PY_MINOR="
py -3.13 -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 set "PY_MINOR=3.13"
if not defined PY_MINOR (
  py -3.12 -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_MINOR=3.12"
)
if not defined PY_MINOR (
  echo HSPTL requires 64-bit Python 3.12 or 3.13. Python 3.14 is not supported by this pinned release.
  echo Install Python 3.12 or 3.13 from python.org, enable the Python launcher, then rerun this installer.
  goto :failed
)
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == tuple(map(int, '%PY_MINOR%'.split('.'))) and struct.calcsize('P') == 8 else 1)"
  if errorlevel 1 (
    echo Existing .venv does not use 64-bit Python %PY_MINOR%. Recreating this disposable environment.
    rmdir /s /q .venv
    if exist ".venv" (
      echo Could not remove the old .venv folder. Close processes using it and retry.
      goto :failed
    )
  )
)
echo Using Python %PY_MINOR%.
if not exist ".venv\Scripts\python.exe" py -%PY_MINOR% -m venv .venv
if errorlevel 1 goto :failed

.venv\Scripts\python.exe scripts\clean_venv_artifacts.py
if errorlevel 1 goto :failed

.venv\Scripts\python.exe -m pip --disable-pip-version-check install --upgrade pip
if errorlevel 1 goto :failed

rem Fail with a clear wheel-resolution error rather than invoking MSVC for pandas/numpy.
.venv\Scripts\python.exe -m pip --disable-pip-version-check install --only-binary=pandas,numpy -r requirements-dev.txt
if errorlevel 1 (
  echo Dependency installation failed. Confirm Python %PY_MINOR% is 64-bit and internet access to PyPI is available.
  echo pandas and numpy are configured to install binary wheels only; no Visual Studio compiler should be required.
  goto :failed
)

rem pip check validates the installed dependency graph before frontend installation.
.venv\Scripts\python.exe -m pip --disable-pip-version-check check
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -c "import fastapi, uvicorn, pandas, requests, pypdf, pytest, httpx; print('Backend and test dependencies verified.')"
if errorlevel 1 goto :failed

where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js and npm are required.
  goto :failed
)
node -e "const [major,minor]=process.versions.node.split('.').map(Number); process.exit((major===20&&minor>=19)||(major>=22&&(major>22||minor>=12))?0:1)" >nul 2>nul
if errorlevel 1 (
  echo Node.js 20.19 or newer in the 20.x line, or Node.js 22.12 or newer, is required.
  goto :failed
)
cd frontend
rem Remove any previous bundle first: a failed dependency/typecheck/build must not leave a stale UI launchable.
if exist "dist" rmdir /s /q "dist"
if exist "dist" (
  echo Could not clear the previous frontend production bundle. Close processes using it and retry.
  goto :failed
)
call npm ci --no-audit --no-fund
if errorlevel 1 goto :failed
call npm run typecheck
if errorlevel 1 goto :failed
call npm run build
if errorlevel 1 goto :failed

echo HSPTL dependencies installed, dependency consistency checked, and frontend checks passed.
echo.
if not defined HSPTL_NO_PAUSE pause
exit /b 0

:failed
echo.
echo HSPTL installation failed. Review the error above.
if not defined HSPTL_NO_PAUSE pause
exit /b 1
