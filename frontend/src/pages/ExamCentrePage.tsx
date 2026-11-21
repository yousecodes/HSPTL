import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import type { ExamItem, QuestionItem } from '../lib/api';
import { api } from '../lib/api';
import { Icon } from '../components/Icon';
import { indexClinicalContent, recordIndexedLearningEvent } from '../lib/tagging';

type Dataset = { id: string; name: string; description: string; url: string; licence: string; format: string };
type ExamResult = { score: number; total: number; percentage: number; results: Array<{ question_id: string; response: string; correct: boolean; answer: string; explanation: string; specialty: string }> };

export default function ExamCentrePage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [exams, setExams] = useState<ExamItem[]>([]);
  const [bank, setBank] = useState<{ count: number; reviewed_count: number; questions: QuestionItem[] }>({ count: 0, reviewed_count: 0, questions: [] });
  const [title, setTitle] = useState('Medical revision examination');
  const [specialty, setSpecialty] = useState('Mixed');
  const [count, setCount] = useState(20);
  const [duration, setDuration] = useState(30);
  const [difficulty, setDifficulty] = useState('Any');
  const [activeExam, setActiveExam] = useState<{ exam: ExamItem; questions: QuestionItem[] } | null>(null);
  const [answers, setAnswers] = useState<Record<string,string>>({});
  const [startedAt, setStartedAt] = useState<number>(0);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [result, setResult] = useState<ExamResult | null>(null);
  const [question, setQuestion] = useState('');
  const [optionsText, setOptionsText] = useState('Option A\nOption B\nOption C\nOption D');
  const [answer, setAnswer] = useState('');
  const [explanation, setExplanation] = useState('');
  const [sourceTitle, setSourceTitle] = useState('My medical study guide');
  const [sourceUrl, setSourceUrl] = useState('');
  const [guideName, setGuideName] = useState('');
  const [tab, setTab] = useState<'library'|'builder'|'author'>('library');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [d,e,b] = await Promise.all([api.examDatasets(), api.exams(), api.examQuestions()]);
      setDatasets(d); setExams(e); setBank(b);
      await Promise.allSettled(b.questions.map((item) => indexClinicalContent({
        content_type: 'exam_question', content_id: item.id, title: item.question.slice(0, 180), workspace: 'exam',
        summary: item.specialty + ' · ' + item.kind,
        source_status: item.reviewed ? 'reviewed' : 'unreviewed', content_url: item.source_url || '',
        tag_pairs: [['specialty', item.specialty], ['difficulty', item.difficulty], ['task', 'Clinical Reasoning']],
      })));
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load Exam Centre.'); }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!activeExam || result || activeExam.exam.duration_minutes <= 0) return;
    const timer = window.setInterval(() => setRemaining((value) => value === null ? null : Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [activeExam?.exam.id, result]);

  async function markReviewed(id: string, reviewed: boolean) {
    setError('');
    try { await api.reviewQuestion(id, reviewed); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not update review status.'); }
  }
  async function importFile(file?: File) {
    if (!file) return;
    setBusy(true); setError(''); setMessage('');
    try { const r = await api.importExamQuestions(file); setMessage(`Imported ${r.created} questions; ${r.skipped} rows skipped (${r.truncated} beyond the per-file limit). All imported questions are marked for review.`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Import failed.'); }
    finally { setBusy(false); }
  }
  async function build(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const r = await api.buildExam({ title, specialty, question_count: count, duration_minutes: duration, difficulty });
      setMessage(`Created "${r.title}" with ${r.question_count} questions.`);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not build examination.'); }
    finally { setBusy(false); }
  }
  async function authorQuestion(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      await api.addExamQuestion({ kind: 'MCQ', specialty: specialty === 'Mixed' ? 'General medicine' : specialty, difficulty, question, options: optionsText.split('\n').map(x=>x.trim()).filter(Boolean), answer, explanation, source_title: sourceTitle, source_url: sourceUrl, licence: 'User-provided / verify permissions', tags: ['Study guide'] });
      setQuestion(''); setAnswer(''); setExplanation(''); setMessage('Question added to your local bank. Review its answer and source before using it in a formal exam.'); await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save question.'); }
    finally { setBusy(false); }
  }
  async function openExam(id: string) {
    setBusy(true); setError(''); setResult(null); setAnswers({});
    try { const e = await api.exam(id); setActiveExam(e); setStartedAt(Date.now()); setRemaining(e.exam.duration_minutes > 0 ? e.exam.duration_minutes * 60 : null); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not open examination.'); }
    finally { setBusy(false); }
  }
  async function submitExam() {
    if (!activeExam) return;
    setBusy(true); setError('');
    try {
      const r = await api.submitExam(activeExam.exam.id, answers, Math.max(0, Math.round((Date.now()-startedAt)/1000)));
      setResult(r);
      await Promise.allSettled(r.results.map((item) => recordIndexedLearningEvent('exam_question', item.question_id, { action: 'completed', score: item.correct ? 1 : 0, max_score: 1 })));
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not submit examination.'); }
    finally { setBusy(false); }
  }

  if (activeExam) return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">ASSESSMENT SESSION</div><h1 className="page-title mt-2">{activeExam.exam.title}</h1><p className="muted mt-1 text-sm">{activeExam.exam.specialty} · {activeExam.questions.length} questions · {activeExam.exam.duration_minutes > 0 ? `${activeExam.exam.duration_minutes} minutes` : 'Untimed'}</p></div><div className="flex items-center gap-2"><div className="rounded-lg border border-hsptl-surface-border px-3 py-2 text-sm font-bold tabular-nums dark:border-hsptl-dark-border">{remaining===null?'Untimed':remaining===0?'Time expired':`${Math.floor(remaining/60).toString().padStart(2,'0')}:${(remaining%60).toString().padStart(2,'0')}`}</div><button className="secondary-button" onClick={() => { setActiveExam(null); setResult(null); setRemaining(null); }}>Exit examination</button></div></div>
    {result ? <section className="hsptl-card p-6"><div className="text-center"><div className="eyebrow">EXAMINATION REPORT</div><div className="mt-2 text-5xl font-extrabold tracking-tight">{result.percentage}%</div><p className="muted mt-2">{result.score} correct out of {result.total}</p></div><div className="mt-6 space-y-3">{result.results.map((r,i)=><div key={r.question_id} className="rounded-lg border border-hsptl-surface-border p-4 dark:border-hsptl-dark-border"><div className="flex items-center justify-between"><span className="text-xs font-bold">Question {i+1}</span><span className={r.correct?'text-emerald-600':'text-rose-600'}>{r.correct?'Correct':'Incorrect'}</span></div><p className="mt-2 text-sm">Your answer: {r.response || 'Not answered'}</p><p className="mt-1 text-sm font-semibold">Expected: {r.answer}</p>{r.explanation && <p className="muted mt-2 text-sm">{r.explanation}</p>}</div>)}</div><button className="primary-button mt-5" onClick={()=>{setActiveExam(null);setResult(null);}}>Return to Exam Centre</button></section> : <>
      <div className="note-warning text-sm">This local examination records your responses and marks them against the imported answer key. Check source validity and question quality before treating scores as formal assessment.</div>
      <div className="space-y-4">{activeExam.questions.map((q,i)=><section className="hsptl-card p-5" key={q.id}><div className="flex justify-between gap-3"><span className="eyebrow">QUESTION {i+1} OF {activeExam.questions.length}</span><span className="muted text-xs">{q.specialty} · {q.difficulty}</span></div><h2 className="mt-3 font-semibold leading-relaxed">{q.question}</h2><div className="mt-4 space-y-2">{q.options.length ? q.options.map((option)=><button key={option} disabled={remaining===0} onClick={()=>setAnswers(prev=>({...prev,[q.id]:option}))} className={`answer-option ${answers[q.id]===option?'answer-option-selected':''}`}>{option}</button>) : <input disabled={remaining===0} className="form-field" placeholder="Enter your answer…" value={answers[q.id]||''} onChange={e=>setAnswers(prev=>({...prev,[q.id]:e.target.value}))}/>}</div></section>)}</div>
      <div className="flex flex-wrap items-center justify-between gap-3"><span className="muted text-sm">{Object.keys(answers).length} of {activeExam.questions.length} answered{remaining===0?' · Time expired':''}</span><button className="primary-button" disabled={busy} onClick={()=>void submitExam()}>{busy?'Submitting…':'Submit examination'}</button></div>
    </>}
  </div>;

  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><div className="eyebrow">HSPTL · ASSESSMENT SERVICE</div><h1 className="page-title mt-2">Exam Hall</h1><p className="muted mt-2 max-w-2xl text-sm">A structured workspace for medical question collections, mock examinations and source-based assessment building.</p></div><div className="rounded-xl bg-hsptl-indigo px-4 py-3 text-white"><div className="text-2xl font-extrabold">{bank.count}</div><div className="text-xs text-indigo-200">Local questions</div></div></header>
    {(message||error)&&<div className={error?'status-error':'status-success'}>{error||message}</div>}
    <div className="flex flex-wrap gap-2 border-b border-hsptl-surface-border pb-3 dark:border-hsptl-dark-border">
      {([['library','Examination library'],['builder','Build an exam'],['author','Write a question']] as const).map(([id,label])=><button key={id} onClick={()=>setTab(id)} className={`rounded-lg px-4 py-2 text-sm font-bold ${tab===id?'bg-hsptl-indigo text-white':'secondary-button'}`}>{label}</button>)}
    </div>
    {tab==='library'&&<div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,.8fr)]">
      <section className="space-y-4"><div className="hsptl-card p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="font-bold">Your examinations</h2><p className="muted mt-1 text-xs">Locally created and saved assessments.</p></div><span className="text-xs text-secondary">{exams.length} saved</span></div>{exams.length?<div className="mt-4 space-y-2">{exams.map(e=><div key={e.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div><div className="font-semibold text-sm">{e.title}</div><div className="muted mt-1 text-xs">{e.specialty} · {e.question_count} questions · {e.duration_minutes} min</div></div><button className="primary-button" onClick={()=>void openExam(e.id)}>Start</button></div>)}</div>:<p className="muted mt-4 text-sm">No examinations yet. Import questions or build your first assessment.</p>}</div>
      <div className="hsptl-card p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="font-bold">Local question bank</h2><p className="muted mt-1 text-xs">{bank.count} imported or authored questions</p></div><label className="secondary-button cursor-pointer"><Icon name="upload" size={15}/> Import<input className="sr-only" type="file" accept=".json,.jsonl,.csv,.tsv" onChange={e=>void importFile(e.target.files?.[0])}/></label></div><div className="mt-4 grid grid-cols-2 gap-2"><div className="metric-card"><div className="text-xl font-extrabold">{bank.count}</div><div className="muted text-xs">Available questions</div></div><div className="metric-card"><div className="text-xl font-extrabold">{bank.reviewed_count}</div><div className="muted text-xs">Reviewed</div></div></div><p className="note-warning mt-4 text-xs">Imported questions are unreviewed by default. Confirm the answer key, source, licence and clinical currency before formal use. Only reviewed questions can enter a new examination.</p><div className="mt-4 space-y-2">{bank.questions.slice(0,12).map(q=><div key={q.id} className="flex items-center justify-between gap-2 rounded-lg border border-hsptl-surface-border p-2 dark:border-hsptl-dark-border"><div className="min-w-0"><div className="truncate text-xs font-semibold">{q.question}</div><div className="muted text-[10px]">{q.specialty} · {q.kind}</div></div><button className="secondary-button shrink-0 text-[11px]" onClick={()=>void markReviewed(q.id,!q.reviewed)}>{q.reviewed?'Mark unreviewed':'Review & approve'}</button></div>)}</div></div></section>
      <aside className="hsptl-card p-5"><h2 className="font-bold">Open exam datasets</h2><p className="muted mt-1 text-xs">External collections to download and import when their terms permit.</p><div className="mt-4 space-y-3">{datasets.map(d=><div key={d.id} className="border-b border-hsptl-surface-border pb-3 last:border-0 dark:border-hsptl-dark-border"><div className="flex items-start justify-between gap-2"><div className="font-semibold text-sm">{d.name}</div><a href={d.url} target="_blank" rel="noreferrer" className="text-xs font-bold text-hsptl-indigo underline dark:text-indigo-200">Open source</a></div><p className="muted mt-1 text-xs">{d.description}</p><p className="muted mt-1 text-[11px]">Format: {d.format} · {d.licence}</p></div>)}</div></aside>
    </div>}
    {tab==='builder'&&<section className="hsptl-card max-w-3xl p-5 sm:p-6"><div className="eyebrow">ASSESSMENT DESIGN</div><h2 className="mt-1 text-xl font-extrabold">Build a new examination</h2><p className="muted mt-2 text-sm">Assemble a reproducible assessment from your reviewed local question bank. Questions can come from open datasets, your own study guides or HSPTL Pearls.</p><form onSubmit={build} className="mt-5 grid gap-4 sm:grid-cols-2"><label className="sm:col-span-2"><span className="field-label">Examination title</span><input className="form-field mt-1" value={title} onChange={e=>setTitle(e.target.value)} required/></label><label><span className="field-label">Specialty</span><select className="form-field mt-1" value={specialty} onChange={e=>setSpecialty(e.target.value)}><option>Mixed</option>{['General medicine','Cardiology','Respiratory','Neurology','Surgery','Paediatrics','Pathology','Radiology'].map(x=><option key={x}>{x}</option>)}</select></label><label><span className="field-label">Difficulty</span><select className="form-field mt-1" value={difficulty} onChange={e=>setDifficulty(e.target.value)}>{['Any','Beginner','Intermediate','Advanced'].map(x=><option key={x}>{x}</option>)}</select></label><label><span className="field-label">Question count</span><input className="form-field mt-1" type="number" min="1" max="200" value={count} onChange={e=>setCount(Number(e.target.value))}/></label><label><span className="field-label">Duration (minutes; 0 = untimed)</span><input className="form-field mt-1" type="number" min="0" max="600" value={duration} onChange={e=>setDuration(Number(e.target.value))}/></label><div className="sm:col-span-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">Available pool: {bank.reviewed_count} reviewed of {bank.count} total questions. The builder selects only reviewed questions matching specialty and difficulty; it will not fabricate questions when the reviewed pool is empty.</div><div className="sm:col-span-2"><button className="primary-button" disabled={busy||bank.reviewed_count===0}>{busy?'Building…':'Create examination'}</button></div></form></section>}
    {tab==='author'&&<section className="hsptl-card max-w-3xl p-5 sm:p-6"><div className="eyebrow">SOURCE-BASED QUESTION AUTHORING</div><h2 className="mt-1 text-xl font-extrabold">Add a question from a study guide</h2><p className="muted mt-2 text-sm">Use your lecture notes, textbooks or study systems as the source. Add a question and answer key yourself, then build an exam from the resulting question bank. Automated question drafting can be added later as an optional local-AI feature.</p><div className="mt-4 rounded-lg border border-dashed border-hsptl-surface-border p-4 dark:border-hsptl-dark-border"><div className="font-semibold text-sm">Attach a PDF study guide</div><p className="muted mt-1 text-xs">Stores the PDF in your local Pearls reference shelf so you can consult and cite it while authoring questions.</p><label className="secondary-button mt-3 inline-flex cursor-pointer"><Icon name="upload" size={15}/> {guideName||'Choose PDF'}<input className="sr-only" type="file" accept=".pdf,application/pdf" onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{await api.uploadReference(file);setGuideName(file.name);setSourceTitle(file.name);setMessage(`${file.name} added to your reference shelf.`);}catch(err){setError(err instanceof Error?err.message:'Could not import study guide.');}}}/></label></div><form onSubmit={authorQuestion} className="mt-5 space-y-4"><label className="block"><span className="field-label">Question</span><textarea className="form-field mt-1 min-h-24" value={question} onChange={e=>setQuestion(e.target.value)} required/></label><label className="block"><span className="field-label">Options (one per line)</span><textarea className="form-field mt-1 min-h-24" value={optionsText} onChange={e=>setOptionsText(e.target.value)}/></label><label className="block"><span className="field-label">Correct answer (must match one option exactly)</span><input className="form-field mt-1" value={answer} onChange={e=>setAnswer(e.target.value)} required/></label><label className="block"><span className="field-label">Explanation / rationale</span><textarea className="form-field mt-1 min-h-20" value={explanation} onChange={e=>setExplanation(e.target.value)}/></label><div className="grid gap-3 sm:grid-cols-2"><label><span className="field-label">Source title</span><input className="form-field mt-1" value={sourceTitle} onChange={e=>setSourceTitle(e.target.value)}/></label><label><span className="field-label">Source URL (optional)</span><input className="form-field mt-1" value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)}/></label></div><button className="primary-button" disabled={busy}>{busy?'Saving…':'Add to question bank'}</button></form></section>}
  </div>;
}
