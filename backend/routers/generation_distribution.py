from __future__ import annotations
import os, hmac
from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from ..runtime import PATHS
from ..hsptl_core.generation_distribution import GenerationDistribution
from ..hsptl_core.workspace_distribution import WorkspaceDistributionAdapter
from ..hsptl_core.ucks import UCKSRepository
from ..runtime import STORE
ADAPTER=WorkspaceDistributionAdapter(STORE)

router=APIRouter(prefix='/api',tags=['generation-distribution'])
ENGINE=GenerationDistribution(PATHS['database'])
UCKS=UCKSRepository(STORE)

def _reviewer(token:str|None)->str:
 expected=os.environ.get('HSPTL_REVIEWER_TOKEN',''); reviewer=os.environ.get('HSPTL_REVIEWER_ID','').strip()
 if len(expected)<32 or not reviewer: raise HTTPException(503,'Reviewer authentication is not configured')
 if not token or not hmac.compare_digest(token,expected): raise HTTPException(401,'Valid reviewer credentials are required')
 return reviewer[:160]

class GenerateRequest(BaseModel):
 workspace:str
 kind:str
 title:str=Field(min_length=1,max_length=200)
 source_documents:list[str]=Field(min_length=1,max_length=20)
class ReviewRequest(BaseModel): decision:str
class RouteRequest(BaseModel): workspace:str; section:str=Field(min_length=1,max_length=80)
class WorkspaceConfig(BaseModel): config:dict[str,Any]

@router.get('/workspaces/manifest')
def workspace_manifest():
 return {'items':ENGINE.manifest(),'customizations':{k:ENGINE.get_customization(k) for k in ENGINE.manifest()}}
@router.get('/generation/provider')
def generation_provider_status():
 return {'configured':True,'mode':'retrieval_cache_extractive','provider':'local_deterministic','requires_api_key':False,'model_required':False}
@router.put('/workspaces/{workspace}/customization')
def update_workspace_customization(workspace:str,payload:WorkspaceConfig):
 try:return ENGINE.customize(workspace,payload.config)
 except ValueError as e: raise HTTPException(400,str(e)) from e
@router.get('/workspaces/{workspace}/customization')
def get_workspace_customization(workspace:str):
 if workspace not in ENGINE.manifest(): raise HTTPException(404,'Workspace not found')
 return ENGINE.get_customization(workspace)
@router.post('/generation/artifacts',status_code=201)
def generate_artifact(payload:GenerateRequest):
 try:
  artifact=ENGINE.generate(workspace=payload.workspace,kind=payload.kind,title=payload.title,source_documents=payload.source_documents,ucks_repo=UCKS)
  route=ENGINE.route(artifact['id'],payload.workspace,'auto-generated learning resources',adapter=ADAPTER)
  artifact['publication']={'status':'provisional','route_status':route.get('status','delivered'),
                           'human_preapproval_required':False,
                           'clinical_validation':'not_assessed'}
  return artifact
 except ValueError as e: raise HTTPException(422,str(e)) from e
 except RuntimeError as e: raise HTTPException(503,str(e)) from e
@router.get('/generation/artifacts')
def list_generated_artifacts(workspace:str|None=None,limit:int=50):
 if workspace and workspace not in ENGINE.manifest(): raise HTTPException(400,'Unknown workspace')
 return ENGINE.list_artifacts(workspace, max(1,min(limit,200)))
@router.get('/generation/artifacts/{artifact_id}')
def get_generated_artifact(artifact_id:str):
 item=ENGINE.get_artifact(artifact_id)
 if not item: raise HTTPException(404,'Generated artifact not found')
 return item
@router.post('/generation/artifacts/{artifact_id}/review')
def review_generated_artifact(artifact_id:str,payload:ReviewRequest,x_hsptl_reviewer_token:str|None=Header(default=None)):
 reviewer=_reviewer(x_hsptl_reviewer_token)
 try:return ENGINE.review(artifact_id,payload.decision,reviewer)
 except ValueError as e: raise HTTPException(400,str(e)) from e
@router.post('/distribution/routes',status_code=201)
def distribute_artifact(payload:RouteRequest,artifact_id:str):
 try:return ENGINE.route(artifact_id,payload.workspace,payload.section,adapter=ADAPTER)
 except ValueError as e: raise HTTPException(400,str(e)) from e
@router.get('/distribution/routes')
def list_distribution_routes(workspace:str|None=None):
 if workspace and workspace not in ENGINE.manifest(): raise HTTPException(400,'Unknown workspace')
 return ENGINE.routes(workspace)
