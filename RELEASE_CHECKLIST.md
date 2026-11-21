# HSPTL release checklist

## Before packaging

- [ ] Run `python scripts/verify_release.py` and confirm Python compilation, backend tests, frontend typecheck/build, identity scan, launcher checks and local backend health check.
- [ ] Confirm the package contains the current HSPTL README, changelog, brand guide and current HSPTL logo assets.
- [ ] Confirm no test databases, user data, credentials, `.env` files, Python bytecode, node_modules or build caches are included.
- [ ] Review legacy migration support and confirm it copies data without deleting the original folders.
- [ ] Review the release notes and `APP_VERSION` in `backend/hsptl_core/config.py`.

## Package

- [ ] Run `python scripts/package_release.py --require-verify` after all verification gates pass.
- [ ] Confirm the generated archive is named `HSPTL-<version>.zip` and includes `MANIFEST.sha256`.
- [ ] Run `unzip -t` or the Windows archive test before sharing.

## Clean-machine smoke test

- [ ] Extract the archive into a clean local directory.
- [ ] Run `install_hsptl.bat` and allow Python and frontend dependencies to install.
- [ ] Run `check_hsptl.bat`.
- [ ] Launch with `start_hsptl.bat` and confirm `http://127.0.0.1:8000` opens.
- [ ] Check Clinic, Rounds, Lab, Ward, Exam Hall and Portfolio.
- [ ] Verify light/dark mode and narrow-screen navigation.
- [ ] Open Rounds → Tagged Report Library and confirm specialty/topic, OSCE/Viva, exam and Clinic content is progressively indexed.
- [ ] Generate a MedNoteGen sample from Synthea FHIR data and verify the output stays labelled synthetic with source references.
- [ ] Run a small Specialty Harvest query and confirm unreviewed content remains in the review queue.

## Clinical and licensing review

- [ ] Verify case answer keys and debriefs with qualified clinical reviewers.
- [ ] Verify question versions, answer explanations and exam blueprints.
- [ ] Verify OSCE station checklists, critical errors and examiner rubrics.
- [ ] Verify the source and reuse licence of every external article and image before redistribution or adaptation.
- [ ] Keep Synthea-derived records labelled synthetic; do not treat coded diagnoses as automatically validated case answers.
