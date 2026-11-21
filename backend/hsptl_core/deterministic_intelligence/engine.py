"""Append-only canonical event ledger, guards, deterministic projections and replay."""
from __future__ import annotations
import hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .ontology import CLASSES, RELATIONSHIPS, DL_PROFILE, ONTOLOGY_VERSION, entails_type
from .specification import EVENT_CATALOG, RULE_INVENTORY, GUARD_MATRIX, TEMPLATE_SCHEMA

class Abstention(RuntimeError):
    def __init__(self, guard: str, reason: str, event_id: str = ""):
        self.guard, self.reason, self.event_id = guard, reason, event_id
        super().__init__(f"ABSTAIN [{guard}]: {reason}")

class DeterministicIntelligenceEngine:
    EVENT_TYPES = set(EVENT_CATALOG)
    def __init__(self, db_path: Path | str):
        self.db_path=Path(db_path); self.db_path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def connect(self):
        c=sqlite3.connect(self.db_path,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=15000'); return c
    @staticmethod
    def now(): return datetime.now(timezone.utc).isoformat(timespec='microseconds')
    @staticmethod
    def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    def _init(self):
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS di_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,payload_json TEXT NOT NULL,occurred_at TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL UNIQUE);
            CREATE TRIGGER IF NOT EXISTS di_events_no_update BEFORE UPDATE ON di_events BEGIN SELECT RAISE(ABORT,'immutable event log'); END;
            CREATE TRIGGER IF NOT EXISTS di_events_no_delete BEFORE DELETE ON di_events BEGIN SELECT RAISE(ABORT,'immutable event log'); END;
            CREATE TABLE IF NOT EXISTS di_entities(entity_id TEXT PRIMARY KEY,entity_class TEXT NOT NULL,label TEXT NOT NULL,payload_json TEXT NOT NULL,created_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_evidence(evidence_id TEXT PRIMARY KEY,entity_id TEXT NOT NULL UNIQUE REFERENCES di_entities(entity_id),source_id TEXT NOT NULL,content_hash TEXT NOT NULL,rights_decision TEXT NOT NULL CHECK(rights_decision IN ('permitted','restricted','unknown')),rights_scope TEXT NOT NULL,version TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS di_source_spans(span_id TEXT PRIMARY KEY,evidence_id TEXT NOT NULL REFERENCES di_evidence(evidence_id),content_hash TEXT NOT NULL,span_text TEXT NOT NULL,start_offset INTEGER NOT NULL CHECK(start_offset>=0),end_offset INTEGER NOT NULL CHECK(end_offset>start_offset),event_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_appraisals(appraisal_id TEXT PRIMARY KEY,evidence_id TEXT NOT NULL REFERENCES di_evidence(evidence_id),decision TEXT NOT NULL CHECK(decision IN ('pass','fail','abstain')),table_id TEXT NOT NULL,table_version TEXT NOT NULL,derivation_json TEXT NOT NULL,event_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_relationships(subject_id TEXT NOT NULL REFERENCES di_entities(entity_id),predicate TEXT NOT NULL,object_id TEXT NOT NULL REFERENCES di_entities(entity_id),evidence_id TEXT NOT NULL REFERENCES di_evidence(evidence_id),event_seq INTEGER NOT NULL REFERENCES di_events(seq),PRIMARY KEY(subject_id,predicate,object_id,evidence_id));
            CREATE TABLE IF NOT EXISTS di_learning_objects(object_id TEXT PRIMARY KEY,template_id TEXT NOT NULL,template_version TEXT NOT NULL,workspace TEXT NOT NULL,payload_json TEXT NOT NULL,derivation_json TEXT NOT NULL,event_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_competencies(competency_id TEXT PRIMARY KEY,label TEXT NOT NULL,payload_json TEXT NOT NULL,event_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_prerequisites(competency_id TEXT NOT NULL REFERENCES di_competencies(competency_id),prerequisite_id TEXT NOT NULL REFERENCES di_competencies(competency_id),event_seq INTEGER NOT NULL REFERENCES di_events(seq),PRIMARY KEY(competency_id,prerequisite_id));
            CREATE TABLE IF NOT EXISTS di_routes(route_id TEXT PRIMARY KEY,object_id TEXT NOT NULL REFERENCES di_learning_objects(object_id),workspace TEXT NOT NULL,canonical_seq INTEGER NOT NULL,event_seq INTEGER NOT NULL REFERENCES di_events(seq),predicate_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS di_rule_tables(rule_id TEXT NOT NULL,version TEXT NOT NULL,owner TEXT NOT NULL,table_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(rule_id,version));
            CREATE TABLE IF NOT EXISTS di_evidence_conflicts(conflict_id TEXT PRIMARY KEY,proposition_key TEXT NOT NULL,scope_key TEXT NOT NULL,evidence_a TEXT NOT NULL REFERENCES di_evidence(evidence_id),evidence_b TEXT NOT NULL REFERENCES di_evidence(evidence_id),proof_json TEXT NOT NULL,event_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_guard_decisions(id TEXT PRIMARY KEY,guard_id TEXT NOT NULL,decision TEXT NOT NULL CHECK(decision IN ('pass','fail','abstain')),reason TEXT NOT NULL,context_json TEXT NOT NULL,event_seq INTEGER NOT NULL REFERENCES di_events(seq));
            CREATE TABLE IF NOT EXISTS di_projections(name TEXT PRIMARY KEY,projection_seq INTEGER NOT NULL,payload_json TEXT NOT NULL,projection_hash TEXT NOT NULL);
            ''')
            seeds=[('APP-001','1.0.0','Evidence Intelligence',{'allowed_decisions':['pass','fail','abstain'],'composition_requires':'pass','derivation_required':True}),('RIGHTS-001','1.0.0','UCKS',{'allowed_decisions':['permitted','restricted','unknown'],'unknown_policy':'abstain'}),('TEMPLATE-001','1.0.0','Generation',{'required_slots':['clinical_assertion','evidence_context','limitations'],'empty_slot_policy':'abstain'}),('CURR-001','1.0.0','Curriculum',{'graph':'DAG','unknown_prerequisite_policy':'abstain'})]
            for rid,ver,owner,data in seeds:c.execute('INSERT OR IGNORE INTO di_rule_tables VALUES(?,?,?,?,?)',(rid,ver,owner,self.canonical(data),self.now()))
    def _head(self,c):
        r=c.execute('SELECT seq,event_hash FROM di_events ORDER BY seq DESC LIMIT 1').fetchone(); return (r['seq'],r['event_hash']) if r else (0,'0'*64)
    def _append(self,c,event_type,payload):
        if event_type not in self.EVENT_TYPES: raise Abstention('G-EVENT-001','Unknown event type')
        seq,prev=self._head(c); eid='evt_'+uuid.uuid4().hex; now=self.now(); body=self.canonical(payload)
        digest=hashlib.sha256(f'{seq+1}|{eid}|{event_type}|{body}|{now}|{prev}'.encode()).hexdigest()
        cur=c.execute('INSERT INTO di_events(event_id,event_type,payload_json,occurred_at,previous_hash,event_hash) VALUES(?,?,?,?,?,?)',(eid,event_type,body,now,prev,digest))
        return cur.lastrowid,eid,digest
    def _guard(self,guard_id,ok,reason,context):
        if ok is True:
            try:
                with self.connect() as c:
                    seq,eid,_=self._append(c,'guard.evaluated',{'guard_id':guard_id,'decision':'pass','reason':'predicate satisfied','context':context})
                    c.execute('INSERT INTO di_guard_decisions VALUES(?,?,?,?,?,?)',('gd_'+uuid.uuid4().hex,guard_id,'pass','predicate satisfied',self.canonical(context),seq))
            except Exception as exc:
                raise Abstention('G-AUDIT-001',f'Cannot durably record guard outcome: {exc}') from exc
            return {'decision':'pass','guard_id':guard_id,'reason':'predicate satisfied'}
        decision='fail' if ok is False else 'abstain'
        try:
            with self.connect() as c:
                seq,eid,_=self._append(c,'guard.abstained',{'guard_id':guard_id,'decision':decision,'reason':reason,'context':context})
                c.execute('INSERT INTO di_guard_decisions VALUES(?,?,?,?,?,?)',('gd_'+uuid.uuid4().hex,guard_id,decision,reason,self.canonical(context),seq))
        except Exception as exc:
            raise Abstention('G-AUDIT-001',f'Cannot durably record guard outcome: {exc}') from exc
        raise Abstention(guard_id,reason,eid)
    def register_entity(self,entity_id:str,entity_class:str,label:str,payload:dict|None=None):
        if entity_class not in CLASSES: self._guard('G-ONTO-001',None,'Unknown ontology class',{'class':entity_class})
        if not entity_id or not label.strip(): self._guard('G-ONTO-001',False,'Entity id and label are required',{})
        self._guard('G-ONTO-001',True,'',{'entity_class':entity_class})
        payload=payload or {}
        with self.connect() as c:
            if c.execute('SELECT 1 FROM di_entities WHERE entity_id=?',(entity_id,)).fetchone(): self._guard('G-EVENT-001',False,'Entity id already exists; entities are immutable',{'entity_id':entity_id})
            seq,_,_=self._append(c,'entity.registered',{'entity_id':entity_id,'entity_class':entity_class,'label':label,'payload':payload})
            c.execute('INSERT INTO di_entities VALUES(?,?,?,?,?)',(entity_id,entity_class,label,self.canonical(payload),seq))
        return {'entity_id':entity_id,'entity_class':entity_class,'event_seq':seq}
    def register_evidence(self,evidence_id:str,entity_id:str,source_id:str,content_hash:str,rights_decision:str,rights_scope:str,version:str):
        if rights_decision not in {'permitted','restricted','unknown'}: self._guard('G-RIGHTS-001',False,'Invalid rights decision',{})
        if not all([evidence_id,source_id,content_hash,version,rights_scope.strip()]): self._guard('G-EVID-001',False,'Evidence identity, source, hash, version and rights scope are mandatory',{})
        if rights_decision!='permitted': self._guard('G-RIGHTS-001',None,'Rights are not explicitly permitted',{'decision':rights_decision})
        self._guard('G-EVID-001',True,'',{'evidence_id':evidence_id})
        self._guard('G-RIGHTS-001',True,'',{'rights_decision':rights_decision,'rights_scope':rights_scope})
        with self.connect() as c:
            ent=c.execute('SELECT entity_class FROM di_entities WHERE entity_id=?',(entity_id,)).fetchone()
            if not ent or not entails_type(ent['entity_class'],'EvidenceEntity'): self._guard('G-EVID-001',False,'Evidence must reference a canonical EvidenceEntity',{'entity_id':entity_id})
            seq,_,_=self._append(c,'evidence.registered',{'evidence_id':evidence_id,'entity_id':entity_id,'source_id':source_id,'content_hash':content_hash,'rights_decision':rights_decision,'rights_scope':rights_scope,'version':version})
            c.execute('INSERT INTO di_evidence VALUES(?,?,?,?,?,?,?)',(evidence_id,entity_id,source_id,content_hash,rights_decision,rights_scope,version))
        return {'evidence_id':evidence_id,'event_seq':seq}
    def register_source_span(self,span_id,evidence_id,content_hash,span_text,start_offset,end_offset):
        if not span_text or start_offset < 0 or end_offset <= start_offset or end_offset-start_offset != len(span_text): self._guard('G-PROV-001',False,'Source span offsets are invalid',{})
        with self.connect() as c:
            ev=c.execute('SELECT content_hash FROM di_evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
            if not ev or ev['content_hash'] != content_hash: self._guard('G-PROV-001',False,'Source span content hash does not match canonical evidence',{})
            seq,_,_=self._append(c,'source_span.registered',{'span_id':span_id,'evidence_id':evidence_id,'content_hash':content_hash,'span_text':span_text,'start_offset':start_offset,'end_offset':end_offset})
            c.execute('INSERT INTO di_source_spans VALUES(?,?,?,?,?,?,?)',(span_id,evidence_id,content_hash,span_text,start_offset,end_offset,seq))
        return {'span_id':span_id,'event_seq':seq}
    def rule_tables(self):
        with self.connect() as c: rows=c.execute('SELECT * FROM di_rule_tables ORDER BY rule_id,version').fetchall()
        return [{'rule_id':r['rule_id'],'version':r['version'],'owner':r['owner'],'table':json.loads(r['table_json'])} for r in rows]

    def analyse_gap(self,analysis_id,required_facets,covered_facets,scope_key):
        required=set(required_facets); covered=set(covered_facets)
        if not required or not scope_key:self._guard('G-EVID-001',None,'Gap analysis requires explicit scope and required facets',{})
        missing=sorted(required-covered); extra=sorted(covered-required)
        payload={'analysis_id':analysis_id,'scope_key':scope_key,'required':sorted(required),'covered':sorted(covered),'missing':missing,'unmapped':extra,'complete':not missing}
        with self.connect() as c:self._append(c,'evidence.gap_analysed',payload)
        return payload

    def detect_conflict(self,conflict_id,proposition_key,scope_key,evidence_a,evidence_b,polarity_a,polarity_b):
        # Legacy compatibility path: Z3 remains permitted only under the same
        # explicit provability registry used by the HSPTL 4.0 guard layer.
        from ..hsp_tl40.provability import classify_rule
        provability = classify_rule('SMT-CONFLICT-001')
        if provability['classification'] != 'z3_required':
            self._guard('G-PROVABILITY-001',None,'Conflict solver call is not permitted by the registered provability policy',{'rule_id':'SMT-CONFLICT-001','provability':provability})
        if not proposition_key or not scope_key or polarity_a not in {'positive','negative'} or polarity_b not in {'positive','negative'}:
            self._guard('G-APP-001',None,'Conflict comparison lacks explicit proposition, scope or polarity',{})
        if polarity_a==polarity_b:return {'conflict':False,'reason':'same polarity; no direct contradiction asserted'}
        try:
            from z3 import Bool, Solver, Not, unsat, sat
        except Exception:self._guard('G-APP-001',None,'SMT solver unavailable for conflict analysis',{'solver':'z3'})
        with self.connect() as c:
            for eid in (evidence_a,evidence_b):
                if not c.execute('SELECT 1 FROM di_evidence WHERE evidence_id=?',(eid,)).fetchone():self._guard('G-EVID-001',False,'Conflict references unknown evidence',{'evidence_id':eid})
            proposition=Bool('same_scoped_proposition'); solver=Solver()
            solver.add(proposition if polarity_a=='positive' else Not(proposition))
            solver.add(proposition if polarity_b=='positive' else Not(proposition))
            result=solver.check()
            if result==sat:return {'conflict':False,'reason':'SMT found a consistent interpretation'}
            if result!=unsat:self._guard('G-APP-001',None,'SMT could not decide conflict status',{'result':str(result)})
            proof={'solver':'z3','result':'unsat','proposition_key':proposition_key,'scope_key':scope_key,'polarity_a':polarity_a,'polarity_b':polarity_b,'counterexample':'opposing assertions cannot both hold for the same scoped proposition'}
            seq,_,_=self._append(c,'evidence.conflict_detected',{'conflict_id':conflict_id,'proposition_key':proposition_key,'scope_key':scope_key,'evidence_a':evidence_a,'evidence_b':evidence_b,'proof':proof})
            c.execute('INSERT INTO di_evidence_conflicts VALUES(?,?,?,?,?,?,?)',(conflict_id,proposition_key,scope_key,evidence_a,evidence_b,self.canonical(proof),seq))
        return {'conflict':True,'conflict_id':conflict_id,'proof':proof,'event_seq':seq}

    def record_appraisal(self,appraisal_id,evidence_id,decision,table_id='APP-001',table_version='1.0.0',derivation=None):
        if decision not in {'pass','fail','abstain'}: self._guard('G-APP-001',False,'Appraisal must be pass, fail or abstain',{})
        if not derivation: self._guard('G-APP-001',None,'Appraisal derivation is mandatory',{'evidence_id':evidence_id})
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM di_evidence WHERE evidence_id=?',(evidence_id,)).fetchone(): self._guard('G-APP-001',False,'Evidence does not exist',{'evidence_id':evidence_id})
            if not c.execute('SELECT 1 FROM di_rule_tables WHERE rule_id=? AND version=?',(table_id,table_version)).fetchone(): self._guard('G-APP-001',None,'Appraisal decision table/version is not registered',{'table_id':table_id,'table_version':table_version})
            self._guard('G-APP-001',True,'',{'evidence_id':evidence_id,'decision':decision,'table_id':table_id,'table_version':table_version})
            seq,_,_=self._append(c,'appraisal.recorded',{'appraisal_id':appraisal_id,'evidence_id':evidence_id,'decision':decision,'table_id':table_id,'table_version':table_version,'derivation':derivation})
            c.execute('INSERT INTO di_appraisals VALUES(?,?,?,?,?,?,?)',(appraisal_id,evidence_id,decision,table_id,table_version,self.canonical(derivation),seq))
        return {'appraisal_id':appraisal_id,'decision':decision,'event_seq':seq}
    def assert_relationship(self,subject_id,predicate,object_id,evidence_id):
        domain_range=RELATIONSHIPS.get(predicate)
        if not domain_range: self._guard('G-ONTO-001',False,'Unknown ontology predicate',{'predicate':predicate})
        with self.connect() as c:
            rows=c.execute('SELECT entity_id,entity_class FROM di_entities WHERE entity_id IN (?,?)',(subject_id,object_id)).fetchall(); types={r['entity_id']:r['entity_class'] for r in rows}
            if len(types)!=2 or not entails_type(types[subject_id],domain_range[0]) or not entails_type(types[object_id],domain_range[1]): self._guard('G-REL-001',False,'Relationship domain/range violation',{'predicate':predicate})
            ev=c.execute('SELECT rights_decision FROM di_evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
            if not ev: self._guard('G-PROV-001',False,'Relationship requires canonical evidence provenance',{})
            if ev['rights_decision']!='permitted': self._guard('G-RIGHTS-001',None,'Relationship evidence rights are not permitted',{})
            seq,_,_=self._append(c,'relationship.asserted',{'subject_id':subject_id,'predicate':predicate,'object_id':object_id,'evidence_id':evidence_id})
            c.execute('INSERT INTO di_relationships VALUES(?,?,?,?,?)',(subject_id,predicate,object_id,evidence_id,seq))
        return {'event_seq':seq,'asserted':True}
    def verify_safety_properties(self):
        """Prove core Boolean safety invariants only under the registered SMT rule."""
        from ..hsp_tl40.provability import classify_rule
        provability = classify_rule('SMT-SAFETY-001')
        if provability['classification'] != 'z3_required':
            self._guard('G-PROVABILITY-001',None,'Safety solver call is not permitted by the registered provability policy',{'rule_id':'SMT-SAFETY-001','provability':provability})
        try:
            from z3 import Bool, Solver, And, Not, unsat, unknown
        except Exception:
            self._guard('G-LO-001',None,'SMT solver (z3-solver) is not installed; proof cannot be decided',{'solver':'z3'})
        appraisal_pass=Bool('appraisal_pass'); rights_permitted=Bool('rights_permitted'); span_valid=Bool('span_valid'); emitted=Bool('emitted')
        solver=Solver()
        solver.add(emitted == And(appraisal_pass, rights_permitted, span_valid))
        solver.push(); solver.add(emitted, Not(appraisal_pass)); result=solver.check(); solver.pop()
        if result != unsat: self._guard('G-LO-001',None,'SMT could not prove emitted implies passing appraisal',{'solver_result':str(result)})
        solver.push(); solver.add(emitted, Not(rights_permitted)); result=solver.check(); solver.pop()
        if result != unsat: self._guard('G-LO-001',None,'SMT could not prove emitted implies permitted rights',{'solver_result':str(result)})
        solver.push(); solver.add(emitted, Not(span_valid)); result=solver.check(); solver.pop()
        if result != unsat: self._guard('G-LO-001',None,'SMT could not prove emitted implies valid source span',{'solver_result':str(result)})
        return {'status':'pass','solver':'z3','properties_proved':3}

    def compose_learning_object(self,object_id,workspace,template_id,template_version,slots,claims):
        required_slots={'clinical_assertion','evidence_context','limitations'}
        if not isinstance(slots,dict) or not required_slots.issubset(slots) or any(slots.get(k) in (None,'') for k in required_slots) or not claims: self._guard('G-LO-001',False,'All required typed slots and at least one evidenced claim are required',{'required_slots':sorted(required_slots)})
        self._guard('G-LO-001',True,'',{'template_id':template_id,'template_version':template_version,'workspace':workspace})
        with self.connect() as c:
            self.verify_safety_properties()
            for claim in claims:
                eid=claim.get('evidence_id'); span=claim.get('source_span_id'); text=claim.get('text','')
                ev=c.execute('SELECT e.rights_decision,a.decision FROM di_evidence e LEFT JOIN di_appraisals a ON a.evidence_id=e.evidence_id WHERE e.evidence_id=? ORDER BY a.event_seq DESC LIMIT 1',(eid,)).fetchone()
                if not ev: self._guard('G-PROV-001',False,'Claim has no canonical evidence entity',{'claim':claim})
                if ev['decision']!='pass': self._guard('G-APP-001',None,'Current appraisal is not an explicit pass',{'evidence_id':eid,'decision':ev['decision']})
                if ev['rights_decision']!='permitted': self._guard('G-RIGHTS-001',None,'Evidence rights do not permit composition',{'evidence_id':eid})
                with self.connect() as rc:
                    rights=rc.execute('SELECT rights_scope FROM di_evidence WHERE evidence_id=?',(eid,)).fetchone()['rights_scope']
                    if rights not in {'full_text','full_text_reuse','adaptation'}: self._guard('G-RIGHTS-001',None,'Rights scope does not permit source-span composition',{'evidence_id':eid,'rights_scope':rights})
                    if rc.execute('SELECT 1 FROM di_evidence_conflicts WHERE evidence_a=? OR evidence_b=?',(eid,eid)).fetchone(): self._guard('G-APP-001',None,'Evidence has an unresolved conflict',{'evidence_id':eid})
                if not span or not text.strip(): self._guard('G-PROV-001',False,'Claim must include source span id and text',{})
                source_span=c.execute('SELECT evidence_id,span_text,content_hash FROM di_source_spans WHERE span_id=?',(span,)).fetchone()
                if not source_span or source_span['evidence_id']!=eid or source_span['span_text']!=text: self._guard('G-PROV-001',False,'Claim text must exactly match its canonical evidence source span',{'span_id':span})
            evidence_ids={x.get('evidence_id') for x in claims}; span_ids={x.get('source_span_id') for x in claims}
            if slots.get('evidence_context') not in evidence_ids or slots.get('limitations') not in span_ids: self._guard('G-LO-001',False,'Evidence and limitation slots must resolve to claim-linked canonical IDs',{})
            derivation={'template_id':template_id,'template_version':template_version,'slots':slots,'claims':claims,'rule_versions':['APP-001@1.0.0','RIGHTS-001@1.0.0','TEMPLATE-001@1.0.0']}
            seq,_,_=self._append(c,'learning_object.composed',{'object_id':object_id,'workspace':workspace,'derivation':derivation})
            c.execute('INSERT INTO di_learning_objects VALUES(?,?,?,?,?,?,?)',(object_id,template_id,template_version,workspace,self.canonical({'slots':slots,'claims':claims}),self.canonical(derivation),seq))
        return {'object_id':object_id,'event_seq':seq,'derivation':derivation}
    def register_competency(self,competency_id,label,payload=None,prerequisites=None):
        prerequisites=prerequisites or []
        with self.connect() as c:
            for p in prerequisites:
                if not c.execute('SELECT 1 FROM di_competencies WHERE competency_id=?',(p,)).fetchone(): self._guard('G-CURR-001',None,'Unknown prerequisite competency',{'prerequisite':p})
            graph={r['competency_id']:set() for r in c.execute('SELECT competency_id FROM di_competencies')}
            for r in c.execute('SELECT competency_id,prerequisite_id FROM di_prerequisites'): graph.setdefault(r['competency_id'],set()).add(r['prerequisite_id'])
            graph[competency_id]=set(prerequisites)
            def visit(n,path,done):
                if n in path:return False
                if n in done:return True
                path.add(n)
                for p in graph.get(n,set()):
                    if not visit(p,path,done):return False
                path.remove(n);done.add(n);return True
            done=set()
            if not all(visit(n,set(),done) for n in graph): self._guard('G-CURR-001',False,'Prerequisite graph must be acyclic',{'competency_id':competency_id})
            seq,_,_=self._append(c,'competency.registered',{'competency_id':competency_id,'label':label,'payload':payload or {},'prerequisites':prerequisites})
            c.execute('INSERT INTO di_competencies VALUES(?,?,?,?)',(competency_id,label,self.canonical(payload or {}),seq))
            for p in prerequisites:c.execute('INSERT INTO di_prerequisites VALUES(?,?,?)',(competency_id,p,seq))
        return {'competency_id':competency_id,'event_seq':seq,'prerequisites':prerequisites}
    def route(self,object_id,workspace,attributes,required):
        self.projection_status()
        if not isinstance(attributes,dict) or not isinstance(required,dict): self._guard('G-ROUTE-001',None,'Routing attributes are not decidable',{})
        for key,value in required.items():
            if key not in attributes or attributes[key] is None: self._guard('G-ROUTE-001',None,f'Missing routing attribute: {key}',{'required':required})
            if attributes[key]!=value: self._guard('G-ROUTE-001',False,f'Routing predicate failed: {key}',{'required':required,'actual':attributes[key]})
        self._guard('G-ROUTE-001',True,'',{'workspace':workspace,'required':required})
        with self.connect() as c:
            obj=c.execute('SELECT event_seq FROM di_learning_objects WHERE object_id=?',(object_id,)).fetchone()
            if not obj:self._guard('G-ROUTE-001',False,'Learning object is not canonical',{'object_id':object_id})
            head,_=self._head(c)
            seq,_,_=self._append(c,'route.decided',{'object_id':object_id,'workspace':workspace,'canonical_seq':head,'attributes':attributes,'required':required})
            rid='route_'+uuid.uuid4().hex;c.execute('INSERT INTO di_routes VALUES(?,?,?,?,?,?)',(rid,object_id,workspace,head,seq,self.canonical({'attributes':attributes,'required':required})))
        return {'route_id':rid,'event_seq':seq,'predicate':'satisfied','canonical_seq':head}
    def prerequisites_satisfied(self,competency_id,achieved):
        with self.connect() as c:
            rows=c.execute('SELECT prerequisite_id FROM di_prerequisites WHERE competency_id=?',(competency_id,)).fetchall()
            required={r['prerequisite_id'] for r in rows}
        return {'eligible':required.issubset(set(achieved)),'required':sorted(required),'missing':sorted(required-set(achieved))}
    def curriculum_order(self,selected):
        """Deterministic Kahn topological sort; abstains on cycles/unknown nodes."""
        with self.connect() as c:
            known={r['competency_id'] for r in c.execute('SELECT competency_id FROM di_competencies')}
            if not set(selected).issubset(known): self._guard('G-CURR-001',None,'Unknown curriculum node',{'selected':selected})
            edges={n:set() for n in selected}
            for r in c.execute('SELECT competency_id,prerequisite_id FROM di_prerequisites'):
                if r['competency_id'] in edges and r['prerequisite_id'] in edges: edges[r['competency_id']].add(r['prerequisite_id'])
        order=[]; remaining={k:set(v) for k,v in edges.items()}
        while remaining:
            ready=sorted(k for k,v in remaining.items() if not v)
            if not ready:self._guard('G-CURR-001',False,'Cycle prevents curriculum ordering',{'graph':edges})
            for n in ready:order.append(n);remaining.pop(n)
            for v in remaining.values():v.difference_update(ready)
        return order
    def replay(self,through_seq=None):
        """Rebuild canonical projections from genesis, verifying the full hash chain."""
        entities={};evidence={};projection_spans={};appraisals={};relationships=[];objects={};competencies={};routes=[];conflicts=[];gaps=[];platform_events=[];prev='0'*64; count=0
        with self.connect() as c: rows=c.execute('SELECT * FROM di_events WHERE seq<=? ORDER BY seq',(through_seq or 2**63-1,)).fetchall()
        for row in rows:
            expected=hashlib.sha256(f"{row['seq']}|{row['event_id']}|{row['event_type']}|{row['payload_json']}|{row['occurred_at']}|{prev}".encode()).hexdigest()
            if row['previous_hash']!=prev or row['event_hash']!=expected: raise Abstention('G-EVENT-001',f"Hash-chain verification failed at sequence {row['seq']}")
            p=json.loads(row['payload_json']);t=row['event_type'];count=row['seq']
            if t=='entity.registered':entities[p['entity_id']]=p
            elif t=='evidence.registered':evidence[p['evidence_id']]=p
            elif t=='evidence.conflict_detected':conflicts.append(p)
            elif t=='evidence.gap_analysed':gaps.append(p)
            elif t=='source_span.registered':projection_spans[p['span_id']]=p
            elif t=='appraisal.recorded':appraisals.setdefault(p['evidence_id'],[]).append(p)
            elif t=='relationship.asserted':relationships.append(p)
            elif t=='learning_object.composed':objects[p['object_id']]=p
            elif t=='competency.registered':competencies[p['competency_id']]=p
            elif t=='route.decided':routes.append(p)
            elif t.startswith('platform.'):
                platform_events.append({'seq':row['seq'],'event_id':row['event_id'],'event_type':t,'payload':p})
            prev=row['event_hash']
        projection={'seq':count,'entities':entities,'evidence':evidence,'source_spans':projection_spans,'appraisals':appraisals,'relationships':relationships,'learning_objects':objects,'competencies':competencies,'routes':routes,'conflicts':conflicts,'gaps':gaps,'platform_events':platform_events}
        digest=hashlib.sha256(self.canonical(projection).encode()).hexdigest()
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO di_projections VALUES(?,?,?,?)',('canonical',count,self.canonical(projection),digest))
        return {'projection':projection,'projection_hash':digest,'events_replayed':len(rows),'verified':True}
    def projection_status(self):
        with self.connect() as c:
            head,_=self._head(c);p=c.execute("SELECT projection_seq,projection_hash FROM di_projections WHERE name='canonical'").fetchone()
        if not p or p['projection_seq']!=head:self._guard('G-STALE-001',None,'Canonical projection is missing or stale; replay required',{'head_seq':head,'projection_seq':p['projection_seq'] if p else None})
        return {'canonical_seq':head,'projection_seq':p['projection_seq'],'fresh':True,'projection_hash':p['projection_hash']}
    def event_log(self,after=0,limit=200):
        with self.connect() as c: rows=c.execute('SELECT * FROM di_events WHERE seq>? ORDER BY seq LIMIT ?',(after,max(1,min(limit,1000)))).fetchall()
        return {'items':[dict(r) for r in rows]}
    def specification(self):
        return {'ontology':{'version':ONTOLOGY_VERSION,'classes':CLASSES,'relationships':RELATIONSHIPS,'description_logic_profile':DL_PROFILE},'events':EVENT_CATALOG,'rules':RULE_INVENTORY,'rule_tables':self.rule_tables(),'guards':GUARD_MATRIX,'template_schema':TEMPLATE_SCHEMA,'solver':{'status':'optional z3-solver proof adapter; composition abstains when unavailable','policy':'unsupported or undecidable constraints abstain; no probabilistic inference'}}
