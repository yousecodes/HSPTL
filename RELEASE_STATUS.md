# HSPTL current release status

**Current packaged application identity:** 5.2.0  
**Current development target:** HSPTL 6.0  
**6.0 status:** release-verification candidate; **not promoted**.

The current 6.0 candidate contains the Phase 0–8 work, including governed content generation and external-source discovery, post-use learner validation, clinical event assignments, Daily Case Archive, specialty Rounds, My Profile / Clinical Journey, and learner portfolio export.

## Release gates

| Gate | Status |
|---|---|
| Backend tests (506) | Passed |
| Python compile/content-pack/startup preflight | Passed |
| Local backend boot and `/api/health` smoke test | Passed |
| Frontend source syntax parse (40 TS/TSX files) | Passed — syntax only |
| Frontend semantic TypeScript typecheck | Blocked: npm dependencies could not be installed (`EAI_AGAIN`) |
| Vite production build | Blocked: npm dependencies could not be installed (`EAI_AGAIN`) |
| Native Windows clean installation | Not yet run; workflow added for `windows-latest` |

See `HSPTL_6.0_RELEASE_CANDIDATE_STATUS.md` and `HSPTL_6.0_PHASES_5-8_IMPLEMENTATION_REPORT.md` for exact checks and outstanding release requirements.

**Do not label or distribute this as final HSPTL 6.0.0.** Keep `APP_VERSION` and frontend package version at 5.2.0 until the frontend typecheck/build and native Windows workflow both pass. After those checks, update the release identity, regenerate the archive and manifest, and rerun the complete release verifier.

HSPTL remains a local-first clinical education and simulation application. It is not a clinical decision-support system, a substitute for clinical supervision, or an institutionally accredited platform.
