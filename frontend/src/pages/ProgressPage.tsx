import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { ProgressSummary, LearningUnitProgress } from '../lib/api';
import { Icon } from '../components/Icon';

type Metric = { key: keyof ProgressSummary['lifetime']; label: string; detail: string; icon: 'book' | 'clock' | 'clipboard' | 'activity' };
const metrics: Metric[] = [
  { key: 'cards', label: 'Revision cards', detail: 'Active cards in your local library', icon: 'book' },
  { key: 'due', label: 'Cards due', detail: 'Ready for review today', icon: 'clock' },
  { key: 'attempts', label: 'Clinical answers', detail: 'Saved stage responses', icon: 'clipboard' },
  { key: 'quizzes', label: 'Quiz attempts', detail: 'Recorded quiz submissions', icon: 'activity' },
  { key: 'debriefs', label: 'Debriefs', detail: 'Saved simulation reflections', icon: 'clipboard' },
  { key: 'scripts', label: 'Clinical scripts', detail: 'Available illness scripts', icon: 'book' },
];

type ProgressMode = 'scores' | 'portfolio';

// HSPTL's provisional F-to-S score bands. Keep these thresholds explicit so they can
// be revised centrally if the institution adopts a different assessment policy.
function scoreGrade(percent: number): string {
  if (percent >= 97) return 'S';
  if (percent >= 90) return 'A';
  if (percent >= 80) return 'B';
  if (percent >= 70) return 'C';
  if (percent >= 60) return 'D';
  if (percent >= 50) return 'E';
  return 'F';
}

export default function ProgressPage({ mode = 'scores' }: { mode?: ProgressMode }) {
  const [data, setData] = useState<ProgressSummary | null>(null);
  const [unitProgress, setUnitProgress] = useState<LearningUnitProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  async function load() {
    setLoading(true); setError('');
    try { const [summary, learning] = await Promise.all([api.progress(), api.learningUnitProgress()]); setData(summary); setUnitProgress(learning); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load learning progress.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  async function exportJourney(){try{const payload=await api.exportPortfolio();const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`hsptl-learning-journey-${new Date().toISOString().slice(0,10)}.json`;document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);}catch(cause){setError(cause instanceof Error?cause.message:'Could not export the learning journey.');}}
  if (loading) return <div className="hsptl-card p-8 text-center muted">Loading saved learning activity…</div>;
  const latestLearningAverage = unitProgress?.latest_average_percent ?? data?.quiz_average_percent ?? null;
  const legacyQuizGrade = data?.quiz_average_percent === null || data?.quiz_average_percent === undefined
    ? null : scoreGrade(data.quiz_average_percent);
  const latestLearningGroups = unitProgress?.latest_average_percent !== null && unitProgress?.latest_average_percent !== undefined
    ? unitProgress.latest_average_units : (data?.quiz_groups ?? 0);
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div><div className="eyebrow">{mode === 'portfolio' ? 'PORTFOLIO · CROSS-WORKSPACE RECORD' : 'EXAM HALL · SCORE REPORT'}</div><h1 className="page-title mt-2">{mode === 'portfolio' ? 'Progress Board' : 'Scores'}</h1><p className="muted mt-2 max-w-2xl text-sm">{mode === 'portfolio' ? 'A consolidated view of recorded activity and available assessment results across all six workspaces. Missing data is shown as not yet recorded; activity counts are not clinical competence or mastery.' : 'Assessment performance with the HSPTL F-to-S grade scale. Clinical activity counts are not treated as examination scores.'}</p></div>
        <div className="flex gap-2"><button onClick={() => void exportJourney()} className="secondary-button inline-flex items-center gap-2 text-sm"><Icon name="download" size={15}/> Export journey</button><button onClick={() => void load()} className="secondary-button inline-flex items-center gap-2 text-sm"><Icon name="refresh" size={15}/> Refresh</button></div>
      </header>
      {error && <div className="status-error">{error}</div>}
      {data && <>
        {mode === 'portfolio' && <section className="hsptl-card p-5"><div className="eyebrow">CLINICAL JOURNEY · LEARNING MILESTONES</div><h2 className="mt-2 text-lg font-bold">Your learning journey</h2><p className="muted mt-1 text-sm">Milestones reflect recorded educational activity only. They are not clinical competence, entrustment or permission to practise independently.</p><div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{[
          {title:'First clinical reasoning attempt',done:data.lifetime.attempts>0,detail:`${data.lifetime.attempts} saved answer(s)`},
          {title:'First case debrief',done:data.lifetime.debriefs>0,detail:`${data.lifetime.debriefs} debrief(s) recorded`},
          {title:'First learning quiz',done:data.lifetime.quizzes+(unitProgress?.total_attempts??0)>0,detail:`${data.lifetime.quizzes+(unitProgress?.total_attempts??0)} quiz attempt(s)`},
          {title:'Started spaced review',done:data.lifetime.cards>0,detail:`${data.lifetime.cards} revision card(s)`},
          {title:'First OSCE practice',done:(data.exam?.osce_by_kind.reduce((n,x)=>n+x.total,0)??0)>0,detail:`${data.exam?.osce_by_kind.reduce((n,x)=>n+x.total,0)??0} OSCE attempt(s)`},
          {title:'Built a topic practice record',done:(unitProgress?.completed_units??0)>0,detail:`${unitProgress?.completed_units??0} topic(s) attempted`},
        ].map(item=><article key={item.title} className="rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div className="flex items-center gap-2"><Icon name={item.done?'check':'clock'} size={16}/><b className="text-sm">{item.title}</b></div><p className="muted mt-1 text-xs">{item.done?'Recorded': 'Not yet recorded'} · {item.detail}</p></article>)}</div></section>}
        {mode === 'portfolio' && <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            { name: 'Clinic', detail: `${data.lifetime.attempts.toLocaleString()} clinical answers · ${data.lifetime.debriefs.toLocaleString()} debriefs`, status: data.lifetime.attempts + data.lifetime.debriefs > 0 ? 'Activity recorded' : 'No activity recorded' },
            { name: 'Rounds', detail: `${data.lifetime.scripts.toLocaleString()} clinical scripts`, status: data.lifetime.scripts > 0 ? 'Library activity' : 'No activity recorded' },
            { name: 'Lab', detail: `${data.exam?.osce_by_kind.reduce((n, x) => n + x.total, 0) ?? 0} OSCE attempts`, status: (data.exam?.osce_by_kind.length ?? 0) > 0 ? 'Assessment recorded' : 'No assessment recorded' },
            { name: 'Ward', detail: 'On-call, handover and consultation activity', status: 'Tracking not yet available' },
            { name: 'Exam Hall', detail: `${(data.lifetime.quizzes + (unitProgress?.total_attempts ?? 0)).toLocaleString()} quiz attempts · ${data.exam?.by_specialty.reduce((n, x) => n + x.total, 0) ?? 0} exam answers`, status: data.lifetime.quizzes + (unitProgress?.total_attempts ?? 0) + (data.exam?.by_specialty.reduce((n, x) => n + x.total, 0) ?? 0) > 0 ? 'Scores available' : 'No scores recorded' },
            { name: 'Portfolio', detail: `${data.lifetime.cards.toLocaleString()} revision cards · ${data.lifetime.due.toLocaleString()} due`, status: 'Profile and data tools' },
          ].map(item => <article key={item.name} className="hsptl-card p-4"><div className="flex items-center justify-between gap-2"><h2 className="font-bold">{item.name}</h2><span className="text-[10px] font-semibold uppercase tracking-wide text-secondary">{item.status}</span></div><p className="muted mt-2 text-xs">{item.detail}</p></article>)}
        </section>}
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {metrics.map((metric) => <article key={metric.key} className="hsptl-card flex items-start gap-3 p-4"><span className="specialty-icon shrink-0"><Icon name={metric.icon} size={19}/></span><div className="min-w-0"><div className="text-2xl font-extrabold tabular-nums">{(metric.key === 'quizzes' ? data.lifetime.quizzes + (unitProgress?.total_attempts ?? 0) : data.lifetime[metric.key]).toLocaleString()}</div><h2 className="mt-1 text-sm font-bold">{metric.label}</h2><p className="muted mt-1 text-xs">{metric.detail}</p></div></article>)}
        </section>
        {unitProgress && <section className="hsptl-card p-5 sm:p-6"><div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">LEARNING LIBRARY · EVENT-DERIVED PROGRESS</div><h2 className="mt-2 text-lg font-bold">Topic practice and objective coverage</h2><p className="muted mt-1 text-sm">Quiz attempts are saved in the canonical event history. Results are formative and objective-linked, not clinical competence measures.</p></div><div className="text-right"><div className="text-2xl font-extrabold">{unitProgress.completed_units}/{unitProgress.units.length}</div><div className="muted text-xs">Topics attempted</div></div></div><div className="mt-4 space-y-3">{unitProgress.units.map((unit) => <article key={unit.unit_id} className="rounded-xl border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div className="flex flex-wrap items-center justify-between gap-2"><div><b className="text-sm">{unit.title}</b><p className="muted mt-1 text-xs">{unit.opened_count} opens · {unit.attempt_count} saved attempts</p></div><div className="text-right">{unit.latest_percent === null ? <span className="muted text-xs">Not attempted</span> : <><b className="text-lg tabular-nums">{unit.latest_percent}%</b><p className="muted text-xs">Latest: {unit.latest_score}/{unit.latest_maximum}</p></>}</div></div>{unit.objective_results.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2">{unit.objective_results.map((objective) => <div key={objective.objective} className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800"><div className="flex justify-between gap-2 text-xs"><span>{objective.objective}</span><b>{objective.percent}%</b></div><div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"><div className="h-full rounded-full bg-hsptl-teal" style={{ width: `${objective.percent}%` }}/></div></div>)}</div>}</article>)}</div><p className="muted mt-3 text-[11px]">{unitProgress.projection}</p></section>}
        <section className="hsptl-card p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow">FORMATIVE QUIZ RECORD</div><h2 className="mt-2 text-lg font-bold">Latest recorded quiz performance</h2><p className="muted mt-1 text-sm">Mean percentage across each topic’s latest saved formative quiz attempt (legacy stage results are used when no topic attempts exist).</p></div><div className="text-right"><div className="text-3xl font-extrabold tabular-nums">{latestLearningAverage === null ? '—' : `${Math.round(latestLearningAverage)}%`}</div><div className="text-sm font-bold">{latestLearningAverage === null ? 'Not graded' : `Grade ${legacyQuizGrade || scoreGrade(latestLearningAverage)}`}</div><div className="muted text-xs">{latestLearningGroups.toLocaleString()} latest topic result(s)</div></div></div>
          <div className="mt-4 flex flex-wrap gap-2">{[{g:'F',r:'0–49'},{g:'E',r:'50–59'},{g:'D',r:'60–69'},{g:'C',r:'70–79'},{g:'B',r:'80–89'},{g:'A',r:'90–96'},{g:'S',r:'97–100'}].map(x=><span key={x.g} className="rounded-lg border border-hsptl-surface-border px-2 py-1 text-xs dark:border-hsptl-dark-border"><b>{x.g}</b><span className="muted ml-1">{x.r}%</span></span>)}</div>
          {latestLearningAverage === null ? <div className="mt-4 rounded-lg border border-dashed border-hsptl-surface-border p-4 text-sm text-secondary dark:border-hsptl-dark-border">No quiz results have been recorded yet. Complete a quiz in the Learning Library to start this summary.</div> : <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700"><div className="h-full rounded-full bg-hsptl-teal" style={{ width: `${Math.max(0, Math.min(100, latestLearningAverage))}%` }}/></div>}
        </section>
        {data.practice && data.reasoning_process && data.retention && data.transfer && (
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <article className="hsptl-card p-4"><div className="eyebrow">PRACTICE</div><div className="mt-2 text-2xl font-extrabold">{data.practice.reasoning_attempts}</div><p className="muted mt-1 text-xs">Saved reasoning attempts · {data.practice.exam_attempts} submitted exams</p></article>
            <article className="hsptl-card p-4"><div className="eyebrow">REASONING PROCESS</div><div className="mt-2 text-2xl font-extrabold">{data.reasoning_process.percent === null ? '—' : `${data.reasoning_process.percent}%`}</div><p className="muted mt-1 text-xs">{data.reasoning_process.attempts_citing_source_facts} attempts cite source facts</p></article>
            <article className="hsptl-card p-4"><div className="eyebrow">RETENTION</div><div className="mt-2 text-2xl font-extrabold">{data.retention.cards_due}</div><p className="muted mt-1 text-xs">{data.retention.again_rate_percent === null ? 'No completed card reviews yet' : `${data.retention.again_rate_percent}% Again rate`}</p></article>
            <article className="hsptl-card p-4"><div className="eyebrow">TRANSFER</div><div className="mt-2 text-2xl font-extrabold">{data.transfer.learning_actions_revisited}</div><p className="muted mt-1 text-xs">Learner-marked learning revisits</p></article>
          </section>
        )}
        {data.exam && (data.exam.by_specialty.length > 0 || data.exam.osce_by_kind.length > 0) && (
          <section className="hsptl-card p-5"><h2 className="font-bold">Exam and OSCE performance breakdown</h2><div className="mt-4 grid gap-3 sm:grid-cols-2">
            {data.exam.by_specialty.map((item) => <div key={item.specialty} className="rounded-lg border border-hsptl-surface-border p-3 text-sm dark:border-hsptl-dark-border"><div className="flex justify-between gap-2"><b>{item.specialty}</b><span>{item.percentage}%</span></div><div className="muted mt-1 text-xs">{item.correct} correct of {item.total} exam answers</div></div>)}
            {data.exam.osce_by_kind.map((item) => <div key={item.kind} className="rounded-lg border border-hsptl-surface-border p-3 text-sm dark:border-hsptl-dark-border"><div className="flex justify-between gap-2"><b>{item.kind}</b><span>{item.percentage}%</span></div><div className="muted mt-1 text-xs">{item.correct} correct of {item.total} OSCE attempts</div></div>)}
          </div></section>
        )}
        {data.recommendations && data.recommendations.length > 0 && (
          <section className="hsptl-card p-5"><div className="eyebrow">PERSONALISED NEXT ACTIONS</div><h2 className="mt-2 font-bold">Evidence-based review suggestions</h2><div className="mt-4 space-y-2">{data.recommendations.map((item) => <article key={item.id} className="rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div className="text-xs font-bold text-hsptl-teal">{item.department}</div><div className="mt-1 font-semibold text-sm">{item.action}</div><div className="muted mt-1 text-xs">{item.reason}</div></article>)}</div></section>
        )}
        <p className="muted text-xs">Scope: {data.scope === 'all_saved_activity' ? 'all saved activity in this local database' : data.scope}. These totals are not a streak, time-on-task measure, diagnostic-accuracy score, or validated mastery assessment.</p>
      </>}
    </div>
  );
}
