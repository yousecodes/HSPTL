# HSPTL 5.1.0 — Release status

**Release type:** local-first clinical education and simulation platform update.  
**Application version:** 5.1.0  
**Production clinical platform:** No. Institutional production blockers remain explicit below.

## 5.1.0 implementation

- Added a reviewer-entered five-domain source reliability appraisal (peer-review/editorial controls, authorship transparency, methods traceability, currency, and conflict/correction controls). Scores are 0–4 and produce weak/limited/moderate/strong *source-control* bands. This is not a licence decision, evidence-certainty rating, clinical-validity score, or endorsement of individual claims.
- Added learner case-practice preferences and deterministic recommendations from the already eligible case pool. The once-per-day Ward Board/Clinic lottery remains shared and unchanged; personalization does not alter the shared draw.
- Added a saved formative case-reasoning submission with optional confidence rating. The learner UI requires submission before revealing the answer. This is not diagnostic-accuracy grading.
- Added 5.1 API endpoints under `/api/v5` and extended the Daily Case Lottery UI.
- Added additive schema migration 35 for source reliability reviews, learner preferences and case attempts.
- Fixed the legacy institutional SQLite startup migration: add `institution_id` columns before dependent indexes, in one explicit transaction; preserve existing rows and make initialization idempotent.
- Hardened Windows installation by cleaning only known interrupted pip-upgrade residue inside `.venv`, disabling pip version-check noise, and running `pip check`.
- Hardened Windows startup by setting `HSPTL_HOME` before imports and running a backend import/migration preflight before opening the browser.

## Verification status

Current consolidated verification on the implementation workspace:

- Python environment, product identity scan, Python compile and content-pack validation: passed.
- Backend tests: **473 passed, 0 failed**.
- Local Uvicorn boot and `/api/health`: passed (HTTP 200).
- Frontend typecheck and production build: **not verified** because `npm ci` timed out and React/type packages were consequently absent in the verification environment. Run `install_hsptl.bat` on a connected Windows machine to install the lockfile dependencies and complete these two gates.
- Launcher contract: the check initially flagged an overly literal `pip check` text expectation; the installer contains the actual `python -m pip --disable-pip-version-check check` command and the comment now makes that contract explicit. The contract correction was not followed by another full release run.

Overall: backend implementation verified; frontend release build remains pending. Do not describe this archive as 9/9 gates passed.

## Remaining limitations

- Source reliability ratings are human-entered metadata and have not been psychometrically validated.
- Personalized recommendations use preferences and prior attempts only; they do not estimate clinical competence.
- The shared daily lottery remains one case per date across Clinic and Ward Board. Personalization applies to additional practice recommendations, not the shared daily selection.
- No production SSO/MFA, hardened multi-tenancy, encryption-at-rest, institutional data isolation or institutional clinical approval is claimed.
- No automated clinical validation or diagnosis accuracy scoring is claimed.
- Institutional terminology, FHIR, CQL and CDS integrations remain bounded adapters requiring local configuration.
