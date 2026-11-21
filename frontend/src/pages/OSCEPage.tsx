import { useEffect, useMemo, useState } from 'react';
import type { QuestionItem } from '../lib/api';
import { api } from '../lib/api';
import { Icon } from '../components/Icon';
import { ClinicalTags, makeClinicalTag, type TagFacet } from '../components/ClinicalTags';
import { indexClinicalContent, recordIndexedLearningEvent } from '../lib/tagging';

const categories = [
  { id: 'Spot diagnosis', title: 'Spot diagnosis', subtitle: 'Recognise patterns from a focused presentation', icon: 'image' as const },
  { id: 'Pathology', title: 'Pathology', subtitle: 'Histology, specimens and mechanisms', icon: 'microscope' as const },
  { id: 'Radiology', title: 'Radiology', subtitle: 'Describe and interpret medical imaging', icon: 'image' as const },
  { id: 'ECG', title: 'ECG', subtitle: 'Rhythm, axis, intervals and patterns', icon: 'activity' as const },
  { id: 'Clinical examination', title: 'Clinical examination', subtitle: 'Technique, findings and interpretation', icon: 'stethoscope' as const },
  { id: 'Viva', title: 'Viva questions', subtitle: 'Explain, justify and defend your reasoning', icon: 'brain' as const },
];

export default function OSCEPage({ initialKind = 'Spot diagnosis', workspaceMode = 'lab' }: { initialKind?: string; workspaceMode?: 'lab' | 'osce' | 'viva' }) {
  const [items, setItems] = useState<QuestionItem[]>([]);
  const [activeKind, setActiveKind] = useState(initialKind);
  const [selected, setSelected] = useState<QuestionItem | null>(null);
  const [response, setResponse] = useState('');
  const [result, setResult] = useState<{ correct: boolean; answer: string; explanation: string; source_title: string; source_url: string; points: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [startedAt, setStartedAt] = useState<number>(0);

  async function refresh() {
    try {
      const challenges = await api.osceChallenges();
      setItems(challenges);
      await Promise.allSettled(challenges.map((item) => {
        const isViva = item.kind.toLowerCase() === 'viva';
        const isOsce = item.kind.toLowerCase() === 'clinical examination';
        const modality = item.kind.toLowerCase() === 'ecg' ? 'ECG'
          : item.kind.toLowerCase() === 'radiology' ? 'X-ray'
          : item.kind.toLowerCase() === 'pathology' ? 'Histopathology'
          : item.kind.toLowerCase().includes('spot') ? 'Clinical Photo'
          : isOsce ? 'Clinical Examination' : '';
        const tagPairs: Array<[TagFacet, string]> = [
          ['specialty', item.specialty], ['difficulty', item.difficulty],
          ['task', isViva ? 'Communication' : isOsce ? 'Procedure' : 'Interpretation'],
        ];
        if (modality) tagPairs.push(['modality', modality]);
        return indexClinicalContent({
          content_type: isViva ? 'viva' : 'osce', content_id: item.id,
          title: item.question.slice(0, 180), workspace: isViva ? 'rounds' : 'lab',
          summary: item.specialty + ' · ' + item.kind,
          source_status: item.reviewed ? 'reviewed' : 'unreviewed', content_url: item.source_url || '',
          tag_pairs: tagPairs,
        });
      }));
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load challenges.'); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (remainingSeconds === null || result) return;
    if (remainingSeconds <= 0) return;
    const timer = window.setInterval(() => setRemainingSeconds((value) => value === null ? null : Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [remainingSeconds, result]);

  const visibleCategories = categories.filter((category) => workspaceMode === 'viva' ? category.id === 'Viva' : workspaceMode === 'osce' ? category.id === 'Clinical examination' : !['Clinical examination', 'Viva'].includes(category.id));
  const visible = useMemo(() => items.filter((x) => x.kind.toLowerCase() === activeKind.toLowerCase()), [items, activeKind]);
  async function importFile(file?: File) {
    if (!file) return;
    setError(''); setMessage('');
    try {
      const r = await api.importOsce(file);
      setMessage(`${r.created} challenge(s) imported; ${r.skipped} row(s) skipped (${r.truncated} beyond the per-file limit). Imported items remain marked for review.`);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Import failed.'); }
  }
  async function approveSelected() {
    if (!selected) return;
    setError('');
    try { await api.reviewQuestion(selected.id, true); setSelected({ ...selected, reviewed: true }); await refresh(); setMessage('Challenge marked reviewed. Check its source and clinical currency periodically.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not approve challenge.'); }
  }
  async function submit() {
    if (!selected || !response.trim()) return;
    setLoading(true); setError('');
    const elapsed = startedAt ? Math.max(0, Math.round((Date.now() - startedAt) / 1000)) : 0;
    try {
      const marked = await api.osceAttempt(selected.id, response.trim(), elapsed);
      setResult(marked);
      await recordIndexedLearningEvent(selected.kind.toLowerCase() === 'viva' ? 'viva' : 'osce', selected.id, { action: 'completed', score: marked.correct ? 1 : 0, max_score: 1 });
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not submit this answer.'); }
    finally { setLoading(false); }
  }

  const pageTitle = workspaceMode === 'viva' ? 'Viva Practice' : workspaceMode === 'osce' ? 'OSCE Stations' : 'Visual Spotters';
  const pageDescription = workspaceMode === 'viva'
    ? 'Practise explaining, justifying and defending clinical decisions in an oral-examination format.'
    : workspaceMode === 'osce'
      ? 'Work through structured examination, communication and practical stations with a timer and debrief.'
      : 'Identify and interpret clinical photographs, ECGs, radiology, pathology and other diagnostic media.';

  return <div className={`space-y-6 osce-workspace osce-workspace-${workspaceMode}`}>
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><div className="eyebrow">{workspaceMode === 'viva' ? 'ORAL EXAMINATION' : workspaceMode === 'osce' ? 'CLINICAL SKILLS CIRCUIT' : 'DIAGNOSTIC IMAGING & SPOTTERS'}</div><h1 className="page-title mt-2">{pageTitle}</h1><p className="muted mt-2 max-w-2xl text-sm">{pageDescription}</p></div>
      <label className="secondary-button cursor-pointer"><Icon name="upload" size={16}/> Import challenges<input type="file" accept=".json,.jsonl,.csv,.tsv" className="sr-only" onChange={(e) => void importFile(e.target.files?.[0])}/></label>
    </header>
    {(message || error) && <div className={error ? 'status-error' : 'status-success'}>{error || message}</div>}
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {visibleCategories.map((c) => <button key={c.id} onClick={() => { setActiveKind(c.id); setSelected(null); setResult(null); setResponse(''); setRemainingSeconds(null); }} className={`specialty-card text-left ${activeKind === c.id ? 'border-hsptl-indigo-glow ring-2 ring-indigo-500/10' : ''}`}>
        <div className="flex items-start justify-between"><span className="specialty-icon"><Icon name={c.icon} size={21}/></span><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600 dark:bg-slate-700 dark:text-slate-200">{items.filter((x) => x.kind.toLowerCase() === c.id.toLowerCase()).length} items</span></div>
        <h2 className="mt-4 font-bold">{c.title}</h2><p className="muted mt-1 text-xs leading-relaxed">{c.subtitle}</p>
      </button>)}
    </section>
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="hsptl-card min-w-0 p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">CHALLENGE LIBRARY</div><h2 className="mt-1 text-xl font-extrabold">{activeKind}</h2></div><span className="muted text-xs">{visible.length} available</span></div>
        {visible.length ? <div className="mt-4 divide-y divide-hsptl-surface-border dark:divide-hsptl-dark-border">{visible.map((item) => <button key={item.id} onClick={() => { setSelected(item); setResponse(''); setResult(null); setRemainingSeconds(item.timer_seconds || 600); setStartedAt(Date.now()); }} className={`w-full rounded-lg px-3 py-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800 ${selected?.id === item.id ? 'bg-indigo-50 dark:bg-indigo-950/40' : ''}`}><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold">{item.question.slice(0,110)}{item.question.length > 110 ? '…' : ''}</span><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 dark:bg-slate-700 dark:text-slate-200">{item.difficulty}</span></div><p className="muted mt-1 text-xs">{item.specialty} · {item.source_title}</p><ClinicalTags className="mt-2" limit={5} tags={[makeClinicalTag('specialty', item.specialty), makeClinicalTag('modality', item.kind), makeClinicalTag('difficulty', item.difficulty), makeClinicalTag('task', workspaceMode === 'viva' ? 'Clinical explanation' : workspaceMode === 'osce' ? 'Procedural skill' : 'Interpretation'), ...(item.tags || []).slice(0, 2).map((tag) => makeClinicalTag('presentation', tag))]}/></button>)}</div> : <div className="mt-5 rounded-xl border border-dashed border-hsptl-surface-border p-6 text-center dark:border-hsptl-dark-border"><Icon name="filePlus" size={28} className="mx-auto muted"/><h3 className="mt-3 font-bold">No {activeKind.toLowerCase()} challenges imported yet</h3><p className="muted mx-auto mt-2 max-w-md text-sm">Import a JSON, CSV or TSV question set. Each item should include a question, answer, specialty and source; optional fields include choices, explanation and image URL. Imports support up to 20,000 rows per file.</p><p className="muted mt-3 text-xs">HSPTL does not invent clinical images or examination findings. Add only material you are permitted to use.</p></div>}
      </div>
      <aside className="space-y-4">
        <div className="hsptl-card p-5"><div className="eyebrow">STATION PREVIEW</div>{selected ? <><h3 className="mt-2 font-bold">{selected.specialty} · {selected.difficulty}</h3><div className="mt-2 flex items-center justify-between gap-2">{selected.reviewed?<span className="text-xs font-bold text-emerald-600">Reviewed for use</span>:<span className="text-xs font-bold text-amber-600">Awaiting source and answer review</span>}<span className="rounded-lg border border-hsptl-surface-border px-2 py-1 text-xs font-bold tabular-nums dark:border-hsptl-dark-border">{remainingSeconds === null ? 'Untimed' : remainingSeconds <= 0 ? 'Time expired' : `${Math.floor(remainingSeconds/60)}:${String(remainingSeconds%60).padStart(2,'0')}`}</span></div>{selected.candidate_instructions && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed dark:bg-slate-800"><b>Candidate instructions:</b> {selected.candidate_instructions}</p>}<p className="mt-3 text-sm leading-relaxed">{selected.question}</p><ClinicalTags className="mt-3" limit={7} tags={[makeClinicalTag('specialty', selected.specialty), makeClinicalTag('modality', selected.kind), makeClinicalTag('difficulty', selected.difficulty), makeClinicalTag('task', workspaceMode === 'viva' ? 'Clinical explanation' : workspaceMode === 'osce' ? 'Procedural skill' : 'Interpretation'), ...(selected.tags || []).map((tag) => makeClinicalTag('presentation', tag))]}/>{selected.checklist?.length ? <div className="mt-3"><div className="text-xs font-bold">Assessment checklist</div><ul className="mt-1 space-y-1 text-xs text-secondary">{selected.checklist.map((item,i)=><li key={i}>• {item}</li>)}</ul></div>:null}{selected.critical_errors?.length ? <div className="mt-3 rounded-lg border border-rose-200 p-3 text-xs text-rose-700 dark:border-rose-900 dark:text-rose-300"><b>Critical errors:</b><ul className="mt-1 space-y-1">{selected.critical_errors.map((item,i)=><li key={i}>• {item}</li>)}</ul></div>:null}{selected.media_url && <img src={selected.media_url} alt="Challenge reference" className="mt-3 max-h-56 w-full rounded-lg border border-hsptl-surface-border object-contain dark:border-hsptl-dark-border"/>}{selected.options.length ? <div className="mt-4 space-y-2">{selected.options.map((option) => <button key={option} onClick={() => setResponse(option)} className={`answer-option ${response === option ? 'answer-option-selected' : ''}`}>{option}</button>)}</div> : <textarea value={response} onChange={(e) => setResponse(e.target.value)} placeholder="Enter your answer…" className="form-field mt-3 min-h-24"/>}
          {!result ? <>{!selected.reviewed&&<button onClick={() => void approveSelected()} className="secondary-button mt-4 w-full">Review source & answer, then approve</button>}<button onClick={() => void submit()} disabled={!selected.reviewed || !response.trim() || loading || remainingSeconds === 0} className="primary-button mt-2 w-full">{loading ? 'Marking…' : remainingSeconds === 0 ? 'Time expired' : 'Submit answer'}</button></> : <div className={`mt-4 rounded-lg border p-3 ${result.correct ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100' : 'border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-100'}`}><div className="font-bold">{result.correct ? 'Correct' : 'Review this answer'}</div><p className="mt-1 text-sm">Expected answer: {result.answer}</p><p className="mt-2 text-sm">{result.explanation || 'No explanation was supplied with this item.'}</p>{result.source_url && <a className="mt-2 inline-flex text-xs underline" href={result.source_url} target="_blank" rel="noreferrer">{result.source_title} · View source</a>}<button className="secondary-button mt-3 w-full" onClick={() => { setSelected(null); setResult(null); setResponse(''); setRemainingSeconds(null); }}>Next challenge</button></div>}
        </> : <div className="py-8 text-center"><Icon name="osce" size={32} className="mx-auto muted"/><p className="muted mt-3 text-sm">Choose a challenge from the library to begin.</p></div>}</div>
        <div className="rounded-xl bg-hsptl-indigo p-4 text-white"><div className="text-xs font-bold uppercase tracking-wider text-indigo-200">Import format</div><p className="mt-2 text-sm leading-relaxed">JSON array or CSV columns: <code>question, options, answer, explanation, kind, specialty, difficulty, source_title, source_url, licence, media_url</code>.</p><p className="mt-2 text-xs text-indigo-200">Imported content is unreviewed until checked by you.</p></div>
      </aside>
    </section>
  </div>;
}
