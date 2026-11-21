import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { EngineMatrix, ExternalAutomationStatus, LocalFolderSummary, NextIncrementsOverview, SourceCatalogueEntry, LearnerFeedbackItem, WorkspaceEngineContracts } from '../lib/api';
import { Icon } from '../components/Icon';
import ArtifactValidationOperations from '../components/ArtifactValidationOperations';

type Feedback = { kind: 'success' | 'error' | 'info'; text: string } | null;

const LABEL_ORDER = ['GENERATED CONTENT', 'IMPORTED CONTENT', 'SYNTHETIC CONTENT', 'DERIVED CONTENT'] as const;

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return <div className="metric-card">
    <div className="text-[10px] font-bold uppercase tracking-[.14em] text-[var(--text-muted)]">{label}</div>
    <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
    {hint && <div className="muted mt-1 text-xs">{hint}</div>}
  </div>;
}

/**
 * Operations surface for content lineage, external-source automation, the
 * rights-aware source catalogue, local folder sources, engine coverage and the
 * pearls factory. External refresh only queues metadata harvesting; review and
 * rights decisions remain explicit human actions.
 */
export default function ContentOperationsPage() {
  const [overview, setOverview] = useState<NextIncrementsOverview | null>(null);
  const [catalogue, setCatalogue] = useState<SourceCatalogueEntry[]>([]);
  const [matrix, setMatrix] = useState<EngineMatrix | null>(null);
  const [workspaceContracts, setWorkspaceContracts] = useState<WorkspaceEngineContracts | null>(null);
  const [folders, setFolders] = useState<LocalFolderSummary | null>(null);
  const [externalAutomation, setExternalAutomation] = useState<ExternalAutomationStatus | null>(null);
  const [externalBusy, setExternalBusy] = useState(false);
  const [pearlTopic, setPearlTopic] = useState('');
  const [pearl, setPearl] = useState<Record<string, unknown> | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const [catalogueQuery, setCatalogueQuery] = useState('');
  const [catalogueFamily, setCatalogueFamily] = useState('All families');
  const [reviewerToken, setReviewerToken] = useState('');
  const [reviewQueueStatus, setReviewQueueStatus] = useState('pending');
  const [learnerReports, setLearnerReports] = useState<LearnerFeedbackItem[]>([]);
  const [reviewQueueError, setReviewQueueError] = useState('');
  const [reviewActionBusy, setReviewActionBusy] = useState('');

  const load = useCallback(async () => {
    try {
      const [o, c, m, w, f, external] = await Promise.all([
        api.nextIncrementsOverview(),
        api.sourceCatalogue(),
        api.engineMatrix(),
        api.workspaceEngineContracts(),
        api.localFolders(),
        api.externalAutomationStatus(),
      ]);
      setOverview(o);
      setCatalogue(c.items);
      setMatrix(m);
      setWorkspaceContracts(w);
      setFolders(f.summary);
      setExternalAutomation(external);
    } catch (err) {
      setFeedback({ kind: 'error', text: err instanceof Error ? err.message : 'Could not load operations data.' });
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function refreshExternalSources() {
    setExternalBusy(true);
    setFeedback(null);
    try {
      const result = await api.refreshExternalSources();
      setFeedback({ kind: 'success', text: result.message });
      const status = await api.externalAutomationStatus();
      setExternalAutomation(status);
    } catch (err) {
      setFeedback({ kind: 'error', text: err instanceof Error ? err.message : 'Could not queue external sources.' });
    } finally {
      setExternalBusy(false);
    }
  }

  const sourceFamilies = useMemo(() => ['All families', ...Array.from(new Set(catalogue.map((item) => item.family))).sort()], [catalogue]);
  const visibleSources = useMemo(() => catalogue.filter((entry) => {
    const text = `${entry.name} ${entry.family} ${entry.content_value || ''} ${(entry.coverage || []).join(' ')} ${entry.note}`.toLowerCase();
    return (catalogueFamily === 'All families' || entry.family === catalogueFamily) && text.includes(catalogueQuery.toLowerCase());
  }), [catalogue, catalogueFamily, catalogueQuery]);

  async function loadLearnerReports() {
    setReviewQueueError('');
    try { const result = await api.learnerFeedbackQueue(reviewerToken.trim(), reviewQueueStatus); setLearnerReports(result.items); }
    catch (err) { setReviewQueueError(err instanceof Error ? err.message : 'Could not load learner feedback queue.'); }
  }

  async function triageLearnerReport(report: LearnerFeedbackItem, status: 'acknowledged'|'source_review_required'|'artifact_revision_required'|'closed') {
    const resolution = window.prompt('Add an audit note explaining this triage action:');
    if (!resolution || resolution.trim().length < 3) return;
    setReviewActionBusy(report.feedback_id); setReviewQueueError('');
    try { await api.resolveLearnerFeedback(report.feedback_id, reviewerToken.trim(), status, resolution.trim()); await loadLearnerReports(); }
    catch (err) { setReviewQueueError(err instanceof Error ? err.message : 'Could not triage learner feedback.'); }
    finally { setReviewActionBusy(''); }
  }

  async function composePearl() {
    if (pearlTopic.trim().length < 2) return;
    setBusy(true);
    setFeedback(null);
    try {
      const result = await api.pearlsFactoryCompose({ topic: pearlTopic.trim() });
      setPearl(result);
      if (result.state === 'insufficient_evidence') {
        setFeedback({ kind: 'info', text: String(result.message ?? 'No source-supported pearl could be composed.') });
      } else {
        setFeedback({ kind: 'success', text: 'Pearl composed from cited source spans.' });
      }
    } catch (err) {
      setFeedback({ kind: 'error', text: err instanceof Error ? err.message : 'Could not compose a pearl.' });
    } finally {
      setBusy(false);
    }
  }

  const labels = overview?.labels;

  return <div className="space-y-6">
    <header>
      <div className="eyebrow">BUILD · CONTENT OPERATIONS</div>
      <h1 className="page-title mt-2">Content operations</h1>
      <p className="muted mt-2 max-w-3xl text-sm leading-relaxed">
        Lineage, source rights, local folders, engine coverage and the pearls factory in one place.
        These views describe where content came from. They are not clinical approvals.
      </p>
    </header>

    {feedback && <div role={feedback.kind === 'error' ? 'alert' : 'status'}
      className={feedback.kind === 'error' ? 'status-error' : feedback.kind === 'success' ? 'status-success' : 'status-info'}>
      {feedback.text}
    </div>}

    <section>
      <h2 className="text-lg font-bold">Content labels</h2>
      <p className="muted mt-1 text-sm">
        Every item carries exactly one label. A label is independent of rights, clinical review,
        source validity and publication status.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {LABEL_ORDER.map(label => <div key={label} className="hsptl-card p-4">
          <div className="text-[10px] font-bold uppercase tracking-[.14em] text-hsptl-teal">{label}</div>
          <div className="mt-2 text-2xl font-bold tabular-nums">{labels?.counts?.[label] ?? 0}</div>
        </div>)}
      </div>
      {labels && labels.derived_without_lineage > 0 && <div className="status-error mt-3">
        {labels.derived_without_lineage} derived item(s) have no lineage. This is an integrity fault.
      </div>}
      {labels && labels.derived_without_lineage === 0 && <p className="muted mt-2 text-xs">
        Lineage integrity: every derived item resolves to at least one parent.
      </p>}
    </section>

    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Registered sources" value={overview?.source_registry.registered ?? 0}
        hint={`${overview?.source_registry.reviewed ?? 0} rights-reviewed`} />
      <Stat label="Local roots" value={folders?.roots ?? 0}
        hint={`${folders?.scheduled_roots ?? 0} scheduled`} />
      <Stat label="Lottery cases" value={overview?.lottery.eligible_cases ?? 0}
        hint={`${overview?.lottery.blocked_cases ?? 0} blocked`} />
      <Stat label="Engine bindings" value={overview?.engines.bindings ?? 0}
        hint={overview?.engines.all_integrated ? 'all seven engines integrated' : 'incomplete'} />
    </section>

    <section className="hsptl-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-lg font-bold">Seven-workspace integration</h2><p className="muted mt-1 text-sm">Product workspaces delegate clinical and governance operations to the shared seven-engine core. Visual skins remain presentation-only.</p></div>
        <span className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs">{workspaceContracts?.workspace_count ?? 0}/7 workspaces</span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {(workspaceContracts?.workspaces ?? []).map((workspace) => <div key={workspace} className="rounded-lg border border-[var(--border-subtle)] p-3">
          <div className="flex items-center justify-between gap-2"><b className="text-sm">{workspace.replaceAll('_', ' ')}</b><span className="text-xs text-hsptl-teal">{workspaceContracts?.matrix[workspace]?.length ?? 0} bindings</span></div>
          <div className="muted mt-1 text-[11px]">{Array.from(new Set((workspaceContracts?.matrix[workspace] ?? []).map((item) => item.engine))).join(' · ')}</div>
        </div>)}
      </div>
      {workspaceContracts && (!workspaceContracts.all_workspaces_integrated || !workspaceContracts.all_seven_engines_covered) && <div role="alert" className="status-error mt-3">Workspace integration contract is incomplete. Review the engine binding matrix.</div>}
    </section>

    <section className="hsptl-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold"><Icon name="shield"/> Expanded clinical knowledge source directory</h2><p className="muted mt-1 max-w-3xl text-sm">A discovery map of guideline publishers, evidence libraries, registries, public-health datasets, terminology systems and clinical references. A directory entry is not an integration claim or a licence grant; only configured connectors ingest automatically.</p></div><span className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs">{catalogue.length} sources · {sourceFamilies.length - 1} families</span></div>
      <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_240px]"><input className="form-field" placeholder="Search a source, specialty, dataset or topic…" value={catalogueQuery} onChange={(event) => setCatalogueQuery(event.target.value)} aria-label="Search source directory"/><select className="form-field" value={catalogueFamily} onChange={(event) => setCatalogueFamily(event.target.value)} aria-label="Filter source family">{sourceFamilies.map((family) => <option key={family}>{family}</option>)}</select></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleSources.map((entry) => <article key={entry.key} className="rounded-xl border border-[var(--border-subtle)] p-4">
          <div className="flex items-start justify-between gap-2"><div><span className="text-[10px] font-bold uppercase tracking-[.12em] text-hsptl-teal">{entry.family.replaceAll('_', ' ')}</span><h3 className="mt-1 font-bold">{entry.name}</h3></div><span className="rounded-full bg-[var(--surface-muted)] px-2 py-1 text-[10px]">Priority {entry.priority}</span></div>
          <p className="muted mt-2 text-xs leading-relaxed">{entry.content_value || entry.note}</p>
          {!!entry.coverage?.length && <div className="mt-3 flex flex-wrap gap-1">{entry.coverage.slice(0, 5).map((tag) => <span key={tag} className="rounded-full bg-hsptl-teal-light px-2 py-1 text-[10px] font-semibold text-hsptl-teal-dark">{tag}</span>)}</div>}
          <div className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-[11px]"><div><b>Access:</b> {entry.default_access.replaceAll('_', ' ')}</div><div><b>Reuse:</b> {entry.default_reuse.replaceAll('_', ' ')} · <b>Adaptation:</b> {entry.default_adaptation.replaceAll('_', ' ')}</div><div className="muted mt-1"><b>Route:</b> {(entry.integration || 'manual review').replaceAll('_', ' ')}</div></div>
          <p className="muted mt-2 text-[11px]">{entry.note}</p>
          {entry.url && <a href={entry.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-xs font-semibold text-hsptl-indigo underline dark:text-indigo-200">Open source website ↗</a>}
        </article>)}
      </div>
      {!visibleSources.length && <p className="muted py-8 text-center text-sm">No sources match this filter.</p>}
      <p className="muted mt-4 text-xs">The rights defaults above are conservative catalogue prompts, not legal determinations. Verify the exact document, version, jurisdiction, licence and embedded third-party material before reuse or adaptation.</p>
    </section>

    <section className="hsptl-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold"><Icon name="file"/> Learner post-use review queue</h2><p className="muted mt-1 max-w-3xl text-sm">Learners can report quality issues only after opening a published artefact. Triage records an audit decision; it does not change source permissions, clinical sign-off or publication status.</p></div></div>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_220px_auto]"><input className="form-field" type="password" autoComplete="off" placeholder="Reviewer token (configured by administrator)" value={reviewerToken} onChange={(event) => setReviewerToken(event.target.value)}/><select className="form-field" value={reviewQueueStatus} onChange={(event) => setReviewQueueStatus(event.target.value)} aria-label="Feedback queue status"><option value="pending">Pending</option><option value="source_review_required">Source review required</option><option value="artifact_revision_required">Artefact revision required</option><option value="acknowledged">Acknowledged</option><option value="closed">Closed</option><option value="all">All reports</option></select><button className="secondary-button" disabled={!reviewerToken.trim()} onClick={() => void loadLearnerReports()}>Load reports</button></div>
      {reviewQueueError && <p role="alert" className="status-error mt-3">{reviewQueueError}</p>}
      <div className="mt-3 space-y-3">{learnerReports.map((report) => <article key={report.feedback_id} className="rounded-xl border border-[var(--border-subtle)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><div><b>{report.artifact_title}</b><div className="muted text-xs">{report.workspace} · {report.kind} · {report.created_at}</div><div className="muted mt-1 text-[10px]">{report.identity_verified ? 'Verified account' : 'Guest / unverified'} · {report.learner_level || 'unspecified'} · {report.account_role || 'guest'} · {report.severity || 'routine'} severity</div></div><span className="rounded-full border px-2 py-1 text-[10px]">{report.status} · {report.rating ? `${report.rating}/5 usefulness` : 'No overall rating'}</span></div>
        {(report.educational_rating || report.clinical_rating || report.source_rating || report.assessment_rating) && <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] sm:grid-cols-4">{[['Education',report.educational_rating],['Clinical',report.clinical_rating],['Sources',report.source_rating],['Assessment',report.assessment_rating]].map(([label,value]) => <div key={String(label)} className="rounded bg-[var(--surface-muted)] p-2"><span className="muted">{label}</span><b className="ml-1">{value ? `${value}/5` : '—'}</b></div>)}</div>}
        <div className="mt-2 flex flex-wrap gap-1">{report.categories.map((category) => <span key={category} className="rounded-full bg-hsptl-surface px-2 py-1 text-[10px] dark:bg-hsptl-dark-surface">{category.replaceAll('_', ' ')}</span>)}</div>
        {report.comment && <p className="mt-2 whitespace-pre-wrap text-sm">{report.comment}</p>}
        {!!report.source_document_ids.length && <p className="muted mt-2 text-xs">Source records: {report.source_document_ids.join(', ')}</p>}
        <div className="mt-3 flex flex-wrap gap-2">{([['acknowledged','Acknowledge'],['source_review_required','Review source'],['artifact_revision_required','Revise artefact'],['closed','Close']] as const).map(([status,label]) => <button key={status} className="secondary-button text-xs" disabled={reviewActionBusy === report.feedback_id} onClick={() => void triageLearnerReport(report,status)}>{label}</button>)}</div>
      </article>)}{reviewerToken && !reviewQueueError && learnerReports.length === 0 && <p className="muted text-xs">No reports loaded, or there are no learner reports in this status.</p>}</div>
    </section>
    <ArtifactValidationOperations />

    <section className="hsptl-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold"><Icon name="refresh"/> Automated external sources</h2>
          <p className="muted mt-1 max-w-3xl text-sm">Public, API-key-free connectors run at startup and daily. Records import automatically without per-record human approval, then pass machine integrity and provenance checks. Machine-screened does not mean clinically validated; reuse is permitted only when the specific item licence allows it.</p>
        </div>
        <button type="button" className="secondary-button" disabled={externalBusy} onClick={() => void refreshExternalSources()}>
          {externalBusy ? 'Queueing…' : 'Refresh external sources'}
        </button>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Provider profiles" value={externalAutomation?.profiles?.length ?? 0} hint="No API keys required" />
        <Stat label="Scheduler status" value={externalAutomation?.status ?? 'Not started'} hint={externalAutomation?.last_completed ? `Last run ${externalAutomation.last_completed}` : 'Waiting for first run'} />
        <Stat label="Automatic import" value={externalAutomation?.automatic_import_enabled === false ? "Off" : "On"} hint="No per-record approval; machine-screened" />
        <Stat label="Clinical validation" value={externalAutomation?.clinical_validity_assessed_automatically ? "On" : "Off"} hint="Never inferred by the importer" />
        <Stat label="Automatic publication" value={externalAutomation?.auto_publish ? "On" : "Off"} hint="Review-gated distribution" />
      </div>
      {!!externalAutomation?.profiles?.length && <div className="mt-3 divide-y divide-[var(--border-subtle)] rounded-lg border border-[var(--border-subtle)]">
        {externalAutomation.profiles.map(profile => <div key={profile.source_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs">
          <div><b>{profile.name}</b><div className="muted mt-1">{profile.connector.replaceAll('_', ' ')} · {profile.schedule?.interval_minutes ?? 0} minute interval</div></div>
          <span className="muted">{profile.enabled && profile.schedule?.enabled ? 'Scheduled' : 'Paused'}</span>
        </div>)}
      </div>}
      {externalAutomation?.last_error && <p className="status-error mt-3 text-xs">Last source refresh warning: {externalAutomation.last_error}</p>}
      <p className="muted mt-3 text-xs">Source rights are not inferred from public availability. Europe PMC full text is fetched automatically only when the item declares an allow-listed CC0, CC-BY or CC-BY-SA licence; other providers remain metadata/abstract/link imports. These licence checks do not establish clinical validity.</p>
    </section>

    <section className="hsptl-card p-5">
      <h2 className="text-lg font-bold"><Icon name="database"/> Local folder sources</h2>
      <p className="muted mt-1 text-sm">
        Folders are added through local administration only. Scanning is read-only and never
        follows symlinks, junctions or hardlinks, and never opens active content.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Scans" value={folders?.scans ?? 0} />
        <Stat label="Quarantined" value={folders?.quarantined ?? 0} hint="identifiers detected" />
        <Stat label="Accepted" value={folders?.files_by_verdict?.accepted ?? 0} />
        <Stat label="Refused" value={folders?.files_by_verdict?.refused ?? 0} hint="unsafe or unsupported" />
      </div>
      {folders && <ul className="muted mt-3 space-y-1 text-xs">
        <li>Read-only: {String(folders.safety.read_only)}</li>
        <li>Follows symlinks: {String(folders.safety.follows_symlinks)}</li>
        <li>Opens active content: {String(folders.safety.opens_active_content)}</li>
        <li>Arbitrary paths over HTTP: {String(folders.safety.arbitrary_paths_over_http)}</li>
      </ul>}
    </section>

    <section className="hsptl-card p-5">
      <h2 className="text-lg font-bold"><Icon name="activity"/> Engine coverage across workspaces</h2>
      <p className="muted mt-1 text-sm">
        Each skin contributes presentation only. Every operation below is executed by a shared engine.
      </p>
      {matrix && <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-[10px] uppercase tracking-[.12em] text-[var(--text-muted)]">
            <tr><th className="py-2">Engine</th><th>Workspaces</th></tr>
          </thead>
          <tbody>
            {matrix.engines.map(engine => <tr key={engine} className="border-t border-[var(--border-subtle)]">
              <td className="py-2 font-bold">{engine}</td>
              <td className="py-2 text-xs">{matrix.engine_coverage[engine]?.join(', ') || '—'}</td>
            </tr>)}
          </tbody>
        </table>
      </div>}
      {matrix && <p className="muted mt-2 text-xs">
        {matrix.binding_count} bindings · all engines integrated: {String(matrix.all_engines_integrated)} ·
        all skins integrated: {String(matrix.all_skins_integrated)}
      </p>}
    </section>

    <section className="hsptl-card p-5">
      <h2 className="text-lg font-bold"><Icon name="pearls"/> Pearls factory</h2>
      <p className="muted mt-1 text-sm">
        Deterministic, source-linked composition. Every point carries a citation; a topic with no
        rights-cleared source yields no pearl rather than an invented one.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <input className="form-field min-w-[220px] flex-1" value={pearlTopic}
          onChange={event => setPearlTopic(event.target.value)}
          placeholder="Clinical topic, e.g. sepsis" aria-label="Pearl topic"/>
        <button type="button" className="primary-button" disabled={busy || pearlTopic.trim().length < 2}
          onClick={() => void composePearl()}>
          {busy ? 'Composing…' : 'Compose pearl'}
        </button>
      </div>
      {pearl && pearl.state === 'composed' && <div className="mt-4">
        <h3 className="font-bold">{String(pearl.title)}</h3>
        <p className="muted text-xs">{String(pearl.label)} · {String(pearl.template_version)}</p>
        <div className="mt-3 space-y-3">
          {Object.entries((pearl.body as Record<string, unknown>)?.sections as Record<string, Array<Record<string, unknown>>> ?? {})
            .filter(([, points]) => points.length)
            .map(([section, points]) => <div key={section}>
              <h4 className="text-sm font-bold capitalize">{section.replace(/_/g, ' ')}</h4>
              <ul className="mt-1 space-y-1 text-sm">
                {points.map((point, index) => <li key={index}>
                  {String(point.text)}
                  <span className="muted text-xs"> — {String((point.citation as Record<string, unknown>)?.title ?? 'source')}</span>
                </li>)}
              </ul>
            </div>)}
        </div>
      </div>}
    </section>

    <section className="hsptl-card p-5">
      <h2 className="text-lg font-bold">Integrity notes</h2>
      <ul className="muted mt-2 space-y-1 text-sm">
        {(overview?.integrity_notes ?? []).map((note, index) => <li key={index}>• {note}</li>)}
      </ul>
    </section>
  </div>;
}
