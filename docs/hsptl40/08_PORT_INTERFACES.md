# 8. Port interfaces: terminology, standards and interoperability

All ports are Python protocols or deterministic adapter functions in the current backend process. They are not deployables.

## Terminology

- `TerminologyPortContract.lookup(term)`: exact concept id/display lookup against the embedded SQLite concept index and small packaged fallback index.
- `TerminologyPortContract.query_ecl(expression)`: abstains unless a Snowstorm ECL adapter is explicitly configured.
- `SnowstormECLPort.expand(expression)`: optional external ECL implementation contract; the package does not implement transport/authentication.
- `TerminologyPort.import_snomed_rf2(...)`: local Snapshot import of active Concept and Description files; requires explicit license confirmation; records edition, effectiveTime and source hashes. It does not import relationship reasoning or implement ECL.

## Standards

- FHIR R4: Observation export from already sourced Pulse observations.
- CQL: export wrapper for reviewed caller-supplied CQL; no interpreter.
- CDS Hooks: descriptor export; no hosted CDS service.

## Interoperability

- LTI 1.3: descriptor/configuration port; OIDC/JWT/JWKS launch verification is not part of this package.
- xAPI: statement construction port; no Learning Record Store.
- SCORM: runtime data mapping; no hosted LMS runtime.

The protocols are in `ports.py`; deterministic mappers are in `standards.py`; the default transport service count remains zero. A future adapter must preserve the same pass/fail/abstain and provenance contracts and must not introduce an untracked clinical decision path.
