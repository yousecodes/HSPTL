# HSPTL 6.0 — Release candidate status

**Status:** NOT PROMOTED — frontend and Windows release gates remain open.

## Passed in the available Linux verification environment

- 64-bit Python 3.13.5 runtime and required backend/test dependencies.
- Python compile and content-pack validation.
- Backend test suite: 506 passed.
- Release verifier with frontend disabled: 7 passed, 0 failed.
- Backend startup/health smoke test: `/api/health` returned HTTP 200.
- 40 TypeScript/TSX files parsed with zero syntax diagnostics (syntax-only check).
- Windows launcher contract checks and Python-version compatibility tests.
- Windows unattended installer/check/startup mode and batch file CRLF checks.

## Still required before final 6.0.0 promotion

1. Run `npm ci` successfully from `frontend/package-lock.json` on a connected build host.
2. Run `npm run typecheck` and `npm run build` successfully; verify `frontend/dist/index.html` and static assets.
3. Run `.github/workflows/windows-release-check.yml` on `windows-latest` and obtain a green run. That workflow exercises the actual `.bat` installer and check scripts in a clean Windows workspace.
4. Only after all gates pass, update `backend/hsptl_core/config.py`, `frontend/package.json`, and `frontend/package-lock.json` to `6.0.0`, update final release notes/status and regenerate the final archive/manifest.

## Known environment blockers

- npm registry requests failed with DNS resolution error `EAI_AGAIN`; no complete local dependency tree was available. No production frontend build was possible.
- The current execution host is Linux and provides no Windows command interpreter, PowerShell or Wine. Static launcher checks are not represented as a native Windows installation test.

Until both outstanding gates pass, retain the 5.2.0 internal application identity and distribute only as a 6.0 release-verification candidate. This is not a clinically accredited or institutionally production-approved system.
