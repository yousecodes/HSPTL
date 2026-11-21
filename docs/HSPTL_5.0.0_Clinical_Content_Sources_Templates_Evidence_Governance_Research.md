# HSPTL 5.0.0 — Clinical Content Sources, Templates & Evidence Governance

**Research and architecture recommendation**  
**Research date:** 20 November 2026  
**Target:** HSPTL 5.0.0  
**Design constraints:** local-first, deterministic, model-free content composition; retain the existing modular-monolith architecture; no API keys required for the initial source set; synthetic patient records remain the exclusive basis for patient-specific case data.

---

## Executive recommendation

HSPTL should have three independent content factories with explicit contracts:

1. **Clinical Knowledge & Educational Content Factory** — creates topic notes, lectures, flashcards, assessments, OSCE/viva material, clinical explanations, learning pathways and evidence summaries from approved medical references, educational resources and competency frameworks.
2. **Synthetic Data Factory** — generates and validates synthetic patient records. Synthea is the patient-record generator; it is not the authority for medical facts, clinical guidance or teaching explanations.
3. **Clinical Case & Simulation Factory** — turns an approved synthetic patient record into a patient-specific case or simulation, then links that case to claims and recommendations in the clinical knowledge repository. It must preserve the distinction between facts present in the synthetic record and additional scenario elements introduced by an approved authoring template.

The factories share a **Reference Registry, Evidence Appraisal Service, Licensing Gate, Terminology Service, Provenance Graph and Content Quality Gate**. They must not share a vague or untyped “source” field.

### The central rule

> Medical references define what learners should know. Competency frameworks define what learners should be able to do. Synthea supplies synthetic patient histories. The Case Factory combines the patient context with separately sourced and reviewed knowledge.

A generated lesson must never be described as imported. A Synthea-derived patient must never be presented as a real patient. A source citation must never be treated as proof that a generated claim is correct merely because the publisher is prestigious.

---

# 1. Source strategy by factory

## 1.1 Clinical Knowledge & Educational Content Factory

### A. Clinical practice guidelines and normative recommendations

These should be the first-choice sources for current recommendations, diagnostic pathways, prevention, treatment, referral and safety guidance.

| Source | Best HSPTL use | Strengths | Important limitation / handling rule | Priority |
|---|---|---|---|---|
| [WHO Guidelines](https://www.who.int/publications/who-guidelines) | Global public-health and clinical guidance; essential medicines, infectious disease, maternal/child health and global recommendations | Formal guideline programme with Guidelines Review Committee approval for listed guidelines; publication and update information | Global guidance may not reflect Egyptian resources, formularies or local pathways. Store population, jurisdiction and implementation context. | Core |
| [WHO Eastern Mediterranean Region](https://www.emro.who.int/) and [Index Medicus for the Eastern Mediterranean Region (IMEMR)](https://www.emro.who.int/information-resources/imemr-database/) | Regional guidance and regional medical literature, including Egypt and neighbouring countries | Regionally relevant sources; IMEMR covers medicine, nursing, pharmacy, public health and allied disciplines and includes Arabic-language literature | IMEMR is a discovery/indexing source, not a blanket quality guarantee for each article. Appraise the underlying publication. | Core regional discovery |
| [Egyptian Health Council (EHC) — Primary Healthcare Protocols](https://lms.ehc.gov.eg/lms/mod/book/tool/print/index.php?id=553) | Egyptian primary-care and nursing education; emergency, family medicine, paediatric, women’s health, dental and nursing care-plan material | Local context and a named expert preparation/supervision group; the online resource states a last update of 18 February 2025 | Record the exact edition/update date; do not assume a 2025 protocol remains current in 2026. Check the issuing body and whether a newer version exists. | Core Egypt |
| [Egyptian Drug Authority (EDA)](https://edaegypt.gov.eg/) | Egyptian medication, pharmaceutical care, antimicrobial use, drug safety and pharmacy guidance | National regulator; publishes national guidance and regulatory reference material | Use for its relevant regulatory/medication scope. Do not generalize a pharmacy or antimicrobial document into a complete disease-management guideline. | Core Egypt medication |
| [GAHAR accreditation standards](https://gahar.gov.eg/en/content-layout/accreditation-standards) | Quality, patient safety, facility processes, infection prevention, governance and institutional competencies | Egyptian national accreditation context; standards are reviewed and field-tested before approval | Accreditation standards are not a substitute for disease-treatment guidelines or evidence of treatment effectiveness. | Core Egypt quality |
| [NICE Guidance](https://www.nice.org.uk/guidance) | Detailed guideline recommendations, evidence reviews, technology appraisals and implementation advice | Transparent guideline methods and structured recommendation content | UK jurisdiction. Store the issuing jurisdiction, publication date, surveillance/update status, and any local adaptation. | Core international |
| [CDC](https://www.cdc.gov/) | Infectious disease, vaccination, public-health, surveillance and infection-prevention guidance | Strong public-health and disease-specific institutional source | US jurisdiction. Check current page date and the exact audience/population. | Core public health |

**Egypt-specific recommendation:** use EHC, EDA and GAHAR as separate source classes, not as one interchangeable “Egypt authority” bucket. EHC’s primary-care protocols are a practical local educational source; EDA is especially relevant to medicine and antimicrobial guidance; GAHAR is valuable for institutional quality and safety standards. The EHC page currently identifies its protocol as last updated 18 February 2025. GAHAR announced its Arabic 2025 primary-healthcare standards in February 2026, describing 144 standards, 21 safety requirements and 14 chapters. These are useful local anchors, but each artifact still needs version and scope checks.

### B. Specialty society and disease-specific guidance

Use these when the topic is within their specialist remit. Maintain a disease-to-source policy rather than assuming one organisation is best for all medicine.

| Specialty / topic | Recommended source | Suitable use | License / currency note |
|---|---|---|---|
| Asthma | [GINA](https://ginasthma.org/) | Strategy reports, diagnosis and management education, asthma severity and control concepts | The 2026 strategy report is available for personal download, but GINA states its documents are copyrighted and cannot be redistributed or posted without permission. Link and cite; do not copy or republish without authorization. |
| COPD | [GOLD](https://goldcopd.org/) | COPD diagnosis, assessment, prevention and management | GOLD has a 2026 report and pocket guide. Check terms for each report and the non-commercial restriction stated for its teaching slide set. |
| Diabetes | [American Diabetes Association Standards of Care](https://professional.diabetes.org/standards-of-care) | Diabetes diagnosis, monitoring, prevention, complications and care across populations | The 2026 Standards are current on the ADA page and are updated annually or more frequently online. Its slide-deck reuse conditions are specific; do not assume all content can be copied or adapted. |
| Cardiovascular disease | [European Society of Cardiology Guidelines](https://www.escardio.org/guidelines/clinical-practice-guidelines) | Cardiovascular diagnosis, risk, heart failure and specialist management | ESC lists 2026 guidelines, including heart failure. Record exact guideline version and European applicability. |
| Resuscitation | [AHA CPR & ECC Guidelines](https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines) | Resuscitation science and emergency cardiovascular care teaching | Use current guideline version and the AHA’s separate permissions policy. Do not mix 2020 and 2025 materials without explicit version handling. |
| Renal medicine | [KDIGO](https://kdigo.org/guidelines/) | Kidney disease guidelines and evidence summaries | Check the status and version of each guideline; distinguish recommendations from evidence certainty. |
| Infectious disease | [IDSA Practice Guidelines](https://www.idsociety.org/practice-guideline/) | Infectious-disease-specific recommendations | Primarily US-focused; check publication/update date and local antimicrobial susceptibility context. |

**Rule:** HSPTL must support more than one jurisdiction. A recommendation from NICE, ADA, GINA, GOLD, ESC or AHA is not automatically an Egyptian national recommendation. Store jurisdiction and applicability explicitly, and require local clinical review before presenting a high-risk recommendation as locally applicable.

### C. Biomedical research and evidence discovery

These sources help discover and appraise the evidence behind teaching claims. A bibliographic database is not itself an evidence-quality rating.

| Source | Best use | Access / automation | Limitations |
|---|---|---|---|
| [PubMed / NCBI E-utilities](https://www.ncbi.nlm.nih.gov/home/develop/api/) | Search biomedical literature, retrieve citation metadata, abstracts and identifiers | Public API. NCBI asks clients to stay at or below 3 requests/second without an API key; register software/tool name and developer contact as required by current NCBI policy. | PubMed is an index, not a quality endorsement. An abstract is not a substitute for full-text appraisal. |
| [Europe PMC REST API](https://dev.europepmc.org/RestfulWebService) | Search publications, retrieve metadata, abstracts, identifiers and links to permitted full text | JSON/XML REST API and open-access services | Full-text availability does not mean unrestricted reuse. Check the license on each article. |
| [PubMed Central Open Access Subset](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/) | Full-text research where the article license permits text mining/reuse | Use only NCBI-authorized retrieval methods such as PMC Cloud, OAI-PMH, E-utilities or BioC. | Not all PMC content is text-minable or reusable; licenses vary article by article. |
| [Cochrane Evidence](https://www.cochrane.org/) | Systematic reviews and evidence summaries | Abstracts and plain-language summaries are openly viewable; institutional access may be needed for full reviews | Do not scrape or republish subscription content. Use the available summary or licensed full text. |
| [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api) | DOI resolution, citation metadata, journal/publisher information, license metadata and post-publication updates | Public JSON REST API; no sign-up required for basic use | Deposited metadata can be incomplete or wrong. Treat Crossref as metadata verification, not peer review or source appraisal. |
| [IMEMR](https://www.emro.who.int/information-resources/imemr-database/) | Regional article discovery, including Arabic and Eastern Mediterranean publications | Web-based bibliographic discovery | Appraise each underlying journal/article; indexing is not proof of low risk of bias. |

### D. Textbooks and open educational resources

| Source | Best HSPTL use | Reuse decision |
|---|---|---|
| [OpenStax](https://openstax.org/subjects/anatomy-and-physiology) | Foundational anatomy, physiology and allied-health teaching | Selected OpenStax books, including Anatomy & Physiology, are CC BY 4.0. Preserve attribution and verify any third-party image or component exclusions. |
| [NCBI Bookshelf](https://www.ncbi.nlm.nih.gov/books/) | Biomedical books, reviews, guideline documents and reference chapters | License varies by book/chapter. Check the copyright/permissions statement on the specific item; do not assume all Bookshelf content is public domain or reusable. |
| [MedEdPORTAL](https://www.mededportal.org/) | Peer-reviewed educational activities, case packages, assessment examples and simulation education | Each publication has its own license. MedEdPORTAL allows CC BY, CC BY-NC or CC0 choices by authors. Use the item’s actual license. |
| Institution-owned textbooks/notes | Locally authored course content | Import only with ownership, license or written permission recorded. |

### E. Competency, curriculum and professional frameworks

| Source | Main use | Jurisdiction / audience note |
|---|---|---|
| [WHO Global Competency and Outcomes Framework for UHC](https://www.who.int/publications/i/item/9789240034662) | Interprofessional health-worker competency structure and outcomes | Global framework; six domains include people-centredness, decision-making, communication, collaboration, evidence-informed practice and personal conduct. |
| [AAMC Core EPAs](https://www.aamc.org/about-us/mission-areas/medical-education/cbme/core-epas) | Medical-school-to-residency clinical activities and assessment mapping | US medical education context; 13 Core EPAs for entering residency. |
| [GMC Outcomes for Graduates](https://www.gmc-uk.org/education/standards-guidance-and-curricula/standards-and-outcomes/outcomes-for-graduates) | Graduate-level knowledge, skills, behaviours and curriculum/assessment blueprinting | UK medical education and regulatory context. |
| [ACGME Milestones and Assessment Resources](https://www.acgme.org/milestones/resources/) | Postgraduate competency and programmatic assessment | US graduate medical education. Do not directly equate with undergraduate competencies. |
| [GAHAR](https://gahar.gov.eg/en/content-layout/accreditation-standards) | Egyptian health-system quality and safety competencies | Institutional accreditation standards, not a complete medical school curriculum. |

---

## 1.2 Synthetic Data Factory — keep Synthea’s scope narrow

Synthea should remain the source for synthetic patient records and population histories. It should not author general medical knowledge, guidelines, teaching notes or answer keys.

| Component | Recommended source / standard | Responsibility |
|---|---|---|
| Patient generation | [Synthea](https://github.com/synthetichealth/synthea) | Reproducible synthetic patients and longitudinal histories |
| Data exchange | [HL7 FHIR R4](https://hl7.org/fhir/R4/) | Patient, Encounter, Condition, Observation, MedicationRequest and related resources |
| FHIR validation | [HL7 FHIR Validator documentation](https://hl7.org/fhir/validation.html) | Structural/profile validation using pinned package versions |
| Terminology | SNOMED CT, LOINC, UCUM, ICD and medication terminology where licensed/appropriate | Code validation and semantic mapping |
| Dataset provenance | HSPTL generation manifest plus FHIR Provenance where relevant | Version, seed, generator, configuration, module checksums, export hashes and validation results |

Every Synthea batch should record the Synthea version, Java version, seed, module-set version, configuration hash, export format, time window, run ID and output checksum. Do not silently fabricate missing patient facts during normalization.

---

## 1.3 Clinical Case & Simulation Factory — combine two independent evidence streams

**Inputs:**

- A validated Synthea patient record (synthetic patient facts).
- HSPTL’s approved knowledge graph (clinical claims and recommendations).
- Approved case/simulation templates.
- Competency and assessment blueprints.

**Do not use real case reports as an unrestricted pool of patient narratives.** Case reports contain information about real patients and may have restrictive copyrights or re-identification risks. Patient-specific data must come from Synthea or properly authorized institutional material.

Recommended design sources:

- [INACSL Healthcare Simulation Standards of Best Practice](https://www.inacsl.org/healthcare-simulation-standards-of-best-practice) — scenario design, measurable objectives, prebriefing, facilitation, debriefing, professional integrity and evaluation. INACSL states its fourth edition was introduced in 2025 and several standards were revised in 2025.
- [MedEdPORTAL](https://www.mededportal.org/) — published educational activities and simulation/standardized-patient examples. Its current author guidance includes a general ESR template and appendices/templates for simulation and standardized patient cases; as of March 2026 it no longer offers separate pedagogically specific ESR templates for every teaching format. Treat current materials as design references and check licenses.
- [AAMC Core EPAs](https://www.aamc.org/about-us/mission-areas/medical-education/cbme/core-epas), [GMC Outcomes for Graduates](https://www.gmc-uk.org/education/standards-guidance-and-curricula/standards-and-outcomes/outcomes-for-graduates), and [WHO competency framework](https://www.who.int/publications/i/item/9789240034662) — competency mapping.

### Case integrity rule

Each case element must be typed as one of:

- `PATIENT_FACT`: present in the Synthea record, with resource ID and path.
- `DERIVED_PATIENT_FACT`: computed from source patient facts by a documented, deterministic rule (for example, age at encounter date).
- `AUTHORED_SCENARIO_DETAIL`: intentionally introduced by an approved scenario template/author; not represented as a fact from the source record.
- `CLINICAL_KNOWLEDGE_CLAIM`: supported by one or more records in the Knowledge Repository.
- `UNKNOWN_OR_NOT_RECORDED`: absent in the source; must not be guessed or filled in automatically.

This prevents generated examination findings, symptom details, treatment response or laboratory results from being falsely attributed to Synthea.

---

# 2. Best content templates for each factory

HSPTL should own versioned, structured templates. External standards guide the fields and workflow; HSPTL should not copy proprietary templates wholesale. Templates below are proposed HSPTL schemas, not representations of any one organization’s copyrighted form.

## 2.1 Knowledge topic / clinical learning article

**Use:** topic notes, core learning material, specialty pages and reference summaries.

Required fields:

1. Topic ID, title, aliases, specialty and version.
2. Intended learner group and prior knowledge.
3. Measurable learning objectives.
4. Key messages / summary.
5. Definition and terminology.
6. Relevant anatomy and physiology.
7. Mechanism/pathophysiology.
8. Clinical presentation and differential considerations (where in scope).
9. Investigations and interpretation.
10. Management concepts, separated by jurisdiction and source date.
11. Contraindications, cautions, uncertainty and exceptions.
12. Common errors / misconceptions.
13. Knowledge-check questions.
14. Claim-level citations and evidence labels.
15. Review owner, review date, next review date and superseded version.

**Acceptance:** every clinical assertion has claim-level source links; recommendations carry population, jurisdiction, version and recommendation strength when the source supplies them; no unsupported dosage or emergency protocol is auto-published.

## 2.2 Lecture / teaching-session template

**Use:** lecture outlines, guided lessons, microlearning and faculty packs.

- Session title, specialty, audience, duration, delivery mode.
- Prior knowledge and prerequisites.
- 3–6 measurable objectives.
- Segment-by-segment structure with time allocation.
- For each segment: core concept, teaching explanation, visual/diagram brief, evidence sources and learner activity.
- Retrieval practice and discussion prompts.
- Summary and take-home messages.
- Knowledge check and assessment alignment.
- Faculty notes and accessibility/language requirements.
- Source/license/attribution metadata.

**Acceptance:** each objective is taught and assessed at least once; lecture statements link to the knowledge graph; imported figures are license checked.

## 2.3 Flashcard template

**Use:** retrieval practice and spaced repetition.

- One learning objective / one atomic knowledge point per card.
- Front: precise question, cloze or cue.
- Back: concise answer.
- Explanation: why the answer is correct, with any necessary qualification.
- Source claim IDs, references and section/page anchors.
- Topic, specialty, difficulty, cognitive process and prerequisite tags.
- Card type, locale, revision and review status.

**Acceptance:** no multi-fact overloaded cards; answer unambiguous; source attached; avoid adding treatment doses to a card without current jurisdiction-specific evidence and clinical review.

## 2.4 SBA / MCQ assessment-item template

**Use:** single-best-answer and other structured question banks.

- Item ID, version, item type and blueprint cell.
- Learner level, specialty, topic, competency and objective.
- Cognitive task and intended difficulty.
- Clinical vignette (only when justified by the objective).
- Focused lead-in; it should pass the “cover-the-options” test.
- Homogeneous, plausible answer options with one best answer.
- Correct answer and explanation.
- Rationale for each distractor (why it is less appropriate, not merely “wrong”).
- Claim-level references for the key and every clinical rationale.
- Source recommendation version/jurisdiction.
- Reviewer decisions and post-use item statistics: facility/difficulty index, discrimination, distractor performance, omission rate and subgroup fairness where sample sizes allow.

**Standards to follow:** NBME Item-Writing Guide (sixth edition; access requires request through NBME) and the RCGP 2026 question-writing guide. The RCGP guide emphasizes a clear single lead-in, one best answer, plausible distractors, application rather than isolated recall and avoiding ambiguous or “least best” formats.

**Acceptance:** answer key supported; no two defensible best answers; no clueing/technical flaws; question is aligned with blueprint and learner level. Do not call an item psychometrically calibrated until sufficient representative response data exist.

## 2.5 OSCE / standardized patient station template

**Use:** clinical skills, communication, consultation, examination, procedures and interprofessional stations.

- Station ID, title, specialty and station type.
- Competency, blueprint objective and learner stage.
- Time, setting, equipment and staffing.
- Candidate-facing instructions.
- Standardized-patient brief, opening line, history prompts and response branches.
- Examiner/facilitator instructions.
- Observable checklist items, each with one action and explicit scoring.
- Global rating scale with anchored descriptors.
- Critical safety items / critical fail criteria with rationale and review approval.
- Expected performance standard and remediation advice.
- Debrief/reflection prompts.
- Claim-level references and source jurisdiction.
- Pilot status, reviewer and version.

**Design basis:** use MedEdPORTAL standardized-patient materials as examples where permitted, plus competency outcomes and an OSCE-specific local blueprint. The Ethiopian Ministry of Health Exam Development Manual and University of Edinburgh OSCE guidance are useful public examples of aligned candidate, examiner, patient, equipment and scoring documents, but are not Egyptian regulatory standards.

**Acceptance:** station instructions align across candidate, examiner and patient documents; checklist items are observable; timing/equipment tested; station pilot completed before summative use.

## 2.6 Simulation scenario template

**Use:** mannequin, computer-based and event-driven HSPTL simulation.

- Scenario ID/version, title, specialty and target learners.
- Needs assessment and rationale.
- Measurable objectives and expected behaviours.
- Learning prerequisites and prebrief.
- Patient/context data with provenance tags.
- Initial state and observations.
- Available actions, expected actions and action preconditions.
- Event/time triggers and conditional branches.
- State changes/consequences and termination criteria.
- Facilitator prompts and confederate cues.
- Expected critical decisions and escalation points.
- Debrief plan, feedback model and reflection prompts.
- Evaluation plan and pilot results.
- Clinical references and recommendation versions.
- Clinical reviewer approval and next review date.

**Design basis:** INACSL’s 2025 fourth-edition standards, especially measurable outcomes/objectives, simulation design, prebriefing, facilitation, debriefing, professional integrity and evaluation. INACSL says all simulation experiences originate with measurable objectives and its standards cover a planned debriefing process.

**Acceptance:** deterministic replay; all state changes trace to rules/events; every clinical action rule links to approved content; new high-risk pathways reviewed and piloted.

## 2.7 Clinical case template (synthetic patient)

**Use:** case-based learning and patient-specific clinical reasoning.

- Case ID/version and `SYNTHETIC CONTENT` marker.
- Synthea dataset ID, patient ID, generation seed reference and source resource IDs.
- Intended learner, specialty, competency and objectives.
- Presenting problem: only source-backed or explicitly authored.
- Patient profile and history, with fact-level origin labels.
- Encounter timeline.
- Recorded conditions, medications, allergies, observations, tests and procedures.
- Missing information explicitly marked as unknown/not recorded.
- Authored simulation additions kept separately from patient facts.
- Clinical questions and evidence-linked answer rationales.
- Expected clinical reasoning/assessment rubric.
- Debrief and further reading.
- Sources and reviewer status.

**Acceptance:** no fabricated patient facts; every displayed source fact has an identifier; added teaching details are labelled as authored scenario detail; all recommendations cite the Knowledge Repository.

## 2.8 Clinical pathway / guideline digest template

**Use:** clinical pathway education, recommendation summaries and decision support teaching.

- Source guideline, issuing organization, jurisdiction, version/date and status.
- Target population and exclusions.
- PICO or equivalent clinical question.
- Recommendation statement verbatim only when permitted; otherwise a clearly labelled paraphrase.
- Recommendation direction and strength (e.g., strong/conditional) as stated by the guideline.
- Certainty of evidence (GRADE high/moderate/low/very low) per outcome where available.
- Benefits, harms, values/preferences, resources, equity, feasibility and applicability.
- Flow/decision structure, assumptions and exceptions.
- Local adaptation decision and reviewer.
- Update trigger and supersession relationship.

**Acceptance:** do not invent GRADE labels; do not convert a recommendation strength into a source credibility score; conflicts between jurisdictions remain visible.

## 2.9 Curriculum / learning pathway template

**Use:** modules, specialty pathways, learning routes and competency maps.

- Programme title, learner profile and scope.
- Governing competency framework and version.
- Competency → objective → learning activity → assessment mapping.
- Prerequisites and sequence constraints.
- Units, duration and delivery mode.
- Knowledge, skills and professional-behaviour coverage.
- Formative/summative assessment blueprint.
- Clinical exposure/simulation requirements.
- Inclusion, accessibility and interprofessional considerations.
- Completion criteria and remediation routes.
- Framework/jurisdiction tags and review date.

**Standards to consider:** WHO Global Competency and Outcomes Framework for UHC; AAMC Core EPAs; GMC Outcomes for Graduates; ACGME Milestones for postgraduate programmes; local institutional curriculum requirements and GAHAR quality standards where relevant.

## 2.10 Debrief / feedback template

**Use:** simulation review and learner feedback.

- Scenario and learner-run IDs.
- Stated learning objectives.
- Learner actions/events and relevant timestamps.
- Expected action/rule and actual action comparison.
- Observed strengths.
- Missed opportunities and their consequences in the simulation model.
- Evidence-linked explanations.
- Reflection questions and learner self-assessment.
- Two or three targeted next steps.
- Related learning resources and revision questions.
- Debrief facilitator/reviewer and version.

**Acceptance:** distinguish observed actions from inferred reasoning; never claim to know a learner’s internal thought process unless they stated it; explain consequences only as represented by the simulation’s validated model.

---

# 3. Reference system: provenance, validity and evidence strength

## 3.1 Do not collapse all trust into one number

HSPTL should display at least four separate assessments:

1. **Reference identity/integrity:** Can HSPTL resolve and verify the cited work and its exact version?
2. **Source appraisal:** Is this source methodologically and editorially trustworthy for its source type?
3. **Evidence certainty / recommendation strength:** What does the source say about certainty and recommendation strength, when applicable?
4. **Claim support:** Does this precise generated claim follow from the referenced source(s), for this population and jurisdiction?

A single “source score” cannot replace these dimensions. For example, GRADE certainty is assessed for a body of evidence and outcome, not assigned to an entire organization or every individual article. GRADE recommendation strength is also distinct from evidence certainty; contextual factors may influence strong versus conditional recommendations.

## 3.2 Source appraisal by source type

| Source type | Recommended appraisal method | Output / warning |
|---|---|---|
| Clinical practice guideline | AGREE II (six domains: scope/purpose, stakeholder involvement, rigour, clarity, applicability, editorial independence); optionally RIGHT for reporting completeness | Report domain scores and appraiser notes. RIGHT is a reporting checklist, not a guideline quality score. Do not invent a universal AGREE II pass threshold. |
| Systematic review | AMSTAR 2 and/or ROBIS | AMSTAR 2 uses critical/non-critical weaknesses to produce High, Moderate, Low or Critically Low confidence; it explicitly should not be collapsed into a simple summed percentage. ROBIS appraises risk of bias in the review process. |
| Randomized controlled trial | Cochrane RoB 2 | Low risk, Some concerns or High risk for the relevant result/domain; not a journal-level rating. |
| Non-randomized intervention study | ROBINS-I (appropriate version) | Risk-of-bias judgment by domains; requires trained appraisal. |
| Diagnostic accuracy study | QUADAS-2 | Risk of bias and applicability across patient selection, index test, reference standard, and flow/timing. |
| Evidence synthesis / systematic review report | PRISMA 2020 | Reporting completeness. PRISMA is not a risk-of-bias or evidence-certainty tool. |
| Textbook / educational resource | Publisher/editorial review, authorship, edition, references, update record, errata and license; optional faculty appraisal | Do not assign GRADE to a textbook. A high-quality textbook may be appropriate for foundations but not current dosing or recommendations. |
| Competency framework / regulator standard | Issuing authority, approval status, date, scope, jurisdiction, revision history and formal adoption status | It defines expected outcomes/standards; it is not a clinical trial or treatment evidence source. |
| Synthetic dataset | Generator version, reproducibility, schema validity, provenance completeness, quality tests and simulation limitations | No clinical evidence certainty rating. Synthetic records are not evidence that a treatment works. |

**Critical distinctions:**

- AGREE II assesses guideline development/reporting quality across domains; use its domain results, not an arbitrary aggregate “clinical truth” score.
- AMSTAR 2 explicitly warns against adding item ratings into a single numerical score; its confidence rating follows critical flaws.
- RIGHT and PRISMA improve transparency of reporting; they do not establish that the guideline or study is valid.
- GRADE certainty (high/moderate/low/very low) applies to outcomes across a body of evidence, not to the publisher or a single isolated citation.
- “Strong recommendation” versus “conditional recommendation” is about the panel’s recommendation, not a score for the source itself.

## 3.3 Proposed HSPTL Reference Validity Index (RVI)

HSPTL may use a transparent **internal triage index** to prioritize verification. It must be labelled “HSPTL Reference Validity Index — internal heuristic”, not “evidence grade”, “probability of correctness” or a validated clinical appraisal instrument.

### Proposed 100-point rubric

| Dimension | Points | What is assessed |
|---|---:|---|
| Authenticity and authority | 15 | Official issuing body/publisher, identifiable authorship, document provenance and stable host |
| Methodological transparency | 20 | How evidence was searched, selected, appraised and converted to recommendations; peer-review/editorial process where applicable |
| Version and currency | 15 | Publication/revision date, current/withdrawn/superseded status, update policy and last verification |
| Applicability / directness | 15 | Population, setting, intervention, profession and jurisdiction match the intended HSPTL content |
| Citation and traceability integrity | 15 | DOI/PMID/ISBN/official identifier, exact section/page/recommendation anchor, stable URI and retrievable source metadata |
| Independent corroboration | 10 | Agreement with independent authoritative evidence or a current guideline; conflicts are recorded rather than hidden |
| Transparency and accountability | 10 | Conflicts of interest, funding, editorial independence, corrections/retractions and responsible organization disclosed |
| **Total** | **100** | Internal triage only |

### Suggested display bands

| RVI | Label | Meaning |
|---:|---|---|
| 85–100 | **Strong source validity** | Source identity and governance are strong, current and applicable; still requires claim-level appraisal. |
| 70–84 | **Moderate source validity** | Generally credible but some caveat exists: indirect population, older edition, incomplete methods or limited corroboration. |
| 50–69 | **Weak source validity** | Material uncertainty about methods, applicability, currency or traceability; discovery/background only unless reviewed. |
| 0–49 | **Insufficient / unverified** | Do not use to support clinical recommendations or auto-publish generated clinical claims. |
| Hard-stop | **Invalid / withdrawn** | Source is retracted, withdrawn, superseded for the relevant recommendation, cannot be authenticated, or has an unresolved integrity concern. |

These thresholds are proposed HSPTL governance choices, not thresholds validated by AGREE II, GRADE or another professional body. Pilot and calibrate them using independent expert ratings before treating them as operationally reliable.

### Hard gates that override a numerical result

- Retraction, withdrawal, serious correction or supersession relevant to the claim → block or suspend affected content pending review.
- Cannot verify the exact item/version → `UNVERIFIED`; no clinical support claim.
- No clear rights to copy/rehost/adapt → import/redistribution blocked; a citation/link may still be permissible subject to applicable law and terms.
- Clinical high-risk domain (dose, contraindication, emergency sequence, pregnancy, paediatric prescribing, antimicrobial selection, etc.) → qualified review required regardless of RVI.
- Major jurisdiction mismatch → cannot present as local guidance without explicit adaptation and approval.
- Conflicting current authoritative recommendations → show conflict and jurisdiction; do not silently average or select one.

## 3.4 Claim Support Index (CSI)

A generated content item contains many claims. Score each clinical claim separately, not merely the entire page.

**Proposed 100-point claim-support rubric:**

| Dimension | Points | Question |
|---|---:|---|
| Direct support | 30 | Does the cited source explicitly support this exact claim, rather than merely discuss the topic? |
| Source appraisal | 20 | Is the underlying source appraisal appropriate and acceptable for this source type? |
| Population / jurisdiction fit | 15 | Does the evidence apply to the stated population, profession, setting and jurisdiction? |
| Currency | 10 | Is the underlying recommendation or knowledge current for this claim? |
| Independent corroboration / conflict handling | 15 | Are there independent supporting sources, or are disagreements identified and explained? |
| Reference fidelity | 10 | Is the correct version, section, page, table or recommendation linked and retrievable? |
| **Total** | **100** | Per-claim support measure; not the probability that a statement is true |

| CSI | Label | Content action |
|---:|---|---|
| 90–100 | **Strongly supported** | May enter automated release only if risk tier and source/licensing gates also pass. |
| 75–89 | **Moderately supported** | Suitable for draft/low-risk educational use; review policy determines publication. |
| 50–74 | **Weakly supported** | Keep in draft or label as uncertain; do not use for a clinical recommendation or keyed assessment without review. |
| 0–49 | **Unsupported** | Block the claim from publication. |
| No verified reference | **Unreferenced** | Block clinical assertion from publication. |

The thresholds are initial HSPTL policy settings and must be calibrated. Avoid false precision: show the score, its dimensions, and why points were lost. A high score cannot overrule a retraction, license failure, unsafe claim or unresolved guideline conflict.

## 3.5 Evidence certainty and recommendation strength fields

Where available, store these as separate structured values:

- `evidence_certainty`: `HIGH | MODERATE | LOW | VERY_LOW | NOT_RATED` (GRADE terminology, only where the source has assessed the body of evidence).
- `recommendation_strength`: `STRONG | CONDITIONAL | WEAK | GOOD_PRACTICE_STATEMENT | NOT_STATED` (map the source’s own terminology; do not force other systems into GRADE labels).
- `direction`: `FOR | AGAINST | NEUTRAL_OR_NO_RECOMMENDATION`.
- `evidence_population`, `intervention`, `comparator`, `outcome` (PICO/PECO as applicable).
- `source_jurisdiction`, `local_applicability`, `adaptation_status`.

Do not derive GRADE from publication type alone. Do not convert “RCT = high” into a permanent article badge; risk of bias, inconsistency, indirectness, imprecision and publication bias can lower certainty. Conversely, strong recommendations can sometimes be issued with low certainty for contextual or ethical reasons.

---

# 4. Reference and provenance data model

## 4.1 Core entities

HSPTL should maintain an immutable/versioned reference registry with these records:

### `ReferenceRecord`

- `reference_id` (stable internal ID)
- `work_type` (guideline, guideline recommendation, systematic review, RCT, observational study, textbook, curriculum framework, educational resource, dataset, regulatory standard)
- `title`, `authors_or_issuing_body`, `publisher`, `publication_date`
- `edition`, `version`, `revision_date`, `status` (current, superseded, withdrawn, corrected, retracted, unknown)
- `jurisdiction`, `language`, `population`, `discipline`
- `doi`, `pmid`, `pmcid`, `isbn`, official document ID and stable URI
- `section`, `page`, `table`, recommendation ID, paragraph/anchor locator
- `license_id`, license URL, attribution text, use permissions, commercial-use permission, derivative/adaptation permission, redistribution permission
- retrieval timestamp, last-verified timestamp, content metadata hash, artifact hash where storage is allowed
- `rvi_score`, sub-scores, appraisal method, reviewer, review date and notes
- `supersedes_reference_id`, `superseded_by_reference_id`, retraction/correction links

### `ClinicalClaim`

- `claim_id`, canonical statement, claim type (definition, mechanism, diagnostic, prognostic, intervention, safety, competency, epidemiology, educational)
- target population, setting, jurisdiction, time context
- applicability/exclusion tags
- linked `ReferenceRecord` IDs and exact locations
- edge relation: `SUPPORTS`, `QUALIFIES`, `CONTRADICTS`, `BACKGROUND_FOR`, `SUPERSEDES`, `DERIVED_FROM`
- evidence certainty and recommendation strength where applicable
- RVI and CSI; review state; reviewer and approval expiry

### `ContentAsset`

- `content_id`, content type, version, title and intended audience
- visible provenance class (generated, imported, synthetic, derived)
- source claim IDs, reference IDs and content lineage
- generator ID/version, template ID/version, rule-pack version
- created/modified dates and content hash
- license/rights declaration and attribution block
- risk tier, validation report, clinical review state, publication state
- supersedes/superseded-by and affected-content relationships

### `GenerationActivity`

- activity ID, started/ended time, actor/system agent
- input reference IDs and source versions
- input synthetic dataset IDs only for case generation
- extraction/parser version, transformation IDs, composer version, template version and deterministic seed where relevant
- output content IDs and hashes
- rules/decisions executed and validation results

## 4.2 Citation granularity

- A clinical paragraph should have references at paragraph/claim level, not only a bibliography at the end of a 20-page document.
- A question must cite the source for the correct answer and every clinically meaningful rationale.
- A dosage, contraindication, emergency pathway or threshold should link to an exact recommendation/table/section in a current authoritative source.
- OSCE criteria must link to the relevant skill/competency standard and, when clinically normative, the clinical guidance supporting the expected action.
- A case timeline fact must link to the exact Synthea FHIR resource/element. Teaching explanations must link to clinical knowledge claims.

## 4.3 Standards alignment

- Use **HL7 FHIR R4 `Provenance`** for provenance of FHIR resources/versions where that exchange use case is relevant.
- Use **FHIR R4 `DocumentReference`** to index source documents and non-FHIR documents.
- Use **FHIR R4 `Library`** for shareable definitional knowledge artifacts where suitable.
- Keep an HSPTL internal citation/reference schema for bibliographic citations and claim-to-source links; do not assume every later FHIR Citation capability is present in the current FHIR R4 baseline.
- Use the W3C **PROV-O** pattern conceptually: source documents are `Entity` records, extraction/composition/review are `Activity` records, and HSPTL/software/reviewers are `Agent` records. Record `used`, `wasGeneratedBy`, `wasDerivedFrom`, `wasAssociatedWith` relationships.

---

# 5. Visible content provenance labels

The UI should distinguish origin from review status. These are separate dimensions.

## 5.1 Four primary origin labels

| Label | Meaning | Typical content | Required metadata |
|---|---|---|---|
| **GENERATED CONTENT** | Composed by HSPTL from approved references, claims, rules and templates. It is generated even if no AI/LLM is used. | Topic note, lecture outline, flashcard, question, OSCE rubric, curriculum | Generator/template/rule versions; cited sources; generated timestamp; review state; attribution |
| **IMPORTED CONTENT** | External material or an institution-provided asset is brought into HSPTL substantially as received. | Uploaded PDF/lecture, licensed slide deck, imported educational package | Origin/publisher/author; exact version; license/permission; import date; file hash; attribution |
| **SYNTHETIC CONTENT** | Patient-specific or data content is simulated rather than describing a real patient. | Synthea patient, synthetic FHIR history, synthetic case source facts | Generator/version/seed/dataset ID; synthetic notice; source resource IDs; transformation lineage |
| **DERIVED CONTENT** | An asset combines more than one origin class or is materially transformed from imported/synthetic material. | Case-based question using synthetic case facts and guideline knowledge; adapted lecture from licensed source | Parent assets; derivation description; each source class; transformation and permission records |

## 5.2 Secondary status labels

Do not confuse origin with approval. Add secondary labels:

- `DRAFT`
- `VALIDATED — AUTOMATED`
- `CLINICALLY REVIEWED`
- `APPROVED FOR EDUCATIONAL USE`
- `PUBLISHED`
- `UNDER REVIEW`
- `SUPERSEDED`
- `WITHDRAWN`
- `EXPIRED / REVIEW DUE`

Examples:

- `GENERATED CONTENT` + `VALIDATED — AUTOMATED` + `CLINICAL REVIEW REQUIRED`.
- `IMPORTED CONTENT` + `LICENSE VERIFIED`.
- `SYNTHETIC CONTENT` + `SYNTHETIC PATIENT — NOT REAL`.
- `DERIVED CONTENT` + `GENERATED FROM SYNTHETIC CASE` + `GUIDELINE-REFERENCED`.

## 5.3 Example learner-facing labels

**Generated lesson:**

> GENERATED CONTENT · Rule-based composition · Evidence: Strongly supported · Clinical review: Approved for educational use · Sources: WHO guideline vX; EHC protocol vY · Last checked: DD MMM YYYY.

**Imported lecture:**

> IMPORTED CONTENT · Publisher/author · License: CC BY 4.0 · Attribution available · Imported: DD MMM YYYY.

**Synthetic case:**

> SYNTHETIC CONTENT · Patient generated with Synthea · Not a real patient · Dataset: … · Seed/version lineage available.

**Hybrid case question:**

> DERIVED CONTENT · Case context: Synthetic patient · Clinical rationale: Referenced guideline · Generated by HSPTL template v…

---

# 6. Licensing and copyright controls

A source can be authoritative but still not be reusable. Licensing is a hard operational permission gate, not a component of medical evidence certainty.

| Source | Important observed reuse condition | HSPTL handling |
|---|---|---|
| OpenStax | Selected textbooks use CC BY 4.0 | Can adapt/redistribute under the license with attribution and any component-specific exclusions respected. |
| NCBI Bookshelf | Copyright and license terms vary by book/chapter | Check each item. Do not treat all Bookshelf content as public domain. |
| PMC Open Access Subset | Article licenses vary; not all PMC items allow text mining/reuse | Check article-specific license and use only authorized retrieval methods. |
| MedEdPORTAL | Publication license may be CC BY, CC BY-NC or CC0 | Store the exact per-publication license and follow its terms. |
| GINA | Documents are copyrighted; free download for personal use does not authorize redistribution or website posting | Link/cite; do not copy or adapt without permission. |
| GOLD | 2026 reports/pocket guide are available; teaching slide set notes non-commercial educational use | Check each file’s terms, version and permitted use before importing. |
| ADA | 2026 slide deck permits presentation use only if content is unaltered and attributed; commercial use or print reproduction requires permission | Do not edit/repackage slides unless separately authorized. |
| WHO / NICE / EDA / EHC / GAHAR | Terms can vary by publication and document | Verify each item’s own reuse terms. Official-hosted does not automatically mean open-license. |

**Factory behavior:**

- If no reuse permission exists, HSPTL may store bibliographic metadata and a link where lawful, but must not download/re-host/reproduce or train/extract content contrary to terms.
- Keep license metadata on imported source documents and derived assets.
- Preserve required attributions and indicate adaptations.
- Block publication if required permission is missing or cannot be verified.
- Do not scrape subscription portals or bypass access controls.

---

# 7. Automated source discovery and updates

## Recommended first connectors

1. **WHO guideline catalogue** — periodic metadata checks, new guideline/update dates and status.
2. **EHC / EDA / GAHAR** — curated local source registry and scheduled link/version checks; manual source approval for new local protocols.
3. **NICE** — guidance pages, publication/update/surveillance information.
4. **PubMed E-utilities** — topic alert searches and citation metadata; obey rate limits and register software identity.
5. **Europe PMC REST** — metadata and permitted open-access full text.
6. **Crossref REST** — DOI metadata, license metadata and post-publication update signals.
7. **Cochrane** — available abstracts/plain-language summaries and institutionally authorized full text.
8. **Specialty guideline repositories** — GINA, GOLD, ADA, ESC, AHA, KDIGO, IDSA, each with a source-specific version monitor.

## Update process

- Store source `published_at`, `updated_at`, `checked_at` and `effective_from` dates where available.
- Detect new edition, update, correction, expression of concern, retraction or withdrawal.
- Identify all claims and assets connected to the affected reference.
- Put affected generated clinical content into `UNDER REVIEW` or `REVIEW DUE`; do not silently change published content.
- Create a deterministic impact report listing affected lessons, questions, OSCEs, simulations and curriculum nodes.
- Publish a new version only after rules and review requirements pass.

## No-API-key first design

- Crossref REST: basic use requires no sign-up.
- Europe PMC REST: public web service.
- NCBI E-utilities: no API key is required for low-rate use under the current documented limit; stay within 3 requests/second, register the tool/contact identity, cache results and use batching. An API key is only needed for higher request rates under NCBI's stated policy.
- For other publishers and guideline authorities, use supported feeds/APIs, downloads, or curated manual ingestion. Do not assume that a webpage is licensed for scraping just because it is publicly viewable.

---

# 8. Publication policy and risk tiers

| Risk tier | Examples | Automated actions allowed | Publication rule |
|---|---|---|---|
| R0 — Low clinical risk | Glossary, basic anatomy, non-clinical orientation | Import metadata, deterministic composition, automated checks | Automatic release if license, citations and quality gates pass |
| R1 — Educational clinical knowledge | Pathophysiology, mechanisms, basic interpretation | Generate draft, map claims, check consistency and sources | Release only if source/claim gates pass; review sampling and expiry policy |
| R2 — Assessment and skills | SBA answer keys, OSCE checklists, viva rubrics, clinical reasoning explanations | Generate drafts and run deterministic validators | Qualified educator/clinical reviewer approval required before summative or high-stakes use |
| R3 — High-risk clinical guidance | Drug doses, contraindications, emergency pathways, antimicrobial recommendations, pregnancy/paediatric treatment | Extract, compare, flag changes and prepare review packets | Qualified clinician/pharmacist review and local approval required; no unattended clinical certification |

Automated validation is not clinical validation. No source score or content score should bypass R2/R3 review gates.

---

# 9. Example content provenance record

```yaml
content_id: HSPTL-EDU-ASTHMA-001-v1
content_type: single_best_answer
origin_labels:
  - GENERATED_CONTENT
status_labels:
  - VALIDATED_AUTOMATED
  - CLINICAL_REVIEW_REQUIRED

generator:
  name: HSPTL Deterministic Content Composer
  version: 5.0.0
  template_id: HSPTL-SBA-CLINICAL-v1
  rule_pack: assessment-rules-1.0

learning:
  specialty: respiratory_medicine
  topic: asthma
  learner_level: undergraduate_clinical
  objective_ids: [RESP-ASTHMA-OBJ-04]
  competency_ids: [WHO-UHC-DECISION-MAKING]

claims:
  - claim_id: CLAIM-ASTHMA-0001
    statement_ref: item.stem
    references:
      - reference_id: REF-GINA-2026
        locator: section/table/page-or-recommendation-id
        relation: SUPPORTS
    rvi: 91
    rvi_band: STRONG_SOURCE_VALIDITY
    csi: 94
    csi_band: STRONGLY_SUPPORTED
    evidence_certainty: NOT_RATED
    recommendation_strength: NOT_STATED
    jurisdiction: INTERNATIONAL
    last_verified: 2026-11-20

rights:
  copied_source_text: false
  source_license_checked: true
  attribution_required: true

review:
  clinical_review_state: PENDING
  reviewer_id: null
  approved_at: null
  next_review_due: null

lineage:
  source_record_ids: [REF-GINA-2026]
  parent_asset_ids: []
  synthetic_patient_id: null
  generated_at: 2026-11-20T00:00:00Z
  content_sha256: '<sha256>'
```

This is an illustrative internal HSPTL data contract. Dates, scores and IDs are examples, not actual appraisal results.

---

# 10. Recommended implementation order for HSPTL 5.0.0

## Phase A — Source governance foundation

- Source registry and per-document license registry.
- Reference identity and version resolver (DOI, PMID, PMCID, ISBN, official document IDs).
- Source status and update monitor.
- Provenance labels and immutable lineage graph.

## Phase B — Knowledge graph and evidence appraisal

- Structured clinical claim records.
- Claim-to-reference links with exact source locators.
- Appraisal workflows selected by source type (AGREE II, AMSTAR 2/ROBIS, RoB 2, ROBINS-I, QUADAS-2, or educational-source appraisal).
- GRADE certainty and recommendation strength kept separate.
- RVI and CSI as explicitly provisional internal triage indices.

## Phase C — Deterministic content templates

- Knowledge topic and lecture templates.
- Flashcard template.
- SBA/MCQ and short-answer template.
- OSCE/viva template.
- Simulation template.
- Curriculum/pathway template.
- Debrief/feedback template.

## Phase D — Three factory contracts

- Knowledge Factory accepts approved reference/claim records and competency data.
- Synthetic Data Factory accepts Synthea configuration and produces synthetic patient datasets.
- Case Factory accepts a synthetic patient record plus approved knowledge claims, scenario rules and case template.

## Phase E — Publication and monitoring

- Risk-tier gates.
- Automated quality and duplication checks.
- Educator/clinical review queue.
- Supersession and retraction impact analysis.
- Learner-facing labels and citation panels.

### Acceptance criteria

1. Every generated clinical assertion has one or more retrievable claim-level references, or is visibly marked as an authored non-evidence scenario detail.
2. Every imported asset has an identifiable source and rights decision.
3. Every synthetic patient/case is visibly marked synthetic and traceable to its Synthea version/seed/dataset.
4. Hybrid assets show all source types and derivation lineage.
5. Source validity, evidence certainty, recommendation strength and claim support are stored and displayed separately.
6. Appraisal method is selected based on source type; checklists are not misapplied.
7. Copyright/license failures block import/re-hosting/adaptation.
8. Retraction, withdrawal or supersession creates an impact report and flags derived content.
9. High-risk clinical recommendations cannot be published without the appropriate qualified approval.
10. No LLM, external generative AI service or API key is required for the deterministic core pipeline.
11. Existing HSPTL learning, simulation, content factory, event log and replay capabilities remain functional.

---

# 11. Shortlist: the highest-value sources to onboard first

For an initial release, do not ingest the entire internet. Start with a curated, license-aware source registry:

1. WHO Guidelines.
2. EHC Primary Healthcare Protocols.
3. EDA pharmaceutical and antimicrobial guidance.
4. GAHAR accreditation and patient-safety standards.
5. NICE Guidance.
6. GINA, GOLD, ADA, ESC and AHA for their specialty areas, with document-specific copyright controls.
7. PubMed / NCBI E-utilities for discovery and bibliographic metadata.
8. Europe PMC and the permitted PMC Open Access subset for licensed full text.
9. Cochrane abstracts and authorized institutional full text.
10. OpenStax for open foundational teaching material.
11. NCBI Bookshelf only after per-item rights inspection.
12. MedEdPORTAL for peer-reviewed educational design examples under per-item license.
13. WHO, AAMC, GMC, ACGME and GAHAR competency/standards resources, mapped by jurisdiction and profession.
14. SNOMED CT, LOINC, UCUM and applicable medication/diagnostic terminologies under their respective licenses.

---

# 12. Research references

The following are official or primary sources used to shape the recommendations. Each item should be rechecked for version and rights during implementation.

## Clinical guidelines and national sources

- WHO. WHO Guidelines catalogue: https://www.who.int/publications/who-guidelines
- NICE. Guidance: https://www.nice.org.uk/guidance
- CDC. ACIP GRADE Handbook: https://www.cdc.gov/acip-grade-handbook/hcp/chapter-7-grade-criteria-determining-certainty-of-evidence/index.html
- Egyptian Health Council. Protocols for the Most Common Diseases in Primary Healthcare Facilities (page indicates last update 18 February 2025): https://lms.ehc.gov.eg/lms/mod/book/tool/print/index.php?id=553
- Egyptian Drug Authority. Regulatory reference and pharmaceutical-care guidance: https://edaegypt.gov.eg/en/the-regulatory-reference-of-the-egyptian-drug-authority-eda/guidance-of-ca-of-pharmaceutical-care/
- EDA. National Guidance for Antimicrobial Stewardship Using Antibiogram (16 August 2026): https://dev.edaegypt.gov.eg/en/media-center/news/egyptian-drug-authority-issues-national-guidance-for-antimicrobial-stewardship-using-antibiogram/
- GAHAR. Accreditation standards: https://gahar.gov.eg/en/content-layout/accreditation-standards
- GAHAR. 2025 Primary Healthcare Accreditation Standards announcement (5 February 2026): https://gahar.gov.eg/en/news/phc-2025
- GINA. 2026 Strategy Report: https://ginasthma.org/2026-gina-strategy-report/
- GOLD. 2026 Report and Pocket Guide: https://goldcopd.org/2026-gold-report-and-pocket-guide/
- ADA. Standards of Care in Diabetes: https://professional.diabetes.org/standards-of-care
- ESC. Clinical Practice Guidelines: https://www.escardio.org/guidelines/clinical-practice-guidelines
- AHA. CPR & ECC Guidelines: https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines
- WHO EMRO. IMEMR database: https://www.emro.who.int/information-resources/imemr-database/

## Discovery, metadata, textbooks and licensing

- NCBI. APIs and E-utilities: https://ncbi.nlm.nih.gov/home/develop/api/
- NCBI. E-utilities usage limits and API key policy: https://eutilities.github.io/site/API_Key/usageandkey/
- Europe PMC. RESTful web service: https://dev.europepmc.org/RestfulWebService
- Europe PMC. Open Access subset and license information: https://dev.europepmc.org/downloads/openaccess
- PMC. Open Access Subset, retrieval and licensing rules: https://pmc.ncbi.nlm.nih.gov/tools/openftlist/
- Crossref. REST API: https://www.crossref.org/documentation/retrieve-metadata/rest-api
- Cochrane. Access to Cochrane Evidence: https://help.cochrane.org/kb/article/27-how-can-i-access-cochrane-evidence/
- OpenStax. Anatomy & Physiology: https://openstax.org/subjects/anatomy-and-physiology
- OpenStax. Anatomy & Physiology 2e preface/license: https://openstax.org/books/anatomy-and-physiology-2e/pages/preface
- NCBI Bookshelf. Copyright notice: https://www.ncbi.nlm.nih.gov/sites/books/about/copyright/
- MedEdPORTAL. Getting Started and template/license information: https://www.mededportal.org/getting-started
- MedEdPORTAL. Author FAQ, including 2026 template guidance: https://www.mededportal.org/faq

## Assessment, simulation and competencies

- NBME. Item-Writing Guide (sixth edition): https://www.nbme.org/institutions/nbme-item-writing-guide/
- RCGP. Question-writing guide for 2026: https://www.rcgp.org.uk/getmedia/e67f9627-7ef5-451e-aefd-eeb0be6953da/Question-writing-guide-for-2026.pdf
- INACSL. Healthcare Simulation Standards of Best Practice: https://www.inacsl.org/healthcare-simulation-standards-of-best-practice
- AAMC. Core EPAs: https://www.aamc.org/about-us/mission-areas/medical-education/cbme/core-epas
- GMC. Outcomes for Graduates: https://www.gmc-uk.org/education/standards-guidance-and-curricula/standards-and-outcomes/outcomes-for-graduates
- ACGME. Milestones resources and Assessment Guidebook: https://www.acgme.org/milestones/resources/
- WHO. Global Competency and Outcomes Framework for UHC: https://www.who.int/publications/i/item/9789240034662

## Evidence appraisal and reporting

- GRADE Working Group. GRADE Book: https://book.gradepro.org/
- GRADE. Overview of the GRADE approach: https://book.gradepro.org/guideline/overview-of-the-grade-approach
- GRADE. Recommendation types and strength: https://book.gradepro.org/guideline/grade-recommendations
- CDC. ACIP GRADE Handbook, certainty of evidence: https://www.cdc.gov/acip-grade-handbook/hcp/chapter-7-grade-criteria-determining-certainty-of-evidence/index.html
- AGREE II. Instrument and user manual: https://www.agreetrust.org/resource-centre/agree-ii/
- AMSTAR 2. Original BMJ paper: https://www.bmj.com/content/358/bmj.j4008
- ROBIS. University of Bristol: https://www.bristol.ac.uk/population-health-sciences/projects/robis/robis-tool/
- Cochrane. RoB 2: https://methods.cochrane.org/bias/resources/rob-2-revised-cochrane-risk-bias-tool-randomized-trials
- QUADAS-2. Original/overview resources: https://www.bristol.ac.uk/population-health-sciences/projects/quadas/quadas-2/
- RIGHT. Reporting guideline: https://equator-network.org/reporting-guidelines/right-statement/
- PRISMA 2020: https://www.prisma-statement.org/prisma-2020
- NICE. Reviewing the evidence and GRADE: https://www.nice.org.uk/process/pmg6/chapter/reviewing-the-evidence

## Provenance and interoperability

- HL7 FHIR R4 Provenance: https://www.hl7.org/fhir/R4/provenance.html
- HL7 FHIR R4 DocumentReference: https://www.hl7.org/fhir/R4/documentreference.html
- HL7 FHIR R4 Library: https://hl7.org/fhir/R4/library.html
- W3C PROV-O: https://www.w3.org/TR/prov-o/

---

## Final decision

For HSPTL 5.0.0, build the **Clinical Knowledge & Educational Content Factory** from trusted guidelines, research, open/licensed textbooks, competency frameworks and educational resources. Keep Synthea in the **Synthetic Data Factory** for synthetic patient histories only. Let the **Clinical Case & Simulation Factory** combine those synthetic records with claim-level clinical knowledge and reviewed scenario rules.

Adopt the four visible origin labels — **GENERATED CONTENT, IMPORTED CONTENT, SYNTHETIC CONTENT and DERIVED CONTENT** — and keep them separate from review/publication status. Use a layered reference system: source validity, type-specific appraisal, GRADE certainty/recommendation strength where appropriate, and per-claim support. Licensing and high-risk clinical approval are non-negotiable gates.
