# HSPTL 6.0 — Final Navigation, Clinical Events and Case Archive Addendum

**Status:** Product/implementation specification. This document refines and supersedes conflicting navigation and daily-case placement proposals in the earlier HSPTL 6.0 blueprint. It is not evidence that these changes are already implemented.

## 1. Final navigation decision

### 1.1 The logo is Home

- Clicking the HSPTL monogram always navigates to the **Daily Clinical Case Home**.
- Home is a route/workspace, but is **not** a visible navigation-bar item.
- The Home workspace is the daily clinical challenge itself, not a generic overview dashboard.
- The daily case remains available if the user navigates elsewhere and returns; it must never redraw on navigation, refresh or restart.
- If no eligible case exists, show an honest no-case state and preserve the archive and other learning destinations.

### 1.2 Main navigation

Home, Profile and Progress must not appear as navigation-bar destinations. The learner-facing navigation contains the clinical workspaces only:

1. Clinic — case reports and clinical reasoning outside the featured daily challenge.
2. Lab — OSCE, examination and diagnostic stations.
3. Ward — practical skills and bedside workflows.
4. Library — clinical pearls and quick reference.
5. Learning — structured lectures and learning pathways.
6. Exam Hall — question bank and mock examinations.
7. Rounds — specialty-indexed learning material.

Other educator/administrator destinations remain in Create & Manage / All Modules and are not promoted into the learner navigation.

### 1.3 Profile and Progress are one destination

- A compact **My Profile** control sits at the top-right of the workspace header.
- Its icon is a stethoscope.
- The control opens one combined Profile destination with internal tabs: **Profile** and **Progress**.
- Progress is removed from the main navigation bar.
- Profile contains identity/preferences, learner stage, specialty interests, goals, saved items, achievements, privacy and account settings.
- Progress contains educational activity, objectives practised, review queue, case reasoning, OSCE, skills, simulations and retention indicators.
- XP, badges and streaks may be summarised in Profile, but educational evidence and review detail belong in Progress.

### 1.4 Archive control placement

- A visible **Archive** button appears in the Home/Daily Case workspace header, directly opposite the My Profile control (top-left of the right-hand action cluster, with My Profile at the far right).
- Archive is not a main navigation item.
- It opens the Daily Case Archive, not the specialty directory or general content library.
- Archive remains accessible when today's lottery has no eligible case.

## 2. Daily Clinical Case Home

The Home workspace should prioritize, in this order:

1. Today's selected clinical event (only when a special event was selected).
2. Presenting complaint and patient age (never reveal diagnosis in the pre-debrief teaser or archive list).
3. Specialty, learner level/difficulty, estimated duration and progress state.
4. Continue case / Start case action.
5. Source/provenance summary where display is permitted.
6. Archive action in the workspace header.

Do not put a separate metrics dashboard above the case. Small progress indicators can be shown after the main challenge, but must not displace it.

## 3. Variable Clinical Events Catalogue

### 3.1 Catalogue is data-driven, not hard-coded into a weekday schedule

HSPTL must maintain a versioned, editable catalogue of special clinical events. The event set may grow, be revised, paused or retired without a frontend release. Examples include:

| Event | Icon concept | Visual theme | Eligible clinical areas |
|---|---|---|---|
| Trauma Call | Siren / emergency lights | Red-orange emergency theme | Trauma, Emergency Medicine, Surgery |
| Emergency Room Shift | Ambulance / activity | Amber and clinical blue | Emergency Medicine, Acute Care |
| Outbreak Investigation | Microbe | Teal/green infection theme | Infectious Diseases, Microbiology, Public Health |
| ICU Deterioration | Heart-pulse | Deep blue / critical-care theme | Critical Care, Respiratory, Cardiology |
| Maternal Emergency | Mother-and-child | Rose theme | Obstetrics, Maternal-Fetal Medicine |
| Paediatric Emergency | Baby | Soft violet/blue theme | Paediatrics, Paediatric Emergency |
| Diagnostic Mystery | Search / microscope | Indigo theme | Cross-specialty |
| Medication Safety Event | Pill / shield | Purple theme | Pharmacology, General Medicine, Pharmacy |
| Neurology Stroke Call | Brain / activity | Indigo-blue theme | Neurology, Emergency Medicine |
| Renal Challenge | Kidney | Aqua theme | Nephrology, Internal Medicine |

These are catalogue examples, not a permanent exhaustive list. A variable catalogue means administrators/educators can add, edit, enable, disable or retire events using data, not code changes.

### 3.2 Event record contract

Each event definition should include:

- `event_id`, `event_version`, `name`, `short_label`, `description`;
- `icon_key`, `theme_key`, accessible colour tokens and optional decorative motif;
- eligible specialty IDs, topic tags, presentation tags and content types;
- target learner levels and difficulty range;
- learning objectives and expected activity format;
- active state, effective dates, optional duration and recurrence/cooldown policy;
- selection weight / priority, maximum consecutive appearances and configured frequency limits;
- event content eligibility rules and fallback behaviour;
- author, reviewer, approval state and timestamps.

Event title, icon, theme and version are snapshotted onto the daily assignment. Later catalogue edits must not retrospectively change the appearance or meaning of archived events.

### 3.3 Random day-to-day event selection

- HSPTL selects an event randomly from the **currently eligible event set**, not from a fixed Monday-to-Sunday rota.
- An event is eligible only if at least one clinically approved, rights-cleared, privacy-cleared case is available for it.
- Random selection must be auditable. Use an operating-system cryptographically secure random source for production selection; do not use case IDs, diagnosis strings, lexical sorting or a predictable date hash as the random source.
- Selection policy may use configured weights and a short event cooldown to reduce monotonous repetition. This is weighted randomness, not a guarantee that every event appears equally often.
- Persist the chosen event, chosen case, event version, case version, candidate counts, pool snapshot hash, selection policy version, selected timestamp and reason codes.
- The same date and scope must resolve to the same persisted assignment after refresh, restart or simultaneous requests. Selection is random at assignment time, idempotent afterwards.
- Personal/local mode uses the local learner profile scope. Classroom mode may use a cohort-wide shared event with individual learner attempts.
- If no event has a matching eligible case, select an ordinary eligible daily case without a special event. If no ordinary case qualifies either, return an explicit no-eligible-case state. Never fabricate a case or attach an unrelated event to fill the slot.
- Any manually forced event or case must be recorded as an administrative override, never represented as random selection.

### 3.4 Event-themed daily case UI

The Home case banner inherits the event's theme and icon. For example, Trauma Call uses a siren icon and emergency red-orange accents; Outbreak Investigation uses a microbe icon and teal accents.

- Theme changes are limited to header/banner, icon treatment, accent details and event-specific labels.
- Body text, form controls, severity colours and accessibility contrast remain consistent with the global design system.
- An event label and text description must always accompany its icon; colour/icon alone must never convey clinical urgency or case meaning.
- The same theme snapshot appears on the Archive entry and event debrief.

## 4. Daily Case Archive

### 4.1 Organize by date, not diagnosis

The archive is a chronological journal of past daily challenges. Its primary group key is the local calendar date (newest first). It must not group, sort, label or filter the list by diagnosis.

Each archive row/card displays only:

- day and date;
- presenting complaint;
- patient age at the encounter (not date of birth);
- specialty and difficulty, where available;
- special event name, icon and theme, when applicable;
- learner status (not started / in progress / completed);
- a link to open the case/debrief if the learner is permitted to access it.

The archive list must not display the diagnosis, final answer, answer key or diagnosis-derived title. Search and filters may use date, presenting complaint, specialty, event and difficulty, but not reveal hidden diagnoses. A case opened for review can display its debrief according to the same answer/reveal policy as other case practice.

### 4.2 Case age means patient age

For clarity, “age” in the archive means **patient age at the time of the case**, not how old the case record is. Store a safe age display or age value/unit (for example, `68 years`, `8 months`, `newborn`). Do not store or derive this from a date of birth. If the source does not provide age, display “Age not stated”; do not infer it.

### 4.3 Complaint must be a dedicated field

Do not parse the complaint from the diagnosis, title or free-text stem at display time. Add a dedicated, reviewed `presenting_complaint` field to the case contract. If an imported source has no safe complaint field, a human editor may write a concise, source-faithful presentation label. Otherwise display “Presenting complaint not stated”.

### 4.4 Archive entry example

**Friday · 21 November 2026**

- **Event:** Trauma Call — siren icon, emergency theme
- **Presenting complaint:** Road-traffic collision with chest pain
- **Patient age:** 34 years
- **Specialty:** Emergency Medicine / Trauma
- **Status:** Completed

No diagnosis is shown in the archive tile. The diagnosis and reasoning are only available within the appropriate case/debrief reveal state.

## 5. Provenance and debrief source panel

Every daily case debrief must display where the case came from:

- open-access journal: article title, authors, journal, publication year, DOI/PMID/PMCID, publisher URL, exact reuse licence and adaptation note;
- educational website: organization/publisher, page title, version/update date, URL, access date and reuse rights;
- imported database: database name, dataset/version, non-identifying record key, import timestamp and licence/permission;
- synthetic: Synthea/generator version, run ID, dataset reference and explicit synthetic label;
- derived: all source components, transformation summary and DERIVED label;
- original HSPTL-authored: authoring record and evidence/source links for clinical claims.

“Open access” is not itself a reuse licence. If reuse/adaptation rights are not established, HSPTL must use link-only treatment and must not reproduce protected article text or images. Retraction, correction, supersession, rights or privacy changes must be reflected in eligibility and archived provenance.

## 6. Suggested data/API changes

### Case fields

Add an additive schema migration for:

- `presenting_complaint` (nullable text, reviewed display field);
- `patient_age_value` and `patient_age_unit` (or a validated `patient_age_display`); no date of birth;
- `specialty_id`, `topic_tags`, `presentation_tags`;
- case content/version digest, source references, rights, publication and clinical review states;
- optional case eligibility tags used by event matching.

### Event and assignment tables

Create a versioned `clinical_event_catalogue` and a `daily_clinical_assignments` (or equivalently named) table. Each assignment has a unique date + scope key and stores event/case snapshots, pool digest, policy version and audit metadata. Use transactions and uniqueness constraints to prevent duplicate daily assignments under concurrency.

### API surface

- `GET /api/daily-case/today` — persisted daily assignment and non-revealing case metadata;
- `GET /api/daily-case/archive` — paginated, date-grouped history, complaint/age/event only;
- `GET /api/clinical-events` — learner-safe active event catalogue;
- reviewer/admin-gated create/update/retire endpoints for event catalogue entries;
- existing case reveal/attempt/debrief endpoints remain server-gated.

Do not expose a case diagnosis or reveal payload in archive responses.

## 7. Acceptance tests

### Navigation and profile

- Logo click always returns to Daily Clinical Case Home.
- Home, Profile and Progress are absent from main navigation.
- My Profile uses the stethoscope icon in the workspace header.
- Profile tabs include Profile and Progress; Progress can no longer be opened as a separate nav item.
- Archive control is visible in Home's header opposite My Profile and opens Daily Case Archive.

### Random clinical events

- Catalogue changes take effect without frontend redeployment.
- Only events with at least one eligible case can be selected.
- Production uses a CSPRNG; tests inject a seeded RNG.
- Frequency/distribution tests compare observed counts with configured weights and tolerances across sufficiently large simulated runs.
- Event cooldown and weight configuration are applied and observable in audit metadata.
- Concurrent requests create exactly one assignment per date/scope.
- Refresh/restart returns the same saved assignment.
- When an event has no eligible case, it is excluded; when no event qualifies, ordinary daily case selection works; when no case qualifies, system abstains.
- Administrative overrides are distinguishable from random draws.

### Archive

- Entries are grouped newest-first by local day/date.
- Every entry shows presenting complaint and patient age if known.
- Diagnosis is absent from list title, fields, search index and API payload.
- Missing complaint/age display explicit unknown states; never infer from diagnosis or DOB.
- Event name, icon and theme are preserved by snapshot for historical entries.
- Archive does not disclose answers before reveal permissions allow them.

### Provenance

- Debrief identifies journal, website, imported database, synthetic, derived or HSPTL-authored origin.
- Exact URL/identifier and rights/licence status are displayed when available.
- Link-only content is never copied into HSPTL.
- Missing provenance, uncertain rights or unresolved privacy flags block eligibility according to policy.

## 8. Implementation order

1. Refactor navigation and header placements; turn Home into the Daily Clinical Case workspace.
2. Merge Profile and Progress into one tabbed destination.
3. Add dedicated presenting complaint and patient-age fields with migration-safe backfill (unknown remains unknown).
4. Add event catalogue and random persisted daily assignment service.
5. Add the chronological Daily Case Archive with event themes/icons and no diagnosis leakage.
6. Add provenance-rich case debrief source panels.
7. Run backend tests, frontend typecheck/build, migration/concurrency tests, statistical event-selection tests, answer-leak tests and a clean Windows installation check.

## 9. Non-negotiable safety and integrity rules

- No diagnosis in archive tiles or pre-debrief case teasers.
- No patient date of birth in the archive data model; show age at encounter only.
- No event without a matching approved, rights-cleared and privacy-cleared case.
- No fabricated case to fill a special event slot.
- Random assignment is recorded once and remains stable for that date/scope.
- Event themes must not obscure clinical warnings, reduce contrast or imply unsupported urgency.
- XP, levels, badges and streaks are educational engagement signals, not clinical competence credentials.
- Daily case sources and reuse rights are visible and traceable in the debrief.
