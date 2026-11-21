# HSPTL 6.0.0 release checklist

## Source and version alignment

- [x] Backend `APP_VERSION`, frontend package metadata and API version metadata aligned to `6.0.0`.
- [x] README merge-conflict markers removed and current workspace layout documented.
- [x] Changelog and release status updated for 6.0.0.
- [x] Corrected Windows Java test adapter, SQLite connection closure, hard-link checks and CRLF batch launchers retained.
- [x] Package excludes virtual environments, dependency trees, build outputs, local databases and secrets.

## Verification and publication

- [ ] Push the exact version-aligned source commit to `main`.
- [ ] Confirm a fresh green Windows clean-install/release workflow for that exact commit.
- [ ] Create annotated Git tag `v6.0.0` only after the exact-commit workflow is green.
- [ ] Publish GitHub Release `v6.0.0` and attach `HSPTL-6.0.0.zip`, SHA-256 checksum and verification report.
- [ ] Perform a clean-install smoke test from the published ZIP.

## Clinical and licensing boundary

- [ ] Continue qualified review of clinical case content and answer keys before using them for supervised teaching.
- [ ] Verify actual source and reuse rights for every external article or image before redistribution or adaptation.
- [ ] Keep learner feedback and validation score separate from clinical competence, entrustment and unsupervised-practice decisions.
