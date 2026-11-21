# HSPTL Tools Architecture (Increments 21–24)

## Scope

The data-tool execution path is now separated into API routers, tool application services, a durable execution facade, and UCKS ingestion adapters. The legacy Specialty Harvest implementation is retained behind a compatibility facade while provider and service boundaries are introduced; its internal harvesting engine has not yet been fully decomposed into independently maintained provider implementations.

## Package layout

```text
backend/hsptl_tools/
├── common/
│   ├── paths.py
│   └── provenance.py
├── mednotegen/
│   ├── fhir.py
│   ├── narratives.py
│   ├── normalization.py
│   ├── validation.py
│   ├── exporters.py
│   ├── service.py
│   └── cli.py
├── specialty_harvest/
│   ├── engine.py                 # retained legacy engine; argv-capable
│   ├── service.py                # in-process application service
│   └── providers/                # provider boundary adapters
├── execution.py                  # durable tool-job facade
├── ingestion.py                  # common UCKS ingestion contract
└── jobs.py                       # job-handler registration
```

`backend/hsptl_tools/specialty_harvest.py` remains as a compatibility CLI/import facade. Existing specialty identifiers, harvest filters, licence extraction, output layout and invocation arguments are preserved. The CLI can be run directly from a source checkout.

## Execution lifecycle

1. The API validates the request and enqueues an allow-listed tool job.
2. `ToolExecutionService` owns job lookup, run eligibility and cancellation requests.
3. `JobRunner` claims and executes the durable job.
4. `MedNoteGenService` or `SpecialtyHarvestService` performs the work in-process and reports checkpoints.
5. `ToolIngestionService` sends output through the existing UCKS ingestion adapters.
6. Imported documents remain `harvested`; no tool job promotes content to clinically validated material.

Cancellation is cooperative. A running tool stops at a checkpoint; a cancelled job is not requeued by retry/backoff handling.

## UCKS contract

Each tool ingestion response includes a channel, completion state, review state, synthetic flag where relevant, and provider-specific counts. Original UCKS ingestion counts are retained in job results for compatibility.

- MedNoteGen: `synthea_mednotegen`, synthetic, harvested.
- Specialty Harvest: `clinical_harvester`, externally sourced, harvested.

Provenance, source evidence, licence review requirements and existing document revision semantics remain owned by UCKS adapters.

## Monitoring API

- `GET /api/tools/status`: tool readiness, UCKS summary and recent tool jobs.
- `GET /api/tools/monitoring`: UCKS statistics, registered sources, ingestion channels and job status counts.
- `POST /api/tools/jobs/{job_id}/cancel`: cooperative cancellation request.

## Portfolio → Data Tools

The Data Tools page now displays UCKS source/document/chunk/embedding counts, registered ingestion channels, recent job states, execution progress and cancellation controls. It retains the existing MedNoteGen and Specialty Harvest forms and staged harvested-case list.

## Known limitations

- Specialty Harvest's large historical engine remains in `specialty_harvest/engine.py`. The new provider modules establish adapter boundaries but still delegate to the compatibility engine. Full extraction of provider-specific search/download/parser logic is a separate follow-on refactor and must preserve existing behaviour.
- Provider pagination, cursor checkpointing and continuous sync remain governed by the UCKS connector implementation, not by these tool services.
- The monitoring page reports current counts and source registrations; it is not yet a full per-source operational dashboard with latency charts, alerting or detailed review queues.
- API authentication and reviewer-role enforcement must be assessed across the wider application before exposing administration endpoints beyond the trusted local deployment.
