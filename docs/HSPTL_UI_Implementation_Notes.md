# HSPTL UI implementation notes

## Approved configuration
- Hybrid workspace-specific layouts
- Adaptive theme preference: System / Light / Dark
- Dual navigation: persistent primary workspace navigation plus contextual workspace tabs
- Balanced interface density
- Clinic is the default landing workspace
- Ward Grid identity and Solid Minimal workspace marks retained

## Changes applied to this source package
1. The existing six-workspace navigation and contextual section architecture are retained.
2. The theme preference now supports `system`, `light`, and `dark`. System mode follows `prefers-color-scheme` and responds to operating-system theme changes.
3. The theme control cycles System -> Light -> Dark -> System. Explicit Light/Dark choices continue to use the existing theme API; System remains a local preference because the existing backend setting contract supports only Light/Dark.
4. The mobile workspace navigation now allocates six columns for the six workspaces.
5. Ward uses its On-Call mark in the primary navigation.
6. Workspace-specific accent tokens and focus-visible treatments are applied without replacing semantic clinical status colours.

## Existing architecture preserved
- React + TypeScript + Vite frontend
- FastAPI backend
- SQLite persistence and existing migrations
- Existing clinical case, FHIR, OSCE, exam, tagging, progress and data-tool services
- Existing API routes and request/response contracts
- Existing user data and Synthea paths

## Known functional scope
The navigation and route-to-section mapping exist in the supplied project. Some areas are still presentation scaffolds using `ServicePanel`, notably Case Conference, Procedure Theatre, Ward On-Call/Handover/Consult workflows, Summaries and Profile. The question review destination currently reuses the Exam Centre page. These are not represented as completed data-driven workflows by this UI pass.

## Verification
- Backend/project test suite: 86 passed.
- Frontend production build: not verified. `npm ci` did not complete in the execution environment, so TypeScript and Vite build validation remain outstanding.
- No destructive database migrations were introduced.
