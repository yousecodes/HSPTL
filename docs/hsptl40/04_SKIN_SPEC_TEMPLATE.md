# 4. Workspace skin specification template

Use one copy of `skin_config.schema.json` per workspace/module and pin a schema version. A skin is a module registry entry with presentation, interaction, route-map and feature configuration. It is not a clinical knowledge owner.

## Specification template

| Field | Required contract |
|---|---|
| `skin_id`, `schema_version` | Stable id and version |
| `label` | User-facing workspace label |
| `modules` | IDs of trusted modules already registered in the host process |
| `presentation` | Density, canvas, accent, layout and visual settings only |
| `routing_profile`, `route_map` | UI destination aliases; clinical eligibility remains in PROforma |
| `config` | JSON-schema-validated presentation/interaction settings |
| `acceptance_predicates` | All predicates below must pass before config is accepted |

## Module registry contract

1. Register module IDs once; duplicate IDs fail.
2. A skin may reference only registered module IDs.
3. Modules execute in the host application; no remote plugin service or dynamic downloaded code.
4. Module config is validated against each contributing module's allow-listed JSON schema.
5. No skin/module may define clinical facts, diagnosis, evidence, appraisal logic, clinical thresholds, routing predicates or task preconditions.
6. Every state-changing clinical action goes through the Pulse bridge or PROforma runtime and creates canonical events.

## Acceptance predicates

- All module references resolve.
- All config keys are declared and all values satisfy type/enum/size constraints.
- No forbidden clinical-fact or executable-logic key exists.
- Pulse visualizations bind only to Pulse state; workflow controls bind only to PROforma enactments.
- Workspace customization does not mutate clinical graph entities or bypass the event API.

The Python registry enforces the server-side config allow-list. `skinRegistry.ts` mirrors the presentation-only allow-list on the client. The server check is authoritative.
