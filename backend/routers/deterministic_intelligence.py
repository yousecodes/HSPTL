"""API for the deterministic, event-sourced intelligence architecture."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from ..runtime import PATHS
from ..hsptl_core.deterministic_intelligence import DeterministicIntelligenceEngine, Abstention

router=APIRouter(prefix='/api/deterministic-intelligence',tags=['deterministic-intelligence'])
ENGINE=DeterministicIntelligenceEngine(PATHS['database'])

class EntityRequest(BaseModel): entity_id:str=Field(min_length=1,max_length=160); entity_class:str; label:str=Field(min_length=1,max_length=300); payload:dict[str,Any]={}
class EvidenceRequest(BaseModel): evidence_id:str; entity_id:str; source_id:str; content_hash:str; rights_decision:str; rights_scope:str; version:str
class AppraisalRequest(BaseModel): appraisal_id:str; evidence_id:str; decision:str; table_id:str='APP-001'; table_version:str='1.0.0'; derivation:dict[str,Any]
class SpanRequest(BaseModel): span_id:str; evidence_id:str; content_hash:str; span_text:str; start_offset:int; end_offset:int
class Claim(BaseModel): evidence_id:str; source_span_id:str; text:str
class ComposeRequest(BaseModel): object_id:str; workspace:str; template_id:str; template_version:str; slots:dict[str,Any]; claims:list[Claim]
class CompetencyRequest(BaseModel): competency_id:str; label:str; payload:dict[str,Any]={}; prerequisites:list[str]=[]
class RouteRequest(BaseModel): object_id:str; workspace:str; attributes:dict[str,Any]; required:dict[str,Any]
class GapRequest(BaseModel): analysis_id:str; required_facets:list[str]; covered_facets:list[str]; scope_key:str
class ConflictRequest(BaseModel): conflict_id:str; proposition_key:str; scope_key:str; evidence_a:str; evidence_b:str; polarity_a:str; polarity_b:str

def call(fn,*args,**kwargs):
 try:return fn(*args,**kwargs)
 except Abstention as e: raise HTTPException(409,{'state':'abstain','guard':e.guard,'reason':e.reason,'event_id':e.event_id}) from e
 except (ValueError,KeyError) as e: raise HTTPException(422,str(e)) from e

@router.get('/specification')
def specification(): return ENGINE.specification()
@router.get('/rules')
def rule_tables(): return {'items':ENGINE.rule_tables()}
@router.get('/status')
def status(): return call(ENGINE.projection_status)
@router.post('/replay')
def replay(through_seq:int|None=None): return call(ENGINE.replay,through_seq)
@router.get('/events')
def events(after:int=0,limit:int=200): return ENGINE.event_log(after,limit)
@router.post('/entities')
def register_entity(p:EntityRequest): return call(ENGINE.register_entity,p.entity_id,p.entity_class,p.label,p.payload)
@router.post('/evidence')
def register_evidence(p:EvidenceRequest): return call(ENGINE.register_evidence,**p.model_dump())
@router.post('/source-spans')
def register_span(p:SpanRequest): return call(ENGINE.register_source_span,**p.model_dump())
@router.post('/appraisals')
def appraisal(p:AppraisalRequest): return call(ENGINE.record_appraisal,**p.model_dump())
@router.post('/relationships')
def relationship(p:dict[str,Any]): return call(ENGINE.assert_relationship,**p)
@router.post('/learning-objects')
def compose(p:ComposeRequest): return call(ENGINE.compose_learning_object,p.object_id,p.workspace,p.template_id,p.template_version,p.slots,[x.model_dump() for x in p.claims])
@router.post('/competencies')
def competency(p:CompetencyRequest): return call(ENGINE.register_competency,**p.model_dump())
@router.get('/curriculum/order')
def curriculum_order(selected:str): return call(ENGINE.curriculum_order,[x for x in selected.split(',') if x])
@router.get('/competencies/{competency_id}/eligibility')
def eligibility(competency_id:str,achieved:str=''): return ENGINE.prerequisites_satisfied(competency_id,[x for x in achieved.split(',') if x])
@router.post('/evidence/gaps')
def evidence_gaps(p:GapRequest): return call(ENGINE.analyse_gap,**p.model_dump())
@router.post('/evidence/conflicts')
def evidence_conflicts(p:ConflictRequest): return call(ENGINE.detect_conflict,**p.model_dump())
@router.post('/routes')
def route(p:RouteRequest): return call(ENGINE.route,p.object_id,p.workspace,p.attributes,p.required)
