# HSPTL 6.0 — Windows Installer TypeScript Check Fix

## User-reported Windows installer result

The provided `install_hsptl.bat` output confirms that the Windows machine:
- selected Python 3.13;
- upgraded pip successfully;
- installed backend and development dependencies successfully;
- passed Python dependency consistency (`No broken requirements found`);
- installed the frontend npm packages successfully (`added 41 packages in 12s`).

The installer stopped at the first frontend typecheck with:

```text
src/App.tsx:9:7 - error TS6133: 'TagIndexPage' is declared but its value is never read.
```

## Root cause and correction

`frontend/src/App.tsx` declared a lazy import for `TagIndexPage`, but the page was not referenced by the active navigation, route type, or render switch. The unused import declaration was removed. The `TagIndexPage.tsx` module itself was retained.

The frontend contract test had two stale expectations requiring the unused import string in `App.tsx`. Those were corrected: the test now asserts that the unused import remains absent and that the page module file remains available.

No npm dependency versions or lockfiles were changed.

## Verification performed after the correction

- Backend test suite: **506 passed**.
- Python compilation: passed.
- Content-pack validation: passed (1 pack, 8 units, 24 questions, 48 deterministic output recipes).
- Startup preflight and migration/import checks: passed.
- ZIP integrity: passed.
- SHA-256 manifest: all 362 entries verified, zero mismatches.

## Remaining verification

The patching environment could not complete a fresh npm dependency installation (`npm ci` timed out, and an offline retry confirmed Vite 8.3.8 was not cached). Therefore the frontend TypeScript check and Vite production build have **not yet been rerun after this patch**.

The user's Windows log shows that `npm ci` did succeed on their machine before the original TypeScript failure. Retest there by running `install_hsptl.bat` from the patched project. Then run `check_hsptl.bat`. The first known TypeScript blocker has been removed; any subsequent diagnostic must be fixed and retested rather than assumed resolved.

This is a source-fix candidate, not final HSPTL 6.0.0 promotion.
