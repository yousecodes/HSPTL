import { useCallback, useEffect, useMemo, useState } from 'react';

type ScenarioSummary = {
  scenario_id: string; version: string; title: string; specialty: string; setting: string;
  learner_level: string; clinical_review_status: string; intended_use: string;
  educational_purpose: string; learning_objectives: string[];
  patient: { synthetic: boolean; display_id: string; age_years: number; presenting_complaint: string };
  source_basis: Array<{ title: string; publisher: string; published: string; url: string; used_for: string }>;
};
type Observation = { display: string; value: string | number; unit?: string; status?: string; history?: number[] };
type AvailableAction = { id: string; label: string; description: string; available: boolean; reason: string; proof_trace: Array<Record<string, unknown>> };
type DocumentRecord = { document_id: string; document_type: string; document_version: number; content: Record<string, string>; event_id: string; seq: number };
type Criterion = { criterion_id: string; points_earned: number; points_possible: number; rationale: string; evidence_event_ids: string[] };
type Assessment = { score: number; maximum: number; percentage: number; criteria: Criterion[]; critical_flags: Array<{ code: string; severity: string; message: string }>; status: string; competence_claimed: boolean; trace_digest: string; derivation?: { derivation_hash: string } };
type Run = {
  run_id: string; status: string; scenario: ScenarioSummary; seed: number; simulation_time_min: number;
  engine_version?: string;
  observations: Record<string, Observation>; actions: Array<{ action_id: string; simulation_time_min: number; event_id: string }>;
  rejected_actions: Array<{ action_id: string; reason: string; event_id: string }>;
  available_actions: AvailableAction[]; documents: DocumentRecord[]; assessment: Assessment | null;
  patient_status: string; debrief_prompts: string[]; review_notice: string; education_only: boolean;
};
type Replay = { semantic_trace_digest: string; state_digest: string; event_count: number; actions_accepted: number; actions_rejected: number; timeline: Array<{ seq: number; event_id: string; simulation_time_min: number; title: string; detail: string }> };
type Counterfactual = {
  omitted_action_id: string; read_only: boolean; retained_action_ids: string[];
  projected_state: Record<string, unknown>; projected_state_digest: string;
  state_changes: string[]; limitations: string[];
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail;
    const message = typeof detail === 'string' ? detail : detail?.reason || detail?.detail || detail?.state;
    throw new Error(message || `Request failed (${response.status}).`);
  }
  return payload as T;
}

const emptyNote = { assessment: '', findings: '', plan: '', uncertainties: '' };
const emptyHandover = { situation: '', background: '', assessment: '', recommendation: '', outstanding_tasks: '' };

/**
 * Clinical Command Centre stages: Orient -> Observe -> Act -> Document ->
 * Assess -> Debrief.
 *
 * Stages are anchored sections rather than exclusive tabs, so no clinical
 * information is ever hidden behind a step and expert navigation is not
 * blocked. Selecting a stage scrolls to its section; the sticky context bar
 * keeps patient identity, simulation time and status visible throughout.
 */
const STAGES = [
  { id: 'orient', label: 'Orient' },
  { id: 'observe', label: 'Observe' },
  { id: 'act', label: 'Act' },
  { id: 'document', label: 'Document' },
  { id: 'assess', label: 'Assess' },
  { id: 'debrief', label: 'Debrief' },
] as const;

type StageId = (typeof STAGES)[number]['id'];

export default function ClinicalSimulationPage() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenarioId, setScenarioId] = useState('');
  const [seed, setSeed] = useState('20261119');
  const [run, setRun] = useState<Run | null>(null);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [note, setNote] = useState(emptyNote);
  const [handover, setHandover] = useState(emptyHandover);
  const [order, setOrder] = useState({ order_type: '', display: '', rationale: '', status: 'entered', result_link: '' });
  const [debriefResponses, setDebriefResponses] = useState<Record<string, string>>({});
  const [counterfactual, setCounterfactual] = useState<Counterfactual | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const selectedScenario = useMemo(() => scenarios.find(item => item.scenario_id === scenarioId) || scenarios[0], [scenarios, scenarioId]);

  const loadRun = useCallback(async (runId: string) => {
    const next = await request<Run>(`/api/v4/simulation/runs/${encodeURIComponent(runId)}`);
    setRun(next);
    return next;
  }, []);

  useEffect(() => {
    let active = true;
    request<{ items: ScenarioSummary[] }>('/api/v4/simulation/scenarios')
      .then(payload => {
        if (!active) return;
        setScenarios(payload.items);
        if (payload.items[0]) setScenarioId(payload.items[0].scenario_id);
      })
      .catch(caught => { if (active) setError(caught instanceof Error ? caught.message : 'Scenario catalogue could not be loaded.'); });
    return () => { active = false; };
  }, []);

  async function runBusy(operation: () => Promise<void>) {
    setBusy(true); setError(''); setMessage('');
    try { await operation(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Simulation operation failed.'); }
    finally { setBusy(false); }
  }

  function startRun() {
    if (!selectedScenario) return;
    void runBusy(async () => {
      const created = await request<Run>('/api/v4/simulation/runs', {
        method: 'POST', body: JSON.stringify({ scenario_id: selectedScenario.scenario_id, seed: Number(seed) }),
      });
      setRun(created); setReplay(null); setCounterfactual(null); setDebriefResponses({});
      setNote(emptyNote); setHandover(emptyHandover);
      setMessage(`Simulation started · ${created.run_id} · seed ${created.seed}.`);
    });
  }

  function performAction(actionId: string) {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<{ run: Run }>(`/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/actions`, {
        method: 'POST', body: JSON.stringify({ action: { id: actionId } }),
      });
      setRun(result.run); setReplay(null);
      setMessage(`Action recorded: ${actionId.replaceAll('_', ' ')}.`);
    });
  }

  function advance(minutes: number) {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<{ run: Run }>(`/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/advance`, {
        method: 'POST', body: JSON.stringify({ minutes }),
      });
      setRun(result.run); setReplay(null);
      setMessage(`Simulation clock advanced to T+${result.run.simulation_time_min} minutes.`);
    });
  }

  function readPulse() {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<{ state: { sequence?: number; status: string }; recorded: boolean; event?: { seq: number } }>(
        `/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/pulse/step`, { method: 'POST' });
      await loadRun(run.run_id);
      setMessage(result.recorded ? `Pulse snapshot recorded at canonical event ${result.event?.seq ?? 'unknown'}.` : 'No Pulse snapshot was recorded.');
    });
  }

  function saveDocument(kind: 'clinical_note' | 'handover' | 'order') {
    if (!run) return;
    void runBusy(async () => {
      const content = kind === 'clinical_note' ? note : kind === 'handover' ? handover : order;
      const result = await request<{ run: Run; document: { document_version: number } }>(
        `/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/documents`, {
          method: 'POST', body: JSON.stringify({ document_type: kind, content }),
        });
      setRun(result.run); setReplay(null);
      setMessage(`${kind.replaceAll('_', ' ')} saved as version ${result.document.document_version}.`);
    });
  }

  function saveDebrief() {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<{ run: Run }>(
        `/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/debrief`,
        { method: 'POST', body: JSON.stringify({ responses: debriefResponses }) });
      setRun(result.run);
      setMessage('Structured debrief responses saved to the canonical run timeline.');
    });
  }

  function createCounterfactual(actionId: string) {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<Counterfactual>(
        `/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/counterfactual`,
        { method: 'POST', body: JSON.stringify({ omit_action_id: actionId }) });
      setCounterfactual(result);
      setMessage(`Read-only counterfactual fork created without ${actionId.replaceAll('_', ' ')}.`);
    });
  }

  function deriveAssessment() {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<{ run: Run; assessment: Assessment }>(
        `/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/assessment`, { method: 'POST' });
      setRun(result.run);
      setMessage(`Formative breakdown derived: ${result.assessment.score}/${result.assessment.maximum}.`);
    });
  }

  function loadReplay() {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<Replay>(`/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/replay`);
      setReplay(result);
      setMessage(`Replay reconstructed ${result.event_count} simulation events.`);
    });
  }

  function completeRun() {
    if (!run) return;
    void runBusy(async () => {
      const result = await request<{ run: Run }>(`/api/v4/simulation/runs/${encodeURIComponent(run.run_id)}/complete`, { method: 'POST' });
      setRun(result.run);
      setMessage('Run completed and sealed against further simulation mutations.');
    });
  }

  const observations = run ? Object.entries(run.observations) : [];
  const vitals = observations.filter(([key]) => ['heart_rate', 'respiratory_rate', 'spo2', 'blood_pressure', 'temperature', 'peak_flow'].includes(key));
  const textObservations = observations.filter(([key]) => !['heart_rate', 'respiratory_rate', 'spo2', 'blood_pressure', 'temperature', 'peak_flow'].includes(key));
  const activeStage: StageId = replay ? 'debrief' : run?.assessment ? 'assess' : run?.documents.length ? 'document' : run?.actions.length ? 'act' : 'observe';

  function goToStage(id: StageId) {
    // Orient collapses once a run starts, so fall back to the top of the run.
    const target = document.getElementById(`cc-${id}`) ?? document.querySelector('.cc-context');
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return <section className="cc-shell" aria-label="Clinical command centre">
    <header className="cc-intro s-panel">
      <div className="s-panel-body">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="s-eyebrow">Clinical simulation runtime</div>
            <h2 className="s-section-title mt-1">Clinical command centre</h2>
            <p className="s-section-sub max-w-3xl">A deterministic, synthetic patient encounter. Orient, observe, act, advance simulated time, document, receive formative feedback and replay the run.</p>
          </div>
          <div className="s-toolbar">
            <span className="s-badge s-badge-plain">No AI models · Local simulation</span>
            {run?.status === 'completed' && <button type="button" className="s-btn s-btn-secondary" onClick={() => { setRun(null); setReplay(null); setCounterfactual(null); setDebriefResponses({}); setNote(emptyNote); setHandover(emptyHandover); }}>New run</button>}
          </div>
        </div>
        <div className="cc-boundary" role="note">
          <b>Education-only boundary.</b> This is a simplified teaching model, not a validated physiological simulator, treatment protocol or clinical decision-support tool. The scenario and rubric are draft and require qualified clinical educator review before wider use. No medication doses are specified.
        </div>
      </div>
    </header>

    {!run && <section id="cc-orient" className="s-panel">
      <div className="s-panel-head">
        <div><h3 className="s-section-title">Choose a scenario</h3><p className="s-section-sub">The first reference case is a synthetic adult moderate-asthma exercise.</p></div>
        <span className="s-badge s-badge-plain">Phase 1–6 vertical slice</span>
      </div>
      <div className="s-panel-body">
      {selectedScenario ? <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="cc-scenario">
          <div className="flex flex-wrap items-center gap-2"><span className="s-badge s-badge-plain">{selectedScenario.specialty}</span><span className="s-badge s-badge-plain">v{selectedScenario.version}</span><span className="s-badge s-badge-warning">{selectedScenario.clinical_review_status.replaceAll('_', ' ')}</span></div>
          <h4>{selectedScenario.title}</h4>
          <p className="s-section-sub">{selectedScenario.educational_purpose}</p>
          <div className="cc-scenario-row"><b>Opening presentation</b><span>{selectedScenario.patient.presenting_complaint}</span></div>
          <ul className="cc-objectives">{selectedScenario.learning_objectives.map(goal => <li key={goal}>{goal}</li>)}</ul>
          <div className="cc-sources">{selectedScenario.source_basis.map(source => <p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> · {source.publisher} ({source.published})</p>)}</div>
        </div>
        <div className="cc-start">
          <label className="s-eyebrow" htmlFor="simulation-seed">Deterministic seed</label>
          <input id="simulation-seed" type="number" min="0" max="4294967295" step="1" value={seed} onChange={event => setSeed(event.target.value)} className="form-field" />
          <p className="s-section-sub">Same scenario, seed, model versions and ordered actions reproduce the same semantic trace and state digests.</p>
          <button type="button" className="s-btn s-btn-primary" onClick={startRun} disabled={busy || !Number.isInteger(Number(seed)) || Number(seed) < 0 || Number(seed) > 4294967295}>Start simulation</button>
        </div>
      </div> : <p className="s-section-sub">No valid scenarios are currently available.</p>}
      </div>
    </section>}

    {run && <>
      <div className="cc-context" role="region" aria-label="Clinical context">
        <div className="cc-context-identity">
          <span className="s-eyebrow">{run.scenario.patient.display_id} · Seed {run.seed}</span>
          <b>{run.scenario.title}</b>
          <small>Run {run.run_id} · {run.engine_version || 'HSPTL Simulation Runtime'}</small>
        </div>
        <div className="cc-context-metrics">
          <div className="cc-metric"><span>Simulation time</span><b>T+{run.simulation_time_min}m</b></div>
          <div className="cc-metric"><span>Run status</span><b className="cc-status-value">{run.status.replaceAll('_', ' ')}</b></div>
          <div className="cc-metric"><span>Actions</span><b>{run.actions.length} accepted · {run.rejected_actions.length} withheld</b></div>
        </div>
        <nav className="cc-stages" aria-label="Simulation stages">
          {STAGES.map((stage, index) => <button key={stage.id} type="button" className={`cc-stage ${activeStage === stage.id ? 'is-active' : ''}`} aria-current={activeStage === stage.id ? 'step' : undefined} onClick={() => goToStage(stage.id)}>
            <span className="cc-stage-num">{index + 1}</span>{stage.label}
          </button>)}
        </nav>
      </div>

      <section id="cc-observe" className="s-panel">
        <div className="s-panel-head">
          <div><h3 className="s-section-title">Observe</h3><p className="s-section-sub">Current learner observations, event-derived. Unmeasured values are not shown as normal.</p></div>
          <button type="button" className="s-btn s-btn-secondary s-btn-sm" onClick={readPulse} disabled={busy || run.status === 'completed'}>Read Pulse snapshot</button>
        </div>
        <div className="s-panel-body">
          <p className="cc-patient-status">{run.patient_status}</p>
          <div className="cc-vitals">
            {vitals.map(([key, observation]) => <div key={key} className="cc-vital">
              <span className="cc-vital-label">{observation.display}</span>
              <b className="cc-vital-value">{observation.value} <span>{observation.unit}</span></b>
              <span className="cc-vital-status">{observation.status}</span>
            </div>)}
            {!run.observations.peak_flow && <div className="cc-vital cc-vital-pending">
              <span className="cc-vital-label">Peak expiratory flow</span>
              <b className="cc-vital-value cc-vital-missing">Not yet measured</b>
              <span className="cc-vital-status">Not interpreted as normal.</span>
            </div>}
          </div>
          {textObservations.length > 0 && <div className="cc-text-observations">{textObservations.map(([key, observation]) => <div key={key} className="cc-text-observation"><span>{observation.display}</span><p>{String(observation.value)}</p></div>)}</div>}
        </div>
      </section>

      <section id="cc-act" className="cc-act-grid">
        <div className="s-panel">
          <div className="s-panel-head">
            <div><h3 className="s-section-title">Act</h3><p className="s-section-sub">Each action is checked by its versioned PROforma action gate and then passed through the simulation Pulse bridge.</p></div>
          </div>
          <div className="s-panel-body">
            <div className="cc-action-grid">
              {run.available_actions.map(action => <div key={action.id} className={`cc-action ${action.available ? '' : 'is-blocked'}`}>
                <div className="cc-action-head"><b>{action.label}</b><span className={`s-badge ${action.available ? 's-badge-success' : 's-badge-plain'}`}>{action.available ? 'Available' : 'Blocked'}</span></div>
                <p className="s-section-sub">{action.description}</p>
                <p className="cc-action-reason">{action.reason}</p>
                <button type="button" className="s-btn s-btn-secondary s-btn-sm cc-action-btn" onClick={() => performAction(action.id)} disabled={busy || !action.available || run.status === 'completed'}>Perform action</button>
              </div>)}
            </div>
            <div className="cc-clock">
              <div><b>Advance the simulation clock</b><p className="s-section-sub">Scheduled findings and patient-state transitions fire at their authored minute boundaries.</p></div>
              <div className="s-toolbar">{[2, 5, 10, 20, 40].map(minutes => <button key={minutes} type="button" className="s-btn s-btn-secondary s-btn-sm" onClick={() => advance(minutes)} disabled={busy || run.status === 'completed' || run.simulation_time_min + minutes > 180}>+{minutes} min</button>)}</div>
            </div>
          </div>
        </div>
        <aside className="s-panel cc-trace">
          <div className="s-panel-head"><div><h3 className="s-section-title">Timeline</h3><p className="s-section-sub">Actions and withheld actions are immutable event records.</p></div></div>
          <div className="s-panel-body">
            <ol className="cc-trace-list">
              {run.actions.map((action, index) => <li key={action.event_id}>
                <span className="cc-trace-index">{index + 1}</span>
                <div><b>{action.action_id.replaceAll('_', ' ')}</b><small>T+{action.simulation_time_min} · {action.event_id}</small></div>
              </li>)}
              {run.rejected_actions.map(action => <li key={action.event_id} className="is-withheld">
                <span className="cc-trace-index">!</span>
                <div><b>Withheld: {action.action_id.replaceAll('_', ' ')}</b><small>{action.reason}</small></div>
              </li>)}
            </ol>
            {run.actions.length === 0 && run.rejected_actions.length === 0 && <p className="s-section-sub">No learner actions recorded yet.</p>}
          </div>
        </aside>
      </section>

      <section id="cc-document">
        <h3 className="cc-stage-heading"><span>Document</span></h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="s-panel">
            <div className="s-panel-head"><div><h3 className="s-section-title">Clinical note</h3><p className="s-section-sub">Documents are saved as immutable versions. Free-text prose is not automatically graded.</p></div></div>
            <div className="s-panel-body cc-form">
              {([['assessment','Assessment'],['findings','Findings'],['plan','Plan'],['uncertainties','Uncertainties / unknowns']] as const).map(([key,label]) => <label key={key} className="block"><span className="field-label">{label}</span><textarea className="form-field min-h-16 w-full" value={note[key]} onChange={event => setNote(prev => ({ ...prev, [key]: event.target.value }))} maxLength={3000} disabled={run.status === 'completed'} /></label>)}
              <button type="button" className="s-btn s-btn-primary" onClick={() => saveDocument('clinical_note')} disabled={busy || run.status === 'completed'}>Save clinical note version</button>
            </div>
          </div>
          <div className="s-panel">
            <div className="s-panel-head"><div><h3 className="s-section-title">Structured handover</h3><p className="s-section-sub">Communicate the current situation, assessment and outstanding work.</p></div></div>
            <div className="s-panel-body cc-form">
              {([['situation','Situation'],['background','Background'],['assessment','Assessment'],['recommendation','Recommendation'],['outstanding_tasks','Outstanding tasks']] as const).map(([key,label]) => <label key={key} className="block"><span className="field-label">{label}</span><textarea className="form-field min-h-14 w-full" value={handover[key]} onChange={event => setHandover(prev => ({ ...prev, [key]: event.target.value }))} maxLength={2000} disabled={run.status === 'completed'} /></label>)}
              <button type="button" className="s-btn s-btn-secondary" onClick={() => saveDocument('handover')} disabled={busy || run.status === 'completed'}>Submit handover version</button>
            </div>
          </div>
        </div>
        <div className="s-panel mt-4">
          <div className="s-panel-head"><div><h3 className="s-section-title">Scenario orders</h3><p className="s-section-sub">Record an educational order linked to the current simulation time. This does not enter a real medical order system.</p></div></div>
          <div className="s-panel-body">
            <div className="cc-order-grid">
              {([['order_type','Order type'],['display','Order description'],['rationale','Rationale'],['status','Status'],['result_link','Related result or action']] as const).map(([key,label]) =>
                <label key={key} className="block"><span className="field-label">{label}</span><input className="form-field w-full" value={order[key]} maxLength={key === 'rationale' ? 2000 : key === 'display' ? 300 : 160} onChange={event => setOrder(previous => ({...previous, [key]: event.target.value}))} disabled={run.status === 'completed'} /></label>)}
            </div>
            <button type="button" className="s-btn s-btn-primary mt-4" onClick={() => saveDocument('order')} disabled={busy || run.status === 'completed' || !order.order_type.trim() || !order.display.trim()}>Save order version</button>
          </div>
        </div>
      </section>

      <section id="cc-assess" className="s-panel">
        <div className="s-panel-head">
          <div><h3 className="s-section-title">Assess</h3><p className="s-section-sub">Rule-based trace scoring. It measures recorded actions and structured-field completeness, not competence or free-text clinical accuracy.</p></div>
          <button type="button" className="s-btn s-btn-primary" onClick={deriveAssessment} disabled={busy || run.status === 'completed'}>Derive assessment</button>
        </div>
        <div className="s-panel-body">
        {run.assessment && <div>
          <div className="cc-score"><div><span className="s-eyebrow">Formative points</span><b>{run.assessment.score}<span>/{run.assessment.maximum}</span></b></div><div className="cc-score-pct">{run.assessment.percentage}% trace rubric completion</div><span className="s-badge s-badge-plain">{run.assessment.status.replaceAll('_', ' ')}</span></div>
          <div className="cc-criteria">{run.assessment.criteria.map(criterion => <div key={criterion.criterion_id} className="cc-criterion"><div className="cc-criterion-head"><b>{criterion.criterion_id.replaceAll('_', ' ')}</b><b>{criterion.points_earned}/{criterion.points_possible}</b></div><p>{criterion.rationale}</p><small>Evidence event IDs: {criterion.evidence_event_ids.join(', ') || 'None'}</small></div>)}</div>
          {run.assessment.critical_flags.length > 0 && <div className="cc-flags"><b>Educator review flags</b>{run.assessment.critical_flags.map(flag => <p key={flag.code}>{flag.message}</p>)}</div>}
          <p className="cc-digest">Trace digest: {run.assessment.trace_digest}</p>
        </div>}
        {run.documents.length > 0 && <div className="cc-docs"><b>Saved document versions</b><div className="s-toolbar">{run.documents.map(document => <span key={document.event_id} className="s-badge s-badge-plain">{document.document_type.replaceAll('_', ' ')} · v{document.document_version}</span>)}</div></div>}
        <div className="s-toolbar mt-4"><button type="button" className="s-btn s-btn-secondary" onClick={loadReplay} disabled={busy}>Replay run</button><button type="button" className="s-btn s-btn-secondary" onClick={completeRun} disabled={busy || run.status === 'completed' || !run.assessment}>Complete and seal run</button><span className="s-section-sub self-center">A run must have an assessment before it can be sealed.</span></div>
        </div>
      </section>

      {replay && <section className="s-panel">
        <div className="s-panel-head"><div><h3 className="s-section-title">Deterministic replay</h3><p className="s-section-sub">Reconstructed from the immutable event log.</p></div></div>
        <div className="s-panel-body">
          <div className="cc-replay-grid"><div className="cc-replay-stat"><span>Simulation events</span><b>{replay.event_count}</b></div><div className="cc-replay-stat"><span>Accepted actions</span><b>{replay.actions_accepted}</b></div><div className="cc-replay-stat"><span>Withheld actions</span><b>{replay.actions_rejected}</b></div><div className="cc-replay-stat"><span>Semantic replay</span><b>Verified</b></div></div>
          <p className="cc-digest">Semantic trace digest: {replay.semantic_trace_digest}</p><p className="cc-digest">Final state digest: {replay.state_digest}</p>
          <ol className="cc-replay-timeline">{replay.timeline.map(item => <li key={item.event_id}><span className="cc-replay-time">T+{item.simulation_time_min}m</span><div><b>{item.title}</b><p>{item.detail}</p><small>{item.event_id} · seq {item.seq}</small></div></li>)}</ol>
        </div>
      </section>}

      <section id="cc-debrief" className="s-panel">
        <div className="s-panel-head"><div><h3 className="s-section-title">Debrief</h3><p className="s-section-sub">Use the run timeline and assessment evidence to reflect. These prompts are not auto-graded.</p></div></div>
        <div className="s-panel-body">
          <ol className="cc-debrief-list">{run.debrief_prompts.map((prompt, index) => <li key={prompt}>
            <p>{prompt}</p><textarea className="form-field mt-2 min-h-20 w-full" value={debriefResponses[`prompt_${index + 1}`] || ''} onChange={event => setDebriefResponses(previous => ({...previous, [`prompt_${index + 1}`]: event.target.value}))} maxLength={3000} disabled={run.status === 'completed'} />
          </li>)}</ol>
          <button type="button" className="s-btn s-btn-secondary mt-4" onClick={saveDebrief} disabled={busy || run.status === 'completed'}>Save structured debrief</button>
        </div>
      </section>

      {run.actions.length > 0 && <section className="s-panel">
        <div className="s-panel-head"><div><h3 className="s-section-title">Read-only counterfactual replay</h3><p className="s-section-sub">Compare the original run with a bounded fork that removes one accepted action. Forks never mutate the original event log.</p></div></div>
        <div className="s-panel-body">
          <div className="s-toolbar">{run.actions.map(action => <button key={action.event_id} type="button" className="s-btn s-btn-secondary s-btn-sm" disabled={busy} onClick={() => createCounterfactual(action.action_id)}>Remove {action.action_id.replaceAll('_', ' ')}</button>)}</div>
          {counterfactual && <div className="cc-counterfactual">
            <div className="cc-counterfactual-head"><b>Fork: remove {counterfactual.omitted_action_id.replaceAll('_', ' ')}</b><span className="s-badge s-badge-plain">Read-only · original unchanged</span></div>
            <ul>{counterfactual.state_changes.map(item => <li key={item}>{item}</li>)}</ul>
            <p className="cc-digest">Projected state digest: {counterfactual.projected_state_digest}</p>
            {counterfactual.limitations.map(item => <p key={item} className="s-section-sub">{item}</p>)}
          </div>}
        </div>
      </section>}
    </>}

    {error && <p role="alert" className="status-error rounded-xl border border-red-400/30 p-3 text-sm">{error}</p>}
    {message && <p role="status" className="status-success rounded-xl border border-emerald-400/30 p-3 text-sm">{message}</p>}
    {busy && <p className="s-section-sub" role="status">Updating canonical simulation events…</p>}
  </section>;
}
