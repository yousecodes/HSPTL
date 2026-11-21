import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type {
  SyntheticDataset, SyntheticPreflight, SyntheticQuality, SyntheticQuarantineItem,
  SyntheticRecipe, SyntheticRun, SyntheticSchedule, SyntheticSettings, SyntheticStatus,
} from '../lib/api';
import { Icon } from '../components/Icon';

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  preflight: 'Preflight checks',
  generating: 'Generating population',
  exporting: 'Exporting FHIR / CSV',
  inventorying: 'Inventorying bundles',
  fhir_validating: 'FHIR validation',
  reference_validating: 'Reference integrity',
  chronology_validating: 'Chronology audit',
  terminology_auditing: 'Terminology audit',
  plausibility_auditing: 'Plausibility audit',
  completeness_scoring: 'Completeness scoring',
  normalizing: 'Canonical normalisation',
  quarantine_partitioning: 'Quarantine partition',
  importing: 'Importing fixtures',
  registering: 'Registering provenance',
  completed: 'Completed',
};

function statusClass(status: string): string {
  if (status.startsWith('completed')) return 'status-success';
  if (status === 'partial_cohort') return 'status-warning';
  if (['failed', 'blocked', 'cancelled'].includes(status)) return 'status-error';
  return 'hx-status-draft';
}

export default function SyntheticDataPage() {
  const [status, setStatus] = useState<SyntheticStatus | null>(null);
  const [settings, setSettings] = useState<SyntheticSettings | null>(null);
  const [recipes, setRecipes] = useState<SyntheticRecipe[]>([]);
  const [runs, setRuns] = useState<SyntheticRun[]>([]);
  const [datasets, setDatasets] = useState<SyntheticDataset[]>([]);
  const [schedules, setSchedules] = useState<SyntheticSchedule[]>([]);
  const [quarantine, setQuarantine] = useState<SyntheticQuarantineItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<SyntheticDataset | null>(null);
  const [quality, setQuality] = useState<SyntheticQuality | null>(null);
  const [preflight, setPreflight] = useState<SyntheticPreflight | null>(null);
  const [selectedRecipe, setSelectedRecipe] = useState('');
  const [population, setPopulation] = useState(10);
  const [acceptedTarget, setAcceptedTarget] = useState(0);
  const [seed, setSeed] = useState(2026);
  const [wantFhir, setWantFhir] = useState(true);
  const [wantCsv, setWantCsv] = useState(true);
  const [reviewerToken, setReviewerToken] = useState('');
  const [scheduleName, setScheduleName] = useState('Weekly teaching cohort');
  const [scheduleFrequency, setScheduleFrequency] = useState('weekly');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    const [nextStatus, nextSettings, nextRecipes, nextRuns, nextDatasets, nextSchedules, nextQuarantine] = await Promise.all([
      api.syntheticStatus(), api.syntheticSettings(), api.syntheticRecipes(),
      api.syntheticJobs(25), api.syntheticDatasets(25), api.syntheticSchedules(),
      api.syntheticQuarantine({ status: 'open' }),
    ]);
    setStatus(nextStatus); setSettings(nextSettings); setRecipes(nextRecipes.items);
    setRuns(nextRuns.items); setDatasets(nextDatasets.items); setSchedules(nextSchedules.items);
    setQuarantine(nextQuarantine.items);
    if (!selectedRecipe && nextRecipes.items.length) setSelectedRecipe(nextRecipes.items[0].recipe_id);
  }

  useEffect(() => {
    void load().catch((err: unknown) => setError(err instanceof Error ? err.message : 'The synthetic data factory could not load.'));
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(''); setMessage('');
    try { await action(); } catch (err) { setError(err instanceof Error ? err.message : 'The operation failed.'); }
    finally { setBusy(false); }
  }

  async function saveSettings() {
    if (!settings) return;
    await run(async () => {
      const saved = await api.saveSyntheticSettings({ ...settings });
      setSettings(saved);
      setMessage('Factory configuration saved. Run preflight to confirm every prerequisite is satisfied.');
      await load();
    });
  }

  async function checkPreflight() {
    await run(async () => {
      const report = await api.syntheticPreflight({
        recipe_id: selectedRecipe, population, fhir: wantFhir, csv: wantCsv,
      });
      setPreflight(report);
      setMessage(report.ok
        ? 'All blocking preflight checks passed. The generator is pinned and ready.'
        : 'Preflight found blocking problems. Generation cannot start until they are resolved.');
    });
  }

  async function queueGeneration() {
    await run(async () => {
      const result = await api.queueSyntheticJob({
        recipe_id: selectedRecipe, population, accepted_target: acceptedTarget,
        seed, fhir: wantFhir, csv: wantCsv,
      });
      setMessage(result.idempotent_reuse
        ? 'Identical inputs were already run. The existing run was returned instead of generating again.'
        : 'Generation job queued. Use "Run now" to execute it on this machine.');
      await load();
    });
  }

  async function runNow(jobId: string) {
    await run(async () => {
      const result = await api.runSyntheticJob(jobId);
      setMessage(result.ran ? 'Job executed. Review the dataset, quality report and quarantine.' : 'The job was not claimable (it may already be running or finished).');
      await load();
    });
  }

  async function openDataset(datasetId: string) {
    await run(async () => {
      const [detail, report] = await Promise.all([api.syntheticDataset(datasetId), api.syntheticQuality(datasetId)]);
      setSelectedDataset(detail); setQuality(report);
    });
  }

  async function verifyManifest(datasetId: string) {
    await run(async () => {
      const result = await api.syntheticManifest(datasetId);
      setMessage(result.verified
        ? `Provenance manifest verified: ${result.verification}`
        : `Manifest verification failed: ${result.verification}`);
    });
  }

  async function activateRecipe(recipe: SyntheticRecipe) {
    if (!reviewerToken) return;
    await run(async () => {
      await api.transitionSyntheticRecipe(recipe.recipe_id, reviewerToken, 'technical_validated');
      const activated = await api.transitionSyntheticRecipe(recipe.recipe_id, reviewerToken, 'clinical_reviewed');
      await api.transitionSyntheticRecipe(recipe.recipe_id, reviewerToken, 'active', 'Clinical review complete for local use.');
      setMessage(`${activated.title} is now active and may run unattended.`);
      await load();
    });
  }

  async function reviewQuarantine(item: SyntheticQuarantineItem, decision: string) {
    if (!reviewerToken) return;
    await run(async () => {
      await api.reviewSyntheticQuarantine(item.item_id, reviewerToken, decision, 'Reviewed in the synthetic data factory.');
      setMessage(`Quarantine item ${decision}.`);
      await load();
    });
  }

  async function createSchedule() {
    await run(async () => {
      await api.createSyntheticSchedule({
        name: scheduleName, recipe_id: selectedRecipe, population,
        accepted_target: acceptedTarget, frequency: scheduleFrequency, enabled: true,
      });
      setMessage('Local schedule created. It runs in-process; no external cron or cloud scheduler is used.');
      await load();
    });
  }

  const activeRecipe = recipes.find((recipe) => recipe.recipe_id === selectedRecipe);
  const blockerCount = preflight?.blockers.length ?? 0;

  return <div className="hx-page-grid">
    <section className="hx-page-heading">
      <div>
        <div className="hx-eyebrow">BUILD · SYNTHETIC DATA FACTORY</div>
        <h1>Synthetic data factory</h1>
        <p>Generate synthetic patient populations locally with a pinned Synthea build, validate them across six independent dimensions, quarantine anything that fails, and register immutable provenance before import.</p>
      </div>
      <div className="hx-heading-badge"><Icon name="flask" size={18}/> Model-free · Local-only</div>
    </section>

    {(error || message) && <div role={error ? 'alert' : 'status'} className={error ? 'status-error' : 'status-success'}>{error || message}</div>}

    <section className="hx-library-summary">
      <div><strong>{datasets.length}</strong><span>Registered datasets</span></div>
      <div><strong>{status?.datasets.accepted ?? '—'}</strong><span>Accepted datasets</span></div>
      <div><strong>{quarantine.length}</strong><span>Open quarantine items</span></div>
      <div><strong>{status?.runs.running ?? 0}</strong><span>Runs in progress</span></div>
    </section>

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">01 · READINESS</span>
          <h2>Generator and validation prerequisites</h2>
          <p>Nothing is downloaded automatically. Point the factory at a local Synthea artifact and pin its SHA-256 so every run is reproducible and tamper-evident.</p>
        </div>
        <Icon name="shield-check" size={22}/>
      </div>
      <div className="hx-readiness-grid">
        <div className={`hx-readiness-card ${status?.generator.configured ? 'is-ok' : 'is-blocked'}`}>
          <b>Synthea artifact</b>
          <span>{status?.generator.configured ? `Pinned ${status.generator.version}` : 'Not configured'}</span>
          <small>{status?.generator.checksum_pinned ? 'SHA-256 pinned' : 'Checksum not pinned — runs will fail closed'}</small>
        </div>
        <div className={`hx-readiness-card ${status?.java.available ? 'is-ok' : 'is-blocked'}`}>
          <b>Java runtime</b>
          <span>{status?.java.available ? 'Available' : 'Not found'}</span>
          <small>{status?.java.detail || 'No Java runtime detected'}</small>
        </div>
        <div className={`hx-readiness-card ${status?.validator.strict_available ? 'is-ok' : 'is-limited'}`}>
          <b>FHIR validator</b>
          <span>{status?.validator.strict_available ? 'Strict conformance available' : 'Local shape checks only'}</span>
          <small>{status?.validator.strict_available ? 'HL7 validator pinned' : 'Strict conformance is not claimed'}</small>
        </div>
        <div className={`hx-readiness-card ${status?.worker.enabled ? 'is-ok' : 'is-limited'}`}>
          <b>Background worker</b>
          <span>{status?.worker.enabled ? 'Enabled' : 'Manual run'}</span>
          <small>{status?.worker.note}</small>
        </div>
      </div>
      <p className="hx-governance-note"><Icon name="shield" size={16}/> Storage: {status?.storage.root} · {status?.storage.free_mb} MB free · rule pack {status?.rule_pack.rule_pack_id} v{status?.rule_pack.rule_pack_version}</p>
    </section>

    {settings && <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">02 · CONFIGURATION</span>
          <h2>Local generator configuration</h2>
          <p>Absolute local paths only. The factory never fetches artifacts and never passes user text to a shell.</p>
        </div>
      </div>
      <div className="hx-settings-grid">
        <label>Synthea JAR path<input value={settings.synthea_jar} onChange={(event) => setSettings({ ...settings, synthea_jar: event.target.value })} placeholder="C:\hsptl\runtime\synthea-with-dependencies.jar"/></label>
        <label>Synthea version<input value={settings.synthea_version} onChange={(event) => setSettings({ ...settings, synthea_version: event.target.value })} placeholder="3.3.0"/></label>
        <label>Synthea SHA-256<input value={settings.synthea_sha256} onChange={(event) => setSettings({ ...settings, synthea_sha256: event.target.value })} placeholder="64 hex characters" maxLength={64}/></label>
        <label>Java executable<input value={settings.java_path} onChange={(event) => setSettings({ ...settings, java_path: event.target.value })} placeholder="java (or absolute path)"/></label>
        <label>Module directory<input value={settings.module_dir} onChange={(event) => setSettings({ ...settings, module_dir: event.target.value })} placeholder="Optional custom modules"/></label>
        <label>Configuration file<input value={settings.config_file} onChange={(event) => setSettings({ ...settings, config_file: event.target.value })} placeholder="Optional synthea.properties"/></label>
        <label>HL7 validator JAR<input value={settings.validator_jar} onChange={(event) => setSettings({ ...settings, validator_jar: event.target.value })} placeholder="Optional validator_cli.jar"/></label>
        <label>Validator SHA-256<input value={settings.validator_sha256} onChange={(event) => setSettings({ ...settings, validator_sha256: event.target.value })} placeholder="64 hex characters" maxLength={64}/></label>
        <label>Heap limit (MB)<input type="number" min={256} max={4096} value={settings.max_heap_mb} onChange={(event) => setSettings({ ...settings, max_heap_mb: Number(event.target.value) })}/></label>
        <label>Minimum free disk (MB)<input type="number" min={256} max={51200} value={settings.min_free_disk_mb} onChange={(event) => setSettings({ ...settings, min_free_disk_mb: Number(event.target.value) })}/></label>
      </div>
      <div className="hx-generation-controls">
        <label className="hx-inline-check"><input type="checkbox" checked={settings.strict_fhir_required} onChange={(event) => setSettings({ ...settings, strict_fhir_required: event.target.checked })}/> Require strict FHIR conformance (needs a pinned validator)</label>
        <button className="hx-button-primary" disabled={busy} onClick={() => void saveSettings()}>Save configuration</button>
      </div>
    </section>}

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">03 · RECIPES</span>
          <h2>Versioned generation recipes</h2>
          <p>Recipes are declarative data. A recipe becomes active only after technical validation and an authenticated clinical review.</p>
        </div>
        <Icon name="layers" size={22}/>
      </div>
      <div className="hx-recipe-grid">
        {recipes.map((recipe) => <div key={`${recipe.recipe_id}-${recipe.version}`} className={`hx-recipe-card ${selectedRecipe === recipe.recipe_id ? 'is-selected' : ''}`}>
          <div className="hx-recipe-head">
            <div><b>{recipe.title}</b><small>v{recipe.version} · {recipe.builtin ? 'Built-in' : recipe.owner}</small></div>
            <em className={`hx-artifact-status status-${recipe.status}`}>{recipe.status.replaceAll('_', ' ')}</em>
          </div>
          <p className="hx-muted">{recipe.description}</p>
          <div className="hx-recipe-actions">
            <button className="hx-text-action" onClick={() => { setSelectedRecipe(recipe.recipe_id); setPreflight(null); }}>Select</button>
            {recipe.status !== 'active' && <button className="hx-text-action" disabled={busy || !reviewerToken} onClick={() => void activateRecipe(recipe)}>Reviewer: activate</button>}
          </div>
        </div>)}
      </div>
      <p className="hx-governance-note"><Icon name="shield" size={16}/> Built-in recipes ship as drafts on purpose. Activating one records your reviewer identity and timestamp in the canonical event history.</p>
    </section>

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">04 · GENERATE</span>
          <h2>Run a generation job</h2>
          <p>Preflight first, then queue. Identical inputs reuse the previous run instead of generating a duplicate.</p>
        </div>
        <Icon name="play" size={22}/>
      </div>
      <div className="hx-generation-controls hx-generation-controls-wide">
        <label>Recipe<select value={selectedRecipe} onChange={(event) => { setSelectedRecipe(event.target.value); setPreflight(null); }}>{recipes.map((recipe) => <option key={recipe.recipe_id} value={recipe.recipe_id}>{recipe.title} (v{recipe.version})</option>)}</select></label>
        <label>Population<input type="number" min={1} max={5000} value={population} onChange={(event) => setPopulation(Number(event.target.value))}/></label>
        <label>Accepted target<input type="number" min={0} max={5000} value={acceptedTarget} onChange={(event) => setAcceptedTarget(Number(event.target.value))}/></label>
        <label>Deterministic seed<input type="number" min={0} max={2147483647} value={seed} onChange={(event) => setSeed(Number(event.target.value))}/></label>
        <label className="hx-inline-check"><input type="checkbox" checked={wantFhir} onChange={(event) => setWantFhir(event.target.checked)}/> FHIR R4</label>
        <label className="hx-inline-check"><input type="checkbox" checked={wantCsv} onChange={(event) => setWantCsv(event.target.checked)}/> CSV</label>
      </div>
      <div className="hx-generation-buttons">
        <button className="hx-button-secondary" disabled={busy || !selectedRecipe} onClick={() => void checkPreflight()}>Run preflight</button>
        <button className="hx-button-primary" disabled={busy || !selectedRecipe || !(wantFhir || wantCsv)} onClick={() => void queueGeneration()}>Queue generation <Icon name="arrow" size={15}/></button>
      </div>
      {preflight && <div className={`hx-preflight-report ${preflight.ok ? 'is-ok' : 'is-blocked'}`}>
        <div className="hx-preflight-head"><b>{preflight.ok ? 'Preflight passed' : `${blockerCount} blocking problem${blockerCount === 1 ? '' : 's'}`}</b><span>{activeRecipe?.title} · population {population}</span></div>
        <ul>{preflight.checks.map((check) => <li key={check.check_id} className={check.ok ? 'is-ok' : check.blocking ? 'is-blocked' : 'is-limited'}><i>{check.ok ? '✓' : check.blocking ? '✕' : '!'}</i><span><b>{check.check_id.replaceAll('_', ' ')}</b><small>{check.detail}</small></span></li>)}</ul>
      </div>}
    </section>

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">05 · RUNS</span>
          <h2>Generation jobs</h2>
          <p>Every job records its stage, counts and error code. A failed validation stops the run before import.</p>
        </div>
        <button className="hx-button-secondary" onClick={() => void load()}><Icon name="refresh" size={15}/> Refresh</button>
      </div>
      <div className="hx-run-list">
        {runs.map((item) => <div key={item.run_id} className="hx-run-row">
          <div className="hx-run-main">
            <div><b>{item.recipe_id}</b><small>{STAGE_LABELS[item.stage] || item.stage} · {new Date(item.created_at).toLocaleString()}</small></div>
            <em className={`hx-artifact-status ${statusClass(item.status)}`}>{item.status.replaceAll('_', ' ')}</em>
          </div>
          {item.error_code && <p className="status-error">{item.error_code}{item.diagnostic ? ` — ${item.diagnostic}` : ''}</p>}
          <div className="hx-run-meta">
            <span>Generated {item.counts?.generation?.generated_patients ?? '—'}</span>
            <span>Accepted {item.counts?.quarantine?.accepted_patients ?? '—'}</span>
            <span>Quarantined {item.counts?.quarantine?.quarantined_patients ?? '—'}</span>
            {item.dataset_id && <span>Dataset {item.dataset_id.slice(-6)}</span>}
          </div>
          <div className="hx-run-actions">
            {['queued', 'failed'].includes(item.status) && <button className="hx-text-action" disabled={busy} onClick={() => void runNow(item.job_id)}>Run now</button>}
            {['queued', 'running'].includes(item.status) && <button className="hx-text-action" disabled={busy} onClick={() => void run(async () => { await api.cancelSyntheticJob(item.job_id); await load(); })}>Cancel</button>}
            {item.dataset_id && <button className="hx-text-action" onClick={() => void openDataset(item.dataset_id)}>Inspect dataset</button>}
          </div>
        </div>)}
        {!runs.length && <p className="hx-muted">No generation jobs yet. Queue one above to begin.</p>}
      </div>
    </section>

    {selectedDataset && <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">06 · DATASET</span>
          <h2>{selectedDataset.name}</h2>
          <p>{selectedDataset.accepted_patients} accepted · {selectedDataset.quarantined_patients} quarantined · cohort {selectedDataset.cohort_status.replaceAll('_', ' ')}</p>
        </div>
        <button className="hx-button-secondary" onClick={() => void verifyManifest(selectedDataset.dataset_id)}>Verify manifest</button>
      </div>
      <div className="hx-dataset-meta">
        <div><b>Seed</b><span>{selectedDataset.seed}</span></div>
        <div><b>Synthea</b><span>{selectedDataset.synthea_version || '—'}</span></div>
        <div><b>FHIR</b><span>{selectedDataset.fhir_version}</span></div>
        <div><b>Strict conformance</b><span>{selectedDataset.strict_conformance ? 'Validated' : 'Not claimed'}</span></div>
        <div><b>Content digest</b><span>{selectedDataset.content_digest.slice(0, 16)}…</span></div>
      </div>
      {quality && <>
        <div className="hx-quality-grid">
          {Object.entries(quality.dimension_counts).map(([dimension, count]) => <div key={dimension}><b>{count}</b><span>{dimension}</span></div>)}
          {!Object.keys(quality.dimension_counts).length && <p className="hx-muted">No quality findings. The dataset passed every audit dimension.</p>}
        </div>
        <div className="hx-artifact-detail"><div className="hx-artifact-title"><div><small>Quality findings</small><h3>{quality.findings.length} finding{quality.findings.length === 1 ? '' : 's'}</h3></div></div>
          <div className="hx-finding-list">{quality.findings.slice(0, 60).map((finding, index) => <div key={`${finding.rule_id}-${index}`} className={`hx-finding-row severity-${finding.severity}`}><em>{finding.severity}</em><div><b>{finding.rule_id} · {finding.dimension}</b><p>{finding.message}</p></div></div>)}</div>
          <ul className="hx-limitations">{quality.limitations.map((note) => <li key={note}>{note}</li>)}</ul>
        </div>
      </>}
    </section>}

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">07 · QUARANTINE</span>
          <h2>Patient-level quarantine review</h2>
          <p>Only failing patient bundles are quarantined. Accepted patients still register; nothing is silently dropped or rewritten.</p>
        </div>
      </div>
      <div className="hx-quarantine-list">
        {quarantine.map((item) => <div key={item.item_id} className="hx-quarantine-row">
          <div><b>{item.patient_key}</b><small>{item.rule_ids.join(', ') || 'no rule recorded'}</small><p>{item.reason}</p></div>
          <div className="hx-run-actions">
            <button className="hx-text-action" disabled={busy || !reviewerToken} onClick={() => void reviewQuarantine(item, 'remediated')}>Mark remediated</button>
            <button className="hx-text-action" disabled={busy || !reviewerToken} onClick={() => void reviewQuarantine(item, 'rejected')}>Reject</button>
          </div>
        </div>)}
        {!quarantine.length && <p className="hx-muted">No open quarantine items. Every generated patient bundle passed validation.</p>}
      </div>
    </section>

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">08 · SCHEDULES</span>
          <h2>Local recurring generation</h2>
          <p>Scheduling is in-process SQLite state. No external cron, cloud scheduler or daemon is required.</p>
        </div>
      </div>
      <div className="hx-generation-controls">
        <label>Schedule name<input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)}/></label>
        <label>Frequency<select value={scheduleFrequency} onChange={(event) => setScheduleFrequency(event.target.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label>
        <button className="hx-button-primary" disabled={busy || !selectedRecipe} onClick={() => void createSchedule()}>Create schedule</button>
      </div>
      <div className="hx-schedule-list">{schedules.map((item) => <div key={item.schedule_id} className="hx-schedule-row">
        <div><b>{item.name}</b><small>{item.recipe_id} · {item.frequency} · population {item.population}</small></div>
        <div className="hx-run-actions">
          <span className={`hx-artifact-status ${item.enabled ? 'status-success' : 'hx-status-draft'}`}>{item.enabled ? 'enabled' : 'disabled'}</span>
          <span className="hx-muted">next {item.next_run_at ? new Date(item.next_run_at).toLocaleDateString() : '—'}</span>
          <button className="hx-text-action" disabled={busy} onClick={() => void run(async () => { await api.updateSyntheticSchedule(item.schedule_id, { enabled: !item.enabled }); await load(); })}>{item.enabled ? 'Disable' : 'Enable'}</button>
        </div>
      </div>)}{!schedules.length && <p className="hx-muted">No schedules configured.</p>}</div>
    </section>

    <section className="hx-content-block">
      <div className="hx-block-heading">
        <div>
          <span className="hx-eyebrow">09 · REVIEW ACCESS</span>
          <h2>Reviewer credential</h2>
          <p>Recipe activation, strict-conformance sign-off and quarantine decisions require an authenticated reviewer. The credential is held in memory for this session only.</p>
        </div>
        <Icon name="shield" size={22}/>
      </div>
      <div className="hx-review-controls">
        <label>Reviewer token<input type="password" value={reviewerToken} onChange={(event) => setReviewerToken(event.target.value)} placeholder="Configured reviewer credential"/></label>
      </div>
      <p className="hx-governance-note"><Icon name="shield" size={16}/> Technical acceptance is automated. Clinical approval of a synthetic dataset as a teaching scenario is not. Generated populations do not represent any real population and must not be used for clinical decisions.</p>
    </section>
  </div>;
}
