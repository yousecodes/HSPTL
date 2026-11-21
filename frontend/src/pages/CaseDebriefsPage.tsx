import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { ClinicalLearningAttemptDetail, ClinicalLearningAttemptSummary, ClinicalDebrief } from '../lib/api';
import { Icon } from '../components/Icon';
import { ClinicalTags, makeClinicalTag } from '../components/ClinicalTags';

function dateLabel(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function CaseDebriefsPage() {
  const [items, setItems] = useState<ClinicalLearningAttemptSummary[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState<ClinicalLearningAttemptDetail | null>(null);
  const [debrief, setDebrief] = useState<ClinicalDebrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.clinicalLearningAttempts(150).then((result) => {
      setItems(result.items);
      if (result.items[0]) setSelectedId(result.items[0].attempt_id);
    }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load saved case debriefs.')).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    setDetailLoading(true); setDetail(null); setDebrief(null);
    Promise.all([api.clinicalLearningAttempt(selectedId), api.clinicalDebrief(selectedId)]).then(([nextDetail, nextDebrief]) => {
      if (active) { setDetail(nextDetail); setDebrief(nextDebrief); }
    }).catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : 'Could not load this debrief.'); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selectedId]);

  if (loading) return <div className="hsptl-card p-8 text-center muted">Loading your case debriefs…</div>;

  return <div className="case-debrief-workspace space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">CLINIC · CASE REVIEW</div><h2 className="page-title mt-2">Case Debriefs</h2><p className="muted mt-2 max-w-2xl text-sm">Revisit the reasoning you recorded for a synthetic patient encounter: the representation, differential, evidence, investigation plan, management and reflection prompts.</p></div><div className="debrief-count-card"><b>{items.length}</b><small>saved debriefs</small></div></header>
    {error && <div role="alert" className="status-error">{error}</div>}
    {!items.length ? <div className="debrief-empty"><Icon name="clipboard" size={32}/><b className="mt-3">No case debriefs saved yet</b><p className="muted mt-1 max-w-md text-sm">Open a Synthea encounter in Clinic, record your clinical reasoning, then save the attempt and reflection to build a debrief here.</p></div> : <div className="case-debrief-layout">
      <aside className="debrief-attempt-list"><div className="eyebrow">RECENT CASE ATTEMPTS</div><div className="mt-3 grid gap-2">{items.map((item) => <button key={item.attempt_id} onClick={() => setSelectedId(item.attempt_id)} className={`debrief-attempt-card ${selectedId === item.attempt_id ? 'is-active' : ''}`}><div className="flex items-center justify-between gap-2"><b>{item.case_code || item.attempt_id.slice(0, 8)}</b><span className="debrief-stage">Stage {item.stage_completed}/5</span></div><p className="mt-2 text-xs">{item.problem_representation || 'No problem representation recorded.'}</p><div className="mt-2 flex items-center justify-between gap-2"><small>{dateLabel(item.created_at)}</small><small>Debrief {item.debrief_completed}/{item.debrief_total}</small></div></button>)}</div></aside>
      <section className="debrief-detail-panel">
        {detailLoading && <div className="p-8 text-center muted">Opening debrief…</div>}
        {detail && !detailLoading && <>
          <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow">SAVED REASONING RECORD</div><h3 className="mt-1 text-xl font-extrabold">{detail.case_code || `Case ${detail.attempt_id.slice(0, 8)}`}</h3><p className="muted mt-1 text-xs">{detail.specialty_pathway} · {dateLabel(detail.created_at)}</p></div><span className="debrief-stage-pill">Confidence {detail.confidence}/5</span></div>
          <ClinicalTags className="mt-3" tags={[makeClinicalTag('specialty', detail.specialty_pathway), makeClinicalTag('task', 'Clinical Reasoning')]} />
          <div className="debrief-section-grid mt-5">
            <article className="debrief-section-card debrief-section-wide"><div className="eyebrow">PROBLEM REPRESENTATION</div><p>{detail.problem_representation || 'Not recorded.'}</p></article>
            <article className="debrief-section-card"><div className="eyebrow">WORKING DIAGNOSIS</div><p>{detail.working_diagnosis || 'Not recorded.'}</p></article>
            <article className="debrief-section-card"><div className="eyebrow">DIFFERENTIAL</div>{detail.differentials.length ? <ul>{detail.differentials.map((item, i) => <li key={`${item}-${i}`}>{item}</li>)}</ul> : <p>Not recorded.</p>}</article>
            <article className="debrief-section-card"><div className="eyebrow">EVIDENCE FOR</div><p>{detail.evidence_for || 'Not recorded.'}</p></article>
            <article className="debrief-section-card"><div className="eyebrow">EVIDENCE AGAINST / UNCERTAINTY</div><p>{detail.evidence_against || 'Not recorded.'}</p></article>
            <article className="debrief-section-card debrief-section-wide"><div className="eyebrow">INVESTIGATION STRATEGY</div><p>{detail.investigation_plan || 'Not recorded.'}</p></article>
            <article className="debrief-section-card"><div className="eyebrow">MANAGEMENT</div><p>{detail.management_plan || 'Not recorded.'}</p></article>
            <article className="debrief-section-card"><div className="eyebrow">SAFETY NET</div><p>{detail.safety_net || 'Not recorded.'}</p></article>
            <article className="debrief-section-card"><div className="eyebrow">COMMUNICATION</div><p>{detail.communication_plan || 'Not recorded.'}</p></article>
          </div>
          {debrief && <section className="debrief-reflection-block mt-5"><div className="flex items-center justify-between gap-3"><div><div className="eyebrow">POST-CASE REFLECTION</div><h4 className="mt-1 font-bold">Your debrief prompts</h4></div><span className="debrief-stage-pill">{debrief.completed}/{debrief.total} completed</span></div><div className="mt-3 grid gap-3">{(debrief.sections || []).map((section) => <article key={section.key} className="debrief-reflection-item"><b>{section.title}</b><p className="muted mt-1 text-xs">{section.prompt}</p><p className="mt-2 text-sm">{debrief.responses[section.key] || 'No reflection saved for this prompt yet.'}</p></article>)}</div></section>}
          <p className="muted mt-4 text-xs leading-relaxed">Educational record only. This page shows the learner's saved reasoning and reflection; it does not independently validate the working diagnosis or establish clinical competence.</p>
        </>}
      </section>
    </div>}
  </div>;
}
