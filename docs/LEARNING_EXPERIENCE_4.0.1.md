# HSPTL 4.0.1 — Learning Experience and Content Factory

## Product changes

The default application landing route is now a learning dashboard rather than the previous hospital-service home. The navigation is organized around the learner's work:

- Learn: Overview and Learning Library.
- Practise: Clinic case reasoning, Simulation Lab and Lab/skills practice.
- Assess: Exam Hall, Case Debriefs and Progress Board.
- Build: Content Factory and Admin Question Review.
- Explore: Rounds, Ward, Clinical Pearls, Attending Lectures, Case Archives, Procedure Theatre, Handover, Consult, Case Conference and Clinical Progression.
- More: Data Tools and Portfolio.

The original workspace skin registry is retained in-process. The shell chooses the corresponding skin presentation based on the current route. Existing clinical feature pages are reused; the redesign does not create a second application or replace the backend.

## Starter library

The default pack contains eight HSPTL-authored acute-care learning units:

1. Acute chest pain.
2. Acute asthma.
3. Suspected sepsis.
4. Suspected stroke.
5. Acute headache and red flags.
6. Transient loss of consciousness.
7. Acute meningitis.
8. Acute abdominal pain.

Together these provide 24 single-best-answer retrieval questions, eight synthetic vignette presentations, 16 viva prompts, eight OSCE station outlines, teaching points, pitfalls and reflection prompts. Linked guidance is referenced rather than reproduced. The pack is explicitly educator-review-required and educational-only.

The Learning Library loads these pack items directly. It does not depend on user documents, Synthea or the Content Factory review queue. The current in-page quiz returns an immediate formative score and rationales; it does not yet create a persistent assessment record.

## Model-free content production

The embedded Content Factory supports six derivatives for each learning unit: case report, case debrief, question set, topic summary, viva set and OSCE station. Seeded variation is currently restricted to MCQ option order. Clinical facts, synthetic observations, rationales and answer meaning are immutable under the seed.

Batch generation is limited to 12 units and six output kinds per request. The maximum request is 72 draft derivatives. The operation persists artifacts in the existing generated-artifact store, appends generation audit records, and deduplicates identical content hashes. It does not auto-approve or publish.

The existing reviewer-authentication and workspace distribution endpoints handle approval and delivery. Distribution is permitted only for approved artifacts and to the artifact's intended workspace. Approval is editorial governance, not clinical validation.

## Extending the library

Place additional pack files in `backend/content_packs/` with names matching `*_v*.json`. Every pack must validate against `content_pack.schema.json`, have a unique `pack_id`, and use unit IDs unique across all installed packs. Source references must be explicit HTTPS entries or the unit must be clearly labelled as an HSPTL-authored framework with no external guideline asserted.

Run:

```bash
python scripts/validate_content_packs.py
```

This validates the JSON schema, programmatic invariants, all six derivatives per unit, deterministic reproduction and MCQ answer preservation. The release verifier runs this command automatically.

## Known gaps

- The new interface has been syntax-transpiled, but full TypeScript typechecking and Vite production build cannot be verified until project dependencies are installed.
- Inline Learning Library quiz results are not yet persisted or included in the learner's Progress Board.
- The current content factory composes from authored facts; it does not autonomously invent new clinical facts. New clinical subject matter must be authored and reviewed in a new content pack.
- No clinical content is auto-published. Clinical educators must review local applicability, safety, source currency and assessment quality.
