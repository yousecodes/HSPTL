import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { SharedClinicalTag, TaggedContentItem } from '../lib/api';
import { Icon } from '../components/Icon';
import { ClinicalTags, type ClinicalTag } from '../components/ClinicalTags';

const facetLabels: Record<string, string> = {
  specialty: 'Specialties', system: 'Body systems', presentation: 'Presentations', task: 'Clinical tasks',
  modality: 'Modalities', setting: 'Care setting', competency: 'Competencies', difficulty: 'Difficulty', level: 'Learner level',
};

export default function TagIndexPage() {
  const [catalogue, setCatalogue] = useState<SharedClinicalTag[]>([]);
  const [facet, setFacet] = useState('specialty');
  const [selectedTag, setSelectedTag] = useState('specialty.cardiology');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<TaggedContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const facets = useMemo(() => [...new Set(catalogue.map((tag) => tag.facet))], [catalogue]);
  const visibleTags = useMemo(() => catalogue.filter((tag) => tag.facet === facet && (!search || tag.label.toLowerCase().includes(search.toLowerCase()))), [catalogue, facet, search]);
  const selected = catalogue.find((tag) => tag.tag_id === selectedTag);

  useEffect(() => {
    api.tagCatalogue().then((result) => {
      setCatalogue(result.tags);
      if (!result.tags.some((tag) => tag.tag_id === 'specialty.cardiology')) setSelectedTag(result.tags[0]?.tag_id || '');
    }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load the shared tag index.')).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedTag) return;
    api.taggedContent({ tag_ids: [selectedTag], limit: 100 }).then((result) => setItems(result.items)).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load tagged content.'));
  }, [selectedTag]);

  const displayTags: ClinicalTag[] = selected ? [{ id: selected.tag_id, label: selected.label, facet: selected.facet as ClinicalTag['facet'] }] : [];

  if (loading) return <div className="hsptl-card p-8 text-center muted">Loading the shared clinical tag index…</div>;

  return <div className="tag-index-workspace space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">SHARED HOSPITAL INDEX</div><h2 className="page-title mt-2">Clinical Tag Index</h2><p className="muted mt-2 max-w-2xl text-sm">Find connected cases, teaching topics, diagnostic spotters, OSCE stations and exam questions through one controlled tag vocabulary.</p></div><div className="tag-count-card"><b>{catalogue.length}</b><small>shared tags</small></div></header>
    {error && <div className="status-error" role="alert">{error}</div>}
    <div className="tag-index-layout">
      <aside className="tag-facet-rail"><div className="eyebrow">TAG DIMENSIONS</div><div className="mt-3 space-y-1">{facets.map((name) => <button key={name} onClick={() => { setFacet(name); setSearch(''); const first = catalogue.find((tag) => tag.facet === name); if (first) setSelectedTag(first.tag_id); }} className={`tag-facet-button ${facet === name ? 'is-active' : ''}`}><span>{facetLabels[name] || name}</span><small>{catalogue.filter((tag) => tag.facet === name).length}</small></button>)}</div></aside>
      <section className="tag-list-panel"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">{facetLabels[facet] || facet}</div><h3 className="mt-1 font-bold">Select a tag</h3></div><div className="relative min-w-[190px] flex-1 sm:max-w-[260px]"><Icon name="search" size={15} className="absolute left-3 top-3 muted"/><input className="form-field pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter tags…" aria-label="Filter tags"/></div></div><div className="mt-4 flex flex-wrap gap-2">{visibleTags.map((tag) => <button key={tag.tag_id} onClick={() => setSelectedTag(tag.tag_id)} className={`tag-index-chip ${selectedTag === tag.tag_id ? 'is-active' : ''}`}>{tag.label}</button>)}</div></section>
      <section className="tag-results-panel"><div className="eyebrow">CROSS-WORKSPACE RESULTS</div><h3 className="mt-1 text-lg font-extrabold">{selected?.label || 'Select a tag'}</h3><ClinicalTags className="mt-2" tags={displayTags}/><div className="mt-4 flex items-center justify-between gap-3"><span className="muted text-xs">{items.length} linked item(s)</span><span className="tag-results-hint">One tag · multiple practice modes</span></div>
        {items.length ? <div className="mt-3 grid gap-2">{items.map((item) => <article key={item.item_id} className="tag-result-card"><div className="flex items-center justify-between gap-2"><span className="tag-workspace-badge">{item.workspace.replaceAll('_', ' ')}</span><span className="tag-source-status">{item.source_status}</span></div><h4 className="mt-2 font-bold text-sm">{item.title}</h4><p className="muted mt-1 text-xs">{item.summary || item.content_type.replaceAll('_', ' ')}</p><div className="mt-2"><ClinicalTags tags={item.tags.map((tag) => ({ id: tag.tag_id, label: tag.label, facet: tag.facet as ClinicalTag['facet'] }))} limit={5}/></div></article>)}</div> : <div className="tag-empty-state mt-4"><Icon name="layers" size={26}/><b className="mt-2">No content linked to this tag yet</b><p className="muted mt-1 max-w-md text-xs">The shared vocabulary is ready. As case reports, specialty teaching topics, visual challenges, OSCE stations and exam questions are indexed, they will appear here under the same tag.</p></div>}
      </section>
    </div>
  </div>;
}
