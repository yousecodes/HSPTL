# HSPTL 6.0.0 — Release status

**Application version:** `6.0.0`  
**Release stream:** 6.0.0 promotion  
**Package status:** source release candidate prepared; final tag/publishing follows a green workflow for this exact versioned commit.

## Release contents

- Seven learner workspaces: Clinic, Lab, Ward, Library, Learning, Exam Hall and Rounds. My Profile, learner progress and the chronological Daily Case Archive are available through the shared workspace shell.
- Persisted Daily Case Lottery is the single daily-case selection path. Clinic and Ward share the same draw; archive projections omit diagnosis and answer payloads.
- Versioned clinical-event and specialty catalogues support configurable learning themes without fabricating cases.
- Deterministic local content generation and content refresh do not require AI models or API keys.
- External-source metadata discovery/import is automated for supported public services; provenance, source permissions, safety screening, clinical validity and post-use learner validation remain separate.
- Version-specific post-use assessment accepts feedback from authenticated learners and contributes evidence to a 0–100 educational validation score with role-aware evidence and domain sign-offs. This is not a clinical competence or entrustment score.
- Seven shared engines remain integrated behind the workspace contracts; the existing local-first modular-monolith deployment is preserved.

## Verification evidence

- Full backend suite for the 6.0.0 version-aligned source: **521 passed, 0 failed**. Static and boot verifier: **6 passed, 0 failed**; details are in `HSPTL_6.0.0_RELEASE_VERIFICATION_REPORT.md`.
- The maintainer reports that the corrected Windows clean-install GitHub Actions workflow completed green before this version-alignment increment. That workflow performs clean Windows installation, Python dependency checks, frontend npm install/typecheck/production build, startup preflight, backend tests and a backend health smoke test.
- **Required final step:** push this version-aligned commit and confirm a fresh green run of `.github/workflows/windows-release-check.yml` for that exact commit before creating the `v6.0.0` tag or publishing the GitHub Release.

## Release limitations

HSPTL is a local-first clinical education and simulation platform. It is not a healthcare provider, clinical decision-support system, independent clinical validation authority or institutionally accredited platform. Learner feedback and validation scores do not establish clinical competence, entrustment or readiness for unsupervised practice. Source reuse must follow the actual licence/terms for each item.
