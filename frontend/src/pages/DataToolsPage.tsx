import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { HarvestedCase, HSPTLJob } from '../lib/api';
import { Icon } from '../components/Icon';

const FHIR_DEFAULT = 'C:\\Users\\YOUSE\\YouseCodes\\Synthea\\output\\fhir';
const SPECIALTY_OPTIONS = [
  ['ophthalmology','Ophthalmology'],['cardiology','Cardiology'],['neurology','Neurology'],['oncology','Oncology'],
  ['infectious','Infectious disease'],['gastro','Gastroenterology'],['pulmonology','Pulmonology'],['nephro-urology','Nephrology / Urology'],
  ['endocrine','Endocrinology'],['hematology','Hematology'],['rheum-immuno','Rheumatology / Immunology'],['dermatology','Dermatology'],
  ['ent','ENT'],['psychiatry','Psychiatry'],['orthopedics','Orthopedics'],['obgyn','Obstetrics / Gynecology'],['pediatrics','Pediatrics'],
  ['genetics','Genetics'],['emergency-trauma','Emergency / Trauma'],['dental-oral','Dental / Oral'],
] as const;

function JobCard({ job, onRun, onCancel }: { job: HSPTLJob; onRun: (id: string) => void; onCancel: (id: string) => void }) {
  const title = job.kind === 'mednotegen_generate' ? 'MedNoteGen · Synthea note generation' : job.kind === 'specialty_harvest' ? 'Clinical Knowledge Harvester · Evidence discovery' : job.kind;
  const isReady = job.status === 'queued' || job.status === 'failed';
  return <div className="metric-card flex flex-wrap items-center justify-between gap-3">
    <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-bold">{title}</span><span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${job.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : job.status === 'failed' ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-700'}`}>{job.status}</span></div>
      <p className="muted mt-1 text-xs">{String(job.checkpoint?.phase || 'Waiting to run')}{job.checkpoint?.last_message ? ` · ${String(job.checkpoint.last_message)}` : ''}</p>
      {job.result && Object.keys(job.result).length > 0 && <p className="muted mt-1 text-xs">{job.kind === 'mednotegen_generate' ? `${job.result.clinic_notes ?? 0} encounter notes · ${job.result.draft_pearl_seeds ?? 0} draft Pearls` : `${job.result.article_count ?? 0} full-text articles · ${job.result.metadata_only_count ?? 0} metadata/abstract records`}</p>}
      {job.error_code && <p className="mt-1 text-xs text-rose-600">{job.error_code}</p>}
    </div>
    {isReady && <button className="secondary-button" onClick={() => onRun(job.id)}><Icon name="play" size={15}/> Run now</button>}
    {job.status === 'running' && <button className="secondary-button" onClick={() => onCancel(job.id)}><Icon name="x" size={15}/> Cancel</button>}
  </div>;
}

export default function DataToolsPage() {
  const [fhirDir, setFhirDir] = useState(FHIR_DEFAULT);
  const [selected, setSelected] = useState<string[]>(['cardiology']);
  const [maxCases, setMaxCases] = useState(20);
  const [knowledgeProfile, setKnowledgeProfile] = useState('case_reports');
  const [providerHealth, setProviderHealth] = useState<any[]>([]);
  const [providerHistory, setProviderHistory] = useState<any[]>([]);
  const [governance, setGovernance] = useState<any>(null);
  const [reviewerStatus, setReviewerStatus] = useState<{configured:boolean;reviewer_id:string}>({configured:false,reviewer_id:''});
  const [reviewerToken, setReviewerToken] = useState('');
  const [governanceDocument, setGovernanceDocument] = useState('');
  const [rightsDecision, setRightsDecision] = useState('needs_clarification');
  const [rightsLicence, setRightsLicence] = useState('');
  const [rightsScope, setRightsScope] = useState('metadata_only');
  const [appraisalDesign, setAppraisalDesign] = useState('not_reported');
  const [appraisalBias, setAppraisalBias] = useState('not_assessed');
  const [appraisalLimitations, setAppraisalLimitations] = useState('');
  const [governanceHistory, setGovernanceHistory] = useState<{rights:any[];appraisals:any[]}>({rights:[],appraisals:[]});
  const [yearFrom, setYearFrom] = useState('');
  const [yearTo, setYearTo] = useState('');
  const [jobs, setJobs] = useState<HSPTLJob[]>([]);
  const [cases, setCases] = useState<HarvestedCase[]>([]);
  const [outputRoot, setOutputRoot] = useState('');
  const [monitoring, setMonitoring] = useState<{ job_counts: Record<string, number>; ucks: Record<string, number | string | unknown>; sources: Array<Record<string, unknown>>; ingestion_channels: string[] } | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const [status, monitor, providers, governanceSnapshot, providerHistorySnapshot, reviewer] = await Promise.all([
        api.dataToolsStatus(), api.dataToolsMonitoring(), api.dataToolsProviderHealth(), api.dataToolsGovernance(), api.dataToolsProviderHealthHistory(), api.ucksReviewerStatus()
      ]);
      setReviewerStatus(reviewer);
      setProviderHealth(providers.items || []);
      setProviderHistory(providerHistorySnapshot.items || []);
      setGovernance(governanceSnapshot);
      setJobs(status.jobs || []);
      setOutputRoot(status.output_root || '');
      setMonitoring(monitor);
      const harvested = await api.harvestedCases();
      setCases(harvested.items || []);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load data tools.'); }
  }
  useEffect(() => { void refresh(); }, []);

  async function queueNotes() {
    setBusy(true); setError(''); setMessage('');
    try { const job = await api.queueMedNoteGen(fhirDir); setMessage(`MedNoteGen job queued: ${job.id}`); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not queue MedNoteGen.'); }
    finally { setBusy(false); }
  }
  async function queueHarvest() {
    setBusy(true); setError(''); setMessage('');
    try {
      const job = await api.queueSpecialtyHarvest({ specialties: selected, max_cases_per_specialty: maxCases, year_from: yearFrom ? Number(yearFrom) : undefined, year_to: yearTo ? Number(yearTo) : undefined, knowledge_profile: knowledgeProfile });
      setMessage(`Clinical Knowledge Harvester job queued: ${job.id}`); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not queue Clinical Knowledge Harvester.'); }
    finally { setBusy(false); }
  }
  async function runJob(id: string) {
    setBusy(true); setError(''); setMessage('');
    try {
      await api.runToolJob(id);
      setMessage('Job started. HSPTL will update its status as the task runs.');
      for (let attempt = 0; attempt < 180; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 2000));
        const [status, monitor] = await Promise.all([api.dataToolsStatus(), api.dataToolsMonitoring()]);
        setJobs(status.jobs || []);
        setOutputRoot(status.output_root || '');
        setMonitoring(monitor);
        const target = (status.jobs || []).find(job => job.id === id);
        if (target && ['completed', 'failed', 'cancelled'].includes(target.status)) {
          const latest = await api.harvestedCases();
          setCases(latest.items || []);
          setMessage(target.status === 'completed' ? 'Job completed.' : `Job ${target.status}: ${target.error_code || 'see job details'}`);
          return;
        }
      }
      setMessage('The job is still running. You can refresh the job list to check its progress.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not run the job.'); }
    finally { setBusy(false); }
  }

  async function cancelJob(id: string) {
    setError(''); setMessage('');
    try { await api.cancelToolJob(id); setMessage('Cancellation requested. The running tool will stop at its next checkpoint.'); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not cancel the job.'); }
  }

  async function loadGovernanceHistory(documentId: string) {
    setGovernanceDocument(documentId);
    if (!documentId) { setGovernanceHistory({rights:[],appraisals:[]}); return; }
    try {
      const [rights, appraisals, appraisal] = await Promise.all([api.ucksRightsReviews(documentId), api.ucksAppraisalHistory(documentId), api.ucksEvidenceAppraisal(documentId)]);
      setGovernanceHistory({rights:rights.items||[],appraisals:appraisals.items||[]});
      setAppraisalDesign(appraisal?.study_design || 'not_reported');
      setAppraisalBias(appraisal?.risk_of_bias || 'not_assessed');
      setAppraisalLimitations(appraisal?.limitations || '');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load document governance history.'); }
  }
  async function saveRightsReview() {
    if (!governanceDocument || !reviewerToken.trim()) return;
    setBusy(true); setError(''); setMessage('');
    try { await api.ucksCreateRightsReview(governanceDocument, reviewerToken, {decision:rightsDecision, licence:rightsLicence, scope:rightsScope, rationale:'Recorded through HSPTL Data Tools'}); setMessage('Rights decision recorded in the append-only audit history.'); await loadGovernanceHistory(governanceDocument); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Rights review failed.'); } finally { setBusy(false); }
  }
  async function saveAppraisal() {
    if (!governanceDocument || !reviewerToken.trim()) return;
    setBusy(true); setError(''); setMessage('');
    try { await api.ucksSaveEvidenceAppraisal(governanceDocument, reviewerToken, {study_design:appraisalDesign, risk_of_bias:appraisalBias, limitations:appraisalLimitations, status:'reviewed'}); setMessage('Evidence appraisal saved; the prior version is retained in history.'); await loadGovernanceHistory(governanceDocument); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Evidence appraisal failed.'); } finally { setBusy(false); }
  }

  const metric = (key: string) => Number(monitoring?.ucks?.[key] ?? 0).toLocaleString();

  return <div className="space-y-6">
    <header><div className="eyebrow">LOCAL DATA WORKFLOWS</div><h1 className="page-title mt-2">Data Tools</h1><p className="muted mt-2 max-w-3xl text-sm">Transform your own Synthea records into source-traceable encounter notes, and discover published clinical evidence for a human-reviewed knowledge library.</p></header>
    {message && <div className="status-success">{message}</div>}{error && <div className="status-error">{error}</div>}
    <section className="hsptl-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><div className="eyebrow">UNIFIED CLINICAL KNOWLEDGE SYSTEM</div><h2 className="mt-1 text-lg font-bold">Ingestion monitoring</h2><p className="muted mt-1 text-xs">Tool outputs enter UCKS through shared provenance-aware ingestion contracts. Imported material remains subject to review.</p></div><span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold text-emerald-800">Service layer active</span></div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[['Sources', metric('sources')], ['Documents', metric('documents')], ['Chunks', metric('chunks')], ['Embeddings', metric('embeddings')]].map(([label,value]) => <div key={label} className="metric-card"><div className="muted text-xs">{label}</div><div className="mt-1 text-xl font-bold tabular-nums">{value}</div></div>)}
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">{(monitoring?.ingestion_channels || ['clinical_harvester','synthea_mednotegen','external_import','online_feed']).map(channel => <span key={channel} className="rounded-full border border-hsptl-surface-border px-2.5 py-1 dark:border-hsptl-dark-border">{channel.replaceAll('_',' ')}</span>)}</div>
      <p className="muted mt-3 text-xs">{monitoring?.sources.length ?? 0} registered UCKS sources · {Object.entries(monitoring?.job_counts || {}).map(([status,count]) => `${count} ${status}`).join(' · ') || 'No tool jobs'}</p>
      {!!monitoring?.sources.length && <div className="mt-3 space-y-2">{monitoring.sources.slice(0, 6).map((source, index) => <div key={String(source.id || index)} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-hsptl-surface-border px-3 py-2 text-xs dark:border-hsptl-dark-border"><span className="font-semibold">{String(source.name || 'Unnamed source')}</span><span className="muted">{String(source.source_type || 'source').replaceAll('_',' ')} · {source.enabled === false ? 'disabled' : 'enabled'}</span></div>)}</div>}
    </section>
    <section className="grid gap-4 xl:grid-cols-2">
      <div className="hsptl-card p-4 sm:p-5"><div className="eyebrow">PROVIDER CONNECTIVITY</div><h2 className="mt-1 text-lg font-bold">Clinical data providers</h2><p className="muted mt-1 text-xs">Cached status is shown until a bounded live probe is requested.</p><div className="mt-3 space-y-2">{providerHealth.map((provider:any) => <div key={provider.id} className="flex items-center justify-between gap-2 rounded-lg border border-hsptl-surface-border px-3 py-2 text-xs dark:border-hsptl-dark-border"><div><span className="font-semibold">{provider.name}</span><div className="muted mt-0.5">{provider.recent_statuses?.length ? `${provider.recent_statuses.length} recent checks` : 'No probe history'}{provider.error_code ? ` · ${provider.error_code}` : ''}</div></div><span className={`rounded-full px-2 py-1 font-semibold ${provider.status === 'healthy' ? 'bg-emerald-100 text-emerald-800' : provider.status === 'not_probed' ? 'bg-slate-100 text-slate-600' : 'bg-amber-100 text-amber-800'}`}>{provider.alert || provider.status}{provider.latency_ms != null ? ` · ${provider.latency_ms} ms` : ''}</span></div>)}</div><p className="muted mt-2 text-xs">{providerHistory.length} recent health observations loaded · endpoint reachability only, not data completeness or licensing.</p><button className="secondary-button mt-3" onClick={async()=>{try{const result=await api.dataToolsProviderHealth(true);const history=await api.dataToolsProviderHealthHistory();setProviderHealth(result.items||[]);setProviderHistory(history.items||[]);}catch(e){setError(e instanceof Error?e.message:'Provider health probe failed.');}}}>Probe providers</button></div>
      <div className="hsptl-card p-4 sm:p-5"><div className="eyebrow">KNOWLEDGE GOVERNANCE</div><h2 className="mt-1 text-lg font-bold">Review and rights overview</h2><p className="muted mt-1 text-xs">Imported records may be harvested or machine-screened until independently reviewed. Neither status means clinically validated. Retrieval scores are not evidence grades.</p><div className="mt-3 grid grid-cols-2 gap-2 text-xs">{Object.entries(governance?.documents?.review_status||{}).map(([key,value])=><div className="metric-card" key={key}><div className="muted">{key.replaceAll('_',' ')}</div><div className="mt-1 text-lg font-bold">{String(value)}</div></div>)}</div><p className="muted mt-3 text-xs">{governance?.rights_and_provenance?.documents_without_declared_licence ?? '—'} documents without a declared licence · {governance?.rights_and_provenance?.reuse_permitted_sources ?? '—'} sources marked reuse-permitted</p><p className="muted mt-1 text-xs">Rights queue: {governance?.rights_review_queue?.count ?? 0} documents require licence assessment.</p><div className="mt-2 space-y-1 text-xs">{Object.entries(governance?.governance_queues||{}).map(([key,value]:any)=><div key={key} className="flex justify-between gap-2"><span className="muted">{key.replace('ucks_','').replaceAll('_',' ')}</span><strong>{value.total}</strong></div>)}</div><p className="muted mt-3 text-xs">Evidence appraisals: {governance?.evidence_appraisals?.total ?? 0} · awaiting review: {governance?.review_backlog?.count ?? 0}</p>{governance?.review_backlog?.oldest_first?.slice(0,3).map((item:any)=><div key={item.id} className="mt-2 rounded-lg border border-hsptl-surface-border px-3 py-2 text-xs dark:border-hsptl-dark-border"><div className="font-semibold">{item.title}</div><div className="muted mt-1">{item.content_type.replaceAll('_',' ')} · {item.source_name || 'Unknown source'} · {item.review_status}</div></div>)}{governance?.rights_review_queue?.unresolved_oldest_first?.slice(0,2).map((item:any)=><div key={`rights-${item.id}`} className="mt-2 rounded-lg border border-amber-300 px-3 py-2 text-xs dark:border-amber-900"><div className="font-semibold">Rights review · {item.title}</div><div className="muted mt-1">{item.source_name || 'Unknown source'} · no document or source licence declaration</div></div>)}</div>
    </section>

    <section className="hsptl-card p-4 sm:p-5 space-y-3">
      <div><div className="eyebrow">CONTROLLED GOVERNANCE WORKFLOW</div><h2 className="mt-1 text-lg font-bold">Rights review and evidence appraisal</h2><p className="muted mt-1 text-xs">Decisions require a configured reviewer token. Reviewer identity is supplied by the backend environment, not entered or self-declared in the form.</p></div>
      <div className="grid gap-2 sm:grid-cols-2"><div><label className="field-label">Reviewer authentication</label><input type="password" autoComplete="off" className="form-field mt-1" value={reviewerToken} onChange={e=>setReviewerToken(e.target.value)} placeholder="HSPTL reviewer token"/><p className="muted mt-1 text-xs">{reviewerStatus.configured ? `Configured reviewer: ${reviewerStatus.reviewer_id}` : 'Not configured · set HSPTL_REVIEWER_TOKEN and HSPTL_REVIEWER_ID before recording decisions'}</p></div><div><label className="field-label">Document for review</label><select className="form-field mt-1" value={governanceDocument} onChange={e=>void loadGovernanceHistory(e.target.value)}><option value="">Select a staged document</option>{Array.from(new Map([...(governance?.rights_review_queue?.unresolved_oldest_first || []), ...(governance?.review_backlog?.oldest_first || [])].map((d:any)=>[d.id,d])).values()).map((d:any)=><option key={d.id} value={d.id}>{d.title} · {d.id}</option>)}</select></div></div>
      {governanceDocument && <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border space-y-2"><h3 className="font-semibold text-sm">Reuse rights decision</h3><select className="form-field" value={rightsDecision} onChange={e=>setRightsDecision(e.target.value)}><option value="needs_clarification">Needs clarification</option><option value="restricted">Restricted</option><option value="permitted">Permitted</option></select><input className="form-field" value={rightsLicence} onChange={e=>setRightsLicence(e.target.value)} placeholder="Licence identifier (required if permitted)"/><select className="form-field" value={rightsScope} onChange={e=>setRightsScope(e.target.value)}><option value="metadata_only">Metadata only</option><option value="abstract_only">Abstract only</option><option value="full_text_reuse">Full-text reuse</option><option value="adaptation">Adaptation</option></select><button disabled={busy || !reviewerStatus.configured || !reviewerToken.trim() || (rightsDecision==='permitted' && !rightsLicence.trim())} className="secondary-button" onClick={()=>void saveRightsReview()}>Record rights decision</button><div className="muted text-xs">{governanceHistory.rights.length} historical rights decisions</div></div>
        <div className="rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border space-y-2"><h3 className="font-semibold text-sm">Structured evidence appraisal</h3><label className="field-label">Study design</label><select className="form-field" value={appraisalDesign} onChange={e=>setAppraisalDesign(e.target.value)}>{['not_reported','guideline','systematic_review','meta_analysis','randomized_trial','nonrandomized_trial','cohort','case_control','cross_sectional','diagnostic_accuracy','case_series','case_report','qualitative','dataset','other'].map(x=><option key={x} value={x}>{x.replaceAll('_',' ')}</option>)}</select><label className="field-label">Risk of bias</label><select className="form-field" value={appraisalBias} onChange={e=>setAppraisalBias(e.target.value)}>{['not_assessed','low','some_concerns','high','unclear'].map(x=><option key={x} value={x}>{x.replaceAll('_',' ')}</option>)}</select><label className="field-label">Limitations</label><textarea className="form-field min-h-20" value={appraisalLimitations} onChange={e=>setAppraisalLimitations(e.target.value)}/><button disabled={busy || !reviewerStatus.configured || !reviewerToken.trim()} className="secondary-button" onClick={()=>void saveAppraisal()}>Save appraisal</button><div className="muted text-xs">{governanceHistory.appraisals.length} historical appraisal snapshots</div></div>
      </div>}
      {(governanceHistory.rights.length>0 || governanceHistory.appraisals.length>0) && <div className="grid gap-2 sm:grid-cols-2 text-xs"><div><strong>Rights audit trail</strong>{governanceHistory.rights.slice(0,4).map((r:any)=><div key={r.id} className="muted mt-1">{r.decision} · {r.scope} · {r.reviewer} · {r.created_at}</div>)}</div><div><strong>Appraisal history</strong>{governanceHistory.appraisals.slice(0,4).map((r:any)=><div key={r.id} className="muted mt-1">Snapshot · {r.created_at}</div>)}</div></div>}
    </section>

    <div className="grid gap-5 xl:grid-cols-2">
      <section className="hsptl-card p-5 sm:p-6">
        <div className="flex items-start gap-3"><span className="dataset-icon"><Icon name="filePlus" size={22}/></span><div className="flex-1"><div className="eyebrow">SYNTHETIC RECORD NOTES</div><h2 className="mt-1 text-xl font-bold">MedNoteGen</h2><p className="muted mt-1 text-sm">Create readable, encounter-linked notes from Synthea FHIR JSON. Deterministic and local; no API key or language model required.</p></div></div>
        <label className="field-label mt-5 block">Synthea FHIR directory</label><input className="form-field mt-2" value={fhirDir} onChange={e => setFhirDir(e.target.value)} spellCheck={false}/>
        <div className="note-warning mt-4 text-xs">MedNoteGen only uses recorded FHIR facts. Missing examination findings remain undocumented. Generated notes are synthetic source summaries, not clinical diagnoses or SOAP recommendations.</div>
        <button disabled={busy || !fhirDir.trim()} onClick={() => void queueNotes()} className="primary-button mt-4 w-full"><Icon name="filePlus" size={16}/> Queue note generation</button>
      </section>

      <section className="hsptl-card p-5 sm:p-6">
        <div className="flex items-start gap-3"><span className="dataset-icon"><Icon name="search" size={22}/></span><div className="flex-1"><div className="eyebrow">OPEN-ACCESS CLINICAL KNOWLEDGE</div><h2 className="mt-1 text-xl font-bold">Clinical Knowledge Harvester</h2><p className="muted mt-1 text-sm">Discover specialty-relevant case reports, guidelines, systematic reviews, trials and observational evidence across Europe PMC, PubMed, PMC OA, Crossref and DOAJ. Full text is used when available; otherwise eligible records may be retained as clearly labelled metadata/abstract records. Results remain staged for rights and clinical review.</p></div></div>
        <label className="field-label mt-5 block">Specialties to harvest</label>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">{SPECIALTY_OPTIONS.map(([key,label]) => <label key={key} className="flex items-center gap-2 rounded-lg border border-hsptl-surface-border px-2.5 py-2 text-xs dark:border-hsptl-dark-border"><input type="checkbox" checked={selected.includes(key)} onChange={e => setSelected(current => e.target.checked ? [...current,key] : current.filter(x => x !== key))} className="accent-hsptl-indigo"/><span>{label}</span></label>)}</div>
        <div className="mt-4"><label className="field-label">Knowledge profile</label><select className="form-field mt-1" value={knowledgeProfile} onChange={e => setKnowledgeProfile(e.target.value)}><option value="case_reports">Case reports</option><option value="guidelines">Clinical guidelines</option><option value="systematic_reviews">Systematic reviews and meta-analyses</option><option value="trials">Clinical trials</option><option value="observational">Observational and diagnostic studies</option><option value="clinical_evidence">Clinical evidence (all listed types)</option><option value="all_open_access">All supported open-access clinical evidence</option></select></div>
        <div className="mt-4 grid grid-cols-3 gap-2"><div><label className="field-label">Max / specialty</label><input type="number" min={1} max={100} className="form-field mt-1" value={maxCases} onChange={e => setMaxCases(Math.max(1,Math.min(100,Number(e.target.value)||1)))}/></div><div><label className="field-label">From year</label><input type="number" min={1900} max={2100} placeholder="Any" className="form-field mt-1" value={yearFrom} onChange={e => setYearFrom(e.target.value)}/></div><div><label className="field-label">To year</label><input type="number" min={1900} max={2100} placeholder="Any" className="form-field mt-1" value={yearTo} onChange={e => setYearTo(e.target.value)}/></div></div>
        <div className="note-warning mt-4 text-xs">Open access does not mean unrestricted reuse. The harvester records any machine-readable licence it can find; unidentified or custom terms must be checked manually. No harvested article becomes an approved case automatically.</div>
        <button disabled={busy || selected.length === 0} onClick={() => void queueHarvest()} className="teal-button mt-4 w-full"><Icon name="search" size={16}/> Queue knowledge harvesting</button>
      </section>
    </div>

    <section className="space-y-3"><div className="flex items-center justify-between gap-3"><div><div className="eyebrow">JOB QUEUE</div><h2 className="text-lg font-bold">Recent data jobs</h2></div><button onClick={() => void refresh()} className="secondary-button"><Icon name="refresh" size={15}/> Refresh</button></div>
      {jobs.length ? jobs.filter(job => ['mednotegen_generate','specialty_harvest'].includes(job.kind)).slice(0,8).map(job => <JobCard key={job.id} job={job} onRun={runJob} onCancel={cancelJob}/>) : <div className="hsptl-card p-5 muted text-sm">No data-tool jobs yet.</div>}
      <p className="muted text-xs">Jobs are stored locally. Use Run now to process a queued job in this session; an optional background worker can be enabled for unattended processing.</p>
    </section>

    <section className="space-y-3"><div className="flex items-end justify-between gap-2"><div><div className="eyebrow">HARVESTED SOURCE MATERIAL</div><h2 className="text-lg font-bold">Staged published cases</h2><p className="muted mt-1 text-xs">{cases.length} shown · output root: {outputRoot || 'HSPTL local imports'}</p></div></div>
      {cases.length ? <div className="grid gap-3 lg:grid-cols-2">{cases.slice(0,20).map((item,i) => <article key={`${item.specialty}-${item.doi || item.pmcid || i}`} className="metric-card"><div className="flex items-center justify-between gap-3"><span className="eyebrow">{item.specialty.replaceAll('-',' ')}</span><span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-800">{item.review_status}</span></div><h3 className="mt-2 font-bold leading-snug">{item.title}</h3><p className="muted mt-1 text-xs">{item.journal} · {item.year} · {item.source || 'source not recorded'}</p><p className="mt-2 text-xs text-secondary">{item.full_text_available ? 'Full text retained under technical licence allow-list; human rights review pending' : 'Metadata/abstract only · full text not retained'}</p><p className="mt-1 text-xs text-secondary">Licence: {item.license_status.replaceAll('_',' ')}</p>{item.url && <a href={item.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-hsptl-indigo underline dark:text-indigo-200">Open source <Icon name="external" size={13}/></a>}</article>)}</div> : <div className="hsptl-card p-5 muted text-sm">No article cases harvested yet. Queue a specialty harvest above to populate this staging library.</div>}
    </section>
  </div>;
}
