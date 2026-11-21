# HSPTL Workflow Implementation Notes

## Implemented in this update

The previously scaffolded sections now use existing HSPTL persistence and governance APIs:

- **Clinic / Case Conference:** structured case timeline, problem representation, differential/uncertainty, decision points, team discussion and learning actions.
- **Rounds / Procedure Theatre:** indication, patient selection, consent/preparation, procedural sequence, complications and aftercare checklist.
- **Ward / On-Call Room:** acute presentation, ABCDE assessment, prioritised problems, investigations, immediate management, escalation and reassessment.
- **Ward / Handover Desk:** SBAR handover, pending tasks, task ownership/deadlines, risk/contingency planning and receiver confirmation.
- **Ward / Consult Room:** focused question, urgency, context, investigation data, actions already taken, consultant response and follow-up.
- **Ward / Clinical Progression:** learner development objective, evidence, feedback, next action and supervisor review fields across Intern, Resident, Registrar and Consultant-track stages.
- **Exam Hall / Summaries:** opens saved source-linked notes and exposes the saved Markdown content.
- **Portfolio / Profile:** local browser preferences for display name, training stage, specialty, jurisdiction and learning focus.
- **Portfolio / Admin:** open content-review queue and question-bank review/approval actions.

## Persistence and data model

Clinical workflow records are stored as `LearningEpisode` entries using the existing `/api/episodes` endpoints. Structured drafts use the existing optimistic-concurrency draft endpoint. A learner-authored `reflection` artifact stores the workflow identifier and fields; the artifact remains `unverified`. Completion closes the episode but does not verify clinical content or confer competence.

Content governance uses the existing `/api/content/review` and `/api/questions/{id}/review` endpoints. Content verification and question-bank review remain distinct actions.

Profile preferences are stored in browser `localStorage` under `hsptl-profile`; they are not synchronized and are not an identity/credential record.

## Clinical safety and limitations

- Do not enter identifiable patient information into these local learning records.
- On-call and procedure workflows are educational checklists, not live decision support, prescribing tools, local protocols or substitutes for direct senior supervision.
- Clinical progression is an evidence-capture pathway, not automatic promotion or a competency assessment. The interface does not authenticate supervisors or verify their sign-off.
- The Admin page is a local review interface; this project currently has no role-based access control boundary. Do not expose it as a secure multi-user administrator console without adding authentication and authorization.
- The summaries page displays saved notes; generation and evidence curation remain in High-Yield Pearls.

## Verification

- Backend and project tests: 88 passed.
- Frontend TypeScript/build: not verified in this environment because `npm ci` could not complete (registry dependency download timed out; offline cache lacked Vite 8.3.8). The partial `node_modules` directory was removed before packaging.
