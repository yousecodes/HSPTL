import { useState } from 'react';

type Argument = { id: string; polarity: 'for' | 'against'; weight: number; label?: string; status?: string; reason?: string; evidence?: Array<Record<string, unknown>>; source_events?: Array<Record<string, unknown>> };
type ArgumentProfile = { candidate_id: string; label?: string; preference_rank: number; support_force: number; opposition_force: number; net_force: number; arguments: Argument[]; conclusive: false };
type Task = { id: string; type: 'inquiry' | 'action' | 'decision'; prompt?: string; label?: string; response_key?: string; required?: boolean; options?: Array<{ id: string; label: string; argument_profile?: ArgumentProfile }> };
type AvailableTask = { task: Task; options: Task['options']; argumentation?: { preference_is_indicative?: boolean; automatic_selection?: boolean; preferred_candidates?: string[]; profiles?: ArgumentProfile[] } };
type Enactment = { enactment_id: string; status: string; abstention_reason?: string; plan: { title?: string; tasks: Task[] }; available?: AvailableTask[]; answers?: Record<string, unknown>; decision_profiles?: Record<string, unknown>; derivation?: { derivation_hash?: string } };

const learningPlan = {
  id: 'workspace-learning-review', type: 'plan', title: 'Structured learning review',
  tasks: [
    { id: 'objective', type: 'inquiry', prompt: 'State the learning objective for this session.', response_key: 'learning_objective', required: true },
    { id: 'reflection', type: 'inquiry', prompt: 'Record one point that remains uncertain.', response_key: 'open_question', required: true },
    { id: 'complete', type: 'action', label: 'Close the learning review', preconditions: { op: 'and', args: [
      { op: 'exists', left: { ref: 'answers.learning_objective' } },
      { op: 'exists', left: { ref: 'answers.open_question' } },
    ] } },
  ],
};

export default function ProformaWorkbench() {
  const [enactment, setEnactment] = useState<Enactment | null>(null);
  const [response, setResponse] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true); setMessage(''); setResponse('');
    try {
      const result = await fetch('/api/v4/logic/enactments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan: learningPlan }) });
      const payload = await result.json();
      if (!result.ok) throw new Error(payload.detail || 'Could not start PROforma plan.');
      setEnactment({ ...(payload.state as Enactment), abstention_reason: payload.availability?.reason || payload.state?.abstention_reason });
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'PROforma runtime unavailable.');
    } finally { setBusy(false); }
  }

  async function advance(task: Task, value?: string) {
    if (!enactment) return;
    setBusy(true); setMessage('');
    try {
      const result = await fetch(`/api/v4/logic/enactments/${encodeURIComponent(enactment.enactment_id)}/step`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: task.id, value }),
      });
      const payload = await result.json();
      if (!result.ok) {
        if (payload.detail?.state?.enactment_id) setEnactment(payload.detail.state as Enactment);
        throw new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.reason || 'Task could not be advanced.');
      }
      setEnactment({ ...(payload.state as Enactment), abstention_reason: payload.availability?.reason || payload.state?.abstention_reason });
      setResponse('');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Task could not be advanced.');
    } finally { setBusy(false); }
  }

  const next = enactment?.available?.[0]?.task;
  return <details className="mb-5 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
    <summary className="cursor-pointer list-none font-semibold"><span className="eyebrow block">HSPTL 4.0 · PROFORMA RUNTIME</span><span className="mt-1 block">Structured workflow enactment</span><span className="muted mt-1 block text-xs">Plan, decision, action and inquiry tasks execute through one event-backed logic runtime.</span></summary>
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <div><div className="font-semibold text-sm">{enactment?.plan.title || 'Learning review plan'}</div><p className="muted mt-1 text-xs">{enactment ? `Status: ${enactment.status}` : 'No active enactment in this panel.'}</p></div>
      <button className="secondary-button" type="button" onClick={() => void start()} disabled={busy}>{enactment?.status === 'active' ? 'Restart review' : 'Start review'}</button>
    </div>
    {enactment && <div className="mt-3 space-y-2">
      {enactment.plan.tasks.map((task, index) => <div key={task.id} className="flex items-center gap-2 rounded-lg bg-[var(--surface-muted)] px-3 py-2 text-sm"><span className="muted w-5">{index + 1}.</span><span className="flex-1">{task.prompt || task.label || task.id}</span><span className="muted text-xs">{task.id === next?.id ? 'Next' : ((enactment.answers?.[task.response_key || `action:${task.id}`] !== undefined || enactment.answers?.[`decision:${task.id}`] !== undefined) ? 'Recorded' : 'Queued')}</span></div>)}
    </div>}
    {next?.type === 'inquiry' && <div className="mt-3"><label className="mb-1 block text-xs font-semibold" htmlFor="proforma-response">{next.prompt}</label><textarea id="proforma-response" className="form-field min-h-20 w-full" value={response} onChange={event => setResponse(event.target.value)} maxLength={2000}/><button className="primary-button mt-2" type="button" disabled={busy || !response.trim()} onClick={() => void advance(next, response)}>Submit response</button></div>}
    {next?.type === 'decision' && <div className="mt-3 space-y-3"><div className="text-xs font-semibold">{next.prompt || 'Choose among the defensible options'}</div><p className="muted text-xs">Preference is indicative, not conclusive. The runtime presents the balance of reasons; you confirm the choice.</p>{(enactment?.available?.[0]?.options || []).map(option => { const profile = option.argument_profile; return <div key={option.id} className="rounded-xl border border-[var(--line)] p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div className="font-semibold text-sm">{option.label || option.id}</div>{profile && <span className="muted text-xs">Preference #{profile.preference_rank}</span>}</div>{profile && <><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div><div className="muted">For</div><div className="font-semibold tabular-nums">{profile.support_force.toFixed(2)}</div></div><div><div className="muted">Against</div><div className="font-semibold tabular-nums">{profile.opposition_force.toFixed(2)}</div></div><div><div className="muted">Net force</div><div className="font-semibold tabular-nums">{profile.net_force.toFixed(2)}</div></div></div><div className="mt-2 space-y-1">{profile.arguments.map(argument => <div key={argument.id} className="rounded-md bg-[var(--surface-muted)] px-2 py-1.5 text-xs"><div className="flex justify-between gap-2"><span>{argument.label || argument.id}</span><span className="muted shrink-0">{argument.status === 'abstain' ? 'Abstain' : argument.polarity === 'for' ? `+${argument.weight}` : `−${argument.weight}`}</span></div>{argument.reason && <p className="muted mt-1">{argument.reason}</p>}{(argument.evidence?.length || argument.source_events?.length) ? <p className="muted mt-1 text-[10px]">Evidence: {argument.evidence?.length || 0} · Source events: {argument.source_events?.length || 0}</p> : null}</div>)}</div></> }<button className="secondary-button mt-3 w-full text-left" type="button" disabled={busy} onClick={() => void advance(next, option.id)}>Choose {option.label || option.id}</button></div>; })}</div>}
    {next?.type === 'action' && <div className="mt-3"><button className="primary-button" type="button" disabled={busy} onClick={() => void advance(next)}>{next.label || 'Complete action'}</button></div>}
    {enactment?.status === 'completed' && <p className="status-success mt-3">Workflow completed. This is a formative learning record, not a clinical competency sign-off.</p>}
    {enactment?.status === 'abstain' && <p role="status" className="status-error mt-3">Abstained — {enactment.abstention_reason || 'The next step could not be proven eligible. Escalation/review is required.'}</p>}
    {message && <p role="alert" className="status-error mt-3">{message}</p>}
    {enactment?.derivation?.derivation_hash && <p className="muted mt-3 break-all text-[10px]">Derivation: {enactment.derivation.derivation_hash}</p>}
  </details>;
}
