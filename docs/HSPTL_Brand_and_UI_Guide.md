# HSPTL — Final Brand and Workspace UI Guide

## Selected identity
- Logo: **HSPTL five-letter grid monogram**. The letterforms are explicit and ordered H/S on the first row, P/T on the second, and L on the third. The T crossbar carries the blue accent. Use the vector mark at 32 px or larger where the letters need to read clearly.
- Wordmark: HSPTL, with “CLINICAL LEARNING” as an optional secondary descriptor. Do not use the descriptor as part of the monogram.
- Icons: **Solid Minimal**. Filled geometric marks with simple internal negative-space details.
- Density: **Calm and task-first**. Keep the three most-used learner actions visible; place less frequent administrative tools in the module directory.

## Brand principles
Minimal, clinical, modular, calm. HSPTL is the product name in all user-facing surfaces. Keep typography, spacing, focus states and navigation consistent while allowing each workspace its own accent and layout.

## Workspace identities
| Workspace | Purpose | Accent | Layout |
|---|---|---|---|
| Clinic | Diagnosis | Green `#16805D` | Case reports, debriefs, conference and archives |
| Rounds | Examination | Blue `#5267A8` | Viva, tagged reports and procedure rehearsal |
| Lab | Investigations | Cyan `#0D8B91` | Spot diagnosis and OSCE interpretation/practice |
| Ward | Management | Terracotta `#A45F35` | On-call, handover, consultation and Intern → Consultant progression |
| Exam Hall | Learning and assessment | Amber `#B77924` | Pearls, summaries, attending lectures, questions and F-to-S scores |
| Portfolio | Personal record and administration | Slate `#66736B` | Profile, cross-workspace progress board, data tools and question review |

### Workspace navigation order
1. Clinic — Case Reports, Case Debriefs, Case Conference, Case Archives.
2. Rounds — Viva Questions, Tagged Report Library, Procedure Theatre.
3. Lab — Spot Diagnosis, OSCE.
4. Ward — On-Call Room, Handover Desk, Consult Room, Clinical Progression (Intern to Consultant).
5. Exam Hall — High-Yield Pearls, Summaries, Attending Lectures, Questions, Scores.
6. Portfolio — Profile, Progress Board, Data Tools, Admin (question review).

The F-to-S score bands currently shown in HSPTL are provisional defaults: F 0–49, E 50–59, D 60–69, C 70–79, B 80–89, A 90–96, S 97–100. Replace these with the institution's approved policy when available. Progress Board activity counts are not measures of clinical competence or mastery.

## Shared palette
Forest `#102D25`; Teal `#0D9488`; Medical Blue `#6366F1`; Amber `#D5B46A`; Coral `#EF4444`; Soft Sage `#E6F1EA`. Workspace accents are the primary navigation cues.

## Balanced density rules
- Main content padding: 22–24px desktop, 16px compact screens.
- Cards use restrained 10px radii, thin borders and minimal shadows.
- Preserve readable line lengths and clear section hierarchy.
- Keep high-value clinical information visible without excessive whitespace.
- Workspace-specific layout and accent colours remain distinct.

## Implementation
The HSPTL five-letter grid monogram is installed as the application mark in SVG, React and favicon variants. WorkspaceMark uses the Solid Minimal family with individual workspace colours. Existing route and component names remain stable for compatibility.
