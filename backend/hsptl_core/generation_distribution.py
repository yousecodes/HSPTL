"""Governed generation and distribution layer over UCKS.

Generation creates versioned, source-linked drafts. Distribution routes only
approved artifacts to workspace destinations; no automatic clinical publishing.
"""
from __future__ import annotations
import hashlib, json, sqlite3, uuid, re, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_SCRIPTS: dict[str, dict[str, Any]] = {
 "clinic": {"label":"Clinic", "purpose":"Diagnostic reasoning", "sequence":["problem_representation","differential_diagnosis","discriminating_evidence","investigation_strategy","diagnostic_debrief"], "outputs":["case_report","case_debrief","conference_brief"], "content_types":["case_report","case_series","observational_study","diagnostic_study","guideline","systematic_review","synthetic_case"]},
 "rounds": {"label":"Rounds", "purpose":"Oral examination and procedural rehearsal", "sequence":["viva_prompt","candidate_response","examiner_probes","model_answer_review","procedure_checklist"], "outputs":["viva_set","tagged_report","procedure_checklist"], "content_types":["case_report","case_series","clinical_note","synthetic_case","reference_document"]},
 "lab": {"label":"Lab", "purpose":"Investigation interpretation and skills assessment", "sequence":["image_or_result_prompt","structured_interpretation","differential_patterns","next_test","osce_station"], "outputs":["spot_diagnosis","osce_station","investigation_guide"], "content_types":["diagnostic_study","observational_study","guideline","systematic_review","dataset","case_report"]},
 "ward": {"label":"Ward", "purpose":"Prioritisation, management and continuity of care", "sequence":["acuity_triage","immediate_actions","management_plan","handover","consultation","reflection"], "outputs":["on_call_scenario","handover_template","consult_note","progression_record"], "content_types":["guideline","systematic_review","trial","observational_study","clinical_note","case_report"]},
 "simulation": {"label":"Simulation", "purpose":"Scenario-based clinical decision practice and debriefing", "sequence":["prebrief","patient_presentation","learner_actions","staged_findings","reassessment","debrief"], "outputs":["simulation_brief"], "content_types":["synthetic_case","case_report","scenario_brief"]},
 "exam_hall": {"label":"Exam Hall", "purpose":"High-yield learning and summative practice", "sequence":["learning_objectives","high_yield_summary","retrieval_questions","answer_rationales","performance_feedback"], "outputs":["pearl","topic_summary","lecture_outline","question_set"], "content_types":["systematic_review","guideline","trial","diagnostic_study","case_report","case_series"]},
 "portfolio": {"label":"Portfolio", "purpose":"Governance, progression and reflective development", "sequence":["activity_evidence","competency_mapping","reflection","review_status","development_plan"], "outputs":["progress_snapshot","review_packet","development_plan"], "content_types":[]},
}

OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
 "case_report": {"sections": ["problem_representation", "differential_diagnosis", "discriminating_evidence", "investigation_strategy", "diagnostic_debrief"]},
 "case_debrief": {"sections": ["learning_points", "reasoning_gaps", "evidence_review", "reflection_questions"]},
 "conference_brief": {"sections": ["case_summary", "clinical_questions", "evidence_discussion", "uncertainties"]},
 "viva_set": {"sections": ["viva_questions", "model_answers", "examiner_probes", "scoring_criteria"]},
 "tagged_report": {"sections": ["clinical_summary", "key_findings", "evidence_appraisal", "limitations"]},
 "procedure_checklist": {"sections": ["indications", "preparation", "steps", "complications", "aftercare"]},
 "spot_diagnosis": {"sections": ["prompt", "observations", "differential", "most_likely_interpretation", "limitations"]},
 "osce_station": {"sections": ["candidate_instructions", "station_tasks", "examiner_checklist", "critical_safety_items"]},
 "investigation_guide": {"sections": ["test_selection", "interpretation", "pitfalls", "next_steps"]},
 "on_call_scenario": {"sections": ["presentation", "acuity_assessment", "immediate_actions", "escalation", "handover"]},
 "handover_template": {"sections": ["situation", "background", "assessment", "recommendation", "safety_checks"]},
 "consult_note": {"sections": ["referral_question", "relevant_evidence", "assessment_framework", "recommendations_to_consider", "uncertainties"]},
 "progression_record": {"sections": ["observed_activity", "competency_evidence", "reflection", "next_steps"]},
 "pearl": {"sections": ["clinical_pearl", "why_it_matters", "evidence_context", "caveats"]},
 "topic_summary": {"sections": ["learning_objectives", "core_concepts", "clinical_application", "limitations"]},
 "lecture_outline": {"sections": ["learning_objectives", "teaching_sequence", "discussion_points", "take_home_messages"]},
 "question_set": {"sections": ["questions", "answer_key", "rationales", "coverage_map"]},
 "progress_snapshot": {"sections": ["activity_evidence", "strengths", "development_needs", "next_steps"]},
 "review_packet": {"sections": ["evidence_summary", "competency_mapping", "reflection", "review_questions"]},
 "development_plan": {"sections": ["priority_needs", "learning_actions", "success_indicators", "review_date"]},
 "simulation_brief": {"sections": ["prebrief", "patient_presentation", "learning_objectives", "staged_findings", "learner_tasks", "debrief_prompts", "limitations"]},
}

class GenerationDistribution:
 def __init__(self, db_path: Path, model_generator: ModelGenerator|None=None):
  # model_generator is accepted only for backwards-compatible construction; it is never called.
  self.model_generator=None
  self.model_name="extractive_retrieval_cache_v1"
  self.db_path=Path(db_path); self.db_path.parent.mkdir(parents=True,exist_ok=True); self._init()
 def connect(self):
  c=sqlite3.connect(self.db_path,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
 def _init(self):
  with self.connect() as c:
   c.executescript('''
   CREATE TABLE IF NOT EXISTS generated_artifacts(id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, workspace TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', body_json TEXT NOT NULL, source_refs_json TEXT NOT NULL, template_version INTEGER NOT NULL DEFAULT 1, content_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT '', reviewed_at TEXT);
   CREATE INDEX IF NOT EXISTS idx_generated_workspace ON generated_artifacts(workspace,status,updated_at DESC);
   CREATE TABLE IF NOT EXISTS distribution_routes(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES generated_artifacts(id), workspace TEXT NOT NULL, section TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', destination_id TEXT NOT NULL DEFAULT '', destination_refs_json TEXT NOT NULL DEFAULT '[]', adapter TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, delivered_at TEXT, UNIQUE(artifact_id,workspace,section));
   CREATE TABLE IF NOT EXISTS generation_audit(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, event TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS workspace_customizations(workspace TEXT PRIMARY KEY, config_json TEXT NOT NULL, updated_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS generation_cache(cache_key TEXT PRIMARY KEY, artifact_json TEXT NOT NULL, created_at TEXT NOT NULL, last_used_at TEXT NOT NULL, hit_count INTEGER NOT NULL DEFAULT 0);
   ''')
   cols={r[1] for r in c.execute('PRAGMA table_info(distribution_routes)')}
   for name,ddl in {'destination_id':"TEXT NOT NULL DEFAULT ''",'destination_refs_json':"TEXT NOT NULL DEFAULT '[]'",'adapter':"TEXT NOT NULL DEFAULT ''",'error':"TEXT NOT NULL DEFAULT ''"}.items():
    if name not in cols: c.execute(f'ALTER TABLE distribution_routes ADD COLUMN {name} {ddl}')
 def _now(self): return datetime.now(timezone.utc).isoformat()
 def manifest(self): return {k:dict(v) for k,v in WORKSPACE_SCRIPTS.items()}
 def customize(self, workspace:str, config:dict[str,Any]):
  if workspace not in WORKSPACE_SCRIPTS: raise ValueError('Unknown workspace')
  allowed={'display_name','focus','enabled_outputs','sequence_overrides','section_labels','hidden_sections','difficulty','specialty','jurisdiction'}
  clean={k:v for k,v in config.items() if k in allowed}
  if 'display_name' in clean and (not isinstance(clean['display_name'],str) or len(clean['display_name'])>60): raise ValueError('display_name must be <=60 characters')
  if 'focus' in clean and (not isinstance(clean['focus'],str) or len(clean['focus'])>300): raise ValueError('focus must be <=300 characters')
  if 'enabled_outputs' in clean:
   if not isinstance(clean['enabled_outputs'],list) or any(x not in WORKSPACE_SCRIPTS[workspace]['outputs'] for x in clean['enabled_outputs']): raise ValueError('enabled_outputs contains unsupported output')
  if 'sequence_overrides' in clean:
   if not isinstance(clean['sequence_overrides'],list) or any(not isinstance(x,str) or len(x)>60 for x in clean['sequence_overrides']): raise ValueError('Invalid sequence override')
  if 'section_labels' in clean:
   if not isinstance(clean['section_labels'],dict) or any(not isinstance(k,str) or not isinstance(v,str) or len(v)>60 for k,v in clean['section_labels'].items()): raise ValueError('Invalid section labels')
  if 'hidden_sections' in clean:
   if not isinstance(clean['hidden_sections'],list) or any(not isinstance(x,str) for x in clean['hidden_sections']): raise ValueError('Invalid hidden sections')
  with self.connect() as c: c.execute('INSERT INTO workspace_customizations VALUES(?,?,?) ON CONFLICT(workspace) DO UPDATE SET config_json=excluded.config_json,updated_at=excluded.updated_at',(workspace,json.dumps(clean),self._now()))
  return self.get_customization(workspace)
 def get_customization(self, workspace:str):
  with self.connect() as c: row=c.execute('SELECT config_json,updated_at FROM workspace_customizations WHERE workspace=?',(workspace,)).fetchone()
  return {'workspace':workspace,'config':json.loads(row['config_json']) if row else {},'updated_at':row['updated_at'] if row else None}
 def _source_spans(self, document_ids:list[str], ucks_repo):
  spans=[]
  for did in document_ids:
   doc=ucks_repo.get_document(did)
   if not doc: raise ValueError(f'Source document not found: {did}')
   if doc.get('review_status')=='rejected' or doc.get('lifecycle_state') in {'retracted','superseded'}: raise ValueError(f'Source is not eligible: {did}')
   # Full text is used only for explicitly reusable licences or approved rights decisions.
   licence=(doc.get('licence') or '').casefold().rstrip('/')
   if 'creativecommons.org/licenses/' in licence:
    licence=licence.split('creativecommons.org/licenses/',1)[1]
   licence_key=''.join(ch for ch in licence if ch.isalnum())
   permitted=licence_key in {'cc0','cc01.0','by','by40','by30','ccby','ccby40','ccby30','bysa','bysa40','bysa30','ccbysa','ccbysa40','ccbysa30'} or doc.get('content_type')=='synthetic_case'
   with ucks_repo.store.transaction() as conn:
    rights=conn.execute("SELECT scope FROM ucks_rights_reviews WHERE document_id=? AND decision='permitted' ORDER BY created_at DESC LIMIT 1",(did,)).fetchone() if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ucks_rights_reviews'").fetchone() else None
    if rights and rights['scope'] in {'full_text_reuse','adaptation'}: permitted=True
    rows=conn.execute('SELECT id,ordinal,heading,body FROM ucks_chunks WHERE document_id=? AND version=? ORDER BY ordinal LIMIT 30',(did,doc['current_version'])).fetchall()
   if not permitted: raise ValueError(f'Full-text generation is not permitted for source {did}; approve reusable rights or use metadata-only output')
   for row in rows:
    text=row['body'] or ''
    if text.strip() and len(spans)<40: spans.append({'chunk_id':row['id'],'document_id':did,'title':doc['title'],'heading':row['heading'],'ordinal':row['ordinal'],'text':text[:6000],'source_url':doc.get('source_url',''),'licence':doc.get('licence',''),'review_status':doc.get('review_status','harvested')})
  if not spans: raise ValueError('Selected sources contain no current, reusable text chunks')
  return spans

 def _validate_output(self, kind:str, output:dict[str,Any], spans:list[dict[str,Any]]):
  required=OUTPUT_SCHEMAS.get(kind,{}).get('sections',[])
  sections=output.get('sections')
  if not isinstance(sections,list) or not sections: raise ValueError('Model output requires non-empty sections')
  by_id={s['chunk_id']:s for s in spans}; seen=set(); validated=[]
  for section in sections:
   if not isinstance(section,dict) or not isinstance(section.get('heading'),str) or not isinstance(section.get('claims'),list): raise ValueError('Each section requires heading and claims')
   key=section['heading'].strip().casefold().replace(' ','_')
   if key not in required: raise ValueError(f'Unexpected section heading: {section["heading"]}')
   claims=[]
   for claim in section['claims']:
    if not isinstance(claim,dict) or not isinstance(claim.get('text'),str) or not claim['text'].strip(): raise ValueError('Claim text is required')
    citations=claim.get('citations')
    if not isinstance(citations,list) or not citations: raise ValueError(f'Uncited claim in section {section["heading"]}')
    checked=[]
    for citation in citations:
     chunk=by_id.get(citation.get('chunk_id')) if isinstance(citation,dict) else None
     quote=citation.get('quote','') if isinstance(citation,dict) else ''
     if not chunk or not isinstance(quote,str) or len(quote.strip())<12: raise ValueError('Citation must identify a valid source chunk and verbatim quote')
     offset=chunk['text'].casefold().find(quote.strip().casefold())
     if offset<0: raise ValueError('Citation quote does not match the source span')
     checked.append({'chunk_id':chunk['chunk_id'],'document_id':chunk['document_id'],'quote':quote.strip(),'start_offset':offset,'end_offset':offset+len(quote.strip()),'source_url':chunk['source_url']})
     seen.add(chunk['chunk_id'])
    claims.append({'text':claim['text'].strip(),'citations':checked})
   if not claims: raise ValueError(f'Section {section["heading"]} has no supported claims')
   validated.append({'heading':section['heading'].strip(),'claims':claims})
  heading_list=[x['heading'].strip().casefold().replace(' ','_') for x in validated]
  headings=set(heading_list)
  if len(heading_list)!=len(headings): raise ValueError('Duplicate output sections are not permitted')
  missing=set(required)-headings
  if missing: raise ValueError('Missing required sections: '+', '.join(sorted(missing)))
  assessment_items=output.get('assessment_items',[])
  if kind in {'question_set','viva_set','osce_station'} and (not isinstance(assessment_items,list) or not assessment_items): raise ValueError(f'{kind} requires structured assessment_items')
  checked_items=[]
  for item in assessment_items:
   if not isinstance(item,dict) or not isinstance(item.get('question'),str) or not item['question'].strip() or not isinstance(item.get('answer'),str) or not item['answer'].strip(): raise ValueError('Assessment items require question and answer fields')
   citations=item.get('citations')
   if not isinstance(citations,list) or not citations: raise ValueError('Every assessment item requires source citations')
   checked_citations=[]
   for citation in citations:
    chunk=by_id.get(citation.get('chunk_id')) if isinstance(citation,dict) else None
    quote=citation.get('quote','') if isinstance(citation,dict) else ''
    offset=chunk['text'].casefold().find(quote.strip().casefold()) if chunk and isinstance(quote,str) else -1
    if offset<0 or len(quote.strip())<12: raise ValueError('Assessment citation quote does not match source span')
    checked_citations.append({'chunk_id':chunk['chunk_id'],'document_id':chunk['document_id'],'quote':quote.strip(),'start_offset':offset,'end_offset':offset+len(quote.strip()),'source_url':chunk['source_url']})
    seen.add(chunk['chunk_id'])
   checked_items.append({**item,'citations':checked_citations})
  return {'sections':validated,'assessment_items':checked_items,'limitations':output.get('limitations',[]),'validation':{'valid':True,'required_sections':required,'cited_chunks':sorted(seen),'uncited_claims':0,'assessment_items':len(checked_items)}}

 def _rank_spans(self, spans:list[dict[str,Any]], query:str, limit:int=12):
  """Deterministic BM25-lite retrieval; ranking never creates clinical content."""
  terms=set(re.findall(r"[a-z0-9]+", query.casefold()))
  scored=[]
  for span in spans:
   words=re.findall(r"[a-z0-9]+", span['text'].casefold())
   if not words: continue
   counts={w:words.count(w) for w in terms}
   overlap=sum(1+math.log(1+n) for n in counts.values() if n)
   title_bonus=1.5 if any(t in (span.get('title','')+' '+span.get('heading','')).casefold() for t in terms) else 0
   score=(overlap+title_bonus)/math.sqrt(max(1,len(words))/100)
   if score>0: scored.append((score,span))
  scored.sort(key=lambda x:(-x[0],x[1]['document_id'],x[1]['ordinal']))
  return [dict(x[1],retrieval_score=round(x[0],6)) for x in scored[:limit]] or spans[:min(limit,len(spans))]

 def _extractive_output(self, kind:str, title:str, spans:list[dict[str,Any]]):
  """Build source-verbatim learning artefacts. No paraphrasing or model inference."""
  required=OUTPUT_SCHEMAS[kind]['sections']; sections=[]; used=[]
  for idx,heading in enumerate(required):
   span=spans[idx % len(spans)]
   # Sentence extraction is conservative; preserve exact source wording and offsets.
   sentences=[x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+",span['text']) if len(x.strip())>=24]
   if not sentences: sentences=[span['text'].strip()[:500]]
   sentence=sentences[min(idx//max(1,len(spans)),len(sentences)-1)][:700]
   if len(sentence)<12: raise ValueError('Retrieved source span is too short for extractive generation')
   offset=span['text'].casefold().find(sentence.casefold())
   citation={'chunk_id':span['chunk_id'],'document_id':span['document_id'],'quote':sentence,'start_offset':offset,'end_offset':offset+len(sentence),'source_url':span.get('source_url','')}
   sections.append({'heading':heading,'claims':[{'text':sentence,'citations':[citation]}]}); used.append(span)
  assessment=[]
  if kind in {'question_set','viva_set','osce_station'}:
   for i,span in enumerate(spans[:min(5,len(spans))]):
    sentence=next((x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+",span['text']) if len(x.strip())>=24),span['text'].strip()[:500])
    if len(sentence)<12: continue
    offset=span['text'].casefold().find(sentence.casefold())
    assessment.append({'question':f"According to the cited source, what does it state about: {title}?",'answer':sentence,'explanation':'Answer reproduced verbatim from the cited source; interpret in the context and limitations of that source.','citations':[{'chunk_id':span['chunk_id'],'document_id':span['document_id'],'quote':sentence,'start_offset':offset,'end_offset':offset+len(sentence),'source_url':span.get('source_url','')} ]})
   if not assessment: raise ValueError('No sufficiently informative source spans for assessment generation')
  return {'sections':sections,'assessment_items':assessment,'limitations':['Deterministic extractive output; wording is source-verbatim and has not been clinically synthesised.','Retrieval relevance does not establish evidence quality, applicability or clinical correctness.']}

 def generate(self, *, workspace:str, kind:str, title:str, source_documents:list[str], ucks_repo):
  if workspace not in WORKSPACE_SCRIPTS: raise ValueError('Unknown workspace')
  if kind not in WORKSPACE_SCRIPTS[workspace]['outputs']: raise ValueError('Output kind is not enabled for this workspace')
  if not isinstance(title,str) or not title.strip(): raise ValueError('Title is required')
  if not source_documents or len(source_documents)>20: raise ValueError('Select 1–20 source documents')
  spans=self._source_spans(source_documents,ucks_repo)
  ranked=self._rank_spans(spans, title+' '+WORKSPACE_SCRIPTS[workspace]['purpose']+' '+' '.join(OUTPUT_SCHEMAS[kind]['sections']))
  # Cache key includes exact retrieved text and template version; source corrections naturally invalidate it.
  source_fingerprint=[(x['chunk_id'],hashlib.sha256(x['text'].encode()).hexdigest(),x.get('source_url',''),x.get('licence',''),x.get('title',''),x.get('review_status','')) for x in ranked]
  cache_key=hashlib.sha256(json.dumps({'workspace':workspace,'kind':kind,'title':title.strip(),'sources':source_fingerprint,'template':1},sort_keys=True).encode()).hexdigest()
  cached_artifact_id=None
  with self.connect() as c:
   cached=c.execute('SELECT artifact_json FROM generation_cache WHERE cache_key=?',(cache_key,)).fetchone()
   if cached:
    payload=json.loads(cached['artifact_json']); c.execute('UPDATE generation_cache SET hit_count=hit_count+1,last_used_at=? WHERE cache_key=?',(self._now(),cache_key))
    # Reuse content but create a distinct auditable draft record.
    body=payload['body']; refs=payload['refs']; aid='gen_'+uuid.uuid4().hex; now=self._now()
    c.execute('INSERT INTO generated_artifacts(id,kind,title,workspace,status,body_json,source_refs_json,content_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,kind,title,workspace,'draft',json.dumps(body,ensure_ascii=False),json.dumps(refs,ensure_ascii=False),hashlib.sha256(cached['artifact_json'].encode()).hexdigest(),now,now))
    c.execute('INSERT INTO generation_audit VALUES(?,?,?,?,?)',('audit_'+uuid.uuid4().hex,aid,'generated_from_cache',json.dumps({'cache_key':cache_key,'retrieved_chunks':len(ranked)}),now))
    cached_artifact_id=aid
  if cached_artifact_id: return self.get_artifact(cached_artifact_id)
  output=self._extractive_output(kind,title,ranked)
  body=self._validate_output(kind,output,ranked)
  refs=[]
  for did in source_documents:
   doc=ucks_repo.get_document(did); refs.append({'document_id':did,'title':doc['title'],'source_url':doc.get('source_url',''),'review_status':doc.get('review_status','harvested'),'licence':doc.get('licence','')})
  body.update({'purpose':WORKSPACE_SCRIPTS[workspace]['purpose'],'workflow':WORKSPACE_SCRIPTS[workspace]['sequence'],'generation_mode':'retrieval_cache_extractive','retrieval':{'method':'bm25_lite','ranked_chunks':[{'chunk_id':x['chunk_id'],'document_id':x['document_id'],'score':x.get('retrieval_score',0)} for x in ranked]},'source_spans':[{'chunk_id':x['chunk_id'],'document_id':x['document_id'],'source_url':x.get('source_url',''),'licence':x.get('licence','')} for x in ranked]})
  payload=json.dumps({'kind':kind,'title':title,'workspace':workspace,'body':body,'refs':refs},sort_keys=True,ensure_ascii=False)
  aid='gen_'+uuid.uuid4().hex; now=self._now()
  with self.connect() as c:
   c.execute('INSERT INTO generated_artifacts(id,kind,title,workspace,status,body_json,source_refs_json,content_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,kind,title,workspace,'draft',json.dumps(body,ensure_ascii=False),json.dumps(refs,ensure_ascii=False),hashlib.sha256(payload.encode()).hexdigest(),now,now))
   c.execute('INSERT OR REPLACE INTO generation_cache(cache_key,artifact_json,created_at,last_used_at,hit_count) VALUES(?,?,?,?,0)',(cache_key,payload,now,now))
   c.execute('INSERT INTO generation_audit VALUES(?,?,?,?,?)',('audit_'+uuid.uuid4().hex,aid,'generated',json.dumps({'mode':'retrieval_cache_extractive','cache_key':cache_key,'retrieved_chunks':len(ranked),'validation':body['validation']}),now))
  return self.get_artifact(aid)
 def create_structured_draft(self, *, workspace:str, kind:str, title:str, body:dict[str,Any], source_refs:list[dict[str,Any]]|None=None, template_version:int=1, audit_event:str="generated_structured_draft"):
  """Persist a validated structured draft into the shared governance lifecycle.

  This is used by embedded deterministic content recipes as well as source-
  extractive generation. It does not approve or distribute the artifact.
  """
  if workspace not in WORKSPACE_SCRIPTS: raise ValueError("Unknown workspace")
  if kind not in WORKSPACE_SCRIPTS[workspace]["outputs"]: raise ValueError("Output kind is not enabled for this workspace")
  if not isinstance(title,str) or not title.strip() or len(title)>200: raise ValueError("A valid title is required")
  if not isinstance(body,dict) or not isinstance(body.get("sections"),list) or not body["sections"]: raise ValueError("Structured draft requires non-empty sections")
  refs=source_refs or []
  canonical={"workspace":workspace,"kind":kind,"title":title.strip(),"body":body,"source_refs":refs,"template_version":int(template_version)}
  payload=json.dumps(canonical,sort_keys=True,ensure_ascii=False,separators=(",",":"))
  content_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest()
  now=self._now()
  with self.connect() as c:
   existing=c.execute("SELECT id FROM generated_artifacts WHERE content_hash=? ORDER BY created_at DESC LIMIT 1",(content_hash,)).fetchone()
   if existing:
    aid=existing["id"]
    c.execute("INSERT INTO generation_audit VALUES(?,?,?,?,?)",("audit_"+uuid.uuid4().hex,aid,"generation_deduplicated",json.dumps({"content_hash":content_hash,"generator":body.get("generation_mode","structured")}),now))
    return self.get_artifact(aid)
   aid="gen_"+uuid.uuid4().hex
   c.execute("INSERT INTO generated_artifacts(id,kind,title,workspace,status,body_json,source_refs_json,template_version,content_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(aid,kind,title.strip(),workspace,"draft",json.dumps(body,ensure_ascii=False),json.dumps(refs,ensure_ascii=False),int(template_version),content_hash,now,now))
   c.execute("INSERT INTO generation_audit VALUES(?,?,?,?,?)",("audit_"+uuid.uuid4().hex,aid,audit_event,json.dumps({"content_hash":content_hash,"generation_mode":body.get("generation_mode","structured"),"unit_id":body.get("unit_id"),"content_pack_id":body.get("content_pack_id"),"seed":body.get("seed")}),now))
  return self.get_artifact(aid)

 def get_artifact(self, aid):
  with self.connect() as c: r=c.execute('SELECT * FROM generated_artifacts WHERE id=?',(aid,)).fetchone()
  if not r:return None
  x=dict(r); x['body']=json.loads(x.pop('body_json')); x['source_refs']=json.loads(x.pop('source_refs_json')); return x
 def list_artifacts(self, workspace:str|None=None, limit:int=50):
  with self.connect() as c:
   rows=c.execute('SELECT id FROM generated_artifacts'+(' WHERE workspace=?' if workspace else '')+' ORDER BY updated_at DESC LIMIT ?',((workspace,limit) if workspace else (limit,))).fetchall()
  return {'items':[self.get_artifact(r['id']) for r in rows]}
 def review(self, aid:str, decision:str, reviewer:str):
  if decision not in {'approved','rejected','needs_revision'}: raise ValueError('Invalid decision')
  if not reviewer.strip(): raise ValueError('Reviewer is required')
  now=self._now()
  with self.connect() as c:
   cur=c.execute('UPDATE generated_artifacts SET status=?,reviewer=?,reviewed_at=?,updated_at=? WHERE id=? AND status IN (\'draft\',\'needs_revision\')',(decision,reviewer.strip()[:120],now,now,aid))
   if not cur.rowcount: raise ValueError('Artifact not found or no longer reviewable')
  with self.connect() as c: c.execute('INSERT INTO generation_audit VALUES(?,?,?,?,?)',('audit_'+uuid.uuid4().hex,aid,'reviewed',json.dumps({'decision':decision,'reviewer':reviewer.strip()[:120]}),now))
  return self.get_artifact(aid)
 def route(self, aid:str, workspace:str, section:str, *, adapter=None):
  art=self.get_artifact(aid)
  if not art: raise ValueError('Artifact not found')
  if art['status']!='approved': raise ValueError('Only approved artifacts can be distributed')
  if workspace not in WORKSPACE_SCRIPTS: raise ValueError('Unknown destination workspace')
  if not section.strip() or len(section)>80: raise ValueError('Valid destination section required')
  if workspace != art['workspace']: raise ValueError('Cross-workspace routing is disabled; generate for the destination workspace')
  with self.connect() as c:
   existing=c.execute('SELECT * FROM distribution_routes WHERE artifact_id=? AND workspace=? AND section=?',(aid,workspace,section)).fetchone()
  if existing and existing['status']=='delivered': return dict(existing)
  delivery=adapter.deliver(art,section) if adapter else {'destination_id':'','adapter':'workspace_library'}
  rid='route_'+uuid.uuid4().hex; now=self._now()
  with self.connect() as c:
   c.execute('INSERT OR IGNORE INTO distribution_routes(id,artifact_id,workspace,section,status,destination_id,destination_refs_json,adapter,created_at,delivered_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,aid,workspace,section,'delivered',delivery.get('destination_id',''),json.dumps(delivery.get('destination_refs',[])),delivery.get('adapter','workspace_library'),now,now))
   row=c.execute('SELECT * FROM distribution_routes WHERE artifact_id=? AND workspace=? AND section=?',(aid,workspace,section)).fetchone()
   c.execute('INSERT INTO generation_audit VALUES(?,?,?,?,?)',('audit_'+uuid.uuid4().hex,aid,'distributed',json.dumps({'workspace':workspace,'section':section,'destination_id':delivery.get('destination_id',''),'adapter':delivery.get('adapter','workspace_library')}),now))
  return dict(row)
 def routes(self, workspace:str|None=None):
  with self.connect() as c:
   rows=c.execute('SELECT r.*,a.title,a.kind,a.status AS artifact_status FROM distribution_routes r JOIN generated_artifacts a ON a.id=r.artifact_id'+(' WHERE r.workspace=?' if workspace else '')+' ORDER BY r.created_at DESC LIMIT 200',((workspace,) if workspace else ())).fetchall()
  return {'items':[dict(r) for r in rows]}
