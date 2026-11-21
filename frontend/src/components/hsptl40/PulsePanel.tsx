import { useCallback, useEffect, useState } from 'react';

type PulseObservation = { value?: string | number; unit?: string; display?: string; effective?: string; status?: string; history?: number[] };
type PulseState = {
  connected: boolean;
  source?: string | null;
  sequence?: number | null;
  observations?: Record<string, PulseObservation>;
  status: string;
  message?: string;
};

/** A source-only SVG trend: scales to the supplied series, never to clinical thresholds. */
function PulseTrend({ history }: { history?: number[] }) {
  const points = (history || []).filter(value => Number.isFinite(value));
  if (points.length < 2) return <svg viewBox="0 0 120 18" className="mt-2 h-4 w-full text-[var(--muted)]" aria-hidden="true"><path d="M2 9 H118" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 4" opacity=".5" /></svg>;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const coords = points.map((value, index) => {
    const x = 2 + (index / (points.length - 1)) * 116;
    const y = 16 - ((value - min) / span) * 12;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return <svg viewBox="0 0 120 18" className="mt-2 h-4 w-full text-[var(--workspace-accent,var(--muted))]" role="img" aria-label="Trend from Pulse-supplied observations; no clinical thresholds applied"><polyline points={coords} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export default function PulsePanel() {
  const [state, setState] = useState<PulseState | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [snapshotStatus, setSnapshotStatus] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v4/pulse/step', { method: 'POST' });
      if (!response.ok) throw new Error(`Pulse bridge returned ${response.status}.`);
      const payload = await response.json() as { state: PulseState; recorded?: boolean; event?: { seq?: number; event_id?: string }; reason?: string };
      setState(payload.state);
      setSnapshotStatus(payload.recorded ? `Snapshot recorded in the canonical event log at event ${payload.event?.seq ?? 'sequence unknown'}.` : (payload.reason || 'No connected Pulse snapshot was recorded.'));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Pulse state could not be read.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  const observations = Object.entries(state?.observations || {});

  async function requestAction() {
    if (!actionId.trim()) return;
    setActionBusy(true);
    setActionMessage('');
    try {
      const response = await fetch('/api/v4/pulse/actions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: { id: actionId.trim(), requested_by: 'workspace_user' } }),
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload.detail;
        const reason = typeof detail === 'string' ? detail : detail?.reason || detail?.state || 'Pulse action was not applied.';
        setActionMessage(`${reason}${detail?.event?.event_id ? ` Event: ${detail.event.event_id}` : ''}`);
      } else {
        setActionMessage(`Applied. Event: ${payload.event?.event_id || 'recorded'}`);
      }
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : 'Pulse action could not be submitted.');
    } finally {
      setActionBusy(false);
    }
  }

  return <section className="mb-5 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4" aria-label="Pulse vital-sign bridge">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="eyebrow">HSPTL 4.0 · PULSE BRIDGE</div>
        <h2 className="mt-1 text-base font-bold">Physiological state</h2>
        <p className="muted mt-1 text-xs">Values are rendered only from the connected Pulse state stream.</p>
      </div>
      <button className="secondary-button" type="button" onClick={() => void refresh()} disabled={loading}>{loading ? 'Reading…' : 'Read and record snapshot'}</button>
    </div>
    {error && <p role="alert" className="status-error mt-3">{error}</p>}
    {!state?.connected ? <div className="mt-3 rounded-xl border border-dashed border-[var(--line)] p-4">
      <div className="font-semibold text-sm">Pulse provider not connected</div>
      <p className="muted mt-1 text-sm">{state?.message || 'Physiological observations remain unknown. No values are simulated or inferred.'}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {['Heart rate', 'Blood pressure', 'Respiratory rate', 'Oxygen saturation'].map(label => <div key={label} className="rounded-lg bg-[var(--surface-muted)] p-2"><div className="muted text-[11px]">{label}</div><div className="mt-1 font-semibold">Unknown</div></div>)}
      </div>
    </div> : <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {observations.length ? observations.map(([key, observation]) => <div key={key} className="rounded-lg bg-[var(--surface-muted)] p-3"><div className="muted text-[11px]">{observation.display || key}</div><div className="mt-1 text-lg font-bold tabular-nums">{observation.value ?? 'Unknown'} <span className="muted text-xs">{observation.unit || ''}</span></div><PulseTrend history={observation.history}/><div className="muted mt-1 text-[10px]">{observation.status || 'Source observation'}</div></div>) : <p className="muted col-span-4 text-sm">Pulse is connected, but the current state contains no observations.</p>}
    </div>}
    <div className="muted mt-3 text-[10px]">Source: {state?.source || 'none'} · Sequence: {state?.sequence ?? 'not available'} · Missing measurements are not converted to normal values.</div>
    {snapshotStatus && <p className="muted mt-1 text-[10px]">{snapshotStatus}</p>}
    <div className="mt-4 border-t border-[var(--line)] pt-3">
      <label className="mb-1 block text-xs font-semibold" htmlFor="pulse-action-id">Pulse action identifier</label>
      <div className="flex flex-wrap gap-2"><input id="pulse-action-id" className="form-field min-w-0 flex-1" value={actionId} onChange={event => setActionId(event.target.value)} placeholder="Provider-defined action ID" maxLength={120}/><button className="secondary-button" type="button" onClick={() => void requestAction()} disabled={actionBusy || !actionId.trim()}>Request action</button></div>
      <p className="muted mt-1 text-[10px]">The action is sent only through the Pulse bridge and is audited. With no connected provider, it is not applied and the bridge abstains.</p>
      {actionMessage && <p role="status" className="muted mt-2 break-all text-xs">{actionMessage}</p>}
    </div>
  </section>;
}
