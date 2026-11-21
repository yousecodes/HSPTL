import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Icon } from '../components/Icon';
import DailyCaseLottery from '../components/DailyCaseLottery';

type Field = { key: string; label: string; prompt: string; rows?: number };
type WorkflowConfig = { id: string; title: string; eyebrow: string; description: string; sourceType?: 'curated_case' | 'fhir_encounter'; fields: Field[]; guidance: string[]; completion: string };
type Episode = { episode_id: string; source_id: string; learning_goal: string; specialty: string; status: string; stage: number; draft_revision: number; updated_at: string; draft?: Record<string, string> };

const configs: Record<string, WorkflowConfig> = {
  conference: { id:'conference', title:'Case Conference', eyebrow:'CLINIC · MULTIDISCIPLINARY REVIEW', description:'Structure a case discussion around the clinical timeline, uncertainty, decision points and agreed learning. This is a learner-authored conference record, not a validated diagnosis.', fields:[{key:'case_summary',label:'Case presentation and timeline',prompt:'Present the relevant history, examination, investigations and chronology.'},{key:'problem_list',label:'Problem representation and problem list',prompt:'Summarise the case and list active problems.'},{key:'differential',label:'Differential diagnosis and uncertainty',prompt:'Rank plausible alternatives. State evidence for, evidence against and unresolved uncertainty.'},{key:'decision_points',label:'Decision points',prompt:'Which decisions materially affected care? What alternatives were considered?'},{key:'team_discussion',label:'Team discussion',prompt:'Record contributions, disagreements and questions requiring follow-up.'},{key:'learning_actions',label:'Learning points and actions',prompt:'Record actions, owner and review date.'}], guidance:['Separate observed facts from interpretation.','Record uncertainty and missing data explicitly.','Do not label a diagnosis as confirmed unless the source record supports it.'], completion:'Conference record saved' },
  procedure: { id:'procedure', title:'Procedure Theatre', eyebrow:'ROUNDS · PROCEDURAL REHEARSAL', description:'Prepare and rehearse a procedure using a structured safety checklist. The record supports education and does not replace local policy, supervision, credentialing or consent.', fields:[{key:'procedure',label:'Procedure and indication',prompt:'Name the procedure, indication and intended outcome.'},{key:'selection',label:'Patient selection and contraindications',prompt:'Relevant anatomy, patient factors, contraindications and alternatives.'},{key:'consent',label:'Consent and preparation',prompt:'Capacity, discussion of benefits/risks/alternatives, equipment, monitoring and asepsis.'},{key:'steps',label:'Procedure sequence',prompt:'Describe the sequence at a level appropriate to your training and local protocol.'},{key:'complications',label:'Complications and response',prompt:'Anticipated complications, recognition, immediate response and escalation.'},{key:'aftercare',label:'Aftercare and documentation',prompt:'Monitoring, instructions, follow-up, documentation and supervision required.'}], guidance:['Check local procedural policy and equipment.','Identify the supervisor and escalation plan before practice.','Do not perform a procedure based solely on this educational checklist.'], completion:'Procedure rehearsal saved' },
  oncall: { id:'oncall', title:'On-Call Room', eyebrow:'WARD · ACUTE CARE', description:'Work through an acute presentation: identify immediate threats, prioritise actions, reassess response and escalate. Use local emergency pathways and senior support.', fields:[{key:'presentation',label:'Initial presentation',prompt:'Presenting concern, time course, relevant history, observations and immediate context.'},{key:'abcde',label:'ABCDE assessment',prompt:'A: airway · B: breathing · C: circulation · D: disability · E: exposure. Record findings and actions.'},{key:'priorities',label:'Prioritised problem list',prompt:'List immediate threats first and explain prioritisation.'},{key:'investigations',label:'Investigations and rationale',prompt:'What is required now, what can wait, and what result would change management?'},{key:'management',label:'Immediate management',prompt:'State actions, monitoring, contraindications to check and response targets.'},{key:'escalation',label:'Escalation and reassessment',prompt:'Who needs to be contacted, when, and what triggers urgent escalation? Record reassessment.'}], guidance:['If the patient may be unstable, initiate local emergency response and obtain senior help immediately.','Use current local protocols; this workspace is not a clinical decision-support device.','Document time-critical actions and reassessment.'], completion:'On-call case saved' },
  handover: { id:'handover', title:'Handover Desk', eyebrow:'WARD · SAFE TRANSITIONS', description:'Create a concise, actionable handover with explicit task ownership, deadlines, risks and contingency plans. Confirm receipt with the receiving clinician.', fields:[{key:'situation',label:'Situation',prompt:'Patient identifier used in your local system, location, reason for handover and current status.'},{key:'background',label:'Background',prompt:'Relevant diagnoses, history, admission course and baseline.'},{key:'assessment',label:'Assessment',prompt:'Current observations, clinical concerns, pending results and your assessment.'},{key:'recommendation',label:'Recommendation and plan',prompt:'Prioritised actions, review thresholds and contingency plan.'},{key:'tasks',label:'Outstanding tasks and deadlines',prompt:'For each task: action, named role/owner and deadline.'},{key:'receiver',label:'Receiver confirmation',prompt:'Receiving clinician/team, time accepted, questions clarified and any limitations.'}], guidance:['Use SBAR: Situation, Background, Assessment, Recommendation.','Assign each task to a named role and deadline.','Avoid unnecessary patient-identifiable information in this local learning record.'], completion:'Handover saved' },
  consult: { id:'consult', title:'Consult Room', eyebrow:'WARD · SPECIALTY COMMUNICATION', description:'Prepare a focused referral or consultation request and record the response. The receiving specialty should be given a clear clinical question and urgency.', fields:[{key:'question',label:'Reason for consultation and urgency',prompt:'State the specific question and how urgently an answer is required.'},{key:'context',label:'Relevant clinical context',prompt:'Concise history, examination, comorbidities and current treatment.'},{key:'data',label:'Relevant investigations',prompt:'Include results, dates, trends and unavailable/pending data.'},{key:'actions',label:'Actions already taken',prompt:'Treatment, response, discussions and escalation so far.'},{key:'response',label:'Consultant response and recommendations',prompt:'Record advice, limitations, agreed plan and who is responsible.'},{key:'followup',label:'Follow-up and closure',prompt:'Review time, triggers for re-contact and confirmation that recommendations were communicated.'}], guidance:['State the question before the background.','Communicate urgency and clinical deterioration directly.','Document advice accurately; clarify uncertainty rather than infer recommendations.'], completion:'Consultation record saved' },
  progression: { id:'progression', title:'Clinical Progression', eyebrow:'WARD · EVIDENCE-BASED DEVELOPMENT', description:'Track development from Intern to Consultant using evidence, feedback and supervisor review. Activity volume alone does not establish competence or independent practice.', fields:[{key:'stage',label:'Current training stage',prompt:'Intern / Resident / Registrar / Consultant-track. State your current supervised scope.'},{key:'objective',label:'Development objective',prompt:'Define one observable clinical or professional capability to develop.'},{key:'evidence',label:'Evidence of practice',prompt:'Describe the encounter, task, simulation, portfolio item or observed performance. Do not include identifiable patient details.'},{key:'feedback',label:'Feedback and reflection',prompt:'Record feedback source/role, strengths, gaps and your response.'},{key:'action',label:'Next development action',prompt:'Specific practice or learning action, supervisor and target review date.'},{key:'review',label:'Supervisor review',prompt:'Supervisor name/role, date, decision, limitations and evidence still required. Leave blank until reviewed.'}], guidance:['Intern: safe foundations, recognition of deterioration and timely escalation.','Resident: consistent supervised assessment and management.','Registrar: prioritisation, coordination and supervision within authorised scope.','Consultant: complex decisions, leadership, governance and supervision.'], completion:'Development evidence saved' },
};

const summaryConfig: WorkflowConfig = { id:'summaries', title:'Clinical Summaries', eyebrow:'EXAM HALL · SOURCE-LINKED REVIEW', description:'Review saved clinical notes generated by the HSPTL evidence workflow. Unsupported sections remain explicitly identified; summaries are not a substitute for current guidelines or local protocols.', fields:[], guidance:['Open a saved summary to inspect its evidence and references.','Sections without supporting extracts should not be treated as complete recommendations.','Check publication date, jurisdiction and local policy before clinical use.'], completion:'' };

function dateText(value: string) { const d = new Date(value); return Number.isNaN(d.getTime()) ? value : d.toLocaleString(); }

export default function WorkflowPage({ workflow }: { workflow: string }) {
  const config = configs[workflow] || summaryConfig;
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selected, setSelected] = useState<Episode | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [title, setTitle] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const result = await api.episodes(undefined, 100, 0);
      const prefix = `HSPTL|${workflow}|`;
      const matches = (result.items as Episode[]).filter((item) => item.learning_goal?.startsWith(prefix));
      setEpisodes(matches);
      if (selected) {
        const latest = matches.find((item) => item.episode_id === selected.episode_id);
        if (latest) setSelected(latest); else setSelected(null);
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load saved workflow records.'); }
    finally { setLoading(false); }
  }, [workflow, selected?.episode_id]);

  useEffect(() => { void load(); }, [load]);

  async function openEpisode(item: Episode) {
    setError(''); setMessage(''); setSelected(item);
    try {
      const [detail, lineage] = await Promise.all([api.episode(item.episode_id), api.episodeLineage(item.episode_id)]);
      setSelected(detail as unknown as Episode);
      setDraft((detail as Episode).draft || {});
      const artifactDraft = (lineage as { artifacts?: Array<{ kind: string; body: Record<string, unknown> }> }).artifacts?.find((a) => a.kind === 'reflection' && a.body.workflow === workflow);
      if (artifactDraft?.body?.fields && typeof artifactDraft.body.fields === 'object') setDraft(artifactDraft.body.fields as Record<string, string>);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not open this record.'); }
  }

  async function createEpisode() {
    const cleanTitle = title.trim().slice(0, 150);
    if (!cleanTitle) { setError('Enter a record title before starting.'); return; }
    setSaving(true); setError(''); setMessage('');
    try {
      const created = await api.startEpisode({ source_type: config.sourceType || 'curated_case', source_id: `${workflow}:${Date.now()}`, idempotency_key: '', learning_goal: `HSPTL|${workflow}|${cleanTitle}`, specialty, provenance_status: 'learner_authored' });
      const episode = created as unknown as Episode;
      setTitle(''); setSelected(episode); setDraft({});
      const result = await api.episodes(undefined, 100, 0);
      setEpisodes((result.items as unknown as Episode[]).filter((item) => item.learning_goal?.startsWith(`HSPTL|${workflow}|`)));
      setMessage('New record created. Complete the structured fields and save your draft.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create a record.'); }
    finally { setSaving(false); }
  }

  async function saveDraft() {
    if (!selected) return;
    setSaving(true); setError(''); setMessage('');
    try {
      await api.saveEpisodeDraft(selected.episode_id, draft, selected.draft_revision ?? 0, 1);
      await api.addEpisodeArtifact(selected.episode_id, { kind:'reflection', body:{ workflow, title:selected.learning_goal.split('|').slice(2).join('|'), fields:draft }, authored_by:'learner', verification_status:'unverified', source_refs:[] });
      setMessage(config.completion || 'Draft saved');
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save this draft. Reload the record if it was changed elsewhere.'); }
    finally { setSaving(false); }
  }

  async function complete() {
    if (!selected) return;
    setSaving(true); setError('');
    try { await saveDraft(); await api.completeEpisode(selected.episode_id); setMessage('Record completed. It remains an educational, learner-authored entry and is not a competency sign-off.'); await load(); setSelected(null); setDraft({}); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not complete this record.'); }
    finally { setSaving(false); }
  }

  if (workflow === 'summaries') return <SummaryLibrary config={summaryConfig}/>;

  const currentStage = selected?.stage || 1;
  return <div className="space-y-5">
    <header><div className="eyebrow">{config.eyebrow}</div><h2 className="page-title mt-2">{config.title}</h2><p className="muted mt-2 max-w-3xl text-sm leading-relaxed">{config.description}</p></header>
    {workflow === 'oncall' && <DailyCaseLottery workspace="ward_board"/>}
    {error && <div role="alert" className="status-error">{error}</div>}{message && <div role="status" className="status-success">{message}</div>}
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(280px,.75fr)]">
      <section className="space-y-4">
        {!selected ? <div className="hsptl-card p-5">
          <div className="flex items-center gap-2"><Icon name="filePlus" size={19}/><h3 className="font-bold">Start a new record</h3></div>
          <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_190px_auto]">
            <input className="form-field" value={title} onChange={(e)=>setTitle(e.target.value)} placeholder={workflow==='progression'?'e.g. Acute assessment development objective':'Record title'} aria-label="Record title"/>
            <input className="form-field" value={specialty} onChange={(e)=>setSpecialty(e.target.value)} placeholder="Specialty (optional)" aria-label="Specialty"/>
            <button className="primary-button" disabled={saving} onClick={()=>void createEpisode()}>{saving?'Creating…':'Create record'}</button>
          </div>
          <p className="muted mt-2 text-xs">Records are stored locally in the HSPTL learning episode ledger.</p>
        </div> : <div className="hsptl-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow">ACTIVE WORKING RECORD · STAGE {currentStage}</div><h3 className="mt-1 text-lg font-extrabold">{selected.learning_goal.split('|').slice(2).join('|')}</h3><p className="muted mt-1 text-xs">{selected.specialty || 'Unspecified specialty'} · Updated {dateText(selected.updated_at)}</p></div><button className="secondary-button" onClick={()=>{setSelected(null);setDraft({});}}>Close</button></div>
          <div className="mt-5 grid gap-4 md:grid-cols-2">{config.fields.map((field)=> <label key={field.key} className="block"><span className="field-label">{field.label}</span><span className="muted mt-1 block text-xs">{field.prompt}</span><textarea className="form-field mt-2 min-h-28 resize-y" rows={field.rows || 4} value={draft[field.key] || ''} onChange={(e)=>setDraft((old)=>({...old,[field.key]:e.target.value}))} placeholder="Record your assessment…"/></label>)}</div>
          <div className="mt-5 flex flex-wrap gap-2"><button className="primary-button" disabled={saving} onClick={()=>void saveDraft()}>{saving?'Saving…':'Save draft'}</button><button className="secondary-button" disabled={saving} onClick={()=>void complete()}>Complete record</button></div>
          <p className="muted mt-3 text-xs">Completion closes this episode. It does not verify clinical accuracy, confer procedural privileges or establish competence.</p>
        </div>}
        <div className="hsptl-card p-5"><div className="flex items-center justify-between gap-3"><h3 className="font-bold">Saved records</h3><button className="icon-button" onClick={()=>void load()} aria-label="Refresh records"><Icon name="refresh" size={16}/></button></div>
          {loading ? <p className="muted mt-4 text-sm">Loading records…</p> : episodes.length ? <div className="mt-3 divide-y divide-[var(--border-subtle)]">{episodes.map((item)=><button key={item.episode_id} onClick={()=>void openEpisode(item)} className={`flex w-full items-center justify-between gap-3 py-3 text-left ${selected?.episode_id===item.episode_id?'text-[var(--hsptl-primary)]':''}`}><span className="min-w-0"><b className="block truncate text-sm">{item.learning_goal.split('|').slice(2).join('|')}</b><small className="muted">{dateText(item.updated_at)} · {item.status}</small></span><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${item.status==='completed'?'bg-emerald-100 text-emerald-800':'bg-amber-100 text-amber-800'}`}>{item.status}</span></button>)}</div> : <p className="muted mt-4 text-sm">No records yet. Start a record above to begin.</p>}
        </div>
      </section>
      <aside className="space-y-4"><section className="hsptl-card p-5"><div className="eyebrow">WORKFLOW SAFEGUARDS</div><h3 className="mt-1 font-bold">Practice standards</h3><ul className="mt-3 space-y-3">{config.guidance.map((item,i)=><li key={i} className="flex gap-2 text-sm leading-relaxed"><Icon name="shield" size={16} className="mt-0.5 shrink-0 text-[var(--hsptl-teal)]"/>{item}</li>)}</ul></section><section className="note-warning"><b className="text-sm">Clinical education only</b><p className="mt-1 text-xs leading-relaxed">Do not enter identifiable patient information. This workspace does not provide real-time clinical advice, prescribe treatment or replace local escalation pathways, supervision or professional judgement.</p></section></aside>
    </div>
  </div>;
}

function SummaryLibrary({ config }: { config: WorkflowConfig }) {
  const [items,setItems]=useState<Array<{id:string;title:string;topic:string;note_type:string;saved_at:string;supported_sections:number;total_sections:number}>>([]);
  const [selected,setSelected]=useState<{markdown:string;note?:{references?:Array<{citation:string;url:string}>;sections?:Array<{title:string;status:string;evidence:Array<{text:string;citation:string;url?:string}>}>}|null} | null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{api.savedPearls().then(setItems).catch(e=>setError(e instanceof Error?e.message:'Could not load saved summaries.'));},[]);
  async function open(id:string){try{const result=await api.savedPearl(id);setSelected(result);}catch(e){setError(e instanceof Error?e.message:'Could not open summary.');}}
  return <div className="space-y-5"><header><div className="eyebrow">{config.eyebrow}</div><h2 className="page-title mt-2">{config.title}</h2><p className="muted mt-2 max-w-3xl text-sm">{config.description}</p></header>{error&&<div className="status-error">{error}</div>}<div className="grid gap-4 lg:grid-cols-[minmax(260px,.75fr)_minmax(0,1.5fr)]"><section className="hsptl-card p-4"><h3 className="font-bold">Saved summaries</h3>{items.length?items.map(item=><button key={item.id} onClick={()=>void open(item.id)} className="mt-2 block w-full rounded-lg border border-[var(--border-subtle)] p-3 text-left"><b className="block text-sm">{item.title}</b><small className="muted">{item.topic} · {item.supported_sections}/{item.total_sections} supported</small></button>):<p className="muted mt-3 text-sm">No saved summaries. Generate and save one in High-Yield Pearls.</p>}</section><section className="hsptl-card p-5">{selected?<><h3 className="font-bold">Summary content</h3><pre className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed">{selected.markdown}</pre></>:<div className="muted py-12 text-center text-sm">Select a saved summary to inspect its source-linked content.</div>}</section></div></div>;
}
