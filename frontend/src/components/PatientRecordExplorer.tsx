import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { ClinicalCase, ClinicalCaseEvent, ClinicalNarrative, ClinicalPatient, ReasoningFeedback } from '../lib/api';
import { indexClinicalContent, recordIndexedLearningEvent } from '../lib/tagging';

const DEFAULT_FHIR_PATH = '';

const pathwayDomains: Record<string, { history: string[]; examination: string[] }> = {
  Emergency: {
    history: ['Presenting symptom and patient agenda', 'Onset, chronology and progression', 'Associated symptoms', 'Red flags and immediate threats', 'Relevant medical and surgical history', 'Medication, allergy and anticoagulant reconciliation', 'Family, social and exposure history'],
    examination: ['ABCDE / immediate stability assessment', 'General appearance and observations', 'Focused system examination', 'Cardiovascular assessment', 'Respiratory assessment', 'Neurological status', 'Pain, hydration and functional status'],
  },
  Cardiology: {
    history: ['Chest pain characteristics and radiation', 'Dyspnoea, orthopnoea and paroxysmal nocturnal dyspnoea', 'Palpitations, syncope and presyncope', 'Exercise tolerance and functional class', 'Cardiovascular risk factors', 'Cardiac history, devices and procedures', 'Medication, allergy and family history'],
    examination: ['Pulse, rhythm and peripheral perfusion', 'Blood pressure in relevant limbs / positions', 'JVP and fluid status', 'Precordial inspection and auscultation', 'Peripheral oedema and pulses', 'Respiratory signs of congestion'],
  },
  Respiratory: {
    history: ['Cough, sputum and haemoptysis', 'Breathlessness and exercise limitation', 'Wheeze, pleuritic pain and fever', 'Smoking, vaping and occupational exposure', 'Asthma, COPD, infection and thromboembolism history', 'Inhaler use and medication review'],
    examination: ['Respiratory rate, oxygenation and work of breathing', 'Chest inspection and expansion', 'Percussion and air entry', 'Breath sounds and added sounds', 'Signs of respiratory distress', 'Peripheral signs and relevant cardiovascular assessment'],
  },
  Abdominal: {
    history: ['Pain site, onset, character and radiation', 'Vomiting, bowel habit and GI bleeding', 'Appetite, weight change and jaundice', 'Urinary and relevant reproductive symptoms', 'Previous abdominal disease or surgery', 'Medication, alcohol and travel / food exposure'],
    examination: ['General state, hydration and observations', 'Abdominal inspection', 'Palpation including peritonism assessment', 'Percussion and auscultation', 'Hernial orifices when relevant', 'Relevant rectal / pelvic examination only when indicated and consented'],
  },
  Neurology: {
    history: ['Onset and time course of neurological symptoms', 'Weakness, sensory change and speech disturbance', 'Headache, seizure, loss of consciousness', 'Vision, balance and coordination', 'Vascular risk factors and previous events', 'Medication, anticoagulation and substance history'],
    examination: ['Mental status and speech', 'Cranial nerves', 'Motor function, tone and power', 'Reflexes and plantar responses', 'Sensation', 'Coordination and gait when safe'],
  },
};
const pathwayNames = Object.keys(pathwayDomains);
const clinicalDebriefSections = [
  { key: 'setting', title: 'Set the scene', prompt: 'What was the purpose of this exercise, and what would make the learning discussion psychologically safe?', hint: 'Keep the focus on learning, not blame.' },
  { key: 'reactions', title: 'Reactions', prompt: 'What felt difficult, surprising or uncertain? When did your confidence change?', hint: 'Identify the moment and what influenced your confidence.' },
  { key: 'description', title: 'Description', prompt: 'What happened? Separate documented facts, your decisions, interpretations and unavailable information.', hint: 'Do not convert missing source data into normal findings.' },
  { key: 'analysis', title: 'Analysis', prompt: 'Why did you make those decisions? Which evidence supported or opposed your leading hypotheses? What else could explain the findings?', hint: 'Consider prioritisation, investigation choices, safety and uncertainty.' },
  { key: 'summary', title: 'Summary and transfer', prompt: 'What are three transferable learning points, and what observable action will you take in the next case?', hint: 'Finish with one specific improvement goal.' },
];

const investigationGroups = [
  'Laboratory testing', 'ECG / physiological testing', 'Imaging',
  'Microbiology / pathology', 'Bedside tests', 'Record review / collateral information',
];

function EvidenceCard({ section }: { section: ClinicalNarrative['sections'][number] }) {
  return (
    <article className="rounded-lg border border-hsptl-border bg-white p-3 dark:border-hsptl-dark-border dark:bg-slate-900/60">
      <div className="flex items-center justify-between gap-2">
        <h5 className="text-xs font-bold">{section.title}</h5>
        <span className={`text-[9px] font-bold uppercase ${section.availability === 'documented' ? 'text-hsptl-teal' : 'text-amber-700 dark:text-amber-300'}`}>{section.availability}</span>
      </div>
      {section.items.length ? (
        <ul className="mt-2 space-y-2">{section.items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="text-xs">
            <span className="font-semibold">{item.label}</span>
            {item.value && <span className="ml-1 font-mono">{item.value}</span>}
            {item.conclusion && <p className="muted mt-0.5">{item.conclusion}</p>}
            <span className="muted mt-0.5 block text-[10px]">{item.date || 'Date not recorded'} · {item.provenance}</span>
          </li>
        ))}</ul>
      ) : <p className="muted mt-2 text-[11px]">{section.note}</p>}
    </article>
  );
}


export default function PatientRecordExplorer() {
  const [path, setPath] = useState(DEFAULT_FHIR_PATH);
  const [patients, setPatients] = useState<ClinicalPatient[]>([]);
  const [selected, setSelected] = useState<ClinicalCase | null>(null);
  const [selectedKey, setSelectedKey] = useState('');
  const [narrative, setNarrative] = useState<ClinicalNarrative | null>(null);
  const [problem, setProblem] = useState('');
  const [differentials, setDifferentials] = useState('');
  const [evidenceFor, setEvidenceFor] = useState('');
  const [evidenceAgainst, setEvidenceAgainst] = useState('');
  const [investigationPlan, setInvestigationPlan] = useState('');
  const [workingDiagnosis, setWorkingDiagnosis] = useState('');
  const [managementPlan, setManagementPlan] = useState('');
  const [safetyNet, setSafetyNet] = useState('');
  const [communicationPlan, setCommunicationPlan] = useState('');
  const [activeStage, setActiveStage] = useState(1);
  const [confidence, setConfidence] = useState(3);
  const [savingAttempt, setSavingAttempt] = useState(false);
  const [attemptMessage, setAttemptMessage] = useState('');
  const [reasoningFeedback, setReasoningFeedback] = useState<ReasoningFeedback | null>(null);
  const [caseEvents, setCaseEvents] = useState<ClinicalCaseEvent[]>([]);
  const [savedAttemptId, setSavedAttemptId] = useState('');
  const [pearlFocus, setPearlFocus] = useState('Investigation strategy');
  const [pearlReflection, setPearlReflection] = useState('');
  const [creatingPearl, setCreatingPearl] = useState(false);
  const [pearlMessage, setPearlMessage] = useState('');
  const [debriefResponses, setDebriefResponses] = useState<Record<string, string>>({});
  const [debriefSaving, setDebriefSaving] = useState(false);
  const [debriefMessage, setDebriefMessage] = useState('');
  const [revealedSections, setRevealedSections] = useState<string[]>([]);
  const [specialtyPathway, setSpecialtyPathway] = useState('Emergency');
  const [historyFocus, setHistoryFocus] = useState<string[]>([]);
  const [examinationFocus, setExaminationFocus] = useState<string[]>([]);
  const [investigationFocus, setInvestigationFocus] = useState<string[]>([]);
  const [encounterKey, setEncounterKey] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const requestedEvidence = narrative?.sections.filter((section) => revealedSections.includes(section.title)) ?? [];

  async function loadPatients(nextOffset = 0) {
    setLoading(true);
    setError('');
    try {
      const result = await api.clinicalPatients(50, nextOffset);
      setPatients(result.items);
      setTotal(result.total);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load imported patients.');
    } finally { setLoading(false); }
  }

  useEffect(() => { void loadPatients(); }, []);

  useEffect(() => {
    if (!savedAttemptId) return;
    let active = true;
    void api.clinicalDebrief(savedAttemptId).then((result) => { if (active) setDebriefResponses(result.responses); }).catch(() => { if (active) setDebriefResponses({}); });
    return () => { active = false; };
  }, [savedAttemptId]);

  async function importFHIR() {
    setImporting(true); setError(''); setMessage('');
    try {
      const result = await api.importFHIR(path.trim());
      setMessage(`Imported ${result.patients} patients, ${result.encounters} encounters and ${result.facts} clinical facts. ${result.skipped_unchanged} unchanged files skipped${result.errors ? `; ${result.errors} file errors` : ''}.`);
      await loadPatients();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'FHIR import failed.');
    } finally { setImporting(false); }
  }

  async function openPatient(key: string, encounter = '') {
    setSelectedKey(key); setEncounterKey(encounter); setNarrative(null); setAttemptMessage(''); setReasoningFeedback(null); setCaseEvents([]); setSavedAttemptId(''); setPearlMessage(''); setPearlReflection(''); setDebriefResponses({}); setDebriefMessage(''); setRevealedSections([]); setHistoryFocus([]); setExaminationFocus([]); setInvestigationFocus([]); setSpecialtyPathway('Emergency'); setActiveStage(1); setError('');
    try { setSelected(await api.clinicalCase(key, encounter || undefined)); }
    catch (err) { setSelected(null); setError(err instanceof Error ? err.message : 'Could not load this patient record.'); }
  }

  async function chooseEncounter(value: string) {
    setEncounterKey(value);
    setNarrative(null); setAttemptMessage(''); setReasoningFeedback(null); setCaseEvents([]); setSavedAttemptId(''); setPearlMessage(''); setPearlReflection(''); setDebriefResponses({}); setDebriefMessage(''); setRevealedSections([]); setActiveStage(1);
    if (selectedKey) {
      await openPatient(selectedKey, value);
      if (value) {
        try { setNarrative(await api.clinicalNarrative(selectedKey, value)); }
        catch (err) { setError(err instanceof Error ? err.message : 'Could not build the encounter learning draft.'); }
      }
    }
  }

  async function saveAttempt() {
    if (!selectedKey || !encounterKey || !narrative || savingAttempt) return;
    setSavingAttempt(true); setAttemptMessage('');
    setCaseEvents([]);
    try {
      const result = await api.saveClinicalAttempt({
        patient_key: selectedKey, encounter_key: encounterKey, case_code: narrative.case_code,
        problem_representation: [
          problem,
          historyFocus.length ? `\n\nLearner-selected history domains to clarify (not source findings):\n- ${historyFocus.join('\n- ')}` : '',
          examinationFocus.length ? `\n\nLearner-selected examination domains to perform (not source findings):\n- ${examinationFocus.join('\n- ')}` : '',
        ].join('').trim(),
        differentials: differentials.split('\n').map((item) => item.trim()).filter(Boolean).slice(0, 8),
        evidence_for: evidenceFor, evidence_against: evidenceAgainst,
        investigation_plan: [investigationPlan, investigationFocus.length ? `\n\nInvestigation categories selected for consideration (not recommendations or results):\n- ${investigationFocus.join('\n- ')}` : ''].join('').trim(),
        working_diagnosis: workingDiagnosis, management_plan: managementPlan, safety_net: safetyNet,
        communication_plan: communicationPlan, stage_completed: activeStage, confidence,
        history_plan: historyFocus, examination_plan: examinationFocus, investigation_selection: investigationFocus, specialty_pathway: specialtyPathway,
      });
      setSavedAttemptId(result.attempt_id);
      await indexClinicalContent({ content_type: 'debrief', content_id: result.attempt_id, title: `Case debrief · ${narrative.case_code}`, workspace: 'clinic', summary: problem, source_status: 'synthetic', tag_pairs: [['specialty', specialtyPathway], ['task', 'Clinical Reasoning']] });
      await recordIndexedLearningEvent('debrief', result.attempt_id, { action: 'completed' });
      setAttemptMessage(`Reasoning draft saved · ${result.attempt_id.slice(0, 8)}`);
      setReasoningFeedback(result.feedback);
      setCaseEvents(result.case_events);
    } catch (err) { setAttemptMessage(err instanceof Error ? err.message : 'Could not save this reasoning draft.'); }
    finally { setSavingAttempt(false); }
  }

  async function saveGuidedDebrief() {
    if (!savedAttemptId || debriefSaving) return;
    setDebriefSaving(true); setDebriefMessage('');
    try {
      const result = await api.saveClinicalDebrief(savedAttemptId, debriefResponses);
      setDebriefResponses(result.responses);
      setDebriefMessage(`Debrief saved · ${result.completed}/${result.total} sections completed`);
    } catch (err) { setDebriefMessage(err instanceof Error ? err.message : 'Could not save the debrief.'); }
    finally { setDebriefSaving(false); }
  }

  async function createReflectionPearl() {
    if (!savedAttemptId || pearlReflection.trim().length < 10 || creatingPearl) return;
    setCreatingPearl(true); setPearlMessage('');
    try {
      const result = await api.createLearningPearl(savedAttemptId, pearlFocus, pearlReflection.trim());
      await indexClinicalContent({ content_type: 'pearl', content_id: result.id, title: result.title, workspace: 'rounds', summary: pearlReflection.trim(), source_status: 'draft', tag_pairs: [['task', 'Clinical Reasoning'], ['level', 'Clinical Years']] });
      setPearlMessage(`Saved to Pearls: ${result.title}`);
    } catch (err) {
      setPearlMessage(err instanceof Error ? err.message : 'Could not save this reflection to Pearls.');
    } finally { setCreatingPearl(false); }
  }

  return (
    <section className="klinika-card overflow-hidden">
      <details>
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-5">
          <span>
            <span className="block text-sm font-bold">Synthea patient records</span>
            <span className="muted mt-1 block text-xs">Encounter-linked source data · {total.toLocaleString()} imported patients</span>
          </span>
          <span className="rounded-lg border border-hsptl-border px-3 py-2 text-xs font-semibold dark:border-hsptl-dark-border">Explore records</span>
        </summary>
        <div className="space-y-4 border-t border-hsptl-border p-4 dark:border-hsptl-dark-border sm:p-5">
          <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900/50">
            <label className="mb-2 block text-xs font-bold" htmlFor="fhir-source-path">FHIR source folder</label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input id="fhir-source-path" className="form-field min-w-0 flex-1" value={path} onChange={(event) => setPath(event.target.value)} placeholder="Path to your local FHIR folder, e.g. /data/synthea/fhir" />
              <button type="button" className="primary-button shrink-0" onClick={() => void importFHIR()} disabled={importing || !path.trim()}>
                {importing ? 'Importing…' : 'Import / update FHIR'}
              </button>
            </div>
            <p className="muted mt-2 text-xs">Imports are local and rerunnable. JSON files are limited to 32 MB each; records are saved in batches. Source files are never modified.</p>
          </div>
          {message && <p role="status" aria-live="polite" className="status-success text-sm">{message}</p>}
          {error && <p role="alert" aria-live="assertive" className="status-error text-sm">{error}</p>}
          <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.8fr)_minmax(0,1.6fr)]">
            <div className="min-w-0">
              <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-bold">Patients</h3><span className="muted text-xs">{total.toLocaleString()} total</span></div>
              <div className="max-h-[420px] space-y-1 overflow-y-auto rounded-lg border border-hsptl-border p-1 dark:border-hsptl-dark-border">
                {patients.map((patient) => (
                  <button key={patient.patient_key} type="button" aria-pressed={selectedKey === patient.patient_key} onClick={() => void openPatient(patient.patient_key)} className={`w-full rounded-md px-3 py-2 text-left ${selectedKey === patient.patient_key ? 'bg-hsptl-indigo/10 text-hsptl-indigo dark:text-indigo-200' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}>
                    <span className="flex items-center justify-between gap-2">
                      <span className="block truncate text-sm font-semibold">{patient.name || 'Unnamed synthetic patient'}</span>
                      {selectedKey === patient.patient_key && <span className="shrink-0 text-[10px] font-bold">Selected</span>}
                    </span>
                    <span className="muted mt-0.5 block text-xs">{patient.birth_date || 'DOB not recorded'} · {patient.gender || 'Gender not recorded'}</span>
                    <span className="muted block text-[11px]">{patient.encounter_count} encounters · {patient.fact_count} facts</span>
                  </button>
                ))}
                {!patients.length && <p className="muted p-3 text-xs">No FHIR patients imported yet.</p>}
              </div>
              <div className="mt-2 flex items-center justify-between">
                <button className="secondary-button text-xs" disabled={loading || offset === 0} onClick={() => void loadPatients(Math.max(0, offset - 50))}>Previous</button>
                <span className="muted text-[11px]">{total ? offset + 1 : 0}–{Math.min(offset + patients.length, total)}</span>
                <button className="secondary-button text-xs" disabled={loading || offset + patients.length >= total} onClick={() => void loadPatients(offset + 50)}>Next</button>
              </div>
            </div>
            <div className="min-w-0">
              {!selected ? (
                <div className="flex min-h-48 items-center justify-center rounded-lg border border-dashed border-hsptl-border p-5 text-center dark:border-hsptl-dark-border"><p className="muted text-sm">Select a patient to inspect documented encounters and clinical facts.</p></div>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div><h3 className="text-base font-bold">{selected.patient.name || 'Unnamed synthetic patient'}</h3><p className="muted mt-1 text-xs">{selected.patient.birth_date || 'DOB not recorded'} · {selected.patient.gender || 'Gender not recorded'} · Synthetic source record</p></div>
                    <span className="rounded-full bg-hsptl-teal/10 px-2.5 py-1 text-[11px] font-semibold text-hsptl-teal">Source documented</span>
                  </div>
                  <div>
                    <label htmlFor="encounter-filter" className="mb-1 block text-xs font-semibold">Encounter view</label>
                    <select id="encounter-filter" className="form-field" value={encounterKey} onChange={(event) => void chooseEncounter(event.target.value)}>
                      <option value="">Full patient timeline</option>
                      {selected.encounters.map((encounter) => <option key={encounter.encounter_key} value={encounter.encounter_key}>{encounter.start_at || 'Date not recorded'} · {encounter.encounter_type || 'Encounter'} · {encounter.status || 'Status unavailable'}</option>)}
                    </select>
                  </div>
                  <div className="rounded-lg border border-hsptl-border p-3 dark:border-hsptl-dark-border">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-bold">Record quality</span>
                      <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${selected.quality.ready_for_human_review ? 'bg-hsptl-teal/10 text-hsptl-teal' : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'}`}>{selected.quality.record_status.replaceAll('_', ' ')}</span>
                    </div>
                    <p className="muted mt-1 text-[11px]">{selected.quality.assessment_scope}</p>
                    {selected.quality.flags.length > 0 && <ul className="mt-2 space-y-1">{selected.quality.flags.map((flag) => <li key={flag.code} className="text-xs text-secondary">• {flag.message}</li>)}</ul>}
                    <p className="mt-2 text-[11px] font-semibold text-amber-700 dark:text-amber-300">Not eligible as a diagnostic puzzle without clinical curation and review.</p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded-md bg-slate-100 px-2 py-1 dark:bg-slate-800">{selected.encounters.length} encounters</span>
                    <span className="rounded-md bg-slate-100 px-2 py-1 dark:bg-slate-800">{selected.facts.length} facts in view</span>
                    {selected.unlinked_facts > 0 && <span className="rounded-md bg-amber-500/10 px-2 py-1 text-amber-700 dark:text-amber-300">{selected.unlinked_facts} not linked to an encounter</span>}
                  </div>
                  {narrative && (
                    <section className="space-y-3 rounded-xl border border-hsptl-teal/30 bg-hsptl-teal/5 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div><div className="text-[10px] font-bold uppercase tracking-[.14em] text-hsptl-teal">Encounter learning draft</div><h4 className="mt-1 text-base font-bold">{narrative.case_code}</h4><p className="muted mt-1 text-[10px]">{narrative.patient_context.age !== null ? `${narrative.patient_context.age} years at encounter · derived from documented dates` : 'Age unavailable'} · {narrative.encounter.start_at || 'Encounter date unavailable'}</p></div>
                        <span className="rounded-full bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-700 dark:text-amber-300">Not a diagnostic case</span>
                      </div>
                      <p className="muted text-xs">{narrative.clinical_prompt}</p>
                      <div className="rounded-xl border border-hsptl-border bg-white p-3 dark:border-hsptl-dark-border dark:bg-slate-900/60">
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h5 className="text-sm font-bold">Five-stage clinical encounter</h5><p className="muted text-[11px]">Move through the encounter in order. Your notes remain in this workspace until you save them.</p></div><span className="font-mono text-xs font-bold">{activeStage}/5</span></div>
                        <div role="group" aria-label="Clinical encounter stages" className="grid grid-cols-5 gap-1">
                          {['Assess','Investigate','Reason','Plan','Debrief'].map((label, index) => {
                            const current = activeStage === index + 1;
                            const complete = activeStage > index + 1;
                            const stageStatus = current ? 'current' : complete ? 'complete' : 'upcoming';
                            return <button key={label} type="button" onClick={() => setActiveStage(index + 1)} aria-label={`Stage ${index + 1}: ${label}, ${stageStatus}`} aria-current={current ? 'step' : undefined} className={`min-h-11 rounded-md px-1 py-2 text-[10px] font-bold ${current ? 'bg-hsptl-indigo text-white' : complete ? 'bg-hsptl-teal/10 text-hsptl-teal' : 'bg-slate-100 text-secondary dark:bg-slate-800'}`}><span className="block">{index + 1}. {label}</span><span aria-hidden="true" className="mt-1 block text-[8px] uppercase leading-tight">{current ? 'Current' : complete ? 'Complete' : 'Upcoming'}</span></button>;
                          })}
                        </div>
                      </div>
                      {activeStage === 2 && <div className="rounded-xl border border-hsptl-border bg-white p-3 dark:border-hsptl-dark-border dark:bg-slate-900/60">
                        <h5 className="text-xs font-bold">Request encounter evidence</h5>
                        <p className="muted mt-1 text-[11px]">Choose which documented record groups to inspect. Only facts explicitly linked to this encounter are available here.</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {narrative.sections.slice(3).map((section) => <button key={section.title} type="button" onClick={() => setRevealedSections((current) => current.includes(section.title) ? current : [...current, section.title])} disabled={revealedSections.includes(section.title)} className="secondary-button text-[11px] disabled:cursor-default disabled:opacity-60">{revealedSections.includes(section.title) ? 'Viewed · ' : 'Request · '}{section.title}</button>)}
                        </div>
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><span className="muted text-[10px]">{revealedSections.length} of {narrative.sections.length - 3} groups viewed</span><button type="button" className="inline-flex min-h-6 items-center px-2 text-[11px] font-semibold text-hsptl-indigo dark:text-indigo-300" onClick={() => setRevealedSections(narrative.sections.slice(3).map((section) => section.title))}>Review all available groups</button></div>
                      </div>}
                      {activeStage === 3 ? (
                        <details open className="rounded-lg border border-hsptl-teal/30 bg-hsptl-teal/5 p-3">
                          <summary className="cursor-pointer text-xs font-bold text-hsptl-teal">Evidence requested during Investigation ({requestedEvidence.length} groups)</summary>
                          {requestedEvidence.length ? (
                            <div className="mt-3 grid gap-2 sm:grid-cols-2">
                              {requestedEvidence.map((section) => <EvidenceCard key={section.title} section={section}/>)}
                            </div>
                          ) : (
                            <p className="muted mt-2 text-xs">No source groups have been requested yet. Return to Investigation to request encounter evidence.</p>
                          )}
                        </details>
                      ) : (
                        <div className="grid gap-2 sm:grid-cols-2">
                          {narrative.sections.filter((section, index) => activeStage === 1 ? index <= 2 : revealedSections.includes(section.title)).map((section) => (
                            <EvidenceCard key={section.title} section={section}/>
                          ))}
                          {activeStage >= 4 && revealedSections.length === 0 && <p className="muted rounded-lg border border-dashed border-hsptl-border p-3 text-xs dark:border-hsptl-dark-border">No source groups have been requested yet. Return to Investigation to request encounter evidence.</p>}
                        </div>
                      )}
                      <div className="space-y-3 border-t border-hsptl-teal/20 pt-3">
                        <div><h5 className="text-sm font-bold">{['Initial assessment','Investigation strategy','Clinical reasoning','Management and safety','Debrief and save'][activeStage - 1]}</h5><p className="muted mt-1 text-xs">{['Build a concise representation and identify what history or examination you would obtain. Missing source data is not a normal finding.','Review only encounter-linked results. Explain why each additional test is needed and how it could change your next step.','Prioritise alternatives and connect each one to evidence for and against. The source record does not provide a validated answer.','Record a learning-level plan, escalation considerations and how you would communicate uncertainty. Do not use this as patient-specific treatment advice.','Review your confidence and save the learning attempt. Feedback checks documentation coverage, not diagnostic correctness.'][activeStage - 1]}</p></div>
                        {activeStage === 1 && <div className="space-y-3">
                          <label className="block text-xs font-semibold">Clinical pathway<select className="form-field mt-1" value={specialtyPathway} onChange={(event) => { setSpecialtyPathway(event.target.value); setHistoryFocus([]); setExaminationFocus([]); }}><option value="Emergency">Emergency / acute assessment</option>{pathwayNames.filter((name) => name !== 'Emergency').map((name) => <option key={name} value={name}>{name}</option>)}</select><span className="muted mt-1 block text-[10px]">This changes the suggested assessment domains; it does not infer findings or prescribe a pathway.</span></label>
                          <label className="block text-xs font-semibold">Problem representation<textarea className="form-field mt-1 min-h-24" value={problem} onChange={(e) => setProblem(e.target.value)} placeholder="Summarise age/context, timeframe and key documented findings. State what is unavailable…" /></label>
                          <div className="rounded-lg border border-hsptl-border p-3 dark:border-hsptl-dark-border">
                            <h6 className="text-xs font-bold">What would you clarify?</h6>
                            <p className="muted mt-1 text-[10px]">Choose assessment domains you would ask about. These are your planned questions, not answers contained in the source record.</p>
                            <div className="mt-2 grid gap-3 sm:grid-cols-2">
                              <div><p className="mb-2 text-[11px] font-semibold">History</p><div className="space-y-2">{pathwayDomains[specialtyPathway].history.map((item) => <label key={item} className="flex items-start gap-2 text-[11px]"><input type="checkbox" className="mt-0.5 h-6 w-6 shrink-0 accent-hsptl-indigo" checked={historyFocus.includes(item)} onChange={(e) => setHistoryFocus((current) => e.target.checked ? [...current, item] : current.filter((value) => value !== item))} /><span>{item}</span></label>)}</div></div>
                              <div><p className="mb-2 text-[11px] font-semibold">Examination</p><div className="space-y-2">{pathwayDomains[specialtyPathway].examination.map((item) => <label key={item} className="flex items-start gap-2 text-[11px]"><input type="checkbox" className="mt-0.5 h-6 w-6 shrink-0 accent-hsptl-indigo" checked={examinationFocus.includes(item)} onChange={(e) => setExaminationFocus((current) => e.target.checked ? [...current, item] : current.filter((value) => value !== item))} /><span>{item}</span></label>)}</div></div>
                            </div>
                          </div>
                        </div>}
                        {activeStage === 2 && <><div className="rounded-lg bg-amber-500/5 p-3 text-xs text-secondary">The source may not contain a complete investigation set. Do not interpret absent tests or measurements as normal.</div><div className="rounded-lg border border-hsptl-border p-3 dark:border-hsptl-dark-border"><h6 className="text-xs font-bold">Investigation categories to consider</h6><p className="muted mt-1 text-[10px]">Select categories relevant to the question you are trying to answer. This is a learner plan, not a test recommendation or a claim that a test was performed. Your selections are saved with this learning attempt.</p><div className="mt-2 grid gap-2 sm:grid-cols-2">{investigationGroups.map((item) => <label key={item} className="flex items-center gap-2 text-[11px]"><input type="checkbox" className="h-6 w-6 shrink-0 accent-hsptl-indigo" checked={investigationFocus.includes(item)} onChange={(e) => setInvestigationFocus((current) => e.target.checked ? [...current, item] : current.filter((value) => value !== item))} /><span>{item}</span></label>)}</div></div><label className="block text-xs font-semibold">Clinical question, rationale and decision impact<textarea className="form-field mt-1 min-h-28" value={investigationPlan} onChange={(e) => setInvestigationPlan(e.target.value)} placeholder="For each proposed investigation: what question are you answering, why is it relevant, what result would you anticipate, and how could it change your next decision?…" /></label></>}
                        {activeStage === 3 && <><label className="block text-xs font-semibold">Differential diagnoses <span className="muted font-normal">(one per line, prioritised)</span><textarea className="form-field mt-1 min-h-24" value={differentials} onChange={(e) => setDifferentials(e.target.value)} placeholder={'1. Most likely possibility\n2. Important alternative\n3. Cannot-miss diagnosis'} /></label><div className="grid gap-3 sm:grid-cols-2"><label className="block text-xs font-semibold">Evidence supporting your leading diagnosis<textarea className="form-field mt-1 min-h-24" value={evidenceFor} onChange={(e) => setEvidenceFor(e.target.value)} placeholder="Link specific documented findings…" /></label><label className="block text-xs font-semibold">Evidence against / uncertainty<textarea className="form-field mt-1 min-h-24" value={evidenceAgainst} onChange={(e) => setEvidenceAgainst(e.target.value)} placeholder="Contradictions, missing data and what would change your view…" /></label></div></>}
                        {activeStage === 4 && <><label className="block text-xs font-semibold">Working diagnosis<textarea className="form-field mt-1 min-h-16" value={workingDiagnosis} onChange={(e) => setWorkingDiagnosis(e.target.value)} placeholder="Your current working impression (not graded for correctness)…" /></label><label className="block text-xs font-semibold">Learning-level management plan<textarea className="form-field mt-1 min-h-24" value={managementPlan} onChange={(e) => setManagementPlan(e.target.value)} placeholder="Immediate priorities, further assessment, review and senior/local guideline input…" /></label><div className="grid gap-3 sm:grid-cols-2"><label className="block text-xs font-semibold">Safety-netting and escalation<textarea className="form-field mt-1 min-h-20" value={safetyNet} onChange={(e) => setSafetyNet(e.target.value)} placeholder="Deterioration signs, escalation triggers and follow-up…" /></label><label className="block text-xs font-semibold">Communication and shared decisions<textarea className="form-field mt-1 min-h-20" value={communicationPlan} onChange={(e) => setCommunicationPlan(e.target.value)} placeholder="Explanation, consent, uncertainty and patient priorities…" /></label></div></>}
                        {activeStage === 5 && <div className="space-y-3 rounded-lg bg-slate-50 p-3 dark:bg-slate-900/60"><div className="text-xs"><strong>Working impression:</strong> {workingDiagnosis || 'Not recorded'}</div><div className="text-xs"><strong>Differentials:</strong> {differentials.trim() ? differentials.split('\n').filter(Boolean).join(' · ') : 'Not recorded'}</div><div className="text-xs"><strong>Plan:</strong> {managementPlan || 'Not recorded'}</div><label className="block text-xs font-semibold">Confidence in your current reasoning: {confidence}/5<input className="mt-2 block min-h-6 w-full accent-hsptl-indigo" type="range" min="1" max="5" value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} /><span className="muted mt-1 block text-[10px]">1 = very uncertain · 5 = highly confident. Compare confidence with later feedback and review.</span></label><p className="muted text-xs">Reflection: what specific new evidence would most increase or decrease your confidence?</p></div>}
                        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-hsptl-border pt-3 dark:border-hsptl-dark-border"><button type="button" className="secondary-button text-xs" onClick={() => setActiveStage((stage) => Math.max(1, stage - 1))} disabled={activeStage === 1}>Previous stage</button><div className="flex flex-wrap gap-2"><button type="button" className="secondary-button text-xs" onClick={() => void saveAttempt()} disabled={savingAttempt}>{savingAttempt ? 'Saving…' : 'Save draft'}</button>{activeStage < 5 ? <button type="button" className="primary-button text-xs" onClick={() => setActiveStage((stage) => Math.min(5, stage + 1))}>Continue</button> : <button type="button" className="primary-button text-xs" onClick={() => void saveAttempt()} disabled={savingAttempt}>{savingAttempt ? 'Saving…' : 'Save and review'}</button>}</div></div>
                        {attemptMessage && <p role="status" aria-live="polite" className="text-xs font-semibold text-hsptl-teal">{attemptMessage}</p>}
                        {reasoningFeedback && <div className="rounded-xl border border-hsptl-border bg-slate-50 p-3 dark:border-hsptl-dark-border dark:bg-slate-900/50">
                          <div className="flex flex-wrap items-center justify-between gap-2"><h6 className="text-xs font-bold">{reasoningFeedback.label}</h6><span className="font-mono text-xs font-bold">{reasoningFeedback.completed}/{reasoningFeedback.total} documented</span></div>
                          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"><div className="h-full rounded-full bg-hsptl-teal" style={{ width: `${reasoningFeedback.coverage_percent}%` }} /></div>
                          <ul className="mt-3 space-y-2">{reasoningFeedback.dimensions.map((item) => <li key={item.id} className="flex gap-2 text-xs"><span className={item.documented ? 'text-hsptl-teal' : 'text-amber-600'}>{item.documented ? '✓' : '○'}</span><span><strong>{item.label}</strong>{item.suggestion && <span className="muted block">{item.suggestion}</span>}</span></li>)}</ul>
                          <p className="muted mt-3 text-[10px]">Completeness only — this does not grade diagnostic accuracy or clinical competence.</p>
                        </div>}
                        {caseEvents.length > 0 && <section aria-label="Case reflection prompts" className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
                          <h6 className="text-xs font-bold">Case reflection prompts</h6>
                          <ul className="mt-2 space-y-2">{caseEvents.map((event) => <li key={event.id} className="text-xs"><strong>{event.title}</strong><p className="muted mt-1">{event.message}</p></li>)}</ul>
                          <p className="muted mt-2 text-[10px]">Automated prompts support learning only; they are not clinical triage or care advice.</p>
                        </section>}
                        {savedAttemptId && <div className="rounded-xl border border-hsptl-indigo/20 p-3 dark:border-hsptl-dark-border">
                          <div className="flex flex-wrap items-center justify-between gap-2"><div><div className="text-xs font-bold">Structured clinical debrief</div><p className="muted mt-1 text-[10px]">A five-part reflection tied to this saved attempt. Completion is tracked; answers are not clinically graded.</p></div><span className="rounded-full bg-hsptl-indigo/10 px-2 py-1 text-[10px] font-bold text-hsptl-indigo dark:text-indigo-200">{clinicalDebriefSections.filter((section) => (debriefResponses[section.key] || '').trim()).length}/5</span></div>
                          <div className="mt-3 space-y-3">{clinicalDebriefSections.map((section, index) => <label key={section.key} className="block rounded-lg bg-hsptl-surface/70 p-3 dark:bg-hsptl-dark-surface"><span className="text-[11px] font-bold">{index + 1}. {section.title}</span><span className="mt-1 block text-xs">{section.prompt}</span><span className="muted mt-1 block text-[10px]">{section.hint}</span><textarea className="form-field mt-2 min-h-16" value={debriefResponses[section.key] || ''} onChange={(event) => setDebriefResponses((current) => ({ ...current, [section.key]: event.target.value }))} placeholder="Your reflection…" /></label>)}</div>
                          <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><span className="muted text-[10px]">Saved locally · attempt-linked · learner-authored</span><button type="button" className="secondary-button text-xs" onClick={() => void saveGuidedDebrief()} disabled={debriefSaving}>{debriefSaving ? 'Saving…' : 'Save structured debrief'}</button></div>
                          {debriefMessage && <p role="status" aria-live="polite" className="mt-2 text-xs font-semibold text-hsptl-teal">{debriefMessage}</p>}
                        </div>}
                        {savedAttemptId && <div className="rounded-xl border border-hsptl-teal/30 bg-hsptl-teal/5 p-3 dark:border-hsptl-teal/20">
                          <div className="text-xs font-bold">Turn a learning gap into a Pearl</div>
                          <p className="muted mt-1 text-[10px]">This saves your own reflection and attempt notes to Pearls. It does not add clinical recommendations or references.</p>
                          <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,180px)_1fr]">
                            <label className="text-[11px] font-semibold">Learning focus<select className="form-field mt-1" value={pearlFocus} onChange={(e) => setPearlFocus(e.target.value)}><option>Investigation strategy</option><option>Differential prioritisation</option><option>Clinical uncertainty</option><option>Safety-netting</option><option>Communication</option><option>History and examination</option></select></label>
                            <label className="text-[11px] font-semibold">What will you review or do differently?<textarea className="form-field mt-1 min-h-16" value={pearlReflection} onChange={(e) => setPearlReflection(e.target.value)} placeholder="Write a specific learning action or reflection (at least 10 characters)…" /></label>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center justify-between gap-2"><span className="muted text-[10px]">Saved locally · learner-authored · unverified</span><button type="button" className="teal-button text-xs" onClick={() => void createReflectionPearl()} disabled={creatingPearl || pearlReflection.trim().length < 10}>{creatingPearl ? 'Saving…' : 'Save reflection to Pearls'}</button></div>
                          {pearlMessage && <p role="status" aria-live="polite" className="mt-2 text-xs font-semibold text-hsptl-teal">{pearlMessage}</p>}
                        </div>}
                      </div>
                      <ul className="list-disc space-y-1 pl-4 text-[10px] text-secondary">{narrative.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
                    </section>
                  )}
                  {!narrative && <div className="rounded-lg border border-dashed border-hsptl-border p-3 text-xs muted dark:border-hsptl-dark-border">Select a specific encounter to begin a staged learning review. The full timeline is available for record exploration, but it is not presented as a diagnostic puzzle.</div>}
                  <div className="rounded-lg bg-amber-500/5 p-3 text-xs text-secondary">
                    <strong>Data limitations</strong>
                    <ul className="mt-1 list-disc space-y-1 pl-4">{selected.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </details>
    </section>
  );
}
