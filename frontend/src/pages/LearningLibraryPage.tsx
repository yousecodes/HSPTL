import { useEffect, useMemo, useState } from 'react';
import { api, type ContentFactoryCatalog, type ContentFactoryUnit, type QuizSubmission, type CurriculumProjection } from '../lib/api';
import { Icon } from '../components/Icon';
import PublishedLearningPanel from '../components/PublishedLearningPanel';

type Props = { initialUnitId?: string };

export default function LearningLibraryPage({ initialUnitId }: Props) {
  const [catalog, setCatalog] = useState<ContentFactoryCatalog | null>(null);
  const [unit, setUnit] = useState<ContentFactoryUnit | null>(null);
  const [activeCurriculum, setActiveCurriculum] = useState<CurriculumProjection['active']>(null);
  const [eligibleUnitIds, setEligibleUnitIds] = useState<string[] | null>(null);
  const [query, setQuery] = useState('');
  const [specialty, setSpecialty] = useState('All specialties');
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [savedAttempt, setSavedAttempt] = useState<QuizSubmission['attempt'] | null>(null);
  const [pendingIdempotencyKey, setPendingIdempotencyKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([api.contentFactoryCatalog(), api.curricula()]).then(async ([result, pathway]) => {
      if (!active) return;
      setCatalog(result); setActiveCurriculum(pathway.active); setEligibleUnitIds(pathway.active ? (pathway.eligible_unit_ids || []) : null);
      const unlocked = pathway.active ? (pathway.eligible_unit_ids || []) : result.units.map((item) => item.unit_id);
      const first = initialUnitId && unlocked.includes(initialUnitId) && result.units.some((item) => item.unit_id === initialUnitId)
        ? initialUnitId : (pathway.active ? unlocked[0] : result.units[0]?.unit_id);
      if (first) {
        await api.openLearningUnit(first, pathway.active?.curriculum_id || '', pathway.active?.version || 0);
        const detail = await api.contentFactoryUnit(first, pathway.active?.curriculum_id || '', pathway.active?.version || 0);
        if (active) setUnit(detail);
      }
    }).catch((err: unknown) => setError(err instanceof Error ? err.message : 'Learning library could not be loaded.'))
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [initialUnitId]);

  const specialties = useMemo(() => ['All specialties', ...Array.from(new Set(catalog?.units.map((item) => item.specialty) || []))], [catalog]);
  const filtered = useMemo(() => (catalog?.units || []).filter((item) => {
    const matchesQuery = `${item.title} ${item.specialty} ${item.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (specialty === 'All specialties' || item.specialty === specialty);
  }), [catalog, query, specialty]);

  async function openUnit(id: string) {
    setError(''); setAnswers({}); setSubmitted(false); setSavedAttempt(null); setPendingIdempotencyKey('');
    try { await api.openLearningUnit(id, activeCurriculum?.curriculum_id || '', activeCurriculum?.version || 0); setUnit(await api.contentFactoryUnit(id, activeCurriculum?.curriculum_id || '', activeCurriculum?.version || 0)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not open this learning unit.'); }
  }

  async function submitQuiz() {
    if (!unit || submitting) return;
    setSubmitting(true); setError('');
    const key = pendingIdempotencyKey || (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID() : `quiz-${unit.unit_id}-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    setPendingIdempotencyKey(key);
    try {
      const result = await api.submitLearningQuiz(unit.unit_id, {
        answers: Object.fromEntries(Object.entries(answers).map(([index, value]) => [index, value])),
        idempotency_key: key,
        curriculum_id: activeCurriculum?.curriculum_id || '',
        curriculum_version: activeCurriculum?.version || 0,
      });
      setSavedAttempt(result.attempt); setSubmitted(true); setPendingIdempotencyKey('');
      const pathway = await api.curricula(); setEligibleUnitIds(pathway.active ? (pathway.eligible_unit_ids || []) : null);
    } catch (err) { setError(err instanceof Error ? err.message : 'Quiz submission could not be saved. Retry to submit the same attempt safely.'); }
    finally { setSubmitting(false); }
  }
  function resetQuiz() { setAnswers({}); setSubmitted(false); setSavedAttempt(null); setPendingIdempotencyKey(''); }
  const score = savedAttempt?.score ?? 0;

  if (loading) return <div className="hx-loading">Loading the starter curriculum…</div>;
  if (error && !catalog) return <div role="alert" className="status-error">{error}</div>;

  return <div className="hx-page-grid">
    <section className="hx-page-heading">
      <div><div className="hx-eyebrow">LEARN · CURATED STARTER CURRICULUM</div><h1>Learning library</h1><p>Short clinical reasoning units with cases, retrieval practice, viva prompts and OSCE stations. Start immediately; no external dataset required.</p></div>
      <div className="hx-heading-badge"><Icon name="book" size={18}/><span>{catalog?.unit_count ?? 0} learning units</span></div>
    </section>

    <section className="hx-library-summary">
      <div><strong>{catalog?.unit_count ?? 0}</strong><span>Topics</span></div>
      <div><strong>{catalog?.question_count ?? 0}</strong><span>Retrieval questions</span></div>
      <div><strong>{(catalog?.unit_count ?? 0) * 2}</strong><span>Viva prompts</span></div>
      <div><strong>{catalog?.unit_count ?? 0}</strong><span>OSCE stations</span></div>
    </section>

    {error && <div role="alert" className="status-error">{error}</div>}

    <PublishedLearningPanel />

    <section className="hx-library-layout">
      <aside className="hx-library-rail">
        <div className="hx-filter-title">Browse topics</div>
        <label className="hx-search"><Icon name="search" size={16}/><input aria-label="Search topics" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search cases, skills…"/></label>
        <label className="hx-filter-label">Specialty<select value={specialty} onChange={(event) => setSpecialty(event.target.value)}>{specialties.map((item) => <option key={item}>{item}</option>)}</select></label>
        <div className="hx-unit-list">
          {filtered.map((item) => { const locked = eligibleUnitIds !== null && !eligibleUnitIds.includes(item.unit_id); return <button key={item.unit_id} disabled={locked} title={locked ? 'Complete the active curriculum prerequisites to unlock this topic.' : undefined} className={`hx-unit-link ${unit?.unit_id === item.unit_id ? 'is-active' : ''} ${locked ? 'opacity-45 cursor-not-allowed' : ''}`} onClick={() => void openUnit(item.unit_id)}>
            <span className="hx-unit-link-icon"><Icon name={item.specialty.toLowerCase().includes('neurology') ? 'brain' : item.specialty.toLowerCase().includes('respiratory') ? 'lungs' : 'clinic'} size={17}/></span>
            <span className="hx-unit-link-copy"><b>{item.title}</b><small>{item.specialty} · {item.minutes} min{locked ? ' · locked by prerequisite' : ''}</small></span>
          </button>; })}
          {!filtered.length && <p className="hx-muted">No topics match this filter.</p>}
        </div>
      </aside>

      {unit ? <article className="hx-unit-detail">
        <div className="hx-unit-meta"><span>{unit.specialty}</span><span>{unit.level}</span><span>{unit.minutes} minutes</span><span className="hx-status-draft">Educator review required</span></div>
        <h2>{unit.title}</h2>
        <p className="hx-unit-intro">{unit.case.task}</p>
        <div className="hx-case-panel">
          <div className="hx-case-panel-top"><span className="hx-panel-kicker">SYNTHETIC CASE</span><span>{unit.case.patient}</span></div>
          <h3>{unit.case.presentation}</h3>
          <p>{unit.case.history}</p>
          <div className="hx-observation-strip"><div><small>Setting</small><b>{unit.case.setting}</b></div><div><small>Initial observations</small><b>{unit.case.observations}</b></div></div>
          <details className="hx-disclosure"><summary>Reveal additional findings</summary><ul>{unit.case.revealed_findings.map((finding) => <li key={finding}>{finding}</li>)}</ul></details>
        </div>

        <section className="hx-content-block"><div className="hx-block-heading"><div><span className="hx-eyebrow">WHAT YOU WILL PRACTISE</span><h3>Learning objectives</h3></div><Icon name="target" size={20}/></div>
          <ol className="hx-objective-list">{unit.objectives.map((objective) => <li key={objective}>{objective}</li>)}</ol>
        </section>

        <section className="hx-content-block"><div className="hx-block-heading"><div><span className="hx-eyebrow">RETRIEVAL PRACTICE</span><h3>Check your reasoning</h3><p>Submit a complete attempt to save your score and objective-level feedback to your local learning history. This is formative practice.</p></div><span className="hx-question-count">{unit.quiz.length} questions</span></div>
          <div className="hx-quiz-list">
            {unit.quiz.map((question, index) => <div key={`${unit.unit_id}-${index}`} className="hx-question-card">
              <div className="hx-question-number">QUESTION {String(index + 1).padStart(2, '0')}</div><h4>{question.stem}</h4>
              <div className="hx-options">{question.options.map((option, optionIndex) => {
                const correct = submitted && optionIndex === question.correct_index;
                const wrong = submitted && answers[index] === optionIndex && optionIndex !== question.correct_index;
                return <button key={option} disabled={submitted} onClick={() => setAnswers((previous) => ({ ...previous, [index]: optionIndex }))} className={`hx-option ${answers[index] === optionIndex ? 'is-selected' : ''} ${correct ? 'is-correct' : ''} ${wrong ? 'is-wrong' : ''}`}>
                  <span>{String.fromCharCode(65 + optionIndex)}</span>{option}{correct && <Icon name="check" size={16}/>}
                </button>;
              })}</div>
              {submitted && <div className="hx-rationale"><b>{answers[index] === question.correct_index ? 'Correct' : 'Review this point'}</b><p>{question.rationale}</p></div>}
            </div>)}
          </div>
          <div className="hx-quiz-actions">{!submitted ? <><span>{Object.keys(answers).length} of {unit.quiz.length} answered</span><button className="hx-button-primary" disabled={Object.keys(answers).length !== unit.quiz.length || submitting} onClick={() => void submitQuiz()}>{submitting ? 'Saving attempt…' : 'Check and save answers'}</button></> : <><strong>Saved score: {score}/{savedAttempt?.maximum ?? unit.quiz.length}</strong><span className="hx-muted">{savedAttempt?.percentage}% · recorded in your local learning history</span><button className="hx-button-secondary" onClick={resetQuiz}>Try again</button></>}</div>
          {submitted && savedAttempt && <div className="mt-3 grid gap-2 sm:grid-cols-2">{savedAttempt.objective_results.map((item) => <div key={item.objective} className="rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div className="flex justify-between gap-2 text-xs"><b>{item.objective}</b><strong>{item.percent}%</strong></div><p className="muted mt-1 text-xs">{item.correct}/{item.total} questions correct</p></div>)}</div>}
        </section>

        <section className="hx-two-column">
          <div className="hx-content-block"><div className="hx-block-heading"><h3>Key teaching points</h3></div><ul className="hx-bullet-list">{unit.teaching_points.map((item) => <li key={item}>{item}</li>)}</ul></div>
          <div className="hx-content-block"><div className="hx-block-heading"><h3>Common pitfalls</h3></div><ul className="hx-bullet-list">{unit.pitfalls.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </section>
        <section className="hx-content-block"><div className="hx-block-heading"><div><span className="hx-eyebrow">FURTHER PRACTICE</span><h3>Viva, OSCE and reflection</h3></div></div>
          <div className="hx-two-column">{unit.viva.map((item, index) => <div className="hx-mini-card" key={item.prompt}><b>Viva {index + 1}</b><p>{item.prompt}</p><details><summary>Examiner points</summary><ul>{item.key_points.map((point) => <li key={point}>{point}</li>)}</ul></details></div>)}
          <div className="hx-mini-card"><b>{unit.osce.title}</b><p>{unit.osce.candidate_instructions}</p><details><summary>View station checklist</summary><ul>{unit.osce.checklist.map((point) => <li key={point}>{point}</li>)}</ul><b className="hx-critical-label">Critical errors to avoid</b><ul>{unit.osce.critical_errors.map((point) => <li key={point}>{point}</li>)}</ul></details></div></div>
          <div className="hx-reflection-box"><b>Debrief prompts</b>{unit.debrief.map((item) => <p key={item}>{item}</p>)}</div>
        </section>
        <section className="hx-source-box"><b>Source and content governance</b><p>HSPTL-authored educational material. The linked guidance is context, not reproduced source text. The unit is available for formative preview but requires qualified educator review before distribution or summative assessment.</p>
          {unit.source_refs.map((ref) => <a key={ref.source_id} href={ref.url} target="_blank" rel="noreferrer">{ref.publisher}: {ref.title} ({ref.version}) ↗</a>)}
          {!unit.source_refs.length && <span>Authored clinical reasoning framework; no external guideline is asserted for this unit.</span>}
        </section>
      </article> : <div className="hx-empty-state">{activeCurriculum && eligibleUnitIds?.length === 0 ? 'No curriculum stage is currently eligible. Review the pathway prerequisites or ask an instructor to inspect the PROforma eligibility trace.' : 'Choose an unlocked topic to begin.'}</div>}
    </section>
  </div>;
}
