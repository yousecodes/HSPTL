# HSPTL — Hospital Workspace & Learning Integration Blueprint

**Release:** 2.2.0 working refactor  
**Product promise:** Solve. Examine. Perform.  
**Product model:** a local-first clinical learning hospital, organised around clinical workspaces rather than a course curriculum.

![HSPTL workspace concept](../HSPTL_Workspace_Design_Concept.png)

![HSPTL custom mark family](../HSPTL_Workspace_Marks.png)

![HSPTL shared tag integration](../HSPTL_Tag_Integration.png)

*Concept art showing distinct Clinic, Rounds, Diagnostics Lab, Exam Hall and On-call layouts. It is a design reference, not a screenshot of the running application.*

## 1. Product direction

HSPTL should feel like entering a teaching hospital to practise clinical work. The learner moves between services that each have a clear job:

- solve a case and understand the decisions;
- attend specialty rounds and defend a clinical explanation;
- identify clinical material and perform practical stations;
- sit a structured examination;
- review practice and choose the next useful activity.

The platform should not lead with a Curriculum destination, textbook tree or generic list of study tools. Content depth belongs inside the workflows where it is used: a case library inside Clinic, a specialty index and teaching material inside Rounds, and a visual/skills library inside Diagnostics Lab.

## 2. Information architecture

### Core workspaces

**Ward Board** — personal practice overview. Internal destinations: resume a case, recent activity, due reviews, weak tags and recommended next practice.

**Clinic** — solve clinical case reports. Internal destinations: Case Reports, Case Library and Case Debriefs.

**Rounds** — learn and defend specialty knowledge. Internal destinations: Specialty Index, High-Yield Pearls, Attending Room, Viva and Tag Index.

**Diagnostics Lab** — visual interpretation and practical performance. Internal destinations: Visual Spotters and OSCE Stations.

**Exam Hall** — formalised practice under exam conditions. Internal destinations: Question Bank, Mock Exams, Timed Sessions and Reports.

**Data Tools** — prepare educational source material. Internal destinations: MedNoteGen, Specialty Harvest and review queue.

### Why this grouping works

Clinic is the patient/case encounter. Rounds is the teaching service. Diagnostics Lab is the image and practical-skills service. Exam Hall is deliberately quiet and time-aware. Ward Board is the entry point. Data Tools stays available but secondary because harvesting and note generation are content operations, not the core learning experience.

## 3. Workspace experience specifications

### A. Clinic — case-solving workspace

**Purpose:** work through a case report progressively, make decisions and receive a substantial debrief.

**Primary views**

1. **Case Reports:** a case list, filters and a progressive case-solving workspace.
2. **Case Library:** browse specialty and presentation-based reports, including harvested/open-access cases after review.
3. **Case Debriefs:** revisit saved Synthea encounter reasoning records and inspect the problem representation, working diagnosis, differential, evidence for/against, investigation and management plan, safety net, communication and saved reflection prompts.

**Recommended layout**

- Left: case list, patient/case identifier, setting, timeline and source/provenance.
- Centre: case narrative, staged clues, results and the current decision.
- Right: problem representation, prioritized differential, evidence for/against, next investigation and management/safety decision.
- Debrief state: a full-width review with the final explanation, decisive findings, why alternatives are less likely, common pitfalls, source references and tag-linked practice.

The layout should feel like a clinician's patient file, not a chat window. Reveal controls should be consistent and the learner's active decision should remain visually prominent.

**Debrief structure**

- Case summary and final diagnosis (when source/authoring review supports it)
- Key discriminating clues
- Differential diagnosis and why alternatives move up/down
- Investigation strategy: clinical question, result and effect on the next decision
- Management priorities and safety considerations
- Common diagnostic traps and learning points
- Evidence/source list and review date
- Related Rounds pearls, Lab spotters, OSCE stations and Exam Hall questions through shared tags

**Safety constraint:** Synthea records remain synthetic, source-linked records. An encounter diagnosis code is not automatically a validated answer key. Imported records do not become diagnostic puzzles without separate case authoring and clinical review.

### B. Rounds — specialty teaching workspace

**Purpose:** explore a specialty, attend a short teaching session, retain high-yield points and answer viva questions.

**Internal destinations**

- **Specialty Index:** departments and topic tags. Selecting a specialty opens topic clusters and linked teaching sources.
- **High-Yield Pearls:** concise, evidence-linked takeaways. Keep the reading density low; each Pearl should point to its evidence and to related practice.
- **Attending Room:** a lecture/explanation mode with an illustration board, source references, key takeaways and pauses for questions.
- **Viva:** oral-style prompts requiring explanation, justification, comparison and prioritisation, with model answer structure and examiner follow-ups.
- **Tag Index:** shared clinical concepts and the practice items linked to each one.

**Recommended layout**

A three-zone editorial teaching room:

- Left rail: specialty/service and topic index.
- Centre: the attending's explanation, diagrams, ECGs, imaging or annotated figures, and structured topic outline.
- Right rail: high-yield pearls, linked tags and viva follow-up prompts.

The Attending Room must distinguish a source-backed explanation from a discussion prompt and from an exam answer. Figures should carry an original source and rights status. If a topic has no verified illustration, show a clear empty state rather than an invented image.

**Viva pattern**

Use progressive oral questioning: define the problem, state the leading explanation, defend the differential, justify a test, interpret an unexpected result, discuss management and identify a safety issue. The system should reveal a model response only after the learner commits an answer. A human examiner or validated rubric is required before any high-stakes use.

### C. Diagnostics Lab — visual and practical workspace

**Purpose:** recognise patterns and demonstrate clinical skills.

**Visual Spotters**

- image-first canvas with zoom/fit controls;
- modality filter: clinical photo, ECG, X-ray, CT/MRI, ultrasound, histopathology, fundus, specimens and laboratory plots;
- short prompt: describe, identify, interpret or choose the next step;
- answer reveal, discriminating features and source;
- related tags to connect the visual case to a Clinic case, Rounds topic and exam item.

**OSCE Stations**

- candidate instructions and task/time boundary;
- station timer and progress;
- checklist grouped by opening, history/examination, explanation, safety and closure;
- critical errors separated from ordinary checklist points;
- response capture and feedback;
- station debrief with model structure, common omissions and related practice.

**Recommended layout**

A darker, low-distraction diagnostics canvas. The image or station task is the visual anchor; tools and answer controls sit in a stable side panel. The learner should not need to scroll past long explanatory text before seeing the image.

### D. Exam Hall — assessment workspace

**Purpose:** practise under realistic test conditions.

**Recommended layout**

- Focused top strip: exam name, timer, completion and exit control.
- Centre: one question at a time, generous reading area and answer options.
- Right navigator: question numbers, answered, flagged and current states.
- Post-submit: score, item-level explanations, weak tags and links to remediation.

Exam mode should minimise navigation and unrelated widgets. Untimed practice and timed examination should be visibly distinct. Questions need metadata for source, version, review status, specialty, task and difficulty.

### E. Ward Board — daily practice overview

**Purpose:** tell the learner what has happened and what useful action to take next.

**Recommended sections**

- Continue last case / continue exam / resume OSCE station.
- Recent practice and unfinished debriefs.
- Due reviews and weak tags.
- Next recommended activity with a short explanation of why it was suggested.
- Recent imported or harvested content awaiting review (for authors/admin mode).

Do not turn this into a gamified score wall. Show activity counts and formative signals transparently. Do not call the learner competent or mastered from a few quiz scores.

### F. Data Tools — content operations

Keep MedNoteGen and Specialty Harvest here, not in the main learning flow.

**MedNoteGen**

- reads Synthea FHIR exports;
- creates deterministic encounter-linked narratives and draft notes;
- preserves source-resource references and missing data;
- exports `hsptl_import.json` and Markdown;
- produces draft Pearl/case seeds only;
- never generates absent examination findings, history or diagnoses.

**Specialty Harvest**

- searches specialty-filtered open-access sources;
- stores original metadata and article XML;
- tracks article rights/licence and review state;
- sends each candidate to a review queue;
- does not convert unreviewed literature into released cases or questions.

## 4. Additional hospital workspaces to consider

The following are useful expansions, not required for the first release. Keep them out of the primary navigation until there is enough content to make each one substantive.

### 1. On-Call Room — highest-priority expansion

A timed acute-care simulation space for triage, prioritisation, escalation and initial management. A case begins with a pager-style call and limited context. The learner chooses immediate actions, requests data, recognises deterioration, escalates and gives a handover. Branches change the next scenario state. The debrief should explain priorities, unsafe delays and what information changed the plan.

Suggested scenario themes: acute chest pain, respiratory distress, sepsis, shock, altered mental status, anaphylaxis, arrhythmia, trauma and post-operative deterioration.

### 2. Case Conference / M&M Room — high-value expansion

A structured review of difficult diagnoses and simulated safety events. Show a timeline, decisions, missed signals, alternative actions, human/system contributors and prevention actions. This must be non-punitive and focused on systems learning, not blame. ACGME's assessment guide describes M&M, root-cause analyses and simulated adverse-event debriefs as educational methods, with rubrics and trained evaluation improving validity.

### 3. Handover Desk — useful bridge

Practice concise case presentation and safe transfer using SBAR or another explicitly chosen local format. The learner converts a case into a prioritized handover, anticipates questions and flags pending results or safety risks. This could begin as a module inside On-Call rather than a separate workspace.

### 4. Procedure Theatre — keep inside Diagnostics Lab initially

Procedure rehearsal with indications, consent, equipment, setup, key steps, infection control, complications and critical fail points. Later add video-based demonstration and an examiner checklist.

### 5. MDT / Consult Room — optional later expansion

A cross-specialty consultation: choose the right service, prepare a succinct referral, justify the question and respond to consultant recommendations. Good for integrated cases but should not duplicate the On-Call or Rounds experience.

## 5. Shared tag architecture — the integration backbone

Tags are not decoration. A tag is the link between a teaching explanation, case, image, viva prompt, OSCE station and exam question.

### Tag facets

**Specialty** — Cardiology, Neurology, Emergency Medicine. Purpose: service ownership and browsing.

**System** — Cardiovascular, Respiratory, Renal. Purpose: shared anatomy/physiology grouping.

**Presentation** — Chest Pain, Dyspnoea, Fever, Syncope. Purpose: entry point by clinical problem.

**Task** — Diagnosis, Differential Diagnosis, Investigation, Management, Interpretation, Communication, Procedure. Purpose: what the learner must do.

**Modality** — ECG, Clinical Photo, X-ray, Histopathology, Ultrasound, Fundoscopy. Purpose: visual/practical format.

**Setting** — Emergency, Outpatient, Inpatient, Critical Care, Primary Care. Purpose: clinical context.

**Competency** — Clinical Reasoning, Data Interpretation, Communication, Patient Safety. Purpose: skill dimension.

**Difficulty** — Foundational, Intermediate, Advanced. Purpose: complexity filter.

**Level** — Preclinical, Clinical Years, Postgraduate. Purpose: learner stage.

Use stable IDs such as `presentation.chest-pain`, not labels as primary keys. Aliases resolve common variants (e.g., dyspnoea/dyspnea) to one canonical tag. Tags should be controlled; free-text keywords may be stored separately but must not become new canonical tags automatically.

### Content model

- `learning_tags`: canonical definitions, facet, label, aliases and active status.
- `tagged_content_items`: stable content identity, type, workspace, title, summary, source status and URL.
- `content_tag_links`: many-to-many relation between content and tags.
- `tag_learning_events`: open, attempt, complete, review and revisit events with score/confidence when available.

Each content item should normally carry 3–8 tags, including at least one specialty (when applicable) and one task or modality. Unknown tags are rejected rather than silently invented.

### Example pathway — acute chest pain

**Rounds** — ACS attending explanation and high-yield pearls. Shared tags: Cardiology, Cardiovascular, Chest Pain, Clinical Reasoning.

**Clinic** — progressive acute chest pain case. Shared tags: Cardiology, Emergency, Chest Pain, Diagnosis, Intermediate.

**Diagnostics Lab** — ECG / chest radiograph spotter. Shared tags: Cardiology, Chest Pain, ECG or X-ray, Interpretation.

**Viva** — defend ACS differential and test choice. Shared tags: Cardiology, Chest Pain, Communication, Advanced.

**Exam Hall** — key-feature question on ACS. Shared tags: Cardiology, Chest Pain, Investigation, Management.

**On-Call** — acute chest pain triage simulation. Shared tags: Emergency Medicine, Chest Pain, Prioritisation, Patient Safety.

### Learner integration

After a learner attempts an item, attach the event to all tags on that item. Aggregate formative signals by tag:

- attempts and completions;
- recent accuracy where an answer key exists;
- confidence calibration where collected;
- time since last practice;
- unanswered or unfinished items.

Recommendations should use transparent rules and explain the reason: “You missed two ECG interpretation questions tagged Cardiology + Chest Pain; try the ECG spotter, then return to the case.” Do not treat every incorrect answer as a clinical incompetence label. Do not make a mastery claim unless a validated assessment design supports it.

### Tag lifecycle

1. Content is created/imported with source metadata.
2. Canonical tags are attached from structured metadata and reviewed keywords.
3. The tag index exposes related content across workspaces.
4. Learner events update formative tag-level activity.
5. Recommendations choose a complementary next action, not merely another item of the same type.

## 6. UI system — Forest Clinical + abstract custom marks

### Palette

- Forest 950 `#102D25` — primary rail and dark surfaces.
- Forest 900 `#174438` — primary brand/interaction.
- Forest 800 `#1F5B49` — active states and important accents.
- Forest 700 `#2F7764` — secondary teal-green actions.
- Sage `#DDEBE2` — soft selection and tag backgrounds.
- Canvas `#F4F7F2` — warm clinical neutral.
- Card `#FCFDF9` — primary reading surface.
- Border `#DCE5DB` — subtle separators.
- Brass `#D5B46A` — restrained attention point for the abstract orbit node.

Dark mode uses a deep green-black canvas with muted sage text and restrained brass focus accents. Avoid saturated neon, glossy gradients and excessive shadows.

### Custom abstract mark family

The logo's signature is the abstract R inside an orbit with one offset node. Workspace marks reuse the ring/monogram and vary node position or secondary orbit strokes. This gives a consistent icon language without stock stethoscopes, books and test tubes in every slot.

### Distinct workspace layouts

- Ward Board: modular dashboard / board layout.
- Clinic: patient-file three-zone layout with timeline and reasoning panel.
- Rounds: editorial teaching room with specialty rail, central explanation/illustration and right-hand pearls/viva.
- Diagnostics Lab: image-first dark canvas and practical station layout.
- Exam Hall: focused assessment canvas with timer and question navigator.
- Data Tools: utility console with job/status and review queue.
- On-Call (future): urgency/triage board with a live event timeline.
- Case Conference (future): timeline, causal analysis and actions board.

### Responsive behavior

Desktop uses a narrow hospital service rail and workspace-specific section navigation. Tablet collapses the rail to marks. Mobile uses a compact bottom service bar, horizontally scrollable workspace sections and single-column content. Preserve the image/answer relationship on small screens.

## 7. Clinical evidence and content governance

Each content item should preserve:

- original source title, author/journal, DOI/PMCID and canonical URL;
- retrieval date and source version where available;
- article/image licence name and URL (or explicit `unknown`);
- specialty and tags;
- clinical reviewer, review date and guideline jurisdiction where relevant;
- content status: harvested-unreviewed, rights-reviewed, clinically-reviewed, authored, approved, retired;
- a content version and change history.

A free-to-read article is not automatically free to adapt or redistribute. Article text and image rights may differ. Keep links and short metadata in discovery mode; only store or adapt full text/media where the source licence permits it. Review clinical currency before using in a debrief or exam question.

For assessment, separate source correctness, item quality and learner performance. A question may have a keyed answer while still being ambiguous or outdated. Formal exam mode should draw only from reviewed, versioned items with a blueprint.

## 8. Phased implementation roadmap

### Already included in this working refactor

- Hospital service rail and new workspace navigation.
- Clinic: Case Reports, Case Library and Case Debriefs sections; the debrief view lists saved encounter reasoning records and opens the full learner response plus reflection prompts.
- Rounds: Specialty Index, High-Yield Pearls, Attending Room, Viva and Tag Index.
- Diagnostics Lab: Visual Spotters and OSCE Stations.
- Exam Hall and Data Tools.
- Forest Clinical tokens, light/dark theme and custom abstract workspace marks.
- Tag schema/API, canonical facets, content registration, tag search and analytics.
- Progressive indexing when case topics, Clinic cases/debriefs, OSCE/Viva items, exam questions and saved Pearls are loaded/created; formative events for case, OSCE and exam attempts.

### Next implementation steps

1. Backfill the existing case, OSCE, exam, specialty and Pearl libraries into the tag index, with source status preserved.
2. Add multi-tag filtering and related-content panels to Case Library, Rounds, Lab and Exam Hall.
3. Upgrade Clinic debriefs into a complete structured explanation with linked evidence and next-practice pathways.
4. Build Attending Room slide/illustration source controls and a dedicated viva scoring rubric.
5. Add richer visual annotation tools (crop/zoom, labelled overlays, blind spotters) and OSCE checklists by specialty.
6. Add an On-Call Room scenario engine.
7. Add Case Conference/M&M with anonymized/simulated cases and non-punitive review.

## 9. Verification and constraints

The current source refactor includes a new additive SQLite migration and tag API, plus list/detail routes for saved clinical learning attempts so Clinic can present case debriefs as a real record shelf. The Python test suite passed **85/85 tests** in this working copy, and TS/TSX syntax transpilation passed. The frontend production build remains unverified: `npm ci` timed out in the available environment, so the UI must be built and smoke-tested on the Windows machine after dependencies install.

The workspace collage in this package is concept art, not a runtime screenshot. Some content sections remain data-dependent: the Attending Room uses existing specialty topic summaries; the illustration area is a source-controlled slot, and an empty state is shown when no verified figure exists. On-Call, Case Conference, Handover and Procedure Theatre are roadmap concepts, not completed workspaces.

## 10. Reference examples and design basis

1. **Aquifer — For Educators.** Its official description combines complete patient encounters, diagnostic tests, images/audio/video, communication modelling and embedded self-assessment with detailed answer explanations. This supports a case-first Clinic model with debriefs rather than a passive course list.
2. **Sectra Education Portal.** Its official product description highlights a multi-specialty anonymized case bank, authentic multimodal imaging, clinical visualization and structured self-paced exercises. This informs the image-first Diagnostics Lab.
3. **ACGME Assessment Guidebook — Review of Medical Errors and Patient Safety Events.** It describes M&M conferences, root-cause analysis and simulated adverse-event debriefs as learning/assessment formats; the guide emphasises contributing factors, prevention and reflection, and notes the importance of standardised cases, scoring criteria and trained evaluators. ACGME Assessment Guidebook (acgme.org)
4. **ACGME Assessment Guidebook — Clinical Reasoning.** The guide lists information gathering, hypothesis generation, problem representation, differential diagnosis, diagnostic justification and management as components of clinical reasoning. This supports tagging and feedback across case, viva and exam tasks.

---

**Product design principle:** HSPTL's unit of learning is not a page or a course. It is a *clinical concept connected to a case, an explanation, a visual or practical skill, an examination task and a review event through shared tags*.


## HSPTL workspace structure (current navigation)

1. **Clinic — Diagnosis:** Case Reports, Case Debriefs, Case Conference, Case Archives.
2. **Rounds — Examination:** Viva Questions, Tagged Report Library, Procedure Theatre.
3. **Lab — Investigations:** Spot Diagnosis, OSCE.
4. **Ward — Management:** On-Call Room, Handover Desk, Consult Room, and Clinical Progression (Intern → Consultant).
5. **Exam Hall — Learning and assessment:** High-Yield Pearls, Summaries, Attending Lectures, Questions, Scores. Scores display the F-to-S scale; the current provisional bands are F 0–49, E 50–59, D 60–69, C 70–79, B 80–89, A 90–96, S 97–100. These bands are product defaults and should be changed if an institution supplies an approved grading policy.
6. **Portfolio — Personal record and administration:** Profile, Progress Board, Data Tools, Admin (question review). The Progress Board shows all six workspaces and distinguishes recorded activity from unavailable tracking; it must not infer competence from activity counts.

