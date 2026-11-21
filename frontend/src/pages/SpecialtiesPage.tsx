import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { Specialty, SpecialtyDetail, SpecialtyTopic } from '../lib/api';
import { Icon } from '../components/Icon';
import type { IconName } from '../components/Icon';
import { ClinicalTags, makeClinicalTag } from '../components/ClinicalTags';
import { indexClinicalContent } from '../lib/tagging';

type Article = { title: string; authors: string; journal: string; year: string; pmcid: string; open_access: boolean; url: string; abstract: string };

const specialtyIcons: Record<string, IconName> = {
  'General Medicine': 'clinic', Cardiology: 'heart', 'Respiratory Medicine': 'lungs',
  'Gastroenterology & Hepatology': 'activity', Nephrology: 'kidney',
  'Endocrinology & Diabetes': 'activity', Neurology: 'brain', 'Stroke Medicine': 'brain',
  'Infectious Diseases': 'shield', Dermatology: 'activity', Haematology: 'droplet',
  'Medical Oncology': 'activity', Rheumatology: 'activity', 'Geriatric Medicine': 'stethoscope',
  'Emergency Medicine': 'siren', 'Critical Care': 'activity',
  'Anaesthetics & Perioperative Medicine': 'stethoscope', 'General Surgery': 'stethoscope',
  'Orthopaedics & Trauma': 'activity', Urology: 'activity',
  'Obstetrics & Gynaecology': 'baby', Paediatrics: 'baby', Neonatology: 'baby',
  'Child & Adolescent Mental Health': 'brain', Psychiatry: 'brain', Ophthalmology: 'activity',
  'ENT & Head and Neck Surgery': 'stethoscope', 'Dentistry & Oral Health': 'tooth',
  'Oral & Maxillofacial Surgery': 'tooth', 'Palliative Care': 'heart',
  'Rehabilitation Medicine': 'activity', 'Primary Care & Family Medicine': 'clinic', 'Public Health & Epidemiology': 'shield',
  'Clinical Pharmacology & Therapeutics': 'flask', 'Medical Genetics & Genomics': 'activity', 'Radiology & Imaging': 'image',
  'Pathology & Laboratory Medicine': 'microscope', 'Clinical Immunology & Allergy': 'shield',
  'Sexual Health & Genitourinary Medicine': 'heart', 'Occupational & Environmental Medicine': 'stethoscope', 'Sports & Exercise Medicine': 'activity',
  'Vascular Surgery': 'heart', Neurosurgery: 'brain', 'Transfusion & Transplant Medicine': 'droplet',
};

function QuizQuestion({ question, index }: { question: NonNullable<SpecialtyTopic['questions']>[number]; index: number }) {
  const [answer, setAnswer] = useState<number | null>(null);
  const [checked, setChecked] = useState(false);
  return (
    <div className="hsptl-card p-5">
      <div className="mb-3 text-xs font-bold uppercase tracking-wide text-hsptl-teal">Question {index + 1}</div>
      <h4 className="font-semibold leading-relaxed">{question.question}</h4>
      <div className="mt-4 grid gap-2">
        {question.options.map((option, optionIndex) => (
          <button key={optionIndex} onClick={() => { setAnswer(optionIndex); setChecked(false); }} className={`answer-option ${answer === optionIndex ? 'answer-option-selected' : ''}`}>
            <span className="answer-letter">{String.fromCharCode(65 + optionIndex)}</span><span>{option}</span>
          </button>
        ))}
      </div>
      {!checked && <button disabled={answer === null} className="primary-button mt-4 disabled:opacity-50" onClick={() => setChecked(true)}>Check answer</button>}
      {checked && <div className={`mt-4 rounded-lg border p-4 ${answer === question.answer ? 'status-success' : 'status-error'}`}>
        <div className="font-bold">{answer === question.answer ? 'Correct' : `Not quite · Correct answer: ${question.options[question.answer]}`}</div>
        <p className="mt-2 text-sm">{question.explanation}</p>
        {question.takeaway && <div className="hsptl-pearl mt-3 text-sm"><b>Clinical pearl</b><p className="mt-1">{question.takeaway}</p></div>}
      </div>}
    </div>
  );
}

export default function SpecialtiesPage({ mode = 'library' }: { mode?: 'library' | 'rounds' }) {
  const [items, setItems] = useState<Specialty[]>([]);
  const [selected, setSelected] = useState<SpecialtyDetail | null>(null);
  const [activeTopic, setActiveTopic] = useState<SpecialtyTopic | null>(null);
  const [query, setQuery] = useState('');
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.specialties().then(setItems).catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not load specialties.')).finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => items.filter((item) => `${item.name} ${item.description} ${(item.focus_areas || []).join(' ')} ${(item.common_presentations || []).join(' ')} ${(item.learning_themes || []).join(' ')}`.toLowerCase().includes(query.toLowerCase())), [items, query]);

  async function openSpecialty(item: Specialty) {
    setError(''); setActiveTopic(null); setArticles([]);
    try {
      const detail = await api.specialty(item.slug);
      setSelected(detail);
      await Promise.allSettled(detail.topics.map((topic) => indexClinicalContent({
        content_type: mode === 'rounds' ? 'lecture' : 'topic',
        content_id: `${detail.slug}:${topic.id}`,
        title: topic.title,
        workspace: mode === 'rounds' ? 'rounds' : 'clinic',
        summary: topic.tagline || topic.summary || '',
        source_status: topic.source_url ? 'unreviewed' : 'draft',
        content_url: topic.source_url || '',
        tag_pairs: [['specialty', detail.name], ['task', 'Clinical Reasoning']],
      })));
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not open this specialty.'); }
  }

  async function selectTopic(topic: SpecialtyTopic) {
    setActiveTopic(topic); setArticles([]);
    if (selected) {
      try { setArticles(await api.specialtyArticles(selected.slug, topic.title)); }
      catch { setArticles([]); }
    }
  }

  if (loading) return <div className="hsptl-card p-8 text-center muted">Loading clinical specialties…</div>;

  const pageTitle = mode === 'rounds' ? 'Specialty Index' : 'Case Library';
  const eyebrow = mode === 'rounds' ? 'SPECIALTY ROUNDS' : 'CASE LIBRARY';
  const description = mode === 'rounds'
    ? 'Move through hospital specialties, find topic tags and open the teaching material linked to each clinical service.'
    : 'Browse clinical case reports and source-linked teaching cases by specialty, presentation and diagnostic theme.';

  return (
    <div className={`space-y-6 specialty-workspace specialty-workspace-${mode}`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><div className="eyebrow">{eyebrow} · {items.length} SERVICES</div><h1 className="page-title mt-2">{pageTitle}</h1><p className="muted mt-2 max-w-2xl text-sm">{description} Search across specialties, focus areas and common presentations.</p></div>
        <div className="relative w-full sm:w-72"><Icon name="search" size={17} className="muted absolute left-3 top-1/2 -translate-y-1/2"/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={mode === 'rounds' ? 'Find a specialty or topic…' : 'Find a case specialty…'} className="form-field pl-10"/></div>
      </div>
      {error && <div className="status-error">{error}</div>}
      {!selected ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item) => (
            <button key={item.slug} onClick={() => void openSpecialty(item)} className="specialty-card group text-left">
              <div className="flex items-start justify-between"><span className="specialty-icon"><Icon name={(specialtyIcons[item.name] || 'stethoscope')} size={22}/></span><span className="text-xs font-semibold text-hsptl-teal">{item.topic_count} topics</span></div>
              <h2 className="mt-5 text-lg font-bold tracking-tight">{item.name}</h2><p className="muted mt-2 min-h-10 text-sm leading-relaxed">{item.description}</p><div className="mt-3 flex flex-wrap gap-1.5">{(item.focus_areas || []).slice(0, 3).map((area) => <span key={area} className="rounded-full bg-hsptl-teal-light px-2 py-1 text-[10px] font-semibold text-hsptl-teal-dark">{area}</span>)}</div><div className="muted mt-2 text-[11px]">{item.curated_pack_count ?? 0} curated packs · {item.discovery_theme_count ?? item.topic_count} discovery themes</div>
              <div className="mt-5 flex items-center justify-between border-t border-hsptl-surface-border pt-3 text-xs font-semibold text-hsptl-indigo dark:border-hsptl-dark-border dark:text-indigo-200"><span>{mode === 'rounds' ? 'Open specialty service' : 'Browse case library'}</span><Icon name="arrow" size={15}/></div>
            </button>
          ))}
          {filtered.length === 0 && <div className="hsptl-card p-8 text-center muted sm:col-span-2 xl:col-span-3">No specialties match your search.</div>}
        </div>
      ) : (
        <div className="space-y-5">
          <button onClick={() => { setSelected(null); setActiveTopic(null); setArticles([]); }} className="secondary-button inline-flex items-center gap-2 text-sm"><Icon name="chevron" className="rotate-90" size={15}/> All case specialties</button>
          <section className="hsptl-card overflow-hidden">
            <div className="brand-band p-6 sm:p-8"><div className="text-xs font-bold uppercase tracking-[.16em] text-indigo-200">{mode === 'rounds' ? 'SPECIALTY SERVICE' : 'CASE SPECIALTY'}</div><h2 className="mt-2 text-2xl font-extrabold">{selected.name}</h2><p className="mt-2 max-w-2xl text-sm text-indigo-100">{selected.description}</p></div>
            <div className="space-y-3 border-b border-hsptl-surface-border p-4 dark:border-hsptl-dark-border">
              {!!selected.focus_areas?.length && <div><b className="text-xs uppercase tracking-wide text-hsptl-teal">Service scope & focus areas</b><div className="mt-2 flex flex-wrap gap-2">{selected.focus_areas.map((value) => <span key={value} className="rounded-full border border-[var(--border-subtle)] px-2.5 py-1 text-xs">{value}</span>)}</div></div>}
              {!!selected.common_presentations?.length && <div><b className="text-xs uppercase tracking-wide text-hsptl-teal">Common clinical presentations</b><div className="mt-2 flex flex-wrap gap-2">{selected.common_presentations.map((value) => <span key={value} className="rounded-full bg-hsptl-surface px-2.5 py-1 text-xs dark:bg-hsptl-dark-surface">{value}</span>)}</div></div>}
              {!!selected.learning_themes?.length && <div><b className="text-xs uppercase tracking-wide text-hsptl-teal">Learning themes</b><div className="mt-2 flex flex-wrap gap-2">{selected.learning_themes.map((value) => <span key={value} className="rounded-full bg-hsptl-teal-light px-2.5 py-1 text-xs font-semibold text-hsptl-teal-dark">{value}</span>)}</div></div>}
            </div>
            <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
              {selected.topics.map((topic) => <button key={topic.id} onClick={() => void selectTopic(topic)} className={`topic-card text-left ${activeTopic?.id === topic.id ? 'topic-card-active' : ''}`}><div className="text-xs font-bold uppercase tracking-wide text-hsptl-teal">{topic.questions?.length || 0} questions</div><div className="mt-2 font-bold">{topic.title}</div><p className="muted mt-1 text-sm">{topic.tagline}</p><ClinicalTags className="mt-3" limit={4} tags={[makeClinicalTag('specialty', selected.name), makeClinicalTag('task', 'Clinical reasoning'), ...((topic.keywords || []).slice(0, 2).map((word) => makeClinicalTag('presentation', word)))]}/></button>)}
            </div>
          </section>
          {activeTopic && (
            <section className="space-y-4">
              <div><div className="eyebrow">{mode === 'rounds' ? 'ROUNDS TOPIC' : 'ACTIVE CASE LIBRARY TOPIC'}</div><h3 className="mt-1 text-xl font-bold">{activeTopic.title}</h3><p className="muted mt-1 text-sm">{activeTopic.summary || activeTopic.tagline || "A discovery theme: use the linked evidence search to find source records and develop reviewed learning content."}</p><ClinicalTags className="mt-3" limit={7} tags={[makeClinicalTag('specialty', selected.name), makeClinicalTag('task', 'Clinical reasoning'), ...((activeTopic.keywords || []).map((word) => makeClinicalTag('presentation', word))) ]}/></div>
              {activeTopic.questions?.map((q, i) => <QuizQuestion key={`${activeTopic.id}-${i}`} question={q} index={i}/>)}
              {activeTopic.source_url && <a className="inline-flex items-center gap-2 text-sm font-semibold text-hsptl-indigo underline dark:text-indigo-200" href={activeTopic.source_url} target="_blank" rel="noreferrer">{activeTopic.source_title || 'Open source guidance'} <Icon name="external" size={14}/></a>}
              <div className="space-y-3"><h3 className="text-lg font-bold">Related published cases</h3>{articles.length ? articles.map((article, i) => <article key={`${article.pmcid}-${i}`} className="hsptl-card p-4"><div className="flex items-center justify-between gap-2"><span className="eyebrow">{article.year || 'Published case'}</span><span className="rounded-full bg-hsptl-teal-light px-2 py-1 text-[11px] font-bold text-hsptl-teal-dark">{article.open_access ? 'Open access' : 'Abstract'}</span></div><h4 className="mt-2 font-bold">{article.title}</h4><p className="muted mt-1 text-xs">{article.authors} · {article.journal}</p><p className="muted mt-3 text-sm leading-relaxed">{article.abstract}</p><a href={article.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-hsptl-indigo dark:text-indigo-200">Read article <Icon name="external" size={14}/></a></article>) : <div className="muted text-sm">No related reports returned. Internet access may be unavailable, or no matching open-access case report was found.</div>}</div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
