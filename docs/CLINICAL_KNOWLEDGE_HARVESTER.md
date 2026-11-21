# HSPTL Clinical Knowledge Harvester

The former Specialty Harvest command is retained as a backward-compatible entry point, while its provider implementations, query construction, specialty filters, JATS parsing and licence extraction now live in dedicated modules.

## Clinical knowledge profiles

The default remains `case_reports` to preserve existing workflows. The harvester additionally supports:

- `guidelines`
- `systematic_reviews`
- `trials`
- `observational`
- `clinical_evidence`
- `all_open_access`

The query builders scope each profile to the selected specialty. Europe PMC requests records marked open access with full text; PubMed discovery is constrained to its free-full-text subset; Crossref is restricted to records declaring a licence; DOAJ is an open-access journal index; PMC OA searches its archive. These provider indicators are discovery filters, not independent confirmation that a particular licence permits redistribution. Publication type metadata is mapped into UCKS content types only when the provider supplies a recognised type. Unrecognised types remain `other`; they are not guessed. Records without acquired JATS may be retained as clearly labelled metadata/abstract-only documents, with full-text availability set false.

## Module boundaries

- `catalogue.py`: specialty and profile catalogue.
- `query_builder.py`: specialty and publication-type query construction.
- `specialty_filters.py`: conservative specialty relevance filters.
- `parsers.py`: metadata, HTML and JATS parsing primitives.
- `licensing.py`: article-level JATS rights extraction.
- `providers/`: Europe PMC, PMC OA, PubMed, Crossref, DOAJ, journal catalogue, exam-curated and exam-title adapters. Broad knowledge profiles now run through Europe PMC, PubMed, PMC OA, Crossref and DOAJ; provider-specific query semantics and metadata limitations are retained.
- `service.py`: application service and checkpoint reporting.
- `models.py` and `providers/base.py`: typed candidate records and provider interface.
- `acquisition.py`: DOI/PMCID resolution, metadata hydration, JATS acquisition and batch download.
- `pipeline.py`: multi-provider search coordination, filtering, deduplication and local staging.
- `common/http.py` and `common/cache.py`: rate-limited transport, retry policy and persistent metadata caches.
- `cli.py`: command-line orchestration; `engine.py` is now a compact compatibility facade and shared configuration module.

Provider adapters use the shared transport, model and query contracts rather than importing one another. The compatibility facade retains stable import names for older scripts while search, acquisition, parsing, filtering, licensing, persistence and orchestration have distinct modules.

## Provider health

`GET /api/tools/providers/health` returns persisted probe status without making network requests. `GET /api/tools/providers/health?probe=true` performs bounded HTTPS requests to a fixed allow-list of provider endpoints, with redirects disabled and short timeouts. It does not accept arbitrary URLs.

## Governance monitoring

`GET /api/tools/ucks/governance` and `GET /api/ucks/governance/monitoring` provide a read-only summary of review states, lifecycle states, content types, rights declarations, oldest-first rights and clinical review queues, governance proposal previews, connector runs and retrieval indexing. `GET /api/tools/providers/health/history` exposes retained provider probe observations. Repeated non-healthy observations produce operational alerts. The snapshot is operational monitoring, not a clinical quality score.

All externally harvested material remains `harvested`. The acquisition layer retains full-text JATS only when the article-level URI matches the conservative CC0, CC BY or CC BY-SA allow-list and contains no NC/ND restriction. Other or unidentified terms result in metadata/abstract-only staging. This is a technical retention safeguard, not legal clearance: attribution, version-specific terms and local reuse rights still require human review. Automated provider status and retrieval ranking do not validate clinical claims.

## Known limitations

- PubMed and Crossref discovery can yield metadata/abstract-only records when a usable full-text copy is not acquired. Their query filters do not establish reuse permission. Crossref and DOAJ records without a provider-supplied clinical publication type remain `other` rather than being classified solely from the selected search profile.
- Provider health probes establish endpoint reachability only, not provider data completeness or licence validity.
- The acquisition/download and shared transport primitives remain in the compatibility engine while their extraction is completed incrementally.
- Full-text access is constrained by provider availability and the conservative article-level licence allow-list. Scanned documents do not receive automatic OCR.
