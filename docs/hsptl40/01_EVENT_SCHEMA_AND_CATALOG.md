# 1. Event schema and event catalogue

**Schema ID:** `hsptl.event/1.0`  
**Canonical store:** the existing SQLite `di_events` append-only SHA-256 chain.  
**Write path:** `EventKernel.append()` → payload schema → runtime monitor → existing ledger append.

## Event envelope

The existing ledger row remains the canonical envelope:

| Field | Meaning |
|---|---|
| `seq` | Monotonic SQLite sequence |
| `event_id` | Unique opaque event identifier |
| `event_type` | Versioned event type from the catalogue |
| `payload_json` | Canonical UTF-8 JSON object |
| `occurred_at` | UTC metadata timestamp |
| `previous_hash` | Hash of the preceding event, or genesis digest |
| `event_hash` | SHA-256 of sequence, id, type, payload, timestamp and previous hash |

`event_contracts.py` defines required fields, object/payload rules and the 1 MB boundary cap. Unknown event types, malformed payloads and monitor failures are rejected before the attempted event is appended. The refusal itself is added as `platform.write.prevented`, with attempted type, reason, payload digest, layer and monitor identifier. The original payload is not duplicated into the refusal event.

## HSPTL 4.0 event types

The exact required fields and descriptions are machine-readable in `event_catalogue.json` and available at `GET /api/v4/event-catalogue`.

| Event | Required payload fields | Use |
|---|---|---|
| `platform.pathway.enacted` | `enactment_id`, `state` | Plan begins |
| `platform.pathway.stepped` | `enactment_id`, `state`, `task_id` | Inquiry/decision/action advances |
| `platform.pathway.abstained` | `enactment_id`, `state`, `reason` | Undecidable workflow transition |
| `platform.learning_object.composed` | `object` | Composed object and derivation |
| `platform.route.decided` | `object_id`, `workspace`, `eligibility` | Proven route |
| `platform.guard.checked` | `guard_id`, `decision`, `reason` | `pass` or `fail` guard result |
| `platform.guard.abstained` | `guard_id`, `decision`, `reason` | Undecidable guard result |
| `platform.pulse.action_requested` | `action`, `decision` | Pulse action request/outcome |
| `platform.pulse.observation_recorded` | `source`, `sequence`, `observations` | Connected Pulse snapshot; optional reviewed clinical-state evidence is event-projected for temporal reasoning |
| `platform.plugin.configured` | `workspace`, `config` | Presentation-only skin change |
| `platform.mastery.signal_recorded` | `competency_id`, `learner_id`, `signal`, `evidence_ref`, `reviewer` | Formative event fold input |
| `platform.write.prevented` | `attempted_event_type`, `reason`, `payload_digest`, `layer` | Immutable refusal audit |
| `platform.terminology.imported` | `edition`, `effective_time`, `concept_count`, `description_count`, `file_hashes` | RF2 import provenance |

The event catalogue is intentionally a compact event contract, not a new event service or a second data store. G adds the canonical `platform.pulse.observation_recorded` event so the ASP temporal module can derive states from source-labelled Pulse observations; patient-scoped clinical-state evidence is only projected when the PROforma plan declares the matching patient/subject id. Historical HSPTL 3.0 event types continue to use the same event ledger. Existing legacy repository migrations are not represented as complete by this event contract.


## 4.0.2 learning and authoring events

The canonical event catalogue additionally includes:

- `platform.learning.unit_opened` and `platform.learning.quiz_submitted` for local learner activity and formative, objective-linked quiz results;
- `platform.curriculum.draft_created` and `platform.curriculum.activated` for versioned curriculum composition and reviewer activation; and
- `platform.scenario.draft_saved` and `platform.scenario.published` for scenario package lifecycle and configured clinical-review publication.

These are appended through the same EventKernel and included in the checked-in `event_catalogue.json`. Progress and active curriculum state are derived by folding these events.
