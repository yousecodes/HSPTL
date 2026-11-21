# HSPTL navigation and module audit — 5.2.0

## Learner navigation

The shared horizontal navigation intentionally exposes only the everyday learning destinations:

1. **Home** — resume and choose the next activity.
2. **Learn** — topics, teaching material, cases, questions, pearls and learning resources.
3. **Practice** — clinical case reasoning and written plans.
4. **Simulate** — staged patient scenarios and debrief.
5. **Skills** — OSCE, procedures and practical stations.
6. **Exams** — question bank and timed assessment.
7. **Progress** — attempts, feedback and topics to revisit.

The **All modules** directory has two views: **Essentials** (the seven destinations above) and **All modules** (the full registry, grouped by learner purpose). The top-bar **Update content** button is shared by all destinations.

## Module disposition

### Keep visible in the primary navigation

| Existing route | Learner label | Reason |
|---|---|---|
| Overview | Home | Starting point and resume actions |
| Learning library | Learn | Main curriculum and source of learning materials |
| Clinic | Practice | Case reasoning and decision documentation |
| Simulation lab | Simulate | Staged scenario practice and debrief |
| Lab | Skills | OSCE, practical skills and procedure rehearsal |
| Exam Hall | Exams | Retrieval practice and formal practice assessment |
| Progress Board | Progress | Learning record and next-practice priorities |

### Merge into a core destination over time

| Existing route | Target | Simplification decision |
|---|---|---|
| Case Debriefs | Practice / Simulate | Show the debrief at the end of the activity that produced it; retain a history filter under Progress. |
| Rounds / Viva | Learn / Practice | Make viva a question/practice mode, not a separate top-level workspace. |
| High-Yield Pearls | Learn | Treat pearls as a content type and filter in the Library. |
| Topic Summaries | Learn | Treat summaries as a topic format in the Library. |
| Attending Lectures | Learn | Add guided teaching as a Library content type. |
| Case Archives | Learn / Practice | Filter the case library by specialty and status. |
| Case Conference | Practice | Make complex case discussion a Practice activity type. |
| Procedure Theatre | Skills | Put procedure rehearsal beside OSCE and skills checklists. |
| Ward / On-call | Practice | Make ward/on-call scenarios a scenario type within Practice. |
| Handover Desk | Practice / Skills | Add SBAR handover as a practical station and case task. |
| Consult Room | Practice | Add consultation request/response as a case activity. |
| Clinical Progression | Progress | Show milestones within the learner's Progress view. |
| Portfolio | Progress / Profile | Put the learning record under Progress and personal preferences in the profile control. |

### Move to Create & Review or Tools & Settings

| Existing route | Destination | Why it should not be a learner's main navigation item |
|---|---|---|
| Content Factory | Create & Review | Advanced authoring; normal learners use the Library. |
| Synthetic Data Factory | Create & Review | Educator/developer dataset preparation, not routine study. |
| Content Operations | Create & Review | Source, lineage and engine administration. |
| Question Review / Admin Review | Create & Review | Qualified-reviewer workflow, not learner practice. |
| Data Tools | Tools & Settings | Diagnostics and data utilities. |
| Profile | Profile control | Account and preferences, not a learning destination. |

## What is removed now versus later

In 5.2.0, only navigation exposure and labels are simplified. No data, route or engine is deleted. The standalone destinations proposed for merging remain available under **All modules** until their capabilities have been embedded in the target workspace and parity tests prove that nothing was lost. A later release may remove duplicate menu entries, but should not remove underlying records or APIs merely to make the menu shorter.

## Suggested final All modules groups

- **Learn:** Library, pearls, lectures, case archive and summaries.
- **Practise:** Clinic, simulation, skills, rounds/viva, ward/on-call, procedure, handover, consultation and case conference.
- **Assess & reflect:** Exams, debrief history, progress and clinical progression.
- **Create & review:** Content Factory, synthetic data, content operations and reviewer queue.
- **Tools & settings:** Data Tools and Profile.

## Acceptance criteria

- The primary navigation contains exactly seven learner destinations.
- The All modules directory can still open every existing route.
- The Essentials filter shows only the seven primary destinations.
- Every existing route remains covered by routing smoke tests.
- Content generation and reviewer tools are discoverable but do not dominate the learner start page.
- No standalone module is physically removed until its replacement flow has feature-parity and regression coverage.
