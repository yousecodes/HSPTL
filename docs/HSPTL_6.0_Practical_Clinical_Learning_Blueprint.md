# Executive decision

HSPTL should evolve through a focused 6.0 programme called **Practical Clinical Learning & Mastery**. The objective is not to add more modules. It is to make the existing capabilities feel like one coherent learning product.

The product should have three learner-facing modes:

1. **Learn** — concise, source-linked teaching organised around observable objectives.
2. **Practice** — retrieval questions, structured cases, viva, OSCE, chart interpretation and communication tasks.
3. **Simulate** — bounded synthetic clinical scenarios with prebrief, staged information, learner actions, a replayable trace and a planned debrief.

The dashboard is the starting point, not a catalogue of every feature. The primary navigation should expose these three modes and a compact home entry. Authoring, review, synthetic-data operations, source governance and institutional settings belong in a secondary **Create & Manage** area.

The learning model is a connected cycle:

**Learn a concept → retrieve it → apply it to a case → practise a decision or skill → debrief → revisit the weak objective.**

This design uses HSPTL's existing React/FastAPI/SQLite modular monolith, content packs, event ledger, deterministic content factory, Learning Library, simulation runtime, assessment pages, OSCE workflow, source registry and synthetic-data tools. It does not introduce a second rule engine, a new deployable service, a required cloud model, a vector database or mandatory API keys.

A crucial boundary remains: completion, quiz performance, rubric points and synthetic simulation results are educational evidence. They do not by themselves establish clinical competence, entrustment, readiness for unsupervised practice or fitness to treat a real patient.

# Product definition and verified baseline

## Document use and evidence labels

This is an implementation blueprint, not a clinical guideline, legal opinion, accreditation decision or claim of clinical validation. It distinguishes:

- **Verified baseline:** directly observed in the inspected HSPTL 5.1.0 source tree or its release documentation.
- **Research-supported direction:** supported by a named external source in the references.
- **Product recommendation:** a design decision proposed for HSPTL; it still requires implementation and validation.
- **Local decision required:** depends on curriculum, jurisdiction, institutional policy, clinical ownership or deployment environment.

External research was checked on 20 November 2026. The references include current 2025–2026 material where available. Standards and evidence must be rechecked at implementation and release time.

## Product mandate

## Product promise

HSPTL helps a learner move from knowing clinical facts to applying them in structured, safe educational practice. It should answer four questions on every screen:

- **What am I practising?** One clear objective or task.
- **What do I need to do?** A small number of explicit actions.
- **How did I do?** Evidence-linked feedback, not an unexplained score.
- **What should I practise next?** A useful next activity or review due date.

A learner should not need to understand the internal names of the six historical workspaces to complete a learning session.

## Product users

| User | Primary job | Product support |
|---|---|---|
| Medical / health-professions student | Build knowledge and practise reasoning | Learn, retrieve, case practice, OSCE and simulation |
| Intern / early-career clinician in training | Rehearse common presentations, prioritisation and communication | Acute cases, handover, reassessment, simulation and feedback |
| Educator / clinical author | Build and review safe teaching material | Content Factory, scenario authoring, review queue and curriculum composition |
| Programme lead / administrator | Govern learning material, privacy and deployment | Roles, review history, retention, backups and cohort reporting after security readiness |

The initial default is a single learner working locally. Cohort and institutional deployment is a later release track, not a prerequisite for a useful personal learning application.

## What HSPTL is not

HSPTL is not an electronic health record for real patients, a prescribing platform, an autonomous diagnostic engine, a replacement for clinical supervision, an accredited OSCE examination system or a validated physiological digital twin. It must not be presented or configured as live clinical decision support.

## HSPTL 5.1.0 verified baseline

The 5.1.0 repository was inspected directly. The local backend test suite was run during this task: **474 tests passed**. This is software-test evidence only. The release notes still identify the full dependency-backed frontend typecheck and production build as not verified in the earlier release environment; those gates must be completed on the Windows installation before calling a new release build-ready.

## Existing capability to preserve

| Area | Verified baseline | 6.0 direction |
|---|---|---|
| Runtime | React + TypeScript + Vite frontend; FastAPI backend; SQLite; one modular monolith | Preserve the deployment model and existing contracts |
| Learning Library | A bundled Acute Care Foundations pack with 8 units; README describes 24 formative retrieval questions, objectives, cases, teaching points, pitfalls, viva, OSCE outlines and reflection prompts | Expand reviewed coverage and link every activity to objectives |
| Content Factory | Deterministic, local, model-free output generation; six draft formats; up to 72 drafts per batch; 48 derivatives from the eight-unit starter pack | Keep deterministic baseline; add better review, provenance and authoring UX |
| Learning events | Unit-open and quiz-submission events, idempotency, derived per-objective progress projections | Evolve activity records into longitudinal evidence; do not label an attempt as mastery |
| Curriculum composition | Unit selection, prerequisite graph validation, topological ordering and PROforma-gated curriculum activation | Make curriculum paths visible as optional guided journeys |
| Clinical case practice | Clinic and Ward Board share a daily case draw; learner reasoning is saved before answer reveal; confidence is optional; practice preferences influence extra recommendations | Reuse the same reasoning form and feedback pattern across cases |
| Simulation | A bounded synthetic adult moderate-asthma vertical slice: seeded runs, staged findings, typed actions, integer simulation clock, delayed PEF result, event trace, documentation, formative rubric, replay and debrief | Extend through more reviewed scenarios; do not claim general physiology simulation |
| Scenario authoring | JSON template, local drafts, structural validation, trace-matrix endpoint and reviewer-gated publication | Build educator-friendly authoring on the existing package contract |
| Assessment | Exam Centre, question review, OSCE surface and rubric helpers | Unify evidence and improve assessment design/quality controls |
| Synthetic data | Local Synthea-driven factory with pinned artifact checks, 16-stage resumable pipeline, six validation dimensions, quarantine and provenance manifest | Turn datasets into structured chart-literacy and clinical reasoning exercises |
| Governance | Local account/session, role and institution concepts; privacy/retention operations, backup/recovery, safety-case review and bounded standards adapters | Treat these as governance foundations, not proof of production readiness |
| Source management | Rights-aware registry, local folders and reviewer-entered source reliability appraisal | Keep rights, source reliability, evidence certainty and clinical approval separate |

## Important limitations already documented

- The starter curriculum is a beginning, not enough breadth for a comprehensive clinical learning platform.
- A quiz attempt may currently satisfy a curriculum sequencing predicate. That is an activity gate, not a validated mastery threshold.
- The single asthma simulation is a bounded authored teaching model. Its state transitions are pedagogical fixtures, not empirically calibrated predictions of real patients.
- A configured reviewer token does not independently prove that a reviewer is clinically qualified or authorised.
- Recommendations are deterministic suggestions from preferences and attempts, not a model of clinical competence.
- Existing institutional governance features do not establish production SSO/MFA, enterprise encryption at rest, hardened multi-tenant isolation or institutional clinical approval.
- FHIR, terminology, CQL and CDS-related adapters are bounded integration surfaces, not evidence of complete standards conformance.
- Some historic workspace pages and routes may overlap in purpose. The blueprint recommends simplifying the learner-facing information architecture while preserving useful capabilities behind it.

**Design consequence:** 6.0 should be an integration, curation, UX and validation programme over the existing foundation—not a rewrite and not a feature-count competition.

# Research basis and product implications

## Simulation must be designed around measurable outcomes

The INACSL Healthcare Simulation Standards of Best Practice fourth edition includes standards for simulation design, prebriefing, facilitation, outcomes/objectives, evaluation, debriefing, professional integrity, operations and simulation-enhanced interprofessional education. The current INACSL site identifies several cornerstone standards as revised in 2025. The simulation design criteria include needs assessment, measurable objectives, alignment of the modality to the objectives, scenario design, prebriefing, debriefing or feedback, evaluation and pilot testing [R1, R2].

**HSPTL implication:** every simulation needs an objective-to-action-to-evidence map before it is built. Realism is not a goal by itself. A short, lower-fidelity case can be excellent when it is aligned to the learning objective and debriefed well.

## Retrieval and spacing deserve a first-class place

A 2024 systematic review of distributed and retrieval practice in health-professions education included 56 eligible articles and 63 experiments; 43 experiments showed significant benefits over control or comparison conditions. The authors noted variation in interventions and outcomes [R3]. A 2026 systematic review and meta-analysis of spaced repetition in medical education included 14 studies, with 13 studies and 21,415 learners in the meta-analysis; it reported a pooled standardised mean difference of 0.78 (95% CI 0.56–0.99) in favour of spaced repetition versus standard study methods [R4]. These findings support scheduled retrieval as a reasonable design choice, but do not prove that every flashcard format or interval is optimal, nor that knowledge recall alone equals clinical competence.

**HSPTL implication:** create a simple **Review due** queue driven by objective-level recall evidence. Use learner response and elapsed time to schedule revisits. Keep the interval algorithm versioned and explainable. Do not overfit the UI to algorithm settings.

## Clinical reasoning improves through active, guided practice

A systematic review first published on 8 September 2026 included 27 studies across medicine, dentistry, nursing and physiotherapy. It reported that case-based learning, illness-script teaching, simulation and deliberate practice with feedback were generally associated with improved clinical reasoning or diagnostic performance, while passive approaches had mixed or limited effects. The synthesis was narrative and the authors called for better longitudinal evaluation and standardisation [R5].

**HSPTL implication:** do not make long reading pages the main experience. Teach a concise concept, then ask the learner to retrieve it, interpret a case, justify decisions and reflect on alternatives.

## Debriefing is part of the learning activity

The PEARLS framework integrates learner self-assessment, focused discussion and directive feedback/teaching into a blended healthcare simulation debrief [R6]. INACSL's current standard states that simulation-based education should include a planned debriefing process, which can include feedback, debriefing and/or guided reflection [R1].

**HSPTL implication:** a scenario is incomplete until its debrief is written and tested. The debrief should be available immediately after the run, tied to events in that run, and end with one or two practical actions for the learner.

## Patient safety should be threaded through the curriculum

WHO's multi-professional Patient Safety Curriculum Guide was designed for medicine, dentistry, midwifery, nursing and pharmacy. It contains 11 teachable patient-safety topics and a teacher-facing guide for curriculum planning [R7]. The AAMC Core EPAs provide an example of organising expectations around professional activities that a new graduate should be ready to perform with appropriate supervision [R8]. These are useful reference frameworks, not universal rules for every jurisdiction or profession.

**HSPTL implication:** map learning objectives to safety behaviours—recognising deterioration, escalating concerns, medication safety, infection prevention, handover, teamwork, speaking up, documentation and learning from error. Label any EPA/competency mapping as a configurable reference map pending local adoption.

## Simplifying the interface protects attention

The W3C WCAG 2.2 Recommendation provides testable accessibility criteria across perceptibility, operability, understandability and robustness [R9]. W3C cognitive-accessibility guidance recommends clear purpose, familiar controls, consistent patterns and explicit relationships between actions and their effects [R10]. Nielsen Norman Group's cognitive-load guidance recommends reducing extraneous load through less visual clutter, familiar mental models and sensible defaults while preserving the meaningful effort of the task [R11].

**HSPTL implication:** simplify the navigation, repeated explanations, cards and tool labels—not the clinical reasoning task. Do not shrink clinical content until it becomes hard to read. Make the UI quiet so the clinical information can be demanding.

## Synthetic data is useful but not automatically risk-free

Synthea describes its output as realistic fictional patients and healthcare records in formats including FHIR [R12]. A 2025 iScience study examined privacy, fidelity and utility trade-offs across synthetic patient-data models and reported that these dimensions can vary; the authors argue for explicit evaluation rather than assuming that synthetic data is automatically private or useful [R13].

**HSPTL implication:** keep the Synthea-first educational data path, identify all datasets as synthetic, retain provenance and avoid importing identifiable patient information. Any synthetic data derived from real source records needs a separate privacy risk assessment and utility evaluation.

## Interoperability should be pragmatic

HL7 FHIR R5 defines Observation as a resource for measurements and simple assertions about a patient or other subject; it is a workflow event resource [R14].

**HSPTL implication:** use FHIR import/export as a boundary for educational patient records and scenarios. Do not build a full FHIR server or terminology platform before there is a concrete interoperability use case and conformance test plan.

# Product design principles

1. **One clear next action.** Each learner screen has one primary action and, at most, a small number of secondary actions.
2. **Objective-first, not module-first.** A learner starts with a goal or presentation and is guided to the relevant activity.
3. **Clinical complexity stays in the case.** Navigation, labels and repeated instructions remain simple; the clinical task remains appropriately challenging.
4. **One canonical history.** Reuse the existing event ledger for learning and simulation history. Projections are read models, not competing truth stores.
5. **No answer leakage.** Answers and unreleased findings remain hidden until the relevant learner action or disclosure stage.
6. **Unknown is not normal.** Keep missing, unknown, conflicting, stale, not-yet-released and explicitly negative states separate.
7. **Content is governed.** Generated or imported material stays draft until rights, source traceability, clinical review and release checks are complete.
8. **Feedback is specific.** Every material point in the debrief links to a criterion and, where possible, a learner action or event.
9. **Local-first by default.** Core practice works without an external model, paid API or cloud account.
10. **No false competence claim.** HSPTL records educational evidence; it does not grant licences, certify competence or replace supervision.

# The simple learner experience

## Primary navigation

The learner-facing application should have four stable entries:

- **Home** — the dashboard and resume point.
- **Learn** — topic teaching, short explanations and references.
- **Practice** — recall, cases, viva, OSCE, chart review and communication.
- **Simulate** — interactive scenario runs and debriefs.

Use the HSPTL brand mark as a Home link. Keep the top navigation horizontal on desktop and collapse it to a clear menu or bottom navigation on small screens. Do not restore a permanent 20-plus-item left sidebar.

Educator-only or infrequent tasks live under **Create & Manage**: Content Factory, scenario authoring, review queue, source registry, synthetic-data tools, operations, institution settings and backups. Visibility and actions must follow the actual user role and deployment security model; hiding a button is not authorisation.

## Dashboard structure

The dashboard should be a compact task board, not a metrics wall:

1. **Continue** — resume the last unfinished topic, case or scenario.
2. **Review due** — the next small batch of objectives/questions due for retrieval.
3. **Practice now** — one suggested 5–15 minute activity.
4. **Your focus** — at most three current learning objectives.
5. **Recent feedback** — the last useful debrief or assessment note.

Avoid large decorative KPI tiles, duplicate navigation cards, lengthy explanatory subtitles, several rows of empty placeholders, and graphs without a clear next action. If no data exists, show one useful starter action rather than zero-valued charts.

## Typography and density

Recommended design tokens (product targets, to be tested with learners):

| Element | Default target |
|---|---:|
| Body and clinical narrative | 16 px minimum default, 1.45–1.6 line height |
| Supporting text / metadata | 13–14 px, adequate contrast |
| Page title | 22–28 px |
| Section title | 17–20 px |
| Button / touch target | At least 40–44 px high where practical; larger on mobile |
| Content measure | 60–80 characters per line for long teaching text |

A small-font setting may be offered as a user preference, but clinical narratives, safety warnings and question text must remain readable. Use progressive disclosure for extended explanations, source details and advanced settings; do not delete clinically important caveats.

## Language and labels

Prefer short action labels: **Start case**, **Submit reasoning**, **Reveal debrief**, **Review topic**, **Save note**, **Advance time**, **Repeat station**. Use a concise one-sentence instruction when a task is new; keep extended teaching explanations inside the relevant learning material. Every icon-only control needs an accessible name and a visible tooltip or nearby label where discoverability matters.

## Responsive and accessible interaction

Target WCAG 2.2 AA as the accessibility baseline [R9]. At minimum, test keyboard-only use, visible focus, labels and error announcements, meaningful heading order, alternative text for meaningful images, contrast, zoom/reflow, reduced motion and touch-target spacing. Verify forms with assistive technology. Keep status information text-based; never rely on colour alone.

# One connected clinical learning cycle

This is the core product behaviour. Every curated topic should support a repeatable sequence, even where the selected topic does not require a full simulation.

| Step | Learner experience | HSPTL record |
|---|---|---|
| 1. Set the goal | Choose a topic/objective or accept a suggested next objective | Session and objective IDs |
| 2. Learn briefly | Read a concise explanation, diagram or teaching note | Content-pack version and time/open event |
| 3. Retrieve | Answer 3–5 questions without seeing answers first | Item response, confidence if useful, rationale version |
| 4. Apply | Work through a synthetic case: represent the problem, identify clues, create a differential, select investigations and plan next steps | Structured reasoning attempt and objective evidence |
| 5. Practise | Choose a focused activity: viva, OSCE, handover, interpretation or simulation | Activity trace and versioned rubric |
| 6. Debrief | Compare decisions with a reviewed rationale; reflect on uncertainty and safety | Criterion-level feedback and reflection |
| 7. Revisit | Receive a small scheduled review set | Due objective / retrieval schedule |

Not every 10-minute session needs all seven steps. The learner can do a quick recall session or a full scenario. The product should preserve a common mental model and carry the relevant objective through each mode.

## The case reasoning template

Reuse the existing reasoning artefacts and standardise the learner-facing form to:

1. **Problem representation** — one-line summary using age/context, time course and discriminating findings.
2. **Leading possibilities** — the short differential, not an unlimited list.
3. **Evidence** — what supports and argues against each leading possibility.
4. **Information needed** — focused history, examination and investigations, including why each matters.
5. **Interpretation** — explain how new information changes the differential.
6. **Plan** — immediate priorities, escalation, reassessment and safety-netting in the context of the educational case.
7. **Communication** — concise summary or handover.
8. **Reflection** — one uncertainty, one missed clue or one alternative pathway.

The system should accept multiple defensible reasoning paths where the scenario author has documented them. It should not award full credit solely because the learner guessed the final diagnosis.

# Content strategy and Content Factory

## Content should be built around objectives

HSPTL's eight-unit Acute Care Foundations pack is the seed, not the full product. Expand by a deliberate curriculum map, not by importing large volumes of unreviewed text. Initial coverage should prioritise common and high-risk presentations across core clinical areas, with local educators choosing the exact syllabus and depth.

Suggested first curriculum map:

| Track | Initial presentation clusters |
|---|---|
| Cardiovascular | Chest pain, acute coronary syndrome concepts, heart failure, arrhythmia, syncope |
| Respiratory | Asthma, COPD exacerbation, pneumonia, hypoxia, pleural presentations |
| Infection / acute care | Sepsis recognition, fever, meningitis, infection prevention, antimicrobial reasoning |
| Neurology | Stroke, seizure, headache red flags, altered consciousness |
| Endocrine / metabolic | Hypoglycaemia, diabetic ketoacidosis, hyperglycaemic emergencies, electrolyte disturbance |
| Gastrointestinal / renal | Acute abdominal pain, GI bleeding, AKI, fluid and electrolyte assessment |
| Cross-cutting safety | ABCDE, escalation, medication safety, handover, consent, documentation and uncertainty |

This is a proposed topic map, not a statement of local examination requirements or treatment protocols. Each unit must be scoped for learner level and reviewed against current applicable guidance before release.

## Minimum content-unit contract

Each versioned content unit should include:

- stable unit ID, title, version, specialty, care setting, level and estimated time;
- one to five measurable learning objectives with stable objective IDs;
- prerequisite knowledge and any required safety prebrief;
- concise teaching explanation and key discriminating concepts;
- synthetic patient vignette with explicit positives, explicit negatives and unknowns;
- retrieval questions with keyed answer, rationale, distractor explanations and objective mapping;
- case reasoning prompts and multiple acceptable answer pathways where justified;
- teaching pearls and common cognitive / safety pitfalls;
- optional viva and OSCE station outline;
- debrief prompts and next-practice recommendations;
- source registry IDs, specific claim-to-source links, source access date, guideline version and jurisdiction;
- reuse rights / licence metadata and provenance;
- author, clinical reviewer, reviewer scope, approval state and date;
- review due date and triggers (guideline update, safety notice, reported defect, terminology change);
- content digest and schema version; and
- intended educational use and explicit out-of-scope use.

A content unit is not ready because it passes JSON validation. Structural validation is necessary but not a substitute for clinical review.

## Content lifecycle

1. **Propose:** select a learning objective and target learner level.
2. **Source:** register guideline, primary literature or authoritative educational source; record rights and version/date.
3. **Draft:** author the teaching unit or use deterministic templates to create candidate derivatives.
4. **Validate:** run schema, completeness, duplicate, source-link, objective-mapping, answer-key, and cross-artifact consistency checks.
5. **Clinical review:** a qualified reviewer checks claims, omissions, red flags, alternative pathways, local fit and references.
6. **Educational review:** a second review checks objective alignment, item quality, cognitive level, clarity and feedback.
7. **Pilot:** test with representative learners; record confusing wording and unexpected interpretations.
8. **Publish:** issue an immutable version with approval metadata and digest.
9. **Monitor:** collect defects, retire or supersede outdated content, preserve version history and learner-attempt lineage.

The app must distinguish **GENERATED**, **IMPORTED**, **SYNTHETIC** and **DERIVED** provenance labels. Rights status, source reliability appraisal, evidence certainty, clinical approval and pedagogical approval must remain separate fields; one must never imply another.

## What the deterministic Content Factory should do

Keep the current local deterministic generator as the reliable default. It can produce draft case reports, debriefs, question sets, topic summaries, viva sets and OSCE station drafts from selected content units. Generation should preserve source links and content hashes. Every output remains a draft until reviewed.

Do not make an external LLM a required dependency. An optional local model may be considered later as a drafting aid, but its output must be treated as untrusted draft text, checked against source material and reviewed by a clinician. It must never independently approve, publish, prescribe or declare a patient safe.

## Quality checks for questions

Each MCQ needs one clearly defensible best answer for its stated objective, plausible distractors, explanation for the key, explanation for why distractors are less suitable, a source/claim link and a review date. Flag ambiguous stems, negative wording, trick questions, irrelevant demographic detail, unsupported absolutes and outdated guideline thresholds. Retain item statistics as descriptive evidence; do not automatically delete an item solely because one cohort performed poorly.

# Clinical case practice

## Case progression

A case should reveal information in stages only when the objective requires it. Example: initial presentation → focused history → examination → investigation request → result availability → interpretation → management priority → reassessment → handover. A static case may use a subset of these stages.

The learner can ask a question, select a finding, request a test, or submit a reasoning statement. HSPTL records what was available at the time so a debrief can distinguish a missed clue from a clue that was never released.

## Feedback dimensions

Feedback should cover the dimensions relevant to the task:

- information gathering;
- problem representation;
- differential breadth and prioritisation;
- evidence integration and uncertainty;
- investigation selection and interpretation;
- prioritisation, escalation and reassessment;
- patient safety and medication awareness;
- communication and documentation.

Not every case should score every dimension. A focused headache case, for example, may assess red-flag recognition and justification of next information rather than a full management plan.

## Multiple defensible paths

Authors must specify accepted variants, required safety constraints and critical omissions. The assessment system should not mistake deviation from one preferred sequence for an unsafe decision when an alternative is clinically defensible. Where the evidence is uncertain or context-dependent, the debrief should say so.

# Simulation design

## Build on the current vertical slice

The existing adult moderate-asthma scenario already establishes the important architecture: scenario package, seeded run, staged observations, typed actions, integer clock, scheduled events, event-backed trace, documentation, itemised formative rubric, replay and debrief. Preserve this implementation as the reference vertical slice, but retain its documented boundary: deterministic educational transitions are not calibrated physiology and do not predict actual treatment response.

## First simulation portfolio

Add scenarios only when each is reviewed, aligned to measurable objectives and has a usable debrief. A sensible order is:

1. Acute asthma / breathlessness (existing reference slice; complete clinical review before wider use).
2. Chest pain / possible acute coronary syndrome (focus on risk recognition, information gathering and escalation).
3. Sepsis recognition and communication (focus on deterioration, uncertainty, escalation and team communication).
4. Hypoglycaemia (focus on recognition, immediate safety actions and reassessment within a bounded teaching model).
5. Acute stroke (focus on time of onset, deficits, urgent pathway recognition and communication).
6. Seizure / transient loss of consciousness (focus on event reconstruction, red flags and observation).

Scenario scope and specific actions must be set by qualified reviewers using current guidance and local policy. Do not encode medication doses, oxygen titration protocols or time-critical treatment instructions until the educational scope, source, jurisdiction and approval pathway are explicit.

## Scenario package

A published scenario package should be immutable and versioned. Required fields:

- scenario identity, setting, target level, learning objectives and estimated run time;
- synthetic-patient marker and initial state;
- source registry IDs, guideline versions, jurisdiction and review metadata;
- explicit positives, negatives, unknowns, conflicting values and not-yet-released information;
- PROforma plan/model identity and digest;
- typed observation disclosure policy;
- allowed action catalogue and validated payload schemas;
- transition model ID/version, parameters and documented limits;
- scheduled events and deterministic time policy;
- endpoint/terminal conditions;
- versioned formative rubric with criteria, critical errors and criterion-to-event evidence mapping;
- debrief plan and teaching points; and
- required engine, schema, terminology and rubric versions.

Scenario data must not execute arbitrary Python, JavaScript, SQL or shell commands. PROforma remains the workflow/guard language. The existing Simulation Runtime remains a small in-process transition module; do not add a second general-purpose rule engine.

## Deterministic run and audit contract

For reproducible semantic replay, persist the scenario digest, model version, PROforma digest, engine version, seed and PRNG version (if randomness is used), integer clock policy, and ordered learner actions. Record accepted and rejected actions, state-transition digests, disclosed observation digests, documentation versions, assessment-rubric version and debrief completion.

Use integer simulation time. Stable ordering is required for events with the same due time. Rejected actions must be recorded with an explanation and must not alter the patient state. Missing data must remain unknown rather than being converted to a normal result. A completed run must be immutable.

## Prebrief and debrief

Prebrief should state: fictional patient, learning objectives, available tools, expected learner role, how to request help, how simulated time behaves and the limits of the model. Keep it short and context-specific.

Debrief should include:

1. learner self-assessment;
2. what the learner noticed and prioritised;
3. what happened in the trace and why the scenario model changed;
4. criterion-level feedback and any critical omission;
5. one evidence-linked teaching point;
6. one safer or more efficient alternative to rehearse; and
7. one follow-up objective for the Review Due queue.

Use PEARLS-inspired options to combine reflection, focused discussion and information-giving [R6]. A debrief is not a shaming scorecard. Keep a psychologically safe tone and make the educational purpose explicit.

# OSCE, practical skills and communication

OSCE should be one focused mode inside Practice, not a disconnected subsystem. Each station should include candidate instructions, context, time limit, patient/standardised-participant prompt, expected actions, examiner criteria, critical errors, global rating guidance, feedback and a repeat link.

Start with station families that map to current content: focused history, physical examination, investigation interpretation, counselling/communication, handover, procedural preparation and acute assessment. Do not imply that a checklist score is a validated examination result without station blueprinting, examiner training, reliability/validity evidence and appropriate standard setting.

Use observable criteria. Separate knowledge of a step from performance of a skill. Where practical performance cannot be observed in the digital environment, label the task as cognitive rehearsal or verbal walkthrough—not demonstration of physical competence.

# Assessment, progress and mastery

## Replace activity counts with objective-level evidence

HSPTL should show what evidence exists for each objective, not just how many pages or quizzes were completed. A suggested learner state is:

- **Not yet practised** — no relevant evidence.
- **Practising** — at least one relevant attempt exists; gaps remain or evidence is limited.
- **Improving** — later attempts show progress on specified criteria.
- **Repeatedly demonstrated in learning tasks** — evidence is consistent across multiple sessions or task types under the defined educational conditions.

Avoid the unqualified labels “competent”, “mastered clinically”, “entrustable” or “ready for independent practice”. An institution can map evidence into its own framework only after formal governance and validation.

## Evidence record

A reusable evidence record should capture: learner-local identifier, objective ID/version, task ID/version, source content version, date, attempt ID, observed response/action evidence, rubric version, criterion result, feedback, confidence where relevant, modality and assessor type (automated formative rule, peer, educator). Store the event as the durable history; derive learner views from that history.

## Do not collapse all evidence into one score

Show a small objective matrix or trend, not a global performance grade. Keep knowledge retrieval, clinical reasoning, simulated action, communication, OSCE observation and reflection distinct. A high MCQ percentage cannot compensate for a critical safety error in a scenario. Conversely, one weak quiz must not erase stronger evidence from other tasks.

## Spaced retrieval

Use the existing FSRS/reasoned-sequencing foundations where their contracts fit. The schedule should respond to recall difficulty, prior performance and elapsed time, with the algorithm and version recorded. Make the default simple: a manageable daily queue, a clear “review later” option and no punishment for missed days. Explain that spacing supports retention, not clinical competence by itself [R3, R4].

## Assessment validation

Before using any score for progression or certification, gather evidence for content coverage, response process, internal structure/reliability, relationship to other measures, consequences/fairness and local interpretation. Use independent assessors for a sample of performance tasks, calibrate rubrics, monitor inter-rater variation, and review subgroup differences. High-stakes uses require a separate governance and validation project.

# Synthea and clinical-record literacy

Synthea should be a practical data-literacy feature, not just a generator. Use synthetic patient records for these exercises:

- summarise a patient's longitudinal history;
- reconstruct a timeline of encounters, conditions and treatments;
- interpret observations and laboratory trends;
- distinguish a missing field from an explicitly negative finding;
- identify inconsistencies or chronology issues;
- prepare a structured handover; and
- explain which conclusion is supported by the record and which remains unknown.

Use FHIR resources such as Patient, Encounter, Condition, Observation, DiagnosticReport, MedicationRequest, Procedure and CarePlan where available and relevant. Observation is a natural event resource for measurements and assertions [R14]. Expose source resource IDs and provenance to the learner, but hide technical identifiers unless the activity is specifically about FHIR.

Keep synthetic data separate from real-patient workflows. Synthea describes its patients as realistic but fictional [R12]. However, research on synthetic patient data shows that privacy, fidelity and utility require evaluation, particularly when data are generated from real records [R13]. HSPTL should reject identifiable patient inputs in the default learner workflow and should not claim that “synthetic” universally means “privacy guaranteed”.

# Architecture and implementation boundaries

## Preserve the modular monolith

Keep the current React/TypeScript client, FastAPI application, SQLite persistence, additive migrations and in-process domain modules. The learner product should be made simpler at the route/component level without replacing the backend or changing working API contracts unnecessarily.

Recommended responsibility map:

| Existing boundary | Responsibility in 6.0 |
|---|---|
| Content packs / Learning Library | Versioned learning objectives and materials |
| Content Factory / generation distribution | Deterministic draft generation, lineage and governed release |
| Learning events / progress projection | Durable attempts and objective-level progress |
| Case engine / Clinic | Structured reasoning, clues and case feedback |
| PROforma | Bounded workflow eligibility and action logic |
| Simulation Runtime / Pulse | Scenario state transitions and learner-visible observations |
| Kernel / event ledger | Canonical event history and reproducible replay |
| Assessment / OSCE / Exam Centre | Rubric-based, task-specific formative evaluation |
| Source registry / content operations | Rights, provenance, source appraisal and review state |
| Synthetic Data Factory / data tools | Synthetic record generation, validation and chart exercises |
| Institution governance | Local roles, retention, backup and safety-case records; not a shortcut to production security |

Do not duplicate the event ledger, introduce a separate progress database as source of truth, add a second rule engine or split the application into services just to achieve a modern-looking architecture.

## Suggested conceptual data model

Reuse existing tables and event contracts where possible. Add only missing fields/entities after migration and replay impact analysis:

- `LearningObjective` — stable ID, statement, competency mapping, version.
- `ContentUnitVersion` — immutable content package, sources, rights, reviewers and digest.
- `LearningActivity` — quiz, case, viva, OSCE, chart exercise or simulation mapped to objectives.
- `Attempt` — learner response, version, confidence and feedback references.
- `EvidenceEvent` — durable evidence linking attempt/action to objective and rubric criterion.
- `MasteryProjection` — rebuildable read model derived from events, never canonical truth.
- `ReviewSchedule` — due state and algorithm version; rebuildable or reconciled against evidence.
- `ScenarioVersion` / `SimulationRun` — immutable scenario digest and event-linked execution.
- `RubricVersion` — criteria, weights, critical errors and evidence mapping.
- `SourceRecord` / `ReviewRecord` — source identity, reuse rights, appraisal, clinical and educational review.

Use stable IDs and semantic versions. Content changes create a new version; never silently rewrite an artefact already attempted by a learner.

## API policy

Reuse current route families for content factory, curriculum composition, learning progress, case reasoning, `/api/v4/simulation/*`, `/api/v5/learning/*`, source registry and synthetic-data operations. Add new endpoints only where the learner flow cannot be expressed with the current contracts. Every new write route needs validation, idempotency where retries are possible, authorization where applicable, event schema, migration strategy and tests.

## Offline and local-first behaviour

Core Learn, Practice and the bundled scenarios should function without external AI or internet after installation. External source links may require connectivity, but the content must show a local cached citation/reference snapshot and review date. Data imports are explicit; no silent upload. Backups should be easy to create and restore, with manifest verification and clear warnings. Do not expose the local server to a public network by default.

# Clinical governance, safety and privacy

## Content safety controls

- Each clinically relevant claim should link to a source and source version/date.
- Each released unit/scenario should have a named reviewer identity and declared scope of review.
- A reviewer credential proves only that a configured token was supplied; it does not independently verify credentials.
- Local protocols and jurisdiction-specific thresholds must be explicit.
- Review triggers include major guideline updates, source correction/withdrawal, safety incidents, content defect reports and terminology changes.
- Unreviewed drafts cannot appear as approved learner content.
- All educational pages and scenarios should state the intended training level and limitations where appropriate.

## Hazard controls

| Hazard | Required control |
|---|---|
| Outdated teaching point | Versioned source, review date, expiry/review trigger and withdrawal mechanism |
| Incorrect generated answer | Draft-only generation, schema validation, clinical review and test questions |
| Answer or finding leaked early | Server-controlled staged disclosure and negative tests |
| Missing data interpreted as normal | Explicit unknown / not-released states; no automatic normal default |
| Invalid treatment inference | Constrain action set; cite educational scope; no live prescribing or patient advice |
| One path treated as the only correct pathway | Author alternate defensible paths and explain context dependence |
| Score overinterpreted as competence | Formative labels, no global competence badge and documented validation boundary |
| Sensitive patient data imported | Default synthetic-only workflow, input warnings, data minimisation and separate approval for real data |
| Reviewer role overtrusted | Institution verifies reviewer identity, qualifications and scope outside token validation |
| Unauthorised institutional access | Do not deploy multi-user until SSO/MFA, isolation, encryption, audit and threat model gates pass |

## Production-readiness boundary

HSPTL 5.1.0 release notes explicitly state that the application is not a production clinical platform and list security/governance limitations. The 6.0 blueprint does not remove those blockers. Institutional production use requires a separate security architecture and threat model, identity proofing, MFA/SSO, encryption and key management, hardened tenant isolation, tested restore, retention governance, vulnerability management and formal institutional clinical/educational approval.

# Phased roadmap

The roadmap is ordered by dependency and value. Calendar estimates should be set after implementation sizing; the release gates below are more important than optimistic dates.

## Phase 0 — establish the trustworthy baseline

**Goal:** a reproducible, installable 5.1.x baseline before major feature work.

Work:

- complete Windows frontend dependency installation, `npm run typecheck` and production build;
- test clean install, repeat install, migration from a populated earlier database, startup with an occupied port, backup and restore;
- confirm manifests and packaged assets;
- document known limitations in the app and release notes;
- preserve a rollback backup.

Exit gate: clean Windows installation and launch; full backend tests; TypeScript typecheck; Vite build; migration/restore checks; no unreviewed content accidentally presented as approved.

## Phase 1 — simplify the product surface

**Goal:** the learner can see what to do next without learning the internal workspace taxonomy.

Work:

- adopt Home / Learn / Practice / Simulate as the only primary learner navigation;
- move authoring, review and data operations under Create & Manage;
- reduce dashboard to Continue, Review due, Practice now, Focus objectives and Recent feedback;
- standardise common activity headers, progress indicators, primary actions and empty states;
- reduce repeated explanatory prose using progressive disclosure;
- conduct task-based usability tests with novice and experienced learners.

Exit gate: key tasks are reachable in no more than two navigation decisions from Home; no permanent long sidebar; the 320 CSS-pixel/zoom reflow and keyboard/focus tests pass; learner tests show fewer navigation errors than baseline.

## Phase 2 — curate a meaningful curriculum

**Goal:** the learner has enough accurate, reviewed material to use the product repeatedly.

Work:

- audit all eight Acute Care Foundations units against the minimum content-unit contract;
- review and release the existing starter pack with qualified clinical and educational reviewers;
- expand the curriculum through the proposed presentation clusters;
- generate question, case, viva, OSCE and debrief derivatives from the same unit version;
- add source-age alerts and review-due status;
- pilot with learners and revise ambiguous questions.

Exit gate: every released claim has source traceability; every activity maps to at least one objective; every quiz key and rationale has review evidence; no generated draft is auto-published.

## Phase 3 — unified case practice and objective review

**Goal:** every case attempt contributes useful evidence to a reviewable objective record.

Work:

- standardise the reasoning template across Daily Case Lottery, Clinic and library cases;
- record released findings, learner actions, confidence and item-level feedback;
- build the Review Due queue on existing FSRS/reasoned-sequencing services;
- create objective-level progress projections with explicit confidence and evidence count;
- schedule repeat practice after a gap or safety-critical omission;
- keep recommendation explanations transparent.

Exit gate: retries are idempotent; progress rebuilds from the event history; an activity completion does not directly set a competence state; review schedules are versioned and testable.

## Phase 4 — clinical simulation and OSCE portfolio

**Goal:** a coherent set of reviewed scenarios and stations with high-quality debrief.

Work:

- complete clinical educator review of the existing asthma vertical slice;
- add scenarios one at a time using the same package/runtime contract;
- extend trace-linked feedback and replay;
- build timed OSCE stations with explicit observable criteria and calibrated rubric guidance;
- add scenario and station pilot evaluation;
- ensure every scenario has prebrief, measurable objectives, feedback/debrief and pilot notes.

Exit gate: deterministic replay tests pass; staged information cannot leak; all accepted/rejected actions are auditable; all scores are trace-linked and formative; scenarios pass clinical review and pilot criteria.

## Phase 5 — synthetic patient record exercises

**Goal:** make the Synthetic Data Factory useful for learning tasks, not just dataset generation.

Work:

- create guided exercises over synthetic Synthea records;
- add longitudinal timeline, observation trends and medication/condition review;
- add source-resource provenance and FHIR export where needed;
- validate terminology, chronology and completeness separately from clinical interpretation;
- keep dataset generation separate from scenario approval.

Exit gate: tasks state the provenance and synthetic status; incomplete data are clearly labelled; all exercises are reviewed; no identifiable patient data are required for default use.

## Phase 6 — educator and cohort workflows

**Goal:** permit supervised curriculum use only after institutional security decisions are complete.

Work:

- define institutional identity, roles, consent, privacy, retention and deployment model;
- verify reviewer qualifications and scope through the institution's process;
- support assignment, facilitated debrief, cohort review and educator feedback;
- generate exportable learning portfolios with transparent evidence semantics.

Exit gate: identity/access controls, isolation, encryption, backup/restore, audit, retention, vulnerability management and formal institutional approval are independently verified. Do not infer production readiness from a feature toggle.

# Acceptance criteria and release gates

## Learner UX

- A first-time learner can locate and start a starter topic without reading a long manual.
- Home presents a single recommended next action and a small number of alternatives.
- Learn, Practice and Simulate are consistently named and placed.
- Authoring and admin tasks are absent from primary learner navigation.
- Common activity pages use the same action placement, progress language and feedback structure.
- No essential clinical text is hidden behind a hover-only control.
- Font scaling, browser zoom, keyboard navigation, contrast and responsive reflow pass accessibility tests.

## Learning and content

- Every released activity maps to stable learning objective IDs.
- Every objective has a meaningful assessment or observation method.
- Every question has a keyed answer, rationale, distractor feedback and source link.
- Every clinical content version has a reviewer and review date.
- Generated content remains draft until approved.
- Review Due items can be postponed without losing the learner's record.
- Progress labels describe evidence and do not imply licence or independent clinical competence.

## Simulation and assessment

- Same scenario digest, model/runtime versions, seed and action sequence reproduce the same semantic result.
- No learner can observe a not-yet-released finding through UI or API.
- Rejected actions never alter patient state and are visible in replay.
- The debrief is generated from the actual run trace and rubric version.
- Critical safety errors are distinct from ordinary lost points.
- All scenarios are piloted before wide release.
- Assessment claims remain formative until reliability, validity, fairness and consequence evidence supports a stronger use.

## Technical and operational

- All migrations are additive, ordered, transactional where needed and tested against a populated database.
- All event writes are schema-validated and idempotent where retries can occur.
- Projections can be rebuilt from canonical events or reconciled with an explicit migration.
- Clean install, repeat install, launch, occupied-port handling, backup and restore are tested on Windows.
- Backend tests, frontend typecheck, production build and release verification pass.
- No required cloud API, remote model or network service is needed for core learner practice.

# Evaluation plan

## Usability evaluation

Conduct short task-based sessions with representative novice and experienced learners. Ask them to: start a topic, complete a question, submit a case reasoning response, launch a simulation, find the debrief and revisit a due objective. Record time, errors, help requests, completion and perceived workload. Compare to the current 5.1.0 baseline. Use the results to remove steps and ambiguity, not to justify adding more dashboard metrics.

## Learning evaluation

For selected objectives, use a planned evaluation design:

- baseline knowledge or task assessment;
- immediate post-practice assessment with parallel items where possible;
- delayed retrieval assessment after a pre-specified interval;
- case reasoning rubric on a new but aligned case;
- learner confidence calibration and feedback usefulness;
- where appropriate, independent educator scoring of a sample of performance tasks.

Do not use app analytics alone to claim improved clinical performance. For a research claim, pre-register outcomes, define comparator, recruit an appropriate sample and seek the relevant institutional ethics review.

## Content and simulation evaluation

For each release, record clinical-review findings, question ambiguity reports, scenario pilot completion, unexpected learner actions, debrief usefulness and changes made. Track version-level defect rates and review latency. A content correction should not erase prior learner attempts or obscure which version was used.

## Suggested product indicators

- Time from opening Home to first meaningful learning action.
- Percentage of first-time learners completing one full learning cycle.
- Review-due completion and return at a later interval.
- Objective-level improvement on a fresh assessment item or case.
- Percentage of simulation runs with debrief completion.
- Learner-reported clarity and feedback usefulness.
- Clinical reviewer defect rate and stale-content rate.
- Navigation errors and usability task failures.

Do not optimise for daily screen time, raw click count, number of generated files, or a single overall score.

# Key risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Feature sprawl | More modules increase navigation and maintenance burden | Organise around Learn / Practice / Simulate; require an outcome justification for each feature |
| Content quantity over quality | An inaccurate large library can damage trust | Prioritise reviewed high-value units; release gates and source lineage |
| Unvalidated scoring | Learners may overinterpret percentages | Formative labels, transparent rubrics and separate validation project |
| Overconfident simulation fidelity | Deterministic teaching model can look like a real physiological prediction | Explicit model limits, scenario-specific review and no live-care use |
| AI draft hallucination | Generated claims may be plausible but unsupported | Local deterministic baseline, source-linked draft, human review and non-publishing generation |
| Synthetic data overclaim | Synthetic data may still have privacy or utility issues depending on provenance | Synthea-first, provenance, no identifiable data by default, separate risk review for derived datasets |
| Technical scope creep | New engines/services make local installation harder | Preserve modular monolith, reuse existing interfaces and add no service without strong rationale |
| Institutional deployment too early | Security controls are incomplete | Defer cohorts/production until independent security and governance gates pass |

# Decisions and defaults

These decisions can be revisited, but the recommended defaults allow development to proceed:

| Decision | Recommended default |
|---|---|
| Primary audience | Medical / health-professions students and early-career clinicians in training, with explicit level tags |
| Main learning modes | Learn, Practice, Simulate |
| Core runtime | Local-first; no mandatory API key or hosted AI |
| Content production | Versioned JSON packs + deterministic generation + human review |
| Initial curriculum | Acute Care Foundations, then high-value core presentations across specialties |
| Language | English first; design for localisation and right-to-left support before adding Arabic content |
| Clinical standards | Source and jurisdiction/version declared per content unit; no assumed one-size-fits-all protocol |
| Assessment | Formative evidence only until separate validation supports stronger claims |
| Institutional mode | Later, after identity, security, privacy and isolation work is independently accepted |

# The HSPTL monogram and brand specification

The supplied image is the visual master for the mark. The new vector asset is traced from the original reference rather than reinterpreted as generic typography.

- **Composition:** asymmetric architectural grid; H and S occupy the upper row; P and T occupy the middle row; L occupies the lower-left region; the lower-right blue panel remains part of the original structural composition.
- **Ink colours:** deep navy `#173142`; blue `#25567F`.
- **Reference background:** pale blue `#E3EDF6` (the SVG itself has a transparent background).
- **Proportion:** artwork viewBox 485 × 614; preserve its vertical proportion and do not stretch.
- **Clear space:** at least one main stroke-width around the outside when used as a standalone mark.
- **Wordmark:** place `HSPTL` alongside or below the mark where the product name is needed. Do not add extra letterforms inside the monogram and do not turn the mark into five separate typeset letters.
- **Variants:** retain the full-colour SVG as the master; derive monochrome variants by recolouring both inks to one colour. Keep a simplified favicon only if the full mark becomes illegible at the target size.
- **Accessibility:** use `HSPTL` as the accessible name when the logo is meaningful; use empty alternative text when the adjacent wordmark already provides the name.

The supplied SVG and PNG are visual assets for review. Replacing the logo throughout a distributable HSPTL installation still requires updating the public SVG, React mark component, app icons and any generated manifest, then running the frontend build and archive verification.

# Final recommendation

HSPTL 6.0 should be judged by whether it becomes easier to start and more useful to finish a clinical learning session—not by how many modules it can display. Make the first minute simple, the clinical task meaningful, the feedback trustworthy and the next practice step obvious.

The implementation order is therefore:

1. verify and stabilise the current release;
2. simplify the learner experience around Home / Learn / Practice / Simulate;
3. expand and clinically review the curriculum;
4. connect attempts, feedback and spaced review at objective level;
5. extend the existing deterministic simulation and OSCE foundations;
6. turn Synthea records into practical chart-literacy exercises; and
7. introduce cohorts only after security and institutional governance are independently ready.

Do less on the screen. Make each clinical task deeper, more transparent and easier to revisit.

# References

**[R1] INACSL.** *Healthcare Simulation Standards of Best Practice®.* Current official standards portal; fourth-edition material and 2025 revisions to cornerstone standards. https://www.inacsl.org/healthcare-simulation-standards-of-best-practice/ (accessed 20 Nov 2026).

**[R2] INACSL.** *Healthcare Simulation Standards of Best Practice — Simfographics.* Summary of simulation design, prebriefing, outcomes/objectives, facilitation, evaluation, debriefing, professional integrity and operations. https://www.inacsl.org/simfographics (accessed 20 Nov 2026).

**[R3] Trumble E, Lodge J, Mandrusiak A, Forbes R.** Systematic review of distributed practice and retrieval practice in health professions education. *Advances in Health Sciences Education.* 2024;29:689–714. https://doi.org/10.1007/s10459-023-10274-3.

**[R4] Maye JA, Hurley F.** The Effectiveness of Spaced Repetition in Medical Education: A Systematic Review and Meta-Analysis. *The Clinical Teacher.* 2026;23(2):e70353. https://doi.org/10.1111/tct.70353.

**[R5] Ahmed S, Naz M, Raza Z, Ali M, Khan MSU, Rizvi M.** Teaching and Assessing Clinical Reasoning in Health Professions Education: A Systematic Review. *Journal of Dental Education.* First published 8 Sep 2026. https://doi.org/10.1002/jdd.70361.

**[R6] Eppich W, Cheng A.** Promoting Excellence and Reflective Learning in Simulation (PEARLS): Development and Rationale for a Blended Approach to Health Care Simulation Debriefing. *Simulation in Healthcare.* 2015;10(2):106–115. https://doi.org/10.1097/SIH.0000000000000072.

**[R7] World Health Organization.** *Patient Safety Curriculum Guide: Multi-professional Edition.* 6 Jul 2011. https://www.who.int/publications/i/item/9789241501958.

**[R8] Association of American Medical Colleges.** *The Core Entrustable Professional Activities (EPAs) for Entering Residency.* https://www.aamc.org/about-us/mission-areas/medical-education/cbme/core-epas (accessed 20 Nov 2026).

**[R9] World Wide Web Consortium.** *Web Content Accessibility Guidelines (WCAG) 2.2.* W3C Recommendation, 12 Dec 2024. https://www.w3.org/TR/WCAG22/.

**[R10] W3C Web Accessibility Initiative.** *Cognitive Accessibility Objective: Help Users Understand What Things Are and How to Use Them.* Supplemental guidance to WCAG. https://www.w3.org/WAI/WCAG2/supplemental/objectives/o1-understandable/.

**[R11] Whitenton K.** Minimize Cognitive Load to Maximize Usability. Nielsen Norman Group, 22 Dec 2013. https://www.nngroup.com/articles/minimize-cognitive-load/.

**[R12] MITRE / Synthea.** *About Synthea.* Synthetic patient population simulator and output formats. https://synthetichealth.github.io/about.html (accessed 20 Nov 2026).

**[R13] Adams T, Birkenbihl C, Otte K, et al.** On the fidelity versus privacy and utility trade-off of synthetic patient data. *iScience.* 2025;28(5):112382. https://doi.org/10.1016/j.isci.2025.112382.

**[R14] HL7 International.** *FHIR Release 5 — Observation Resource.* https://hl7.org/fhir/observation.html (accessed 20 Nov 2026).

---

# Appendix A — Repository areas to reuse

The following observed project areas are starting points, not a prescription to create all-new modules:

- `frontend/src/App.tsx` — navigation and route composition.
- `frontend/src/pages/HomeDashboardPage.tsx` — dashboard.
- `frontend/src/pages/LearningLibraryPage.tsx` — topic learning.
- `frontend/src/pages/ContentFactoryPage.tsx` and `ContentStudioPage.tsx` — content generation/authoring surfaces.
- `frontend/src/pages/ClinicPage.tsx` — case practice.
- `frontend/src/pages/ClinicalSimulationPage.tsx` — simulation run.
- `frontend/src/pages/OSCEPage.tsx` and `ExamCentrePage.tsx` — skills and questions.
- `frontend/src/pages/ProgressPage.tsx` — progress.
- `backend/content_packs/acute_care_foundations_v1.json` — starter curriculum pack.
- `backend/routers/content_factory.py`, `learning.py`, `assessment.py`, `next_increments.py`, `synthetic_data.py`, `hsp_tl40.py` — existing API families.
- `backend/hsptl_core/hsp_tl40/clinical_simulation.py`, `kernel.py`, `proforma.py`, `pulse.py` — current simulation/event/logic boundaries.
- `fixtures/scenarios/asthma-moderate-adult-001/scenario.json` — reference simulation package.

# Appendix B — Verified review notes

- Source tree application version: `5.1.0`.
- Backend test run during this blueprint task: `474 passed`.
- Existing release status: frontend dependency-backed typecheck and production build were not verified in the inspected release environment.
- Current asthma vertical slice: deterministic educational model, clinical educator review pending per repository documentation.
- Current institutional posture: local learning product; production clinical and enterprise deployment blockers remain explicit.
