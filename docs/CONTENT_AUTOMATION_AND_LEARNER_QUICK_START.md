# HSPTL learner quick start and automatic content

## Start learning

1. Start HSPTL with `start_hsptl.bat`.
2. Open **Learn** to use the installed Acute Care Foundations starter pack (8 topics and 24 retrieval questions).
3. Choose a topic, read the short teaching material, answer the questions, then open **Practice** or **Simulate** to apply it.
4. Use **Skills** for OSCE and practical station work, **Exams** for assessment, and **Progress** to review saved attempts.

## What happens automatically

On application startup, HSPTL reads installed versioned local content packs and prepares deterministic educational drafts. With the current 8-topic starter pack, this prepares up to 72 draft outputs across Clinic, Exam Hall, Rounds, Lab, Ward and Simulation (9 output formats per topic).

This runs locally. No AI service, internet connection or API key is required. Existing built-in Library topics and questions are available for learning independently of the draft-review workflow.

## Update content from any workspace

Use the **Update content** button in the shared top bar. It checks installed pack versions again and prepares outputs for changed or newly added topics. Running it again without a content change reuses the existing outputs instead of creating duplicates.

If new drafts were created, open **All modules → Create & Review → Admin · Question Review** to inspect them. The draft lifecycle must be completed before generated outputs are distributed into learner-facing collections.

## Clinical review boundary

Automatic output is a deterministic educational draft, not an independent medical author, clinical source verifier or approval authority. It is never auto-approved or auto-published. Qualified educators remain responsible for clinical accuracy, suitability, rights and publication. Simulation briefs and handover templates are teaching exercises, not instructions for real patient care.

## Adding more local content

Add a new versioned JSON pack following the existing pack schema in `backend/content_packs/`. Keep pack IDs stable and increment pack versions for material updates. Restart HSPTL or use **Update content** to discover the new pack. Invalid packs fail closed and do not replace the last valid content factory. Use **All modules → Create & Review → Content factory** for advanced manual composition and the review workflow.
