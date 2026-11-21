# HSPTL learner and content-authoring guide

## 1. Start practising with the included curriculum

The bundled **Acute Care Foundations** pack contains 8 topics and 24 retrieval questions. It is available without importing a dataset or configuring an AI provider.

1. Start HSPTL with `start_hsptl.bat` and open the local address shown by the launcher.
2. On Overview, choose **Start learning** or **Open starter topics**.
3. In Learning Library, select a topic. Read the synthetic case and task, open additional findings when ready, then answer every MCQ and choose **Check and save answers**.
4. Review the rationales, teaching points, pitfalls, viva prompts and OSCE checklist. The attempt is saved to the local learning history.

Other practice routes:

- **Clinic:** write at least 20 characters of clinical reasoning for the daily shared case, optionally rate confidence from 1–5, then submit to save the attempt before the debrief is revealed.
- **Simulation:** open Simulation, start an available scenario, take the actions offered by that scenario and review its debrief.
- **Skills:** open the Lab for OSCE and viva stations.
- **Exam Hall:** use the question and mock-exam workflows.

All cases in the starter pack are synthetic educational material. They are not patient records, patient-care instructions or substitutes for local clinical protocols.

## 2. Generate learning materials from the starter pack

1. Choose **Create** in the top navigation.
2. Select one or more curriculum units.
3. Select output formats: question sets, viva prompts, OSCE stations, topic summaries, case reports or case debriefs.
4. Keep or change the deterministic seed, then choose **Generate selected batch**.
5. Select an artifact in the Generated artifacts list to inspect its content and status.

The composer uses versioned, HSPTL-authored source packs and deterministic templates. It does not call an AI model, change clinical facts or require an API key. Generated items are drafts; generation does not approve or distribute them.

## 3. Review and route generated materials

A reviewer must inspect each draft and use the configured reviewer credentials to approve it. Only approved items can be routed to their target HSPTL workspace. If reviewer authentication is not configured, approval is intentionally blocked. A review decision is a governance control, not proof that clinical content is correct; an appropriately qualified educator remains responsible for clinical review.

## 4. Generate an evidence-extractive draft from your own material

Open the advanced source-content workflow from the Content Factory, or open Content Studio from All modules. Search material already ingested into HSPTL's local evidence/source system, select the relevant source documents, set the target workspace, output type and title, then generate the draft. This workflow extracts and cites selected source spans; it is not a general-purpose AI writer. Add and rights-clear sources in the source-management workflow before expecting them to appear in search.

## 5. Add your own curriculum topics

The simplest way to create more learner-library content is to make a new versioned JSON pack:

1. Copy `backend/content_packs/acute_care_foundations_v1.json` to a new filename matching `*_vN.json`, for example `cardiology_topics_v1.json`.
2. Give the pack a unique `pack_id`, and give every new unit a unique `unit_id`. Update the title, version, description, sources and units.
3. Follow `backend/content_packs/content_pack.schema.json`. Every unit needs objectives, a synthetic case, teaching points, pitfalls, at least 3 MCQs with valid options/answer indexes and meaningful rationales, at least 2 viva prompts with key points, an OSCE station with a checklist and critical errors, debrief prompts, and valid source IDs. Source entries require a title, publisher and HTTPS URL.
4. Use material you authored or have permission to adapt. Attribute references accurately; do not paste copyrighted textbook chapters or identifiable patient records into a pack.
5. From the HSPTL project root, run:

   ```bat
   .venv\Scripts\python.exe scripts\validate_content_packs.py
   ```

6. Restart HSPTL. The content factory loads versioned packs from `backend/content_packs` at backend startup; the new units then appear in Learning Library and Content Factory.

The validator checks the JSON schema, required clinical-learning fields, generated output validity and determinism. Fix every reported validation error before using the pack.

## 6. Synthetic patient datasets are a separate workflow

Use **Synthetic data factory** to generate and validate synthetic patient datasets for analysis and data-tool practice. This is separate from authoring clinical teaching topics: a dataset does not automatically become a reviewed case, quiz or learning unit.
