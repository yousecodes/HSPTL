import { useEffect, useMemo, useState } from 'react';
import { api, type LotteryArchiveItem } from '../lib/api';
import { Icon } from '../components/Icon';

function formatDay(value: string) {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(date);
}

export default function DailyCaseArchivePage() {
  const [items, setItems] = useState<LotteryArchiveItem[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => { api.lotteryHistory(365).then(result => setItems(result.items)).catch(err => setError(err instanceof Error ? err.message : 'Archive could not be loaded.')).finally(() => setLoading(false)); }, []);
  const filtered = useMemo(() => items.filter(item => `${item.case?.presenting_complaint || ''} ${item.case?.specialty || ''} ${item.event?.title || ''} ${item.draw_date}`.toLowerCase().includes(query.toLowerCase())), [items, query]);
  const groups = useMemo(() => filtered.reduce<Record<string, LotteryArchiveItem[]>>((acc, item) => { (acc[item.draw_date] ||= []).push(item); return acc; }, {}), [filtered]);
  return <div className="space-y-6">
    <header><div className="eyebrow">CLINICAL JOURNEY · DAILY CASES</div><h2 className="page-title mt-2">Daily Case Archive</h2><p className="muted mt-2 max-w-2xl text-sm">Revisit previous daily assignments by date. Archive cards intentionally show presenting information—not diagnoses or unrevealed answers.</p></header>
    <div className="flex flex-wrap items-center gap-3"><label className="min-w-0 flex-1"><span className="sr-only">Search archive</span><input className="form-field" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search complaint, specialty or event…"/></label><span className="muted text-xs">{filtered.length} assignments</span></div>
    {loading && <div className="hsptl-card p-6 text-center muted">Loading archive…</div>}
    {error && <div className="status-error" role="alert">{error}</div>}
    {!loading && !error && filtered.length === 0 && <div className="hsptl-card p-8 text-center"><Icon name="fileSearch" size={26}/><h3 className="mt-2 font-bold">No archived daily cases yet</h3><p className="muted mt-1 text-sm">Completed and assigned daily cases will appear here as they are drawn.</p></div>}
    {Object.entries(groups).sort(([a],[b]) => b.localeCompare(a)).map(([day, dayItems]) => <section key={day} className="space-y-3"><h3 className="eyebrow">{formatDay(day)}</h3><div className="grid gap-3 md:grid-cols-2">{dayItems.map(item => <article key={item.draw_id} className="hsptl-card p-4">
      <div className="flex items-start justify-between gap-3"><div className="flex min-w-0 items-start gap-3">{item.event && <span className="text-2xl" aria-hidden="true">{item.event.icon}</span>}<div className="min-w-0"><div className="eyebrow">{item.event?.title || 'Daily clinical case'}</div><h4 className="mt-1 font-bold">{item.case?.presenting_complaint || 'Unknown presentation'}</h4></div></div><span className="clinical-tag shrink-0">{item.state === 'selected' ? 'Drawn' : 'No case'}</span></div>
      {item.case && <div className="muted mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs"><span>{item.case.patient_age_value == null ? 'Age unknown' : `Age ${item.case.patient_age_value} ${item.case.patient_age_unit}`}</span><span>{item.case.specialty}</span><span>{item.case.difficulty}</span></div>}
      <div className="muted mt-3 border-t border-[var(--border-subtle)] pt-2 text-[11px]">{item.event?.category || 'Clinical learning'} · {item.pool_size} eligible cases at draw · {item.reveal_count} debrief reveal(s) recorded across the installation</div>
    </article>)}</div></section>)}
    <p className="muted text-xs">Historical event themes are snapshots. Diagnoses and answer payloads are deliberately excluded from this archive endpoint.</p>
  </div>;
}
