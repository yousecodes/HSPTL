import { useEffect, useMemo, useState } from 'react';
import { api, type ClinicalEventCatalogueItem } from '../lib/api';

export default function ClinicalEventCataloguePanel() {
  const [items, setItems] = useState<ClinicalEventCatalogueItem[]>([]);
  const [category, setCategory] = useState('All themes');
  const [expanded, setExpanded] = useState<string>('');
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState('');
  const [reviewerToken, setReviewerToken] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [newCategory, setNewCategory] = useState('General');
  const [newIcon, setNewIcon] = useState('🏥');
  const [newSignals, setNewSignals] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.clinicalEventCatalogue().then((result) => setItems(result.items)).catch(() => setError('Clinical scenario themes could not be loaded.')); }, []);
  const categories = useMemo(() => ['All themes', ...Array.from(new Set(items.map((item) => item.category))).sort()], [items]);
  const filtered = useMemo(() => items.filter((item) => category === 'All themes' || item.category === category), [items, category]);
  const visible = showAll ? filtered : filtered.slice(0, 6);
  async function createEvent(){if(!reviewerToken||!newTitle.trim())return;setSaving(true);setError('');const id=newTitle.toLowerCase().trim().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');try{await api.saveClinicalEvent({id,title:newTitle.trim(),category:newCategory,icon:newIcon,summary:'Institution-authored educational event theme.',setting:'Clinical learning',learning_objectives:['Structured assessment','Clinical reasoning','Team communication'],case_signals:newSignals.split(',').map(x=>x.trim()).filter(Boolean),workspaces:['clinic','ward','rounds'],active:true,selection_weight:1,cooldown_days:2,review_note:'Reviewer-managed catalogue entry.'},reviewerToken);const result=await api.clinicalEventCatalogue();setItems(result.items);setNewTitle('');setNewSignals('');}catch(err){setError(err instanceof Error?err.message:'Could not save the event.');}finally{setSaving(false);}}
  async function pauseEvent(item:ClinicalEventCatalogueItem){if(!reviewerToken)return;setSaving(true);try{await api.saveClinicalEvent({...item,active:false},reviewerToken);setItems(current=>current.filter(x=>x.id!==item.id));}catch(err){setError(err instanceof Error?err.message:'Could not pause the event.');}finally{setSaving(false);}}
  return <section className="hsptl-card p-5 space-y-4">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">CLINICAL EVENTS · SCENARIO THEMES</div><h2 className="mt-1 text-lg font-bold">Clinical events catalogue</h2><p className="muted mt-1 max-w-3xl text-sm">A growing library of teaching-event themes for case discovery, simulation and structured debrief—not patient-case content, a prerequisite for the Daily Case, live hospital alerts or care protocols.</p></div><div className="text-xs muted">{items.length} scenario themes</div></div>
    <label className="block max-w-sm text-xs font-semibold">Filter by clinical stream<select className="form-field mt-1 w-full" value={category} onChange={(event) => { setCategory(event.target.value); setShowAll(false); }} >{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
    <details className="rounded-xl border border-[var(--border-subtle)] p-3"><summary className="cursor-pointer text-sm font-semibold">Reviewer: manage event catalogue</summary><div className="mt-3 grid gap-2 sm:grid-cols-2"><label className="text-xs font-semibold sm:col-span-2">Reviewer token<input type="password" className="form-field mt-1" value={reviewerToken} onChange={e=>setReviewerToken(e.target.value)} placeholder="HSPTL_REVIEWER_TOKEN" autoComplete="off"/></label><label className="text-xs font-semibold">Event title<input className="form-field mt-1" value={newTitle} onChange={e=>setNewTitle(e.target.value)} placeholder="e.g. Trauma Call"/></label><label className="text-xs font-semibold">Category<input className="form-field mt-1" value={newCategory} onChange={e=>setNewCategory(e.target.value)}/></label><label className="text-xs font-semibold">Icon / emoji<input className="form-field mt-1" value={newIcon} onChange={e=>setNewIcon(e.target.value)}/></label><label className="text-xs font-semibold">Case matching signals<input className="form-field mt-1" value={newSignals} onChange={e=>setNewSignals(e.target.value)} placeholder="trauma, collision, fracture"/></label><button className="secondary-button sm:col-span-2" disabled={!reviewerToken||!newTitle.trim()||saving} onClick={()=>void createEvent()}>{saving?'Saving…':'Add event theme'}</button><p className="muted text-xs sm:col-span-2">Existing themes can be paused from their cards. Event themes are only selected when an eligible, reviewed and rights-cleared case matches.</p></div></details>
    {error && <p role="alert" className="status-error">{error}</p>}
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{visible.map((item) => <article key={item.id} className="rounded-xl border border-[var(--border-subtle)] p-3">
      <button className="flex w-full items-start gap-3 text-left" onClick={() => setExpanded(expanded === item.id ? '' : item.id)}><span className="text-2xl" aria-hidden="true">{item.icon}</span><span className="min-w-0 flex-1"><b className="block text-sm">{item.title}</b><span className="muted text-[11px]">{item.category} · {item.setting}</span></span><span className="text-xs muted">{expanded === item.id ? '−' : '+'}</span></button>
      <p className="muted mt-2 text-xs leading-relaxed">{item.summary}</p>
      {reviewerToken && <button type="button" className="mt-2 text-[11px] font-semibold text-rose-700 underline dark:text-rose-300" disabled={saving} onClick={()=>void pauseEvent(item)}>Pause this event</button>}
      {expanded === item.id && <div className="mt-3 space-y-2 border-t border-[var(--border-subtle)] pt-3 text-xs"><div><b>Learning objectives</b><ul className="mt-1 list-disc pl-4">{item.learning_objectives.map((goal) => <li key={goal}>{goal}</li>)}</ul></div><div><b>Case discovery signals</b><p className="muted mt-1">{item.case_signals.join(' · ')}</p></div><div><b>Suitable workspaces</b><p className="muted mt-1">{item.workspaces.join(' · ')}</p></div><p className="muted italic">{item.review_note}</p></div>}
    </article>)}</div>
    {filtered.length > 6 && <button className="secondary-button" onClick={() => setShowAll((old) => !old)}>{showAll ? 'Show fewer themes' : `Show all ${filtered.length} themes`}</button>}
  </section>;
}
