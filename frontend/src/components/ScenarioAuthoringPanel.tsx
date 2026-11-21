import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Icon } from './Icon';

type Draft = { scenario_id: string; version: string; title: string; clinical_review_status: string; published?: boolean; updated_at: string };

export default function ScenarioAuthoringPanel() {
  const [source, setSource] = useState('');
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [reviewToken, setReviewToken] = useState('');
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[]; warnings: string[]; checks: string[]; dynamic_path_coverage: string; clinical_validity: string } | null>(null);
  const [traceMatrix, setTraceMatrix] = useState<{ valid: boolean; trace_matrix: Array<Record<string, any>>; fault_injection: Array<Record<string, any>>; clinical_review_required: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function load() {
    const result = await api.scenarioDrafts();
    setDrafts(result.items);
  }
  useEffect(() => {
    let alive = true;
    Promise.all([api.scenarioAuthoringTemplate(), api.scenarioDrafts()]).then(([template, result]) => {
      if (!alive) return;
      setSource(JSON.stringify(template.scenario, null, 2)); setDrafts(result.items);
    }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Scenario authoring could not load.'));
    return () => { alive = false; };
  }, []);

  function parse(): Record<string, any> {
    const value = JSON.parse(source) as Record<string, any>;
    if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Scenario package must be a JSON object.');
    return value;
  }
  async function validate() {
    setBusy(true); setError(''); setMessage('');
    try { setValidation(await api.validateScenarioDraft(parse())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Scenario validation failed.'); setValidation(null); }
    finally { setBusy(false); }
  }
  async function buildTraceMatrix() {
    setBusy(true); setError(''); setMessage('');
    try { setTraceMatrix(await api.scenarioTraceMatrix(parse())); setMessage('Deterministic strong, partial, poor and unsafe trace coverage prepared.'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Trace matrix could not be generated.'); setTraceMatrix(null); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError(''); setMessage('');
    try { const result = await api.saveScenarioDraft(parse()); setMessage(`Saved ${result.scenario_id} as a local draft. It is not in the learner catalogue.`); setValidation(result.validation); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Scenario draft could not be saved.'); }
    finally { setBusy(false); }
  }
  async function editDraft(id: string) {
    setBusy(true); setError('');
    try { const result = await api.scenarioDraftDetail(id); setSource(JSON.stringify(result.scenario, null, 2)); setValidation(null); setMessage(`Loaded ${id}. Increment the version before saving changed content.`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Scenario draft could not be loaded.'); }
    finally { setBusy(false); }
  }
  async function publish(id: string) {
    setBusy(true); setError(''); setMessage('');
    try { await api.publishScenarioDraft(id, reviewToken); setMessage(`Scenario ${id} published after authenticated clinical review.`); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Scenario publication failed.'); }
    finally { setBusy(false); }
  }

  function updateScenarioField(field: string, value: string) {
    try {
      const scenario = parse();
      scenario[field] = value;
      setSource(JSON.stringify(scenario, null, 2));
      setValidation(null);
      setTraceMatrix(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Scenario JSON could not be edited.');
    }
  }

  return <section className="hx-content-block">
    <div className="hx-block-heading"><div><span className="hx-eyebrow">SCENARIO AUTHORING · PHASE 7</span><h2>Scenario package editor</h2><p>Author a versioned synthetic case using the existing scenario contract and PROforma model library. Validation is structural; it does not establish clinical validity or complete dynamic path coverage.</p></div><Icon name="file-code" size={22}/></div>
    {(error || message) && <div role={error ? 'alert' : 'status'} className={error ? 'status-error' : 'status-success'}>{error || message}</div>}
    <div className="grid gap-3 md:grid-cols-4">
      {(['scenario_id','version','title','specialty'] as const).map((field) => {
        let value = '';
        try { value = String(parse()[field] || ''); } catch { value = ''; }
        return <label key={field} className="text-xs font-semibold">{field.replaceAll('_',' ')}
          <input className="mt-1 w-full rounded-lg border border-hsptl-surface-border bg-transparent p-2 dark:border-hsptl-dark-border" value={value} onChange={(event) => updateScenarioField(field, event.target.value)} />
        </label>;
      })}
    </div>
    <label className="block text-sm font-semibold">Scenario JSON package<textarea aria-label="Scenario JSON package" spellCheck={false} className="mt-2 min-h-[440px] w-full rounded-xl border border-hsptl-surface-border bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-100 dark:border-hsptl-dark-border" value={source} onChange={(event) => { setSource(event.target.value); setValidation(null); }} /></label>
    <div className="mt-3 flex flex-wrap gap-2"><button className="hx-button-secondary" disabled={busy} onClick={() => void validate()}><Icon name="shield-check" size={15}/> Validate package</button><button className="hx-button-secondary" disabled={busy} onClick={() => void buildTraceMatrix()}><Icon name="workflow" size={15}/> Build trace/fault matrix</button><button className="hx-button-primary" disabled={busy} onClick={() => void save()}>Save draft <Icon name="arrow" size={15}/></button></div>
    {validation && <div className={`mt-3 rounded-xl border p-3 ${validation.valid ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30' : 'border-rose-300 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/30'}`}><b>{validation.valid ? 'Structural validation passed' : 'Validation errors found'}</b>{validation.errors.map((item) => <p key={item} className="mt-1 text-sm">• {item}</p>)}{validation.warnings.map((item) => <p key={item} className="muted mt-1 text-sm">• {item}</p>)}<p className="muted mt-2 text-xs">Dynamic path coverage: {validation.dynamic_path_coverage}. Clinical validity: {validation.clinical_validity}.</p></div>}
    {traceMatrix && <div className="mt-3 rounded-xl border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border">
      <b>Scenario trace and fault matrix</b>
      <div className="mt-2 grid gap-2 md:grid-cols-2">{traceMatrix.trace_matrix.map((trace) => <div key={String(trace.trace)} className="rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-900"><b>{String(trace.trace)}</b><p className="muted mt-1">Actions: {Array.isArray(trace.ordered_actions) ? trace.ordered_actions.join(', ') || 'none' : 'none'}</p><p className="muted mt-1">{String(trace.expected)}</p></div>)}</div>
      <div className="mt-3"><b className="text-xs">Fault injection cases</b>{traceMatrix.fault_injection.map((fault) => <p key={String(fault.fault)} className="muted mt-1 text-xs">• <b>{String(fault.fault)}:</b> {String(fault.policy)}</p>)}</div>
      {traceMatrix.clinical_review_required && <p className="muted mt-3 text-xs">Clinical review remains required before publication or learner use.</p>}
    </div>}
    <div className="mt-5 border-t border-hsptl-surface-border pt-4 dark:border-hsptl-dark-border"><h3 className="font-bold">Saved scenario drafts</h3>{drafts.map((draft) => <div key={draft.scenario_id} className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-hsptl-surface-border p-3 dark:border-hsptl-dark-border"><div><b className="text-sm">{draft.title}</b><p className="muted text-xs">{draft.scenario_id} · v{draft.version} · {draft.clinical_review_status}</p></div><div className="flex flex-wrap gap-2"><button className="hx-button-secondary" disabled={busy} onClick={() => void editDraft(draft.scenario_id)}>Edit draft</button><button className="hx-button-secondary" disabled={busy || !reviewToken || draft.published} onClick={() => void publish(draft.scenario_id)}>{draft.published ? 'Published' : 'Publish after clinical review'}</button></div></div>)}{!drafts.length && <p className="muted mt-2 text-sm">No saved scenario drafts.</p>}<label className="mt-4 block text-sm font-semibold">Clinical reviewer credential<input type="password" className="mt-1 w-full rounded-lg border border-hsptl-surface-border bg-transparent p-2 dark:border-hsptl-dark-border" value={reviewToken} onChange={(event) => setReviewToken(event.target.value)} placeholder="HSPTL_CLINICAL_REVIEWER_TOKEN"/></label><p className="muted mt-2 text-xs">The application only verifies the configured credential. The institution remains responsible for verifying the reviewer's clinical qualifications and authorization.</p></div>
  </section>;
}
