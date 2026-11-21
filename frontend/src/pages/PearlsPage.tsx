import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { NoteSection, SavedPearl, StudyNote } from '../lib/api';
import { Icon } from '../components/Icon';
import { ClinicalTags, makeClinicalTag } from '../components/ClinicalTags';
import { indexClinicalContent } from '../lib/tagging';

type Options = { note_types: string[]; levels: string[]; jurisdictions: string[]; packs: Array<{ id: string; title: string; tagline: string; source_title: string; source_url: string }> };
type Generated = { note: StudyNote; markdown: string; tutor_prompt: string; local_reference_count: number; matched_curated_pack: boolean };

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

function EvidenceSection({ section }: { section: NoteSection }) {
  return <section className="hsptl-card p-5"><div className="flex items-start justify-between gap-3"><div><h3 className="font-bold">{section.title}</h3><p className="muted mt-1 text-xs">{section.objective}</p></div><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${section.evidence.length ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200'}`}>{section.evidence.length ? (section.evidence.every((item) => item.kind === 'learner_reflection') ? 'Learner reflection' : `${section.evidence.length} source extract${section.evidence.length > 1 ? 's' : ''}`) : 'Needs verification'}</span></div>{section.evidence.length ? <div className="mt-4 space-y-3">{section.evidence.map((e, i) => <div className="hsptl-pearl" key={`${section.title}-${i}`}><p className="text-sm leading-relaxed">{e.text}</p><div className="muted mt-2 text-xs">{e.citation}{e.section ? ` · ${e.section}` : ''}{e.license ? ` · ${e.license}` : ''}</div>{e.url && <a href={e.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-hsptl-indigo underline dark:text-indigo-200">View source <Icon name="external" size={12}/></a>}</div>)}</div> : <div className="mt-4 rounded-lg border border-dashed border-hsptl-surface-border p-4 text-sm text-secondary dark:border-hsptl-dark-border">Use the objective above as a study prompt. No matching excerpt was found in the selected sources; do not treat this section as a complete clinical recommendation.</div>}</section>;
}

export default function PearlsPage({ mode = 'debrief' }: { mode?: 'debrief' | 'pearls' }) {
  const [options, setOptions] = useState<Options | null>(null);
  const [refs, setRefs] = useState<Array<{ name: string; modified: string; size_bytes: number }>>([]);
  const [saved, setSaved] = useState<SavedPearl[]>([]);
  const [topic, setTopic] = useState('');
  const [noteType, setNoteType] = useState('Condition');
  const [level, setLevel] = useState('Clinical years');
  const [jurisdiction, setJurisdiction] = useState('Egypt');
  const [usePdfs, setUsePdfs] = useState(true);
  const [useArticles, setUseArticles] = useState(false);
  const [generated, setGenerated] = useState<Generated | null>(null);
  const [activeSaved, setActiveSaved] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function loadSupportingData() {
    try { const [o, r, s] = await Promise.all([api.pearlsOptions(), api.references(), api.savedPearls()]); setOptions(o); setRefs(r); setSaved(s); if (o.note_types.length) setNoteType(o.note_types[0]); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load Study resources.'); }
  }
  useEffect(() => { void loadSupportingData(); }, []);

  const curatedMatch = useMemo(() => options?.packs.find((p) => `${p.title} ${p.id}`.toLowerCase().includes(topic.toLowerCase().trim())) ?? null, [options, topic]);

  async function generate() {
    if (topic.trim().length < 2) { setError('Enter a topic with at least two characters.'); return; }
    setLoading(true); setError(''); setMessage(''); setGenerated(null); setActiveSaved(null);
    try { const result = await api.generateNote({ topic: topic.trim(), note_type: noteType, level, jurisdiction, use_local_pdfs: usePdfs, use_open_access: useArticles }); setGenerated(result); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not generate the note.'); }
    finally { setLoading(false); }
  }

  async function save() {
    if (!generated) return;
    try {
      const result = await api.saveNote(generated.note);
      if (result.id) await indexClinicalContent({
        content_type: 'pearl', content_id: result.id, title: result.title || generated.note.title,
        workspace: 'rounds', summary: generated.note.topic, source_status: 'draft',
        tag_pairs: [['task', 'Clinical Reasoning'], ['level', generated.note.level]],
      });
      setMessage('Note saved to your local study library.'); setSaved(await api.savedPearls());
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save note.'); }
  }
  async function makeCards() {
    if (!generated) return;
    try { const result = await api.createCards(generated.note); setMessage(`${result.created} revision cards added. Duplicate questions were skipped.`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create revision cards.'); }
  }
  async function openSaved(id: string) {
    setError(''); setLoading(true);
    try { const item = await api.savedPearl(id); setGenerated({ note: item.note, markdown: item.markdown, tutor_prompt: '', local_reference_count: item.note.evidence_count, matched_curated_pack: !!item.note.curated_pack }); setActiveSaved(id); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not open saved note.'); }
    finally { setLoading(false); }
  }
  async function upload(file?: File) {
    if (!file) return;
    setError(''); setMessage('');
    try { const result = await api.uploadReference(file); setMessage(`${result.name} imported successfully.`); setRefs(await api.references()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not import PDF.'); }
  }

  const isPearls = mode === 'pearls';
  const heading = isPearls ? 'High-Yield Pearls' : 'Case Debriefs';
  const eyebrow = isPearls ? 'ATTENDING TAKEAWAYS & RAPID RECALL' : 'POST-CASE REVIEW & REFLECTION';
  const description = isPearls
    ? 'Keep concise, evidence-linked clinical pearls and turn the most useful points into recall prompts.'
    : 'Review the reasoning behind a case, capture what changed your decision and identify the next point to practise.';

  return (
    <div className={`space-y-6 pearls-workspace pearls-workspace-${mode}`}>
      <div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">{eyebrow}</div><h1 className="page-title mt-2">{heading}</h1><p className="muted mt-2 max-w-2xl text-sm">{description} Every section shows what is supported and what still needs verification.</p></div><div className="rounded-xl border border-hsptl-surface-border bg-hsptl-card px-4 py-3 dark:border-hsptl-dark-border dark:bg-hsptl-dark-card"><div className="text-2xl font-extrabold">{saved.length}</div><div className="muted text-xs">Saved debriefs</div></div></div>
      {(message || error) && <div className={error ? 'status-error' : 'status-success'}>{error || message}</div>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <main className="min-w-0 space-y-5">
          <section className="hsptl-card p-5 sm:p-6">
            <div className="flex items-center gap-2"><span className="specialty-icon"><Icon name="sparkles" size={20}/></span><div><h2 className="text-lg font-bold">{isPearls ? 'Capture a high-yield pearl' : 'Build a case debrief'}</h2><p className="muted text-xs">{isPearls ? 'Start with a clinical question and create a concise, source-aware takeaway.' : 'Choose one learning goal; HSPTL builds a structured source-aware framework.'}</p></div></div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="sm:col-span-2"><span className="field-label">Topic or clinical question</span><input value={topic} onChange={(e) => setTopic(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void generate(); }} placeholder="e.g. acute heart failure, chest pain, iron deficiency anaemia" className="form-field mt-2"/></label>
              <label><span className="field-label">Note type</span><select value={noteType} onChange={(e) => setNoteType(e.target.value)} className="form-field mt-2">{(options?.note_types || ['Condition','Clinical presentation','Differential diagnosis','Investigation','Medicine','OSCE / Procedure']).map((x) => <option key={x}>{x}</option>)}</select></label>
              <label><span className="field-label">Study level</span><select value={level} onChange={(e) => setLevel(e.target.value)} className="form-field mt-2">{(options?.levels || ['Preclinical','Clinical years','Final-year / exam revision','OSCE / practical']).map((x) => <option key={x}>{x}</option>)}</select></label>
              <label><span className="field-label">Clinical jurisdiction</span><select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} className="form-field mt-2">{(options?.jurisdictions || ['Egypt','UK','WHO / global','International']).map((x) => <option key={x}>{x}</option>)}</select></label>
            </div>
            <div className="mt-5 rounded-xl bg-hsptl-surface-canvas p-4 dark:bg-hsptl-dark-canvas"><div className="field-label mb-3">Use these sources</div><div className="flex flex-wrap gap-4"><label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={usePdfs} onChange={(e) => setUsePdfs(e.target.checked)}/> My imported PDFs ({refs.length})</label><label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={useArticles} onChange={(e) => setUseArticles(e.target.checked)}/> Eligible open-access articles</label></div><p className="muted mt-2 text-xs">Local extraction is deterministic. Open-access retrieval requires an internet connection and the article's licence to permit excerpts.</p></div>
            {curatedMatch && <div className="hsptl-pearl mt-4"><div className="text-xs font-bold uppercase tracking-wide text-hsptl-teal">Matching teaching pack</div><div className="mt-1 font-semibold">{curatedMatch.title}</div><p className="muted mt-1 text-sm">{curatedMatch.tagline}</p><a className="mt-2 inline-flex text-xs font-semibold text-hsptl-indigo underline dark:text-indigo-200" href={curatedMatch.source_url} target="_blank" rel="noreferrer">{curatedMatch.source_title} <Icon name="external" size={12}/></a></div>}
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><span className="muted text-xs">No AI API key required</span><button onClick={() => void generate()} disabled={loading || topic.trim().length < 2} className="primary-button inline-flex items-center gap-2 disabled:opacity-50">{loading ? 'Building note…' : 'Generate note'} <Icon name="arrow" size={15}/></button></div>
          </section>
          {generated && <section className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow">GENERATED STUDY NOTE</div><h2 className="mt-1 text-2xl font-extrabold">{generated.note.title}</h2><p className="muted mt-1 text-sm">{generated.note.note_type} · {generated.note.level} · {generated.note.jurisdiction}</p><ClinicalTags className="mt-3" limit={6} tags={[makeClinicalTag('task', generated.note.note_type), makeClinicalTag('level', generated.note.level), makeClinicalTag('setting', generated.note.jurisdiction), makeClinicalTag('presentation', generated.note.topic)]}/></div><div className="flex flex-wrap gap-2"><button onClick={() => void save()} className="secondary-button inline-flex items-center gap-2 text-sm"><Icon name="save" size={15}/> Save</button><button onClick={() => downloadText(`${generated.note.topic.toLowerCase().replace(/[^a-z0-9]+/g,'-')}.md`, generated.markdown)} className="secondary-button inline-flex items-center gap-2 text-sm"><Icon name="download" size={15}/> Export</button><button onClick={() => void makeCards()} className="primary-button inline-flex items-center gap-2 text-sm"><Icon name="plus" size={15}/> Make cards</button></div></div>
            <div className="grid gap-3 sm:grid-cols-3"><div className="metric-card"><div className="text-xl font-extrabold">{generated.note.supported_sections}/{generated.note.total_sections}</div><div className="muted text-xs">Sections with excerpts</div></div><div className="metric-card"><div className="text-xl font-extrabold">{generated.note.evidence_count}</div><div className="muted text-xs">Source extracts</div></div><div className="metric-card"><div className="text-xl font-extrabold">{generated.local_reference_count}</div><div className="muted text-xs">Retrieved passages</div></div></div>
            <div className="note-warning"><b>Evidence coverage is not a completeness or accuracy score.</b><p className="mt-1 text-sm">Unmatched sections are learning prompts, not confirmed clinical recommendations. Verify diagnosis and management against current applicable guidance.</p></div>
            {generated.note.curated_pack && <section className="hsptl-card p-5"><div className="eyebrow">CURATED TEACHING PACK</div><h3 className="mt-1 font-bold">{generated.note.curated_pack.title}</h3><p className="muted mt-2 text-sm">{generated.note.curated_pack.summary}</p><div className="mt-3 flex flex-wrap gap-2">{generated.note.curated_pack.curated_takeaways.slice(0,5).map((x,i)=><span key={i} className="rounded-full bg-hsptl-teal-light px-3 py-1 text-xs text-hsptl-teal-dark">{x}</span>)}</div></section>}
            {generated.note.sections.map((section, i) => <EvidenceSection key={`${section.title}-${i}`} section={section}/>) }
            {generated.note.recall_prompts.length > 0 && <section className="hsptl-card p-5"><h3 className="font-bold">Active recall</h3><div className="mt-3 space-y-3">{generated.note.recall_prompts.map((prompt,i)=><details className="rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border" key={i}><summary className="cursor-pointer text-sm font-semibold">{prompt.question}</summary><p className="muted mt-3 text-sm leading-relaxed">{prompt.answer}</p><p className="muted mt-2 text-xs">{prompt.source}</p></details>)}</div></section>}
            {generated.tutor_prompt && <details className="hsptl-card p-4"><summary className="cursor-pointer font-semibold">Prepare deeper tutor feedback</summary><textarea readOnly value={generated.tutor_prompt} className="form-field mt-3 min-h-48 text-xs"/><button className="secondary-button mt-2 text-sm" onClick={() => navigator.clipboard.writeText(generated.tutor_prompt)}>Copy tutor prompt</button></details>}
          </section>}
        </main>
        <aside className="space-y-4">
          <section className="hsptl-card p-4"><div className="flex items-center justify-between"><h3 className="font-bold">Your reference shelf</h3><label className="icon-button" title="Import PDF"><Icon name="upload"/><input className="sr-only" type="file" accept="application/pdf,.pdf" onChange={(e) => void upload(e.target.files?.[0])}/></label></div><p className="muted mt-1 text-xs">Upload local guidelines, formulary chapters and lecture PDFs.</p>{refs.length ? <div className="mt-3 space-y-2">{refs.slice(0,7).map((r) => <div key={r.name} className="flex items-start gap-2 text-xs"><Icon name="file" className="muted mt-0.5" size={14}/><span className="min-w-0 break-words">{r.name}</span></div>)}</div> : <div className="muted mt-4 text-sm">No PDFs imported yet.</div>}</section>
          <section className="hsptl-card p-4"><h3 className="font-bold">Saved debriefs</h3>{saved.length ? <div className="mt-3 space-y-1">{saved.slice(0,12).map((s) => <button key={s.id} onClick={() => void openSaved(s.id)} className={`w-full rounded-lg p-2 text-left hover:bg-hsptl-surface-canvas dark:hover:bg-hsptl-dark-canvas ${activeSaved === s.id ? 'bg-hsptl-surface-canvas dark:bg-hsptl-dark-canvas' : ''}`}><div className="truncate text-sm font-semibold">{s.title}</div><div className="muted mt-1 text-xs">{s.note_type} · {s.supported_sections}/{s.total_sections}</div></button>)}</div> : <p className="muted mt-3 text-sm">Your saved debriefs will appear here.</p>}</section>
          <section className="rounded-xl bg-hsptl-indigo p-4 text-white"><div className="text-xs font-bold uppercase tracking-wide text-indigo-200">Debrief principle</div><p className="mt-2 text-sm leading-relaxed">Start with retrieval, use evidence to correct gaps, then convert the most important learning points into spaced revision.</p></section>
        </aside>
      </div>
    </div>
  );
}
