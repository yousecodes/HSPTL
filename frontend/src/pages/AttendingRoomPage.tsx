import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { Specialty, SpecialtyDetail, SpecialtyTopic } from '../lib/api';
import { Icon } from '../components/Icon';
import { ClinicalTags, makeClinicalTag } from '../components/ClinicalTags';

export default function AttendingRoomPage() {
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [selectedSpecialty, setSelectedSpecialty] = useState<SpecialtyDetail | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<SpecialtyTopic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.specialties().then(async (items) => {
      setSpecialties(items);
      const first = items[0];
      if (first) {
        const detail = await api.specialty(first.slug);
        setSelectedSpecialty(detail);
        setSelectedTopic(detail.topics[0] || null);
      }
    }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load the teaching index.')).finally(() => setLoading(false));
  }, []);

  async function openSpecialty(item: Specialty) {
    setError(''); setSelectedTopic(null);
    try {
      const detail = await api.specialty(item.slug);
      setSelectedSpecialty(detail);
      setSelectedTopic(detail.topics[0] || null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not open this specialty.'); }
  }

  const tags = useMemo(() => {
    if (!selectedSpecialty || !selectedTopic) return [];
    return [
      makeClinicalTag('specialty', selectedSpecialty.name),
      ...((selectedTopic.keywords || []).slice(0, 5).map((word) => makeClinicalTag('presentation', word))),
      makeClinicalTag('task', 'Clinical reasoning'),
    ];
  }, [selectedSpecialty, selectedTopic]);

  if (loading) return <div className="hsptl-card p-8 text-center muted">Preparing the attending room…</div>;

  return <div className="attending-room space-y-5">
    <header className="attending-room-intro">
      <div><div className="eyebrow">CONSULTANT-LED TEACHING</div><h2 className="page-title mt-2">Attending Room</h2><p className="muted mt-2 max-w-2xl text-sm">A focused teaching session: choose a specialty, select a topic, follow the explanation and connect its tags to cases, practical stations and examinations.</p></div>
      <div className="attending-live-label"><span className="rail-status-dot is-ready"/> Teaching library</div>
    </header>
    {error && <div role="alert" className="status-error">{error}</div>}
    <div className="attending-layout">
      <aside className="attending-specialty-rail">
        <div className="eyebrow">SPECIALTY SERVICES</div>
        <h3 className="mt-1 font-bold">Choose a service</h3>
        <div className="mt-3 space-y-1">{specialties.map((item) => <button key={item.slug} onClick={() => void openSpecialty(item)} className={`attending-specialty-link ${selectedSpecialty?.slug === item.slug ? 'is-active' : ''}`}><span>{item.name}</span><small>{item.topic_count} topics</small></button>)}</div>
      </aside>
      <section className="attending-session">
        {selectedSpecialty && <div className="attending-session-heading"><div><div className="eyebrow">{selectedSpecialty.name.toUpperCase()} · ATTENDING SESSION</div><h3 className="mt-1 text-xl font-extrabold">{selectedTopic?.title || 'Select a teaching topic'}</h3><p className="muted mt-1 text-sm">{selectedTopic?.tagline || selectedSpecialty.description}</p></div><span className="session-chip">TEACHING ROUND</span></div>}
        <div className="attending-topic-grid">{selectedSpecialty?.topics.map((topic) => <button key={topic.id} onClick={() => setSelectedTopic(topic)} className={`attending-topic-card ${selectedTopic?.id === topic.id ? 'is-active' : ''}`}><b>{topic.title}</b><small>{topic.tagline || 'Open teaching summary'}</small></button>)}</div>
        {selectedTopic && <>
          <div className="attending-main-grid">
            <article className="attending-explanation-panel">
              <div className="attending-panel-heading"><span className="attending-panel-mark"><Icon name="book" size={18}/></span><div><div className="eyebrow">THE ATTENDING EXPLAINS</div><h4 className="font-bold">Clinical explanation</h4></div></div>
              <p className="mt-4 text-sm leading-7">{selectedTopic.summary || 'A reviewed explanation for this topic has not been added yet. Use the source link and indexed teaching prompts to guide a faculty-reviewed session.'}</p>
              {selectedTopic.source_url && <a href={selectedTopic.source_url} target="_blank" rel="noreferrer" className="attending-source-link mt-4 inline-flex items-center gap-2 text-sm font-semibold">{selectedTopic.source_title || 'Open teaching source'} <Icon name="external" size={14}/></a>}
              <div className="mt-5 rounded-xl border border-dashed border-[var(--border-subtle)] bg-[var(--bg-canvas)] p-4">
                <div className="flex items-center gap-2 text-sm font-bold"><Icon name="image" size={16}/> Illustration board</div>
                <p className="muted mt-2 text-xs leading-relaxed">Topic-linked figures, ECGs, radiology and diagrams belong here. Only media with a verified source and reuse status should be embedded; the current teaching pack does not provide an illustration for every topic.</p>
                <div className="illustration-placeholder mt-3"><span className="illustration-orbit"/><span className="illustration-center"><WorkspaceMarkForTeaching/></span><small>Verified illustration area</small></div>
              </div>
            </article>
            <aside className="attending-rounds-sidebar">
              <section className="attending-side-card"><div className="eyebrow">LINKED INDEX TAGS</div><h4 className="mt-1 font-bold">Learning connections</h4><ClinicalTags tags={tags} limit={8} className="mt-3"/><p className="muted mt-3 text-xs">The same tag identities are intended to connect this teaching topic to Clinic cases, Lab spotters, Viva prompts and Exam Hall questions.</p></section>
              <section className="attending-side-card"><div className="eyebrow">VIVA PREPARATION</div><h4 className="mt-1 font-bold">Defend your reasoning</h4><ul className="mt-3 space-y-2 text-sm leading-relaxed"><li>Explain the underlying mechanism.</li><li>Identify the finding that changes the differential.</li><li>Justify the next investigation.</li><li>State the complication or safety issue you must not miss.</li></ul><p className="muted mt-3 text-xs">These are session prompts, not a marked viva bank. Use the Rounds → Viva section for imported, reviewed questions.</p></section>
            </aside>
          </div>
        </>}
      </section>
    </div>
  </div>;
}

function WorkspaceMarkForTeaching() {
  return <svg viewBox="0 0 32 32" width="42" height="42" fill="none" aria-hidden="true"><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5"/><path d="M10.5 23V9h6c4 0 6 5 1.5 7l6 7h-4l-5.5-6v6h-4Z" fill="currentColor"/><circle cx="25" cy="7" r="2.5" fill="var(--mark-accent)" stroke="currentColor" strokeWidth="1"/></svg>;
}
