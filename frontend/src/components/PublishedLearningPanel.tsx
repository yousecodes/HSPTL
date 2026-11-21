import { useEffect, useMemo, useState } from 'react';
import { api, type PublishedLearningArtifact } from '../lib/api';
import { Icon } from './Icon';

type LearnerSession = {
  session_id: string;
  subject_id: string;
  role: string;
  training_level: string;
};

const CATEGORIES = [
  ['no_issue', 'No issue identified; content supports learning'],
  ['factual_accuracy', 'Possible factual or clinical error'],
  ['outdated_information', 'Outdated information'],
  ['missing_context', 'Missing context or limitation'],
  ['unclear_explanation', 'Unclear explanation'],
  ['citation_or_source_problem', 'Citation or source problem'],
  ['accessibility_or_format', 'Accessibility or format'],
  ['technical_problem', 'Technical problem'],
  ['other', 'Other'],
] as const;

const DIMENSIONS = [
  { key: 'educational_rating', label: 'Educational validity', hint: 'Clarity, learning value, level-appropriateness and usefulness' },
  { key: 'clinical_rating', label: 'Clinical validity', hint: 'Clinical accuracy, reasoning, safety and relevance' },
  { key: 'source_rating', label: 'Source validity', hint: 'Credibility, currency, traceability and source fit' },
  { key: 'assessment_rating', label: 'Assessment validity', hint: 'Question quality, answer correctness and explanation alignment' },
] as const;

type DimensionKey = typeof DIMENSIONS[number]['key'];
type DimensionRatings = Record<DimensionKey, number>;
const DEFAULT_RATINGS: DimensionRatings = {
  educational_rating: 4, clinical_rating: 4, source_rating: 4, assessment_rating: 4,
};

function bodyText(body: Record<string, unknown>): string {
  const direct = body.summary ?? body.content ?? body.text ?? body.description;
  if (typeof direct === 'string') return direct;
  const sections = body.sections;
  if (Array.isArray(sections)) return sections.map((section) => {
    if (!section || typeof section !== 'object') return String(section ?? '');
    const item = section as Record<string, unknown>;
    const title = String(item.title ?? item.heading ?? '');
    const content = item.content ?? item.body ?? item.text ?? item.items ?? item.claims;
    const rendered = Array.isArray(content) ? content.map((part) => {
      if (typeof part === 'string') return part;
      if (part && typeof part === 'object') {
        const record = part as Record<string, unknown>;
        return String(record.text ?? record.label ?? record.content ?? JSON.stringify(record));
      }
      return String(part ?? '');
    }).join('\n') : typeof content === 'object' && content !== null ? JSON.stringify(content, null, 2) : String(content ?? '');
    return `${title}${rendered ? `\n${rendered}` : ''}`;
  }).filter(Boolean).join('\n\n');
  return JSON.stringify(body, null, 2);
}

function readSession(): LearnerSession | null {
  try {
    const parsed = JSON.parse(localStorage.getItem('hsptl-session') || 'null') as LearnerSession | null;
    return parsed?.session_id && parsed.subject_id ? parsed : null;
  } catch { return null; }
}

function validationLabel(state: string): string {
  const labels: Record<string, string> = {
    awaiting_post_use_evidence: 'Awaiting post-use evidence',
    collecting_learner_evidence: 'Collecting learner evidence',
    expert_signoff_pending: 'Expert sign-off pending',
    critical_review_pending: 'Critical review pending',
    revision_required: 'Revision required',
    validation_improvement_required: 'Further validation required',
    validated: 'Validation requirements met',
  };
  return labels[state] || state.replaceAll('_', ' ');
}

export default function PublishedLearningPanel() {
  const [items, setItems] = useState<PublishedLearningArtifact[]>([]);
  const [session, setSession] = useState<LearnerSession | null>(() => readSession());
  const [usage, setUsage] = useState<Record<string, string>>({});
  const [completed, setCompleted] = useState<Record<string, boolean>>({});
  const [opened, setOpened] = useState<string>('');
  const [rating, setRating] = useState(4);
  const [ratings, setRatings] = useState<DimensionRatings>(DEFAULT_RATINGS);
  const [categories, setCategories] = useState<string[]>(['no_issue']);
  const [sources, setSources] = useState<string[]>([]);
  const [severity, setSeverity] = useState<'routine' | 'major' | 'critical'>('routine');
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    setSession(readSession());
    api.publishedLearningArtifacts().then((result) => { if (mounted) setItems(result.items); })
      .catch(() => { if (mounted) setError('Published artefacts could not be loaded.'); });
    return () => { mounted = false; };
  }, []);

  const identityLabel = useMemo(() => session
    ? `${session.subject_id} · ${(session.training_level || 'unspecified').replaceAll('_', ' ')}`
    : 'Guest session · not counted in the validation metric', [session]);

  async function openArtifact(item: PublishedLearningArtifact) {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.recordPublishedArtifactUse(item.id, session?.subject_id || 'local-default', session?.session_id || '');
      setUsage((old) => ({ ...old, [item.id]: result.usage_id }));
      setCompleted((old) => ({ ...old, [item.id]: false }));
      setOpened(item.id); setCategories(['no_issue']); setSources([]); setComment(''); setRating(4);
      setRatings(DEFAULT_RATINGS); setSeverity('routine');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not record this learning session.'); }
    finally { setBusy(false); }
  }

  async function completeUse(item: PublishedLearningArtifact) {
    const usageId = usage[item.id];
    if (!usageId) return;
    setBusy(true); setError('');
    try {
      await api.completePublishedArtifactUse(item.id, usageId, session?.subject_id || 'local-default', session?.session_id || '');
      setCompleted((old) => ({ ...old, [item.id]: true }));
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not record completion.'); }
    finally { setBusy(false); }
  }

  async function sendFeedback(item: PublishedLearningArtifact) {
    const usageId = usage[item.id];
    if (!usageId) return;
    if (!categories.length) { setError('Select at least one validation observation.'); return; }
    if (severity !== 'routine' && comment.trim().length < 20) {
      setError('Major or critical reports need at least 20 characters describing the concern.'); return;
    }
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.submitPublishedArtifactFeedback(item.id, {
        usage_id: usageId, learner_id: session?.subject_id || 'local-default',
        session_id: session?.session_id || '', rating, ...ratings, severity, categories,
        source_document_ids: sources, comment: comment.trim(),
      });
      setMessage(result.message);
      setItems((old) => old.map((entry) => entry.id === item.id ? { ...entry, validation: result.validation } : entry));
      setOpened('');
    } catch (err) { setError(err instanceof Error ? err.message : 'Post-use validation could not be submitted.'); }
    finally { setBusy(false); }
  }

  return <section className="mt-8 space-y-4" aria-labelledby="published-learning-title">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><div className="eyebrow">PUBLISHED · USE · VALIDATE</div><h2 id="published-learning-title" className="text-xl font-bold mt-1">Published learning artefacts</h2>
        <p className="muted mt-1 max-w-3xl text-sm">Provisional artefacts are available for educational use before expert approval. Use the artefact first, complete the activity, then assess its educational, clinical, source and assessment validity. Provisional availability is not clinical approval; validation is version-specific.</p></div>
      <span className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs">{items.length} available</span>
    </div>
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">Validation contributor</span><span>{identityLabel}</span></div>
      {!session && <p className="muted mt-2">Sign in through My Profile with an institution-assigned account to contribute to the 0–100% score. Guest issue reports are still accepted, but are not included in the score or role-weighted evidence.</p>}
    </div>
    {error && <div role="alert" className="status-error">{error}</div>}
    {message && <div role="status" className="status-success">{message}</div>}
    {!items.length && !error && <div className="hsptl-card p-5 text-sm muted">No provisionally published or approved learning artefacts are available yet. Drafts and withdrawn or unsafe items remain hidden.</div>}
    <div className="grid gap-3 lg:grid-cols-2">
      {items.map((item) => {
        const validation = item.validation;
        return <article key={item.id} className="hsptl-card p-5">
          <div className="flex items-start justify-between gap-3"><div><div className="eyebrow">{item.workspace} · {item.kind.replaceAll('_', ' ')}</div><h3 className="mt-1 font-bold">{item.title}</h3></div><span className="rounded-full border border-[var(--border-subtle)] px-2 py-1 text-[10px] font-bold">{item.status === 'approved' ? 'Approved' : 'Provisional · educational use'}</span></div>
          <p className="muted mt-2 text-sm">{bodyText(item.body).slice(0, 260) || 'Source-linked learning resource. Open to review the available content.'}</p>
          <div className="mt-4 rounded-lg border border-[var(--border-subtle)] p-3">
            <div className="flex flex-wrap items-center justify-between gap-2"><div><div className="text-[10px] font-bold uppercase tracking-wider muted">Validation score</div><div className="text-2xl font-bold tabular-nums">{validation?.validation_percent ?? 0}<span className="text-base font-semibold">%</span></div></div><span className="rounded-full border border-[var(--border-subtle)] px-2 py-1 text-[10px]">{validationLabel(validation?.state || 'awaiting_post_use_evidence')}</span></div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-hsptl-teal transition-all" style={{ width: `${Math.max(0, Math.min(100, validation?.validation_percent ?? 0))}%` }}/></div>
            <div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] muted"><span>{validation?.contributor_count ?? 0}/{validation?.target_contributors ?? 10} verified learners</span><span>Expert sign-offs: {validation?.expert_signoff_coverage_percent ?? 0}%</span><span>Level diversity: {validation?.role_diversity_coverage_percent ?? 0}%</span></div>
            <details className="mt-2 text-xs"><summary className="cursor-pointer font-semibold">How this score is calculated</summary><p className="muted mt-2">Four post-use dimensions are weighted: educational 25%, clinical 35%, sources 20%, assessment 20%. Ratings map from 1–5 to 0–100, with modest institution-assigned training-level weights. The quality score is multiplied by verified unique learner coverage (target: 10), expert sign-off factor (70% baseline plus 30% for all four domains), and a learner-level diversity factor (90% baseline plus 10% for at least two assigned levels). An unresolved critical issue caps the score at 49%. A score of 100% also requires all four domain sign-offs, at least 10 unique verified learners and at least two assigned learner levels; it is not a guarantee of clinical correctness.</p><div className="mt-2 grid grid-cols-2 gap-2">{Object.entries(validation?.dimension_scores || {}).map(([key, value]) => <div key={key} className="rounded bg-[var(--surface-muted)] p-2"><span className="muted">{key}</span><b className="ml-2">{value === null ? '—' : `${value}%`}</b></div>)}</div><div className="mt-2 grid grid-cols-2 gap-2">{Object.entries(validation?.approvals || {}).map(([key, value]) => <div key={key} className="rounded border border-[var(--border-subtle)] p-2"><span className="muted">{key} sign-off</span><b className="ml-2">{value.decision.replaceAll('_', ' ')}</b></div>)}</div></details>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs muted"><span>{item.source_refs?.length ?? 0} linked sources</span><span>·</span><span>{item.published_routes?.length ?? 0} distribution routes</span></div>
          <div className="mt-4 flex flex-wrap gap-2"><button disabled={busy} className="primary-button" onClick={() => void openArtifact(item)}><Icon name="book" size={15}/> {usage[item.id] ? 'Continue review & validate' : 'Open & use artefact'}</button>
            {!!item.source_refs?.length && <details className="text-sm"><summary className="cursor-pointer py-2 font-semibold">Source records</summary><div className="mt-2 space-y-1">{item.source_refs.map((ref, index) => <div key={`${ref.document_id || ref.source_id || index}`} className="text-xs">{ref.url ? <a href={ref.url} target="_blank" rel="noreferrer" className="underline">{ref.title || ref.document_id || 'Open source'} ↗</a> : (ref.title || ref.document_id || ref.source_id || 'Linked record')}</div>)}</div></details>}
          </div>
          {opened === item.id && <div className="mt-4 border-t border-[var(--border-subtle)] pt-4">
            <section className="rounded-lg bg-[var(--surface-muted)] p-4"><h4 className="font-bold">Learning artefact content</h4><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap font-sans text-sm leading-relaxed">{bodyText(item.body) || 'This published artefact has no text body available in this format.'}</pre></section>
            {!completed[item.id] ? <div className="mt-4 flex flex-wrap items-center justify-between gap-2"><p className="muted text-xs">Use and review the content, then mark the learning activity complete to unlock validation.</p><button className="primary-button" disabled={busy} onClick={() => void completeUse(item)}>Mark learning activity complete</button></div> : <>
              <h4 className="mt-4 font-bold">Post-use validation assessment</h4>
              <p className="muted mt-1 text-xs">Rate each dimension based on your experience. These ratings are educational evidence and do not replace expert clinical/source review. Do not include patient-identifiable information.</p>
              <div className="mt-3 space-y-3">{DIMENSIONS.map((dimension) => <label key={dimension.key} className="block rounded-lg border border-[var(--border-subtle)] p-3"><span className="flex flex-wrap items-center justify-between gap-2 text-sm font-semibold"><span>{dimension.label}</span><b>{ratings[dimension.key]}/5</b></span><span className="muted mt-1 block text-xs">{dimension.hint}</span><input aria-label={dimension.label} className="mt-2 w-full" type="range" min="1" max="5" step="1" value={ratings[dimension.key]} onChange={(event) => setRatings((old) => ({ ...old, [dimension.key]: Number(event.target.value) }))}/><span className="muted flex justify-between text-[10px]"><span>1 · Poor</span><span>3 · Adequate</span><span>5 · Excellent</span></span></label>)}</div>
              <label className="mt-3 block text-sm font-semibold">Overall usefulness <span className="font-normal muted">({rating}/5)</span><input aria-label="Overall usefulness rating" className="mt-2 w-full" type="range" min="1" max="5" value={rating} onChange={(event) => setRating(Number(event.target.value))}/></label>
              <fieldset className="mt-3"><legend className="text-sm font-semibold">What did you observe?</legend><div className="mt-2 grid gap-2 sm:grid-cols-2">{CATEGORIES.map(([value, label]) => <label key={value} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={categories.includes(value)} onChange={(event) => setCategories((old) => event.target.checked ? (value === 'no_issue' ? ['no_issue'] : [...old.filter((item) => item !== 'no_issue'), value]) : old.filter((item) => item !== value))}/>{label}</label>)}</div></fieldset>
              <label className="mt-3 block text-sm font-semibold">Issue severity<select className="form-field mt-2 w-full" value={severity} onChange={(event) => setSeverity(event.target.value as 'routine'|'major'|'critical')}><option value="routine">Routine observation</option><option value="major">Major issue · requires review</option><option value="critical">Potential patient-safety / critical issue</option></select></label>
              {!!item.source_refs?.length && <fieldset className="mt-3"><legend className="text-sm font-semibold">Related source records (optional)</legend><div className="mt-2 grid gap-2">{item.source_refs.filter((ref) => ref.document_id).map((ref) => <label key={ref.document_id} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={sources.includes(ref.document_id!)} onChange={(event) => setSources((old) => event.target.checked ? [...old, ref.document_id!] : old.filter((id) => id !== ref.document_id))}/>{ref.title || ref.document_id}</label>)}</div></fieldset>}
              <label className="mt-3 block text-sm font-semibold">Comments / evidence<textarea className="form-field mt-2 min-h-24 w-full" maxLength={4000} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Explain what supports or weakens your ratings. For major or critical issues, describe the concern clearly."/></label>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><p className="muted text-[10px]">{session ? 'Your institution-assigned learner level is recorded with this version-specific vote.' : 'Guest report only: sign in to count toward the validation score.'}</p><div className="flex gap-2"><button className="secondary-button" onClick={() => setOpened('')}>Close</button><button className="primary-button" disabled={busy} onClick={() => void sendFeedback(item)}>Submit validation</button></div></div>
            </>}
          </div>}
        </article>;
      })}
    </div>
  </section>;
}
