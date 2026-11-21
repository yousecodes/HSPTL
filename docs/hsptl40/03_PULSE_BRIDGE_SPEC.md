# 3. Pulse bridge specification and vital-renderer inventory

## Bridge contract

`PulseProvider` is an in-process Python protocol. `PulseBridge` is the only client-facing bridge:

| Operation | Input | Output / rule |
|---|---|---|
| `step()` | none | One provider step plus current state; no inferred observations |
| `getState()` | none | Connection status, source, sequence and observation map |
| `applyAction(action)` | provider-defined action object | Provider result, with request and outcome appended to the canonical event log |

The default provider is `UnavailablePulseProvider`: `connected=false`, empty observations and no fabricated measurements. An action cannot be applied unless a connected provider explicitly reports success. Missing observations remain unknown; no clinical thresholds are hidden in the renderer.

## Observation contract

A connected provider supplies a state object with `connected`, `source`, `sequence`, and `observations`. Each observation may supply `display`, numeric or textual `value`, `unit`, `status`, and optional numeric `history`. The client must not infer a measurement, unit conversion, normal range, diagnosis or alert from absence.

## Current renderer inventory

The currently bundled client has a single generic observation-tile renderer and a small SVG trend trace, not a separate chart implementation for every vital sign. See `pulse_renderer_inventory.json` for explicit scope.

| Renderer | Data binding | Behavior |
|---|---|---|
| `PulseObservationTile` | One named observation from Pulse state | Displays source display/key, value, unit and status |
| `PulseTrend` | Optional numeric `history` from the same observation | SVG polyline scaled to supplied values; no threshold bands |
| `PulseUnavailableGrid` | `connected=false` | Displays labelled `Unknown` placeholders for heart rate, blood pressure, respiratory rate and oxygen saturation |
| `PulseActionRequest` | User-supplied provider action id | Calls `applyAction`; result is shown as applied/abstain and is event-audited |

The bridge does not ship a physiological simulator, medical device driver, waveform renderer or alarm engine. Such providers remain adapters behind the same three-operation interface.
