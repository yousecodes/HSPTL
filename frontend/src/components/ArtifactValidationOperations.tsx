import { useEffect, useMemo, useState } from 'react';
import { api, type PublishedLearningArtifact } from '../lib/api';
import { Icon } from './Icon';

const DOMAINS = [
  ['educational', 'Educational quality'],
  ['clinical', 'Clinical validity'],
  ['sources', 'Source validity'],
  ['assessment', 'Assessment validity'],
] as const;

type Domain = typeof DOMAINS[number][0];
type ReviewerSession = { session_id: string; subject_id: string; role: string; training_level: string };

function readSession(): ReviewerSession | null {
  try {
    const value = JSON.parse(localStorage.getItem('hsptl-session') || 'null') as ReviewerSession | null;
    return value?.session_id ? value : null;
  } catch { return null; }
}

export default function ArtifactValidationOperations() {
  const [items, setItems] = useState<PublishedLearningArtifact[]>([]);
  const [session] = useState<ReviewerSession | null>(() => readSession());
  const [artifactId, setArtifactId] = useState('');
  const [domain, setDomain] = useState<Domain>('clinical');
  const [decision, setDecision] = useState<'affirmed'|'revision_required'|'rejected'>('affirmed');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    try {
      const result = await api.publishedLearningArtifacts();
      setItems(result.items);
      setArtifactId((old) => old || result.items[0]?.id || '');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load validation records.'); }
  }
  useEffect(() => { void load(); }, []);

  const selected = useMemo(() => items.find((item) => item.id === artifactId), [items, artifactId]);

  async function submit() {
    if (!session || !selected || note.trim().length < 8) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.signoffPublishedArtifactValidation(selected.id, session.session_id, {
        domain, decision, note: note.trim(),
      });
      setItems((old) => old.map((item) => item.id === selected.id ? { ...item, validation: result.validation } : item));
      setMessage(`${domain} sign-off recorded for this content version. Publication status was not changed.`);
      setNote('');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not record the expert sign-off.'); }
    finally { setBusy(false); }
  }

  return <section className="hsptl-card p-5">
    <div className="flex items-start gap-3"><Icon name="shield-check" size={20}/><div><h2 className="text-lg font-bold">Versioned validation and expert sign-off</h2><p className="muted mt-1 max-w-3xl text-sm">The 0–100% score combines weighted learner ratings, verified learner coverage, level diversity and expert sign-off coverage. A 100% result requires all four domain sign-offs, ten verified contributors, at least two institution-assigned levels and no unresolved critical report.</p></div></div>
    {error && <p role="alert" className="status-error mt-3">{error}</p>}{message && <p role="status" className="status-success mt-3">{message}</p>}
    <div className="mt-4 grid gap-3 lg:grid-cols-2">
      {items.map((item) => <article key={item.id} className="rounded-xl border border-[var(--border-subtle)] p-3">
        <div className="flex items-start justify-between gap-2"><b className="text-sm">{item.title}</b><strong className="text-lg tabular-nums">{item.validation?.validation_percent ?? 0}%</strong></div>
        <div className="muted mt-1 text-[10px]">{item.validation?.contributor_count ?? 0} verified contributors · {item.validation?.state?.replaceAll('_', ' ') || 'awaiting evidence'}</div>
        <div className="mt-2 grid grid-cols-2 gap-2">{DOMAINS.map(([key, label]) => {
          const approval = item.validation?.approvals?.[key];
          return <div key={key} className="rounded bg-[var(--surface-muted)] px-2 py-1.5 text-[10px]"><div className="muted">{label}</div><b>{approval?.decision?.replaceAll('_', ' ') || 'pending'}</b>{approval?.reviewer_id && <div className="muted">{approval.reviewer_id}</div>}</div>;
        })}</div>
        {!!item.validation?.open_critical_issues && <p className="mt-2 text-xs font-semibold text-rose-700 dark:text-rose-300">{item.validation.open_critical_issues} unresolved critical issue(s)</p>}
      </article>)}
    </div>
    {!items.length && <p className="muted mt-3 text-sm">No published artefacts are available for validation yet.</p>}
    <div className="mt-4 rounded-xl border border-[var(--border-subtle)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Record an expert domain decision</h3><span className="muted text-xs">{session ? `${session.subject_id} · ${session.role} · ${session.training_level}` : 'Not signed in'}</span></div>
      {!session && <p className="muted mt-2 text-xs">Sign in through My Profile with an institution-assigned facilitator, reviewer or administrator account. Your training level is set by the institution administrator.</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-semibold">Published artefact<select className="form-field mt-1" value={artifactId} onChange={(event) => setArtifactId(event.target.value)}><option value="">Select artefact</option>{items.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        <label className="text-xs font-semibold">Validation domain<select className="form-field mt-1" value={domain} onChange={(event) => setDomain(event.target.value as Domain)}>{DOMAINS.map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label className="text-xs font-semibold">Decision<select className="form-field mt-1" value={decision} onChange={(event) => setDecision(event.target.value as typeof decision)}><option value="affirmed">Affirmed for this version</option><option value="revision_required">Revision required</option><option value="rejected">Not valid / rejected</option></select></label>
        <label className="text-xs font-semibold sm:col-span-2">Rationale / evidence note<textarea className="form-field mt-1 min-h-20" minLength={8} maxLength={3000} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Record the evidence, limitations, guideline/version checked, or required corrections."/></label>
      </div>
      <button type="button" className="primary-button mt-3" disabled={!session || !selected || note.trim().length < 8 || busy} onClick={() => void submit()}>{busy ? 'Recording…' : 'Record version-specific sign-off'}</button>
      <p className="muted mt-2 text-[10px]">Clinical sign-off: reviewer/admin with institution-assigned specialist or consultant level. Educational/assessment: faculty facilitator/reviewer. Source: reviewer/admin. Sign-offs are immutable audit entries; a later decision supersedes the previous domain state.</p>
    </div>
  </section>;
}
