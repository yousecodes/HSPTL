# HSPTL Windows CI Fix Report

## Changes made

- Replaced the Unix-only shell-script Java test stub with an injected deterministic Java detector for tests using `FakeSyntheaAdapter`. Production preflight continues to detect and execute the configured real Java runtime.
- Changed `FactoryStore` connections to commit/roll back and always close, preventing SQLite handles from keeping temporary database files locked on Windows.
- Strengthened local-source hard-link detection on Windows by querying the file handle's native link count. If the count cannot be established, the scanner refuses to read the file.
- Added `.gitattributes` rules and CRLF endings for the Windows batch launchers so Windows clean-install checks see native line endings.
- Added a regression test confirming that the factory's SQLite connection is closed after its context exits.
- Regenerated `MANIFEST.sha256` and packaged the complete source tree.

## Verification

- Focused synthetic-data, local-source and release-verification tests: **189 passed**.
- Full backend suite: **521 passed, 0 failed**.
- Static release checks (Python environment, product identity scan, Python compile, content-pack validation, launcher contract): **5 passed, 0 failed**.
- ZIP integrity: all **399** source-file manifest records verified; no missing or mismatched files.
- Windows batch launchers in the ZIP: CRLF line endings verified.

## Not re-verified in this environment

- `npm ci` did not complete in this environment, so frontend typecheck and Vite build were not rerun here. The earlier Windows run reported those frontend steps passing.
- The GitHub Actions Windows runner has not yet been rerun against this corrected ZIP. Its result is the final confirmation of native Windows behaviour.
