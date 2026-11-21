# HSPTL 4.0 — UI/UX Redesign Implementation Script

**Purpose:** Implement the agreed HSPTL visual and interaction redesign in the existing HSPTL 4.0.2 repository.

**Implementation mode:** Modify the existing application in place. This is a coding-agent implementation directive, not a standalone installer. Run it from the repository root in an agent that can inspect and edit the project files.

---

## MASTER IMPLEMENTATION PROMPT

Act as a senior product designer, accessibility specialist, and senior React/TypeScript engineer. Implement the agreed HSPTL UI/UX redesign in the existing repository. Do not stop after producing a plan. Inspect the current application, implement the redesign, preserve existing behaviour, and provide a concise implementation report.

### 0. Non-negotiable project rules

1. **Preserve the existing product.** HSPTL remains a hospital-inspired clinical learning and simulation platform. Do not convert it into a generic LMS, generic SaaS dashboard, or a collection of unrelated tools.
2. **Preserve hospital destinations.** Keep the existing hospital destination labels, routes, permissions, workflows, and working department pages. Destinations such as Emergency, ICU, Wards, Operating Theatre, Laboratory, Radiology, Pharmacy, and Clinical Rounds are examples; use the actual repository's current destination registry as the source of truth. Do not remove or rename a destination merely to simplify navigation.
3. **Preserve all working functionality.** Keep existing APIs, event names, event history, simulation logic, PROforma behaviour, assessments, content packs, curriculum rules, progress calculations, replay, documentation, and clinical safety gates. This task is primarily a frontend presentation and interaction redesign. Do not change backend contracts unless a clearly documented UI requirement cannot be met otherwise.
4. **No new services or AI dependencies.** Do not add hosted APIs, API keys, external AI models, new deployable services, or unnecessary runtime dependencies. Prefer the existing component and styling stack.
5. **Do not fake clinical behaviour.** Never invent patient observations, clinical outcomes, department capabilities, simulation data, or status. Use existing data and existing empty/loading/error states. Clearly label illustrative/demo content.
6. **Do not claim production readiness.** This redesign does not solve the known authentication, institutional privacy, cohort governance, or clinical safety validation gaps.
7. **Inspect before editing.** Read the current routes, navigation configuration, logo assets, component library, CSS/tokens, page components, and package scripts. Reuse existing patterns where sound. Do not create duplicate pages or a parallel design system.
8. **Protect user work.** Check Git status first. Do not overwrite user changes. Make a branch or backup according to the repository's existing workflow if available.

### 1. Agreed product direction

Implement one coherent product with three connected interface modes:

- **A — Refined Hospital Hub:** the default application shell and dashboard.
- **B — Visual Hospital Directory:** opened when the user clicks the HSPTL logo. It provides visual wayfinding by floor/area, department, and specialty where the current information supports those groupings.
- **C — Clinical Command Centre:** a focused clinical workspace used inside simulation experiences, not a replacement for the whole application shell.

The application must continue to feel like a **digital teaching hospital**. Hospital departments remain first-class destinations. The directory is an alternate way to discover and enter those destinations, not a new taxonomy that replaces them.

### 2. Brand identity: Five-Module Grid monogram

The selected logo direction is the **Five-Module Grid**. The mark must integrate all five letters **H-S-P-T-L** into one unified geometric symbol.

#### Design requirements

- Build the mark as clean vector artwork (prefer a reusable React SVG component and/or standalone SVG files). Do not use a raster image as the primary logo.
- The five letters must be intentionally represented within one modular grid construction. Use shared strokes, negative space, aligned geometry, and controlled openings; avoid simply placing five unrelated letters in five ordinary boxes.
- It must not become an H-only symbol with “SPTL” written beside it. All five letters are part of the monogram.
- Create at least three internal geometry refinements during development, compare them at actual sizes, and select the strongest balanced version. Do not expose unfinished logo drafts as the live brand.
- Provide: primary mark, horizontal lockup, compact mark, monochrome dark mark, monochrome light mark, and a reduced-size optical variant if required.
- Clicking the main logo/brand area opens the Visual Hospital Directory. Provide an accessible tooltip/title such as “Open hospital directory”.
- Include accessible SVG title/description text. Decorative copies should be hidden from assistive technology when an adjacent accessible label already exists.

#### Small-size legibility checks

Create a logo specimen page or development-only showcase that renders the mark at **16px and 32px** on:

1. Light background.
2. Dark background.
3. One-colour dark/black treatment.
4. One-colour light/white treatment.

Also show enlarged samples for visual inspection. Check the actual rendered mark at those pixel dimensions, not only a scaled-up preview.

At 32px, the five-letter construction should remain recognisable. At 16px, preserve the five-module silhouette and avoid collapsing into an unrelated generic glyph. If all five letterforms cannot remain individually legible at 16px, use a carefully simplified optical variant and document the limitation honestly; do not claim each letter is individually readable when it is not.

### 3. Colour system: Midnight Cobalt

Use this palette as the starting point and convert it into semantic design tokens. Do not scatter raw hex values through components.

| Token | Hex | Intended role |
|---|---|---|
| `midnight-900` | `#172B40` | Primary brand, dark navigation, dark theme surfaces |
| `cobalt-700` | `#285B87` | Primary actions, selected navigation, interactive emphasis |
| `steel-400` | `#6D9FC5` | Secondary accents, charts, supporting data |
| `ice-100` | `#E6EFF5` | Soft surfaces and backgrounds |
| `gold-500` | `#D6A34A` | Caution or restrained highlight; never decorative overuse |
| `success-600` | `#27845D` | Successful/completed/normal states when semantically correct |
| `danger-600` | `#C95D5D` | Critical/error states when semantically correct |

Create neutral surfaces, text, borders, focus, disabled, hover, and overlay tokens to make both themes usable. Ensure contrast is measured for each foreground/background pairing. Do not assume the brand colours automatically satisfy WCAG contrast.

#### Theme requirements

- Support light and dark themes using the same semantic token names.
- Preserve user theme selection using the existing project mechanism; do not introduce unnecessary storage dependencies.
- Clinical alert colours retain their semantic meaning in both themes. Never use red/amber as ordinary decoration.
- Charts, vitals, status badges, and data visualisations must remain distinguishable without relying on colour alone.

### 4. A — Refined Hospital Hub (default shell)

Refine the current shell rather than rebuilding routing from scratch.

#### Header

- Left: Five-Module Grid logo and HSPTL wordmark. Clicking this area opens the Visual Hospital Directory.
- Centre or flexible area: global search only if existing search behaviour supports it. Do not add a non-functional search field.
- Right: existing notifications, account/profile controls, and theme toggle where currently supported.
- Keep header height, alignment, responsive behaviour, and focus order consistent across pages.

#### Hospital sidebar

- Retain all existing department destinations and their current route destinations.
- Group related destinations only when this does not hide or rename them. Use clear section labels such as Hospital, Learning, Assessment, and My Development only as supporting groups; do not replace hospital departments with generic categories.
- Preserve current route-active states, permissions, badges, and collapsed/expanded behaviour.
- Use one coherent icon family. Prefer recognisable clinical/departments icons; do not mix unrelated icon styles.
- On smaller screens, use an accessible drawer with correct focus management, Escape handling, and focus return.

#### Dashboard content

Prioritise information hierarchy:

1. Welcome/context and the learner's next meaningful activity.
2. Current learning pathway or curriculum progress, if available.
3. Continue learning / continue simulation, based on real recent activity.
4. Recent cases, assessments, and simulation runs, if available.
5. Relevant announcements or tasks, if supported by existing data.

Do not add decorative KPI cards with invented numbers. Every data element must be sourced from existing application state or display an honest empty state.

### 5. B — Visual Hospital Directory (logo click)

Implement the directory as a polished accessible overlay, full-page view, or existing application navigation pattern that best fits the current architecture. Keep the user's prior route/context intact when the directory is closed.

#### Directory capabilities

- Entry point: click the HSPTL logo/brand mark from the application header.
- Search/filter departments only if the current list can be searched locally.
- Offer views or filters for **Hospital Area/Floor**, **Department**, and **Specialty** only where the repository contains reliable metadata. Do not fabricate floor assignments or specialty mappings.
- Show each existing destination with its actual name, icon, short description (if already available), and a clear open action.
- Selecting a destination navigates to its existing route.
- Provide keyboard navigation, visible focus, dialog semantics if modal, Escape to close, focus trapping when appropriate, and focus return to the logo trigger.
- Provide a clear close/back control. The directory must not unexpectedly discard an in-progress simulation or unsaved form.
- If no floor/area metadata exists, show a department directory rather than inventing a hospital floor plan. Explain in code comments/docs how optional metadata can be added later.

### 6. C — Clinical Command Centre (simulation workspace)

Apply this layout to existing simulation experiences without changing the simulation engine or event semantics.

#### Persistent clinical context

Keep the available patient/context identity, simulation state, current time, and critical status visible. Do not display unavailable patient details or infer missing values.

#### Workspace organisation

Use a clear primary working area with responsive supporting panels:

- **Patient/context header:** identity and scenario state using only existing data.
- **Observations:** vital signs and investigation results, with units, timestamps, reference/context information when provided by the source.
- **Clinical actions:** available assessment/intervention/order actions already exposed by the simulation.
- **Timeline:** simulation clock and event/consequence history.
- **Documentation:** notes, orders, and handover workflow.
- **Assessment:** formative feedback and rubric/result information.
- **Debrief:** replay, event trace, derivation/provenance, and reflection.

Organise the user journey as **Orient → Observe → Act → Document → Assess → Debrief**. These can be tabs, steps, or anchored sections based on the existing workflow, but do not block expert navigation or hide urgent information behind unnecessary steps.

#### Safety and clarity

- Clearly distinguish current observations, prior observations, pending actions, completed actions, and simulated outcomes.
- Confirm consequential actions where the existing workflow requires confirmation.
- Preserve disabled states and validation feedback. Never make a prohibited action look available.
- Keep event trace, audit details, and technical provenance accessible in expandable panels rather than allowing them to overwhelm the main clinical task.
- Keep assessment and debrief feedback visibly separate from real clinical decision support. This remains an educational simulation.

### 7. Shared design system and component quality

Create or refine a small set of reusable tokens and components using the existing stack:

- App shell, header, sidebar, mobile drawer.
- Hospital destination item/card.
- Directory dialog/page and directory filters.
- Page title/toolbar patterns.
- Cards, panels, section headers, empty states, loading states, error states.
- Buttons with clear primary/secondary/destructive hierarchy.
- Form fields, validation, helper text, and disabled state.
- Clinical status badges, observation rows, event timeline, and expandable trace panel.
- Light/dark theme support.

Use consistent spacing, radius, borders, shadows, elevation, typography, and icon sizing. Prefer the existing components if they are suitable. Avoid a large component-library migration just for visual polish.

### 8. Typography, density, and accessibility

- Use a readable type scale. Aim for body text around 16px and supporting text around 14px; avoid tiny 8–11px body labels. Small metadata may be smaller only when still legible and accessible.
- Use adequate line-height and line length for clinical notes and educational material.
- Ensure keyboard-only operation, visible focus indicators, semantic headings, accessible names, labels, and meaningful error announcements.
- Ensure touch controls are comfortably sized on mobile.
- Test contrast for normal text, large text, controls, borders, focus rings, and clinical status colours.
- Respect reduced-motion preferences. Motion must not convey the only indication of state.
- Do not use colour as the only way to communicate critical/normal/warning status.

### 9. Responsive behaviour

Support at minimum:

- Wide desktop: persistent hospital sidebar and multi-panel simulation workspace.
- Tablet: collapsible navigation and adaptive two-column panels.
- Mobile: drawer navigation, stacked clinical panels, readable observations, and reachable actions.

Avoid horizontal scrolling for normal page content. A data table may use a labelled, intentional responsive overflow container if necessary.

### 10. Scope and implementation strategy

Proceed in this order:

1. Audit existing app shell, route registry, destination metadata, theme support, logo assets, and simulation components.
2. Document the exact files to change and any risks in a short implementation note.
3. Implement tokens and typography first.
4. Implement the Five-Module Grid logo variants and small-size specimen page.
5. Update the app shell/header/sidebar and dashboard.
6. Implement the logo-triggered Visual Hospital Directory using existing destination data.
7. Refine the simulation workspace into the Clinical Command Centre.
8. Apply shared components and responsive/accessibility refinements to remaining pages without removing or changing their functionality.
9. Update screenshots or UI documentation if the repository already has a suitable convention.

Do not rewrite unrelated backend modules. Do not introduce a second routing system. Do not remove current pages because they do not fit the new visual direction; adapt their presentation.

### 11. Verification policy

During implementation, do not repeatedly run the full test/build suite after every small change. Finish the implementation first, then perform one consolidated verification pass using the repository's existing verification commands.

The consolidated pass should cover:

- TypeScript/type checking.
- Frontend production build.
- Existing backend tests only if frontend changes affect backend/API contracts (otherwise do not touch or rerun backend tests unnecessarily).
- Route/navigation smoke checks for every existing hospital destination.
- Logo rendering at 16px and 32px, monochrome, light and dark backgrounds.
- Directory open/close, keyboard use, route selection, and preservation of current context.
- Light/dark theme across dashboard, directory, and simulation.
- Responsive review at desktop, tablet, and mobile widths.
- Simulation workflow regression: observations, actions, clock, notes, orders, handover, assessment, replay, and debrief.

If a check fails, fix the relevant issue and run only the smallest targeted check necessary; do not automatically rerun the entire suite unless the user explicitly authorises another complete verification cycle. Report any environment limitation honestly.

### 12. Acceptance criteria

The redesign is complete only when all of the following are true:

- The Five-Module Grid mark contains all five letters H-S-P-T-L in one integrated modular symbol; it is not an H-only logo.
- The mark has primary, compact, monochrome-light, and monochrome-dark variants.
- The 16px and 32px specimen renders exist for light and dark backgrounds, and the 16px optical trade-off is documented honestly.
- Clicking the logo opens the Visual Hospital Directory.
- The directory uses the actual existing department/destination registry and routes to the existing pages.
- Existing hospital destinations remain available and retain their behaviour.
- The main application feels like a coherent hospital hub, not a generic LMS.
- The simulation workspace has a clear clinical hierarchy and preserves all current simulation workflows.
- Midnight Cobalt is applied through semantic tokens, with both light and dark themes.
- Text, controls, navigation, forms, and alerts are accessible and responsive.
- No existing API, event contract, simulation rule, PROforma logic, assessment calculation, replay behaviour, or content pack is silently removed or altered.
- No new hosted service, AI API, API key, or unnecessary dependency has been added.

### 13. Required delivery report

At completion, provide:

1. Summary of the implemented UI/UX changes.
2. Files created, modified, and removed (there should be no removals without explicit justification).
3. Final Five-Module Grid SVG/vector assets and where they live.
4. How the logo opens the directory and how the directory uses the existing route registry.
5. Which pages use the Hospital Hub shell and which use the Clinical Command Centre layout.
6. Accessibility and responsive work completed.
7. Verification commands run and their exact results.
8. Known limitations or items requiring a human design/clinical review.

**Begin by inspecting the existing repository. Then implement the redesign end-to-end; do not stop at a plan or mockup.**

---

## Suggested use

1. Open the existing HSPTL 4.0.2 repository in your coding agent (for example, the agent inside your IDE).
2. Open this Markdown file and copy the entire **MASTER IMPLEMENTATION PROMPT** section into the agent's task instructions.
3. Ensure the agent is operating at the repository root and can edit the frontend files.
4. Review the implementation diff before accepting it. Do not let the agent overwrite unrelated local changes.
