import { useEffect, useState } from 'react';
import { api, type ContentFactoryCatalog, type CurriculumProjection } from '../lib/api';
import { Icon } from '../components/Icon';
import SourceContentStudio from './ContentStudioPage';
import ScenarioAuthoringPanel from '../components/ScenarioAuthoringPanel';

const OUTPUTS = [
  { id: 'question_set', label: 'Question sets', note: '3 MCQs per topic' },
  { id: 'viva_set', label: 'Viva prompts', note: '2 oral prompts per topic' },
  { id: 'osce_station', label: 'OSCE stations', note: 'Instructions + checklist' },
  { id: 'topic_summary', label: 'Topic summaries', note: 'Objectives + key points' },
  { id: 'case_report', label: 'Case reports', note: 'Structured synthetic vignette' },
  { id: 'case_debrief', label: 'Case debriefs', note: 'Pitfalls + reflection prompts' },
  { id: 'simulation_brief', label: 'Simulation briefs', note: 'Scenario outline for educator review' },
  { id: 'on_call_scenario', label: 'On-call scenarios', note: 'Prioritisation and escalation practice' },
  { id: 'handover_template', label: 'Handover exercises', note: 'SBAR-style practice from case data' },
];

type Artifact = { id: string; title: string; kind: string; workspace: string; status: string; body?: Record<string, unknown>; source_refs?: Array<{ title: string; source_id?: string }> };

export default function ContentFactoryPage() {
  const [catalog, setCatalog] = useState<ContentFactoryCatalog | null>(null);
  const [curricula, setCurricula] = useState<CurriculumProjection | null>(null);
  const [curriculumTitle, setCurriculumTitle] = useState('Acute Care Foundations Pathway');
  const [sequentialPath, setSequentialPath] = useState(true);
  const [selectedUnits, setSelectedUnits] = useState<string[]>([]);
  const [selectedKinds, setSelectedKinds] = useState<string[]>(['question_set', 'viva_set', 'osce_station', 'topic_summary']);
  const [seed, setSeed] = useState(2026);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [reviewerToken, setReviewerToken] = useState('');
  const [destination, setDestination] = useState('questions');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    const [nextCatalog, recent, nextCurricula] = await Promise.all([api.contentFactoryCatalog(), api.generationArtifacts(), api.curricula()]);
    setCatalog(nextCatalog); setCurricula(nextCurricula);
    setArtifacts((recent.items as Artifact[]).filter((item) => item.body?.generation_mode === 'deterministic_template_composer'));
    if (!selectedUnits.length) setSelectedUnits(nextCatalog.units.map((unit) => unit.unit_id));
  }
  useEffect(() => { void load().catch((err: unknown) => setError(err instanceof Error ? err.message : 'Content factory could not load.')); }, []);

  function toggleUnit(id: string) { setSelectedUnits((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]); }
  function toggleKind(id: string) { setSelectedKinds((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]); }

  async function generate() {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.generateContentBatch({ unit_ids: selectedUnits, kinds: selectedKinds, seed });
      setMessage(`Created or reused ${result.draft_count} deterministic drafts (${result.requested} requested). All remain unapproved.`);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Draft generation failed.'); }
    finally { setBusy(false); }
  }

  async function composePathway() {
    if (!selectedUnits.length) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const prerequisites: Record<string, string[]> = {};
      if (sequentialPath) selectedUnits.forEach((unitId, index) => { prerequisites[unitId] = index > 0 ? [selectedUnits[index - 1]] : []; });
      const result = await api.composeCurriculum({ title: curriculumTitle, description: 'Composed from versioned HSPTL learning units; unlock rules are evaluated by the PROforma predicate runtime.', unit_ids: selectedUnits, prerequisites });
      setMessage(`Curriculum draft created with ${result.curriculum.stages.length} stages. Reviewer activation is required before learner use.`);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Curriculum composition failed.'); }
    finally { setBusy(false); }
  }

  async function activatePathway(curriculumId: string) {
    if (!reviewerToken) return;
    setBusy(true); setError('');
    try { await api.activateCurriculum(curriculumId, reviewerToken); setMessage('Curriculum activated. Its version and approval are recorded in the canonical event history.'); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Curriculum activation failed.'); }
    finally { setBusy(false); }
  }

  async function review(decision: 'approved' | 'needs_revision' | 'rejected') {
    if (!selectedArtifact || !reviewerToken) return;
    setBusy(true); setError('');
    try {
      const updated = await api.reviewGeneratedArtifact(selectedArtifact.id, reviewerToken, decision) as Artifact;
      setSelectedArtifact(updated); setMessage(`Draft marked ${decision}.`); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Review could not be saved.'); }
    finally { setBusy(false); }
  }

  async function distribute() {
    if (!selectedArtifact) return;
    setBusy(true); setError('');
    try {
      await api.distributeArtifact(selectedArtifact.id, selectedArtifact.workspace, destination);
      setMessage(`Approved artifact routed to ${selectedArtifact.workspace} / ${destination}.`); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Distribution failed.'); }
    finally { setBusy(false); }
  }

  const draftCount = artifacts.filter((item) => item.status === 'draft' || item.status === 'needs_revision').length;
  const approvedCount = artifacts.filter((item) => item.status === 'approved').length;
  return <div className="hx-page-grid">
    <section className="hx-page-heading"><div><div className="hx-eyebrow">AUTHORING · DETERMINISTIC CONTENT OPERATIONS</div><h1>Content factory</h1><p>Build practice materials from the bundled starter curriculum. No model or API key required.</p></div><div className="hx-heading-badge"><Icon name="sparkles" size={18}/> Model-free generation</div></section>
    {(error || message) && <div role={error ? 'alert' : 'status'} className={error ? 'status-error' : 'status-success'}>{error || message}</div>}
    <section className="hx-library-summary"><div><strong>{catalog?.unit_count ?? '—'}</strong><span>Source learning units</span></div><div><strong>{catalog?.question_count ?? '—'}</strong><span>Authored retrieval items</span></div><div><strong>{draftCount}</strong><span>Pending drafts</span></div><div><strong>{approvedCount}</strong><span>Approved artifacts</span></div></section>

    <section className="hx-factory-grid">
      <div className="hx-content-block hx-generator-panel">
        <div className="hx-block-heading"><div><span className="hx-eyebrow">01 · SELECT INPUTS</span><h2>Build a content batch</h2><p>Select topics and learning formats, then generate drafts.</p></div><Icon name="layers" size={22}/></div>
        <div className="hx-choice-heading"><b>Curriculum units</b><button className="hx-text-action" onClick={() => setSelectedUnits(catalog?.units.map((unit) => unit.unit_id) || [])}>Select all</button></div>
        <div className="hx-choice-grid">{catalog?.units.map((unit) => <label key={unit.unit_id} className={`hx-choice-card ${selectedUnits.includes(unit.unit_id) ? 'is-selected' : ''}`}><input type="checkbox" checked={selectedUnits.includes(unit.unit_id)} onChange={() => toggleUnit(unit.unit_id)}/><span><b>{unit.title}</b><small>{unit.specialty} · {unit.minutes} min</small></span></label>)}</div>
        <div className="hx-choice-heading"><b>Output types</b><button className="hx-text-action" onClick={() => setSelectedKinds(OUTPUTS.map((item) => item.id))}>Select all</button></div>
        <div className="hx-output-grid">{OUTPUTS.map((item) => <label key={item.id} className={`hx-output-choice ${selectedKinds.includes(item.id) ? 'is-selected' : ''}`}><input type="checkbox" checked={selectedKinds.includes(item.id)} onChange={() => toggleKind(item.id)}/><span><b>{item.label}</b><small>{item.note}</small></span></label>)}</div>
        <div className="hx-generation-controls"><label>Deterministic seed<input type="number" min="0" max="2147483647" value={seed} onChange={(event) => setSeed(Number(event.target.value))}/></label><div><span>{selectedUnits.length * selectedKinds.length} draft outputs planned</span><button className="hx-button-primary" disabled={busy || !selectedUnits.length || !selectedKinds.length} onClick={() => void generate()}>{busy ? 'Generating…' : 'Generate selected batch'} <Icon name="arrow" size={15}/></button></div></div>
        <p className="hx-governance-note"><Icon name="shield" size={16}/> Generation is deterministic and model-free. It may reorder question options using the seed; clinical facts do not change. Nothing is approved or published automatically.</p>
      </div>

      <aside className="hx-factory-side">
        <div className="hx-content-block hx-factory-guide"><span className="hx-eyebrow">HOW TO GENERATE</span><h3>Three steps</h3><ol><li><b>Choose topics</b><span>Select one or more units from the starter pack.</span></li><li><b>Choose formats</b><span>Questions, viva, OSCE, summaries or case materials.</span></li><li><b>Generate drafts</b><span>Review, approve and route them to a workspace.</span></li></ol><p className="hx-muted">Local deterministic generation · no API key · educator approval required</p></div>
      </aside>
    </section>

    <section className="hx-content-block"><div className="hx-block-heading"><div><span className="hx-eyebrow">03 · CURRICULUM COMPOSER</span><h2>Compose a learning pathway</h2><p>Sequence existing versioned units, map objectives and create PROforma unlock predicates. Composition creates a draft; an authenticated reviewer must activate it.</p></div><Icon name="workflow" size={22}/></div><div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end"><label className="block text-sm font-semibold">Pathway title<input className="mt-1 w-full rounded-lg border border-hsptl-surface-border bg-transparent p-2 dark:border-hsptl-dark-border" value={curriculumTitle} onChange={(event) => setCurriculumTitle(event.target.value)} maxLength={180}/></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sequentialPath} onChange={(event) => setSequentialPath(event.target.checked)}/> Require previous unit completion</label></div><div className="mt-3 flex flex-wrap items-center justify-between gap-3"><span className="muted text-xs">{selectedUnits.length} selected units · {sequentialPath ? 'sequential prerequisites' : 'independent stage eligibility'}</span><button className="hx-button-primary" disabled={busy || !selectedUnits.length || curriculumTitle.trim().length < 3} onClick={() => void composePathway()}>Compose pathway draft <Icon name="arrow" size={15}/></button></div>{curricula?.active && <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900 dark:bg-emerald-950/30"><div className="eyebrow">ACTIVE CURRICULUM · VERSION {curricula.active.version}</div><b>{curricula.active.title}</b><p className="muted mt-1 text-xs">{curricula.active.unit_ids.length} stages · {curricula.active.content_digest.slice(0, 16)}…</p></div>}{curricula?.drafts.filter((item) => item.status === 'draft').map((draft) => <div key={draft.curriculum_id} className="mt-3 rounded-xl border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div className="flex flex-wrap items-start justify-between gap-3"><div><span className="hx-status-draft">DRAFT · VERSION {draft.version}</span><h3 className="mt-1 font-bold">{draft.title}</h3><p className="muted mt-1 text-xs">{draft.stages.length} stages · {draft.content_digest.slice(0, 16)}…</p></div><button className="hx-button-secondary" disabled={busy || !reviewerToken} onClick={() => void activatePathway(draft.curriculum_id)}>Reviewer: activate</button></div><ol className="mt-3 grid gap-2 sm:grid-cols-2">{draft.stages.map((stage) => <li key={String(stage.unit_id)} className="rounded-lg bg-slate-50 p-2 text-sm dark:bg-slate-800"><b>{stage.position}. {stage.title}</b><p className="muted mt-1 text-xs">{Array.isArray(stage.prerequisites) && stage.prerequisites.length ? `Unlocks after: ${stage.prerequisites.join(', ')}` : 'No prerequisite'}</p></li>)}</ol></div>)}<p className="muted mt-3 text-xs">Activation uses the configured reviewer credential. If reviewer authentication is not configured, activation remains blocked rather than silently publishing the curriculum.</p></section>

    <section className="hx-content-block"><div className="hx-block-heading"><div><span className="hx-eyebrow">04 · REVIEW QUEUE</span><h2>Generated artifacts</h2><p>Inspect drafts, request changes or approve and route them.</p></div><button className="hx-button-secondary" onClick={() => void load()}><Icon name="refresh" size={15}/> Refresh</button></div>
      <div className="hx-artifact-layout"><div className="hx-artifact-list">{artifacts.map((item) => <button key={item.id} className={`hx-artifact-row ${selectedArtifact?.id === item.id ? 'is-selected' : ''}`} onClick={() => { setSelectedArtifact(item); setDestination(item.kind === 'question_set' ? 'questions' : item.kind === 'viva_set' ? 'viva' : item.kind === 'osce_station' ? 'osce' : item.kind === 'case_debrief' ? 'debriefs' : item.kind === 'case_report' ? 'reports' : 'summaries'); }}><span><b>{item.title}</b><small>{item.kind.replaceAll('_', ' ')} · {item.workspace}</small></span><em className={`hx-artifact-status status-${item.status}`}>{item.status.replaceAll('_', ' ')}</em></button>)}{!artifacts.length && <p className="hx-muted">No generated drafts yet. Select topics above and generate your first batch.</p>}</div>
      {selectedArtifact ? <div className="hx-artifact-detail"><div className="hx-artifact-title"><div><small>{selectedArtifact.kind} · {selectedArtifact.workspace}</small><h3>{selectedArtifact.title}</h3></div><span className={`hx-artifact-status status-${selectedArtifact.status}`}>{selectedArtifact.status}</span></div><p className="hx-muted">Source references: {Array.isArray(selectedArtifact.source_refs) && selectedArtifact.source_refs.length ? selectedArtifact.source_refs.map((ref) => ref.title).join(' · ') : 'Authored from the versioned HSPTL content pack; inspect artifact metadata for pack and source provenance.'}</p><pre>{JSON.stringify(selectedArtifact.body, null, 2)}</pre>
        {(selectedArtifact.status === 'draft' || selectedArtifact.status === 'needs_revision') && <div className="hx-review-controls"><label>Reviewer token<input type="password" value={reviewerToken} onChange={(event) => setReviewerToken(event.target.value)} placeholder="Configured reviewer credential"/></label><div><button className="hx-button-primary" disabled={busy || !reviewerToken} onClick={() => void review('approved')}>Approve</button><button className="hx-button-secondary" disabled={busy || !reviewerToken} onClick={() => void review('needs_revision')}>Request changes</button><button className="hx-button-secondary" disabled={busy || !reviewerToken} onClick={() => void review('rejected')}>Reject</button></div></div>}
        {selectedArtifact.status === 'approved' && <div className="hx-review-controls"><label>Destination section<input value={destination} onChange={(event) => setDestination(event.target.value)}/></label><button className="hx-button-primary" disabled={busy} onClick={() => void distribute()}>Distribute approved artifact</button></div>}
      </div> : <div className="hx-empty-state">Select an artifact to inspect its contents and governance status.</div>}</div>
    </section>

    <ScenarioAuthoringPanel />

    <details className="hx-source-generator"><summary>Advanced: extractive generation from your own evidence documents</summary><p>Use the original UCKS source-span generator when you have ingested material with documented rights and review status.</p><SourceContentStudio/></details>
  </div>;
}
