import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { LotteryDaily } from '../lib/api';
import { Icon } from './Icon';

/**
 * Shared Daily Clinical Case Lottery.
 *
 * This is the only daily-case source in Clinic and Ward Board. The answer is
 * withheld by the server until an explicit reveal; this component never holds
 * the answer before then, and it never substitutes a different case source.
 */
export default function DailyCaseLottery({ workspace }: { workspace: 'clinic' | 'ward_board' }) {
  const [daily, setDaily] = useState<LotteryDaily | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState<Record<string, unknown> | null>(null);
  const [response, setResponse] = useState('');
  const [confidence, setConfidence] = useState('3');
  const [specialtyPreference, setSpecialtyPreference] = useState('');
  const [difficultyPreference, setDifficultyPreference] = useState('Any');
  const [recommendations, setRecommendations] = useState<Array<{case_id:string;title:string;specialty:string;difficulty:string;reason:string}>>([]);
  const [preferenceMessage, setPreferenceMessage] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      setDaily(await api.lotteryDaily(workspace));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load today’s lottery case.');
    }
  }, [workspace]);

  useEffect(() => { void load(); void api.learningRecommendations('local-learner').then(data => setRecommendations(Array.isArray(data.items) ? data.items as Array<{case_id:string;title:string;specialty:string;difficulty:string;reason:string}> : [])).catch(() => undefined); }, [load]);

  async function savePreferences() {
    setPreferenceMessage('');
    try {
      await api.learningPreferences('local-learner', specialtyPreference ? [specialtyPreference] : [], difficultyPreference);
      const data = await api.learningRecommendations('local-learner');
      setRecommendations(Array.isArray(data.items) ? data.items as Array<{case_id:string;title:string;specialty:string;difficulty:string;reason:string}> : []);
      setPreferenceMessage('Practice preferences saved.');
    } catch (err) { setPreferenceMessage(err instanceof Error ? err.message : 'Could not save preferences.'); }
  }

  async function submitAndReveal() {
    if (!daily?.draw_id || response.trim().length < 20) {
      setError('Write at least 20 characters of clinical reasoning before revealing the answer.');
      return;
    }
    setBusy(true); setError('');
    try {
      await api.lotteryAttempt(daily.draw_id, 'local-learner', response, Number(confidence));
      setRevealed(await api.lotteryReveal(daily.draw_id, 'local-learner'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit the case attempt.');
    } finally { setBusy(false); }
  }

  if (error) {
    return <section className="hsptl-card p-5" role="alert" aria-live="assertive">
      <h3 className="font-bold">Daily case lottery</h3>
      <p className="muted mt-1 text-sm">{error}</p>
      <button type="button" className="secondary-button mt-3" onClick={() => void load()}>Try again</button>
    </section>;
  }

  if (!daily) {
    return <section className="hsptl-card p-5" aria-busy="true" role="status" aria-live="polite">
      <h3 className="font-bold">Daily case lottery</h3>
      <p className="muted mt-1 text-sm">Drawing today’s shared case…</p>
    </section>;
  }

  if (daily.state === 'no_eligible_case' || !daily.case) {
    return <section className="hsptl-card p-5" role="status" aria-live="polite">
      <h3 className="flex items-center gap-2 font-bold"><Icon name="clipboard"/> No eligible case in today’s lottery</h3>
      <p className="muted mt-1 text-sm">{daily.message}</p>
      <p className="muted mt-2 text-xs">Clinic and Ward use this same lottery. No separate puzzle or synthetic-case fallback is displayed as today's case.</p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs muted">
        <span>Eligible: {daily.eligibility?.eligible_count ?? 0}</span>
        <span>Blocked: {daily.eligibility?.blocked_count ?? 0}</span>
        <span>Date: {daily.draw_date}</span>
      </div>
      {daily.ineligibility_reasons?.length ? <p className="muted mt-3 text-sm">
        The drawn case was withdrawn: {daily.ineligibility_reasons.join(', ')}.
      </p> : null}
      <p className="muted mt-2 text-xs">
        The lottery draws published HSPTL-curated teaching cases and separately reviewed or validated cases, provided the applicable reuse rights permit the intended use.
      </p>
    </section>;
  }

  const item = daily.case;
  const revealData = revealed?.reveal as Record<string, unknown> | undefined;

  return <section className="hsptl-card p-5">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 className="flex items-center gap-2 font-bold"><Icon name="pearls"/> Today’s clinical case</h3>
        <p className="muted mt-1 text-xs">
          Shared with {daily.shared_across_workspaces?.filter(w => w !== workspace).join(', ') || 'the other workspace'}
          {' · '}{daily.draw_date}{' · '}pool of {daily.pool_size}
        </p>
      </div>
      <span className="clinical-tag">{item.label}</span>
    </header>

    <h4 className="mt-3 font-bold">{item.presenting_complaint || item.title}</h4>
    <div className="muted mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">{item.patient_age_value != null && <span>Age {item.patient_age_value} {item.patient_age_unit || 'years'}</span>}<span>{item.specialty}</span><span>{item.difficulty}</span></div>
    <p className="muted mt-1 text-xs">{item.specialty} · {item.difficulty}</p>
    <p className="mt-3 text-sm leading-relaxed">{item.stem}</p>
    <p className="mt-2 font-semibold leading-relaxed">{item.prompt}</p>

    <div className="hx-dataset-meta mt-3">
      <div><b>Curriculum / review</b><span>{item.clinical_review_status === 'curated' ? 'HSPTL-curated teaching vignette' : item.clinical_review_status}</span></div>
      <div><b>Rights</b><span>{item.rights_status}</span></div>
      <div><b>Publication</b><span>{item.publication_status}</span></div>
    </div>

    {item.clinical_review_status === 'curated' ? <p className="muted mt-3 text-xs">HSPTL-authored fictional teaching vignette. It is not a real patient record and is not presented as independently expert-validated.</p> : null}

    {daily.clinical_event ? <div className="mt-3 rounded-lg bg-[var(--surface-muted)] p-3 text-xs"><b>Today's clinical theme:</b> {daily.clinical_event.title}</div> : null}

    {item.source_refs.length ? <div className="mt-4">
      <h5 className="eyebrow">Sources</h5>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {item.source_refs.map((ref, index) => <li key={index}>
          <b>{String((ref as Record<string, unknown>).title ?? 'Source')}</b>
          {(ref as Record<string, unknown>).source_type ? <span className="muted"> · {String((ref as Record<string, unknown>).source_type)}</span> : null}
          {(ref as Record<string, unknown>).licence ? <span className="muted"> · Licence: {String((ref as Record<string, unknown>).licence)}</span> : null}
          {(ref as Record<string, unknown>).reuse_status ? <span className="muted"> · Reuse: {String((ref as Record<string, unknown>).reuse_status)}</span> : null}
          {(ref as Record<string, unknown>).source_url
            ? <> — <a href={String((ref as Record<string, unknown>).source_url)} target="_blank" rel="noreferrer noopener">open</a></>
            : null}
        </li>)}
      </ul>
    </div> : null}

    {revealData
      ? <div className="mt-4 border-t border-hsptl-surface-border pt-3 dark:border-hsptl-dark-border">
          <h5 className="eyebrow">Answer</h5>
          <div className="hx-dataset-meta mt-2">
            {Object.entries(revealData).map(([key, value]) => <div key={key}>
              <b>{key.replace(/_/g, ' ')}</b>
              <span>{typeof value === 'string' ? value : JSON.stringify(value)}</span>
            </div>)}
          </div>
          <p className="muted mt-2 text-xs">Reveal recorded for audit.</p>
        </div>
      : <div className="mt-4 space-y-3">
          <label className="block text-sm font-semibold" htmlFor="daily-case-reasoning">Your differential and clinical reasoning</label>
          <textarea id="daily-case-reasoning" className="w-full rounded-lg border border-hsptl-surface-border bg-transparent p-3 text-sm dark:border-hsptl-dark-border" rows={4} value={response} onChange={e => setResponse(e.target.value)} placeholder="List your leading diagnosis, supporting findings, alternatives and what you would investigate next…" />
          <label className="block text-xs font-semibold" htmlFor="daily-case-confidence">Confidence (1–5)</label>
          <select id="daily-case-confidence" className="rounded-lg border border-hsptl-surface-border bg-transparent p-2 text-sm dark:border-hsptl-dark-border" value={confidence} onChange={e => setConfidence(e.target.value)}>{[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}</select>
          <button type="button" className="primary-button" disabled={busy || response.trim().length < 20} onClick={() => void submitAndReveal()}>
            {busy ? 'Saving and revealing…' : 'Submit reasoning & reveal debrief'}
          </button>
          <p className="muted text-xs">Your formative reasoning response is saved before the answer is released. It is not graded as diagnostic accuracy.</p>
        </div>}
    <div className="mt-5 border-t border-hsptl-surface-border pt-4 dark:border-hsptl-dark-border">
      <h4 className="font-bold text-sm">Personal practice recommendations</h4>
      <p className="muted mt-1 text-xs">Preferences affect additional practice suggestions, not the shared daily draw.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <select aria-label="Preferred specialty" className="rounded-lg border border-hsptl-surface-border bg-transparent p-2 text-sm dark:border-hsptl-dark-border" value={specialtyPreference} onChange={e => setSpecialtyPreference(e.target.value)}>
          <option value="">Any specialty</option><option>Cardiology</option><option>Emergency Medicine</option><option>Internal Medicine</option><option>Neurology</option><option>Respiratory Medicine</option><option>Infectious Diseases</option>
        </select>
        <select aria-label="Preferred case difficulty" className="rounded-lg border border-hsptl-surface-border bg-transparent p-2 text-sm dark:border-hsptl-dark-border" value={difficultyPreference} onChange={e => setDifficultyPreference(e.target.value)}>
          <option>Any</option><option>Foundational</option><option>Intermediate</option><option>Advanced</option>
        </select>
        <button type="button" className="secondary-button text-sm" onClick={() => void savePreferences()}>Save preferences</button>
      </div>
      {preferenceMessage && <p className="muted mt-2 text-xs" role="status">{preferenceMessage}</p>}
      {recommendations.length > 0 && <ul className="mt-3 grid gap-2 sm:grid-cols-2">{recommendations.slice(0,4).map(item => <li key={item.case_id} className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800"><b>{item.title}</b><p className="muted mt-1 text-xs">{item.specialty} · {item.difficulty} · {item.reason.replace(/_/g,' ')}</p></li>)}</ul>}
    </div>
  </section>;
}
