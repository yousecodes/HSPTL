# HSPTL — Windows clean install and frontend production build

This guide describes the same checks used by `.github/workflows/windows-release-check.yml`.

## Supported toolchain

- 64-bit Python 3.13 (Python 3.12 is also supported by `install_hsptl.bat`)
- Node.js 22.16.0 for the release workflow (the frontend accepts Node 20.19+ or 22.12+)
- npm supplied with Node.js
- Network access to PyPI and `registry.npmjs.org` during dependency installation

Do not replace `npm ci` with `npm install` for release verification: `npm ci` installs the exact dependency graph pinned by `frontend/package-lock.json`.

## Local Windows clean-install test

1. Extract the source ZIP into a **new, empty application folder**. Do not run this test over the existing project folder because an existing `.venv`, `frontend/node_modules` or `frontend/dist` would make it an upgrade test rather than a clean-install test.
2. Open PowerShell in the extracted folder and run:

```powershell
$ErrorActionPreference = 'Stop'

# Keep this verification run isolated from the normal user database.
$env:HSPTL_HOME = Join-Path $env:LOCALAPPDATA ("HSPTL-CleanInstall-" + [guid]::NewGuid().ToString('N'))
$env:HSPTL_NO_PAUSE = '1'

foreach ($path in @('.venv', 'frontend/node_modules', 'frontend/dist')) {
    if (Test-Path $path) { throw "Not a clean source tree: $path already exists." }
}

cmd.exe /d /c install_hsptl.bat
if ($LASTEXITCODE -ne 0) { throw "Installer failed with exit code $LASTEXITCODE" }

cmd.exe /d /c check_hsptl.bat
if ($LASTEXITCODE -ne 0) { throw "Release checks failed with exit code $LASTEXITCODE" }

if (-not (Test-Path 'frontend/dist/index.html')) { throw 'Production frontend entrypoint is missing.' }
Write-Host 'PASS: Windows clean install, frontend build and release verification.'
```

The installer runs `npm ci`, TypeScript checking and the Vite production build. The release check repeats frontend checks, executes the full Python test suite and performs a backend health smoke test. The startup preflight can also be run directly:

```powershell
& .\.venv\Scripts\python.exe scripts\startup_preflight.py
if ($LASTEXITCODE -ne 0) { throw 'HSPTL startup preflight failed.' }
```

The install script and `npm run build` remove any old `frontend/dist` before building. This is intentional: a failed typecheck or build must not leave a stale bundle that can be mistaken for the updated application. Do not start HSPTL if installation reports a failure.

## Frontend-only production build

From the project root:

```powershell
Push-Location frontend
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }

    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'TypeScript typecheck failed.' }

    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Vite production build failed.' }

    if (-not (Test-Path 'dist/index.html')) { throw 'Vite did not emit dist/index.html.' }
    Write-Host 'PASS: frontend production build.'
}
finally {
    Pop-Location
}
```

If `npm ci` fails with DNS/network errors, the build has not been tested. Restore access to `registry.npmjs.org`, then rerun from `frontend` after removing partial dependencies:

```powershell
Remove-Item -Recurse -Force node_modules, dist -ErrorAction SilentlyContinue
npm ci --no-audit --no-fund
npm run typecheck
npm run build
```

## Getting a green native Windows GitHub Actions run

The workflow runs on `windows-latest` and now triggers on pushes, pull requests and manual dispatch. It starts from a clean checkout and checks that `.venv`, `frontend/node_modules` and `frontend/dist` do not exist before installation. It then runs:

1. Windows `install_hsptl.bat` (Python dependencies, `pip check`, `npm ci`, TypeScript and Vite build)
2. `scripts/startup_preflight.py` using an isolated data home
3. Windows `check_hsptl.bat` (release verification, backend tests and HTTP health smoke test)
4. Checks the production `frontend/dist/index.html` exists and uploads `frontend/dist` as a workflow artifact

Commit the updated project and push it to the GitHub repository. Open **Actions → HSPTL Windows clean-install and release verification** and inspect the run for that commit. A green job is the evidence of a successful native Windows clean-install. The uploaded artifact is named `hsptl-windows-python-3.13-production-build`.

A local or Linux test cannot mark the GitHub-hosted Windows run green; that status is produced only after the Windows runner completes the workflow.
