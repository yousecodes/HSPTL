# HSPTL 6.0 — Post-use validation and approval model

## Purpose

HSPTL validation is earned through documented use, learner evidence, and domain-specific expert review. It is not granted merely because content was generated, imported, or uploaded. Each score and decision is tied to one exact artefact content hash.

The displayed **Validation score (0–100%)** is an evidence-progress and quality metric. It is not a guarantee of clinical correctness, a professional credential, or a substitute for institutional approval.

## Lifecycle

1. **Pre-use safeguards:** An artefact must already satisfy the platform's existing approval/distribution requirements before it appears in the published Learning Library. Source access, attribution, licensing, patient privacy, and clinical safety controls remain separate mandatory safeguards.
2. **Use:** A learner opens an approved and delivered artefact. HSPTL records a usage session tied to the artefact ID and content hash.
3. **Completion:** The learner marks the activity complete. Post-use assessment is unavailable until this step.
4. **Post-use evidence:** An authenticated learner can score all four validation domains and submit observations. Guest issue reports may be accepted, but they do not influence the numeric score.
5. **Domain review:** Appropriately authorised reviewers record an immutable, version-specific decision for each domain.
6. **Decision and revision:** The artefact's validation state is recalculated. A content revision changes the hash and starts a new validation cycle; previous votes and sign-offs remain linked to the previous version.

## The four validation domains

| Domain | Weight | What contributors assess |
|---|---:|---|
| Educational quality | 25% | Clarity, structure, learning value, relevance, completeness and suitability for the stated learner level |
| Clinical validity | 35% | Clinical accuracy, reasoning, safety, currency and consistency with appropriate evidence/guidance |
| Source validity | 20% | Authenticity, relevance, currency, attribution and traceability of linked references |
| Assessment validity | 20% | Accuracy of questions/answers, explanation quality, alignment with objectives and whether assessment measures the intended learning |

Each domain is rated 1–5, mapped to 0, 25, 50, 75, and 100 respectively. Only a complete four-domain assessment from an authenticated institutional session contributes to the numerical metric. Issue-only reports remain visible for triage but do not add a numeric rating.

## Role/training-level contribution weights

The multiplier is applied to each rating when calculating the weighted mean for that domain. It modestly distinguishes perspective; it does not certify that a person is competent in every subject. HSPTL uses the training level assigned to the user's institutional account/session, never a level selected in the learner's own profile.

| Institution-assigned training level | Weight multiplier |
|---|---:|
| Student | 0.70 |
| Intern | 0.82 |
| Resident | 0.95 |
| Registrar | 1.05 |
| Fellow | 1.12 |
| Specialist | 1.18 |
| Consultant | 1.22 |
| Faculty | 1.18 |
| Unspecified | 0.60 |

## Score calculation

For each domain, HSPTL calculates the weighted mean of the completed 1–5 ratings after mapping each rating to 0–100.

- `quality_score` = 25% educational + 35% clinical + 20% sources + 20% assessment.
- `learner_evidence_coverage` = `min(unique verified contributors / 10, 1)`.
- `expert_approval_coverage` = `affirmed domains / 4`.
- `expert_approval_factor` = `0.70 + (0.30 × expert_approval_coverage)`.
- `level_diversity_coverage` = `min(distinct institution-assigned, non-unspecified learner levels / 2, 1)`.
- `level_diversity_factor` = `0.90 + (0.10 × level_diversity_coverage)`.
- `validation_score` = rounded `quality_score × learner_evidence_coverage × expert_approval_factor × level_diversity_factor`.

An unresolved critical report caps the score at **49%** and sets the status to `critical_review_pending`. This is a score cap and a review blocker; it does not silently change an artefact's existing publication status. An authorised reviewer must separately decide whether to revise, suspend, or withdraw the artefact through the relevant governance workflow.

### How to interpret the percentage

- The percentage combines quality ratings with evidence coverage and required review progress; it is not simply the percentage of people who approved the content.
- The target evidence cohort is 10 unique, authenticated contributors per content version.
- At least two distinct, institution-assigned learner levels are required for the final `validated` state.
- All four domain sign-offs must be affirmed for the final `validated` state.
- The final state also requires a score of at least 90% and no unresolved critical reports.
- A 100% score therefore requires maximum quality ratings, full contributor and level-diversity coverage, all four affirmed domain sign-offs, and no unresolved critical issue.

## Domain sign-off authorisation

| Domain | Required authenticated role | Additional training-level requirement |
|---|---|---|
| Clinical | Reviewer or administrator | Specialist or consultant |
| Sources | Reviewer or administrator | None beyond assigned authenticated account |
| Educational | Facilitator, reviewer or administrator | Faculty |
| Assessment | Facilitator, reviewer or administrator | Faculty |

Every sign-off stores the reviewer identity, role, institution, assigned training level, decision, rationale, timestamp and content hash. Sign-off history is append-only; the latest domain decision determines current domain coverage.

## Validation states

- `awaiting_post_use_evidence` — no scored learner evidence yet.
- `collecting_learner_evidence` — evidence exists but fewer than 10 verified contributors have completed all four domains.
- `expert_signoff_pending` — target contributor count reached but one or more domain decisions are not affirmed.
- `critical_review_pending` — at least one unresolved critical issue exists.
- `revision_required` — a domain reviewer requires revision or rejects the version.
- `validation_improvement_required` — the evidence, score or learner-level diversity is below the final threshold.
- `validated` — all final score, contributor, diversity and domain sign-off requirements are satisfied.

## Integrity and safeguards

- Votes, usage sessions and sign-offs are bound to the exact content hash. A changed version requires new evidence.
- An authenticated learner can contribute only once per artefact content version; duplicate use-session reports and duplicate verified votes are rejected.
- Learner feedback is only accepted after a recorded completed-use session.
- Learners may challenge linked source records, but cannot approve reuse rights or change source permissions.
- Clinical, source, educational and assessment sign-offs are separate domain decisions.
- Existing artefact approval/publication and source-rights controls remain mandatory and are not replaced by a high validation score.
- The metric is a governance signal. Institutions remain responsible for their policies, expert appointments, evidence standards, and decisions about clinical use.

## Known implementation boundary

HSPTL currently provides local institutional accounts and role-based sessions. Training-level assignments and sign-off controls operate within that local governance boundary; this is not enterprise SSO, MFA, an external credential-verification service, or a production multi-tenant identity platform. Institutions must administer account roles and training levels accurately before relying on their contribution weights.
