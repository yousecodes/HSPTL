from contextlib import contextmanager
import sqlite3
from pathlib import Path
import pytest
from backend.hsptl_core.generation_distribution import GenerationDistribution, OUTPUT_SCHEMAS
from backend.hsptl_core.workspace_distribution import WorkspaceDistributionAdapter
from backend.hsptl_core.store import StudyStore

TEXT='The guideline recommends structured assessment and documented clinical review before escalation.'

class FakeStore:
    def __init__(self,path):
        self.path=path
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE ucks_chunks(id TEXT,document_id TEXT,version INTEGER,ordinal INTEGER,heading TEXT,body TEXT)')
            c.execute('CREATE TABLE ucks_rights_reviews(document_id TEXT,decision TEXT,scope TEXT,created_at TEXT)')
            c.execute('INSERT INTO ucks_chunks VALUES(?,?,?,?,?,?)',('chunk-1','d1',1,0,'Evidence',TEXT))
    @contextmanager
    def transaction(self):
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row
        try:
            yield c; c.commit()
        except Exception:
            c.rollback(); raise
        finally: c.close()

class FakeUCKS:
    def __init__(self, store, docs): self.store=store; self.docs=docs
    def get_document(self, did): return self.docs.get(did)

class FakeModel:
    def generate(self, *, model, system, user):
        import json
        req=json.loads(user)
        return {'sections':[{'heading':heading,'claims':[{'text':'The source describes structured assessment.','citations':[{'chunk_id':'chunk-1','quote':'The guideline recommends structured assessment'}]}]} for heading in req['required_sections']], 'limitations':['Evidence is limited to the supplied source spans.']}

def doc(i='d1', status='reviewed'):
    return {'id':i,'title':'Acute asthma review','content_type':'guideline','specialty':'Respiratory','jurisdiction':'UK','publication_date':'2025','review_status':status,'lifecycle_state':'current','current_version':1,'source_url':'https://example.test/source','licence':'CC-BY','provenance':{'origin':'test'}}

def engine(tmp_path):
    e=GenerationDistribution(tmp_path/'generation.db', FakeModel()); e.model_name='test-model'
    store=FakeStore(tmp_path/'ucks.db')
    return e, FakeUCKS(store,{'d1':doc()})

def test_workspace_scripts_are_distinct_and_config_is_scoped(tmp_path):
    e,_=engine(tmp_path); m=e.manifest()
    assert len({tuple(x['sequence']) for x in m.values()}) == 7
    saved=e.customize('clinic', {'display_name':'Acute Clinic','focus':'Respiratory','sequence_overrides':['triage','reasoning']})
    assert saved['config']['display_name']=='Acute Clinic'
    assert e.get_customization('ward')['config']=={}

def test_retrieval_cache_generation_is_provisionally_published_without_preapproval(tmp_path):
    e,repo=engine(tmp_path)
    a=e.generate(workspace='clinic',kind='case_report',title='Asthma case synthesis',source_documents=['d1'],ucks_repo=repo)
    assert a['status']=='provisional' and a['body']['generation_mode']=='retrieval_cache_extractive'
    assert a['body']['publication']['human_preapproval_required'] is False
    assert a['body']['validation']['valid'] is True
    citation=a['body']['sections'][0]['claims'][0]['citations'][0]
    assert citation['start_offset']==0 and citation['end_offset']>0
    delivered=e.route(a['id'],'clinic','reports')
    assert delivered['status']=='delivered'
    approved=e.review(a['id'],'approved','Clinical Reviewer')
    assert approved['status']=='approved'

def test_generation_rejects_retracted_and_rejected_sources(tmp_path):
    e,repo=engine(tmp_path)
    for d in (doc(status='rejected'), {**doc(), 'lifecycle_state':'retracted'}):
        repo.docs['d1']=d
        with pytest.raises(ValueError):
            e.generate(workspace='clinic',kind='case_report',title='Test',source_documents=['d1'],ucks_repo=repo)

def test_generation_rejects_unlicensed_full_text(tmp_path):
    e,repo=engine(tmp_path); repo.docs['d1']={**doc(),'licence':'All rights reserved'}
    with pytest.raises(ValueError,match='Full-text generation is not permitted'):
        e.generate(workspace='clinic',kind='case_report',title='Test',source_documents=['d1'],ucks_repo=repo)

def test_output_specific_validation_rejects_missing_section_and_false_quote(tmp_path):
    e,_=engine(tmp_path)
    spans=[{'chunk_id':'chunk-1','document_id':'d1','text':TEXT,'source_url':'https://example.test'}]
    with pytest.raises(ValueError,match='Missing required sections'):
        e._validate_output('case_report',{'sections':[{'heading':'problem_representation','claims':[{'text':'Claim','citations':[{'chunk_id':'chunk-1','quote':TEXT[:30]}]}]}]},spans)
    bad={'sections':[{'heading':h,'claims':[{'text':'Claim','citations':[{'chunk_id':'chunk-1','quote':'invented source quotation'}]}]} for h in OUTPUT_SCHEMAS['case_report']['sections']]}
    with pytest.raises(ValueError,match='does not match'):
        e._validate_output('case_report',bad,spans)

def test_distribution_adapter_delivers_to_native_workspace_content_index(tmp_path):
    store=StudyStore(tmp_path/'study.db')
    adapter=WorkspaceDistributionAdapter(store)
    artifact={'id':'gen_test','kind':'pearl','title':'Acute asthma pearl','workspace':'exam_hall','body':{'sections':[{'heading':'clinical_pearl','claims':[{'text':'Use a structured assessment.'}]}]}}
    delivered=adapter.deliver(artifact,'high-yield pearls')
    assert delivered['adapter']=='tagged_content_index'
    with store.transaction() as c:
        row=c.execute('SELECT workspace,source_status,title FROM tagged_content_items WHERE item_id=?',(delivered['destination_id'],)).fetchone()
    assert tuple(row)==('exam','unreviewed','Acute asthma pearl')

def test_distribution_adapter_maps_all_six_workspaces(tmp_path):
    store=StudyStore(tmp_path/'all-workspaces.db')
    adapter=WorkspaceDistributionAdapter(store)
    cases=[('clinic','case_report','case_report','conference'),('rounds','tagged_report','case_report','rounds'),('lab','spot_diagnosis','osce','lab'),('ward','on_call_scenario','simulation','on_call'),('exam_hall','pearl','pearl','exam'),('portfolio','progress_snapshot','case','data_tools')]
    for i,(workspace,kind,content_type,target) in enumerate(cases):
        result=adapter.deliver({'id':f'gen-{i}','kind':kind,'title':f'Artifact {i}','workspace':workspace,'body':{'sections':[]}},'default')
        with store.transaction() as c:
            row=c.execute('SELECT content_type,workspace,source_status FROM tagged_content_items WHERE item_id=?',(result['destination_id'],)).fetchone()
        assert tuple(row)==(content_type,target,'unreviewed')

def test_question_set_adapter_populates_unreviewed_exam_bank(tmp_path):
    store=StudyStore(tmp_path/'exam-bank.db')
    adapter=WorkspaceDistributionAdapter(store)
    artifact={'id':'gen-q','kind':'question_set','title':'Respiratory question set','workspace':'exam_hall',
      'source_refs':[{'title':'Guideline','source_url':'https://example.test/guideline','licence':'CC-BY-4.0','specialty':'Respiratory'}],
      'body':{'sections':[],'assessment_items':[{'question':'Which assessment is recommended?','options':['Structured assessment','No assessment'],'answer':'Structured assessment','explanation':'Source-based rationale.','citations':[{'chunk_id':'c1','document_id':'d1','quote':'The guideline recommends structured assessment','start_offset':0,'end_offset':44,'source_url':'https://example.test/guideline'}]}]}}
    adapter.deliver(artifact,'question bank')
    questions=adapter.exams.questions(kind='MCQ',reviewed=False)
    assert questions['count']==1
    assert questions['questions'][0]['question']=='Which assessment is recommended?'
    assert 'HSPTL source-span citations' in questions['questions'][0]['explanation']


def test_generation_cache_reuses_retrieved_content_without_calling_model(tmp_path):
    e,repo=engine(tmp_path)
    class ExplodingModel:
        def generate(self, **kwargs): raise AssertionError('model must never be called')
    e.model_generator=ExplodingModel()
    first=e.generate(workspace='clinic',kind='case_report',title='Asthma case synthesis',source_documents=['d1'],ucks_repo=repo)
    second=e.generate(workspace='clinic',kind='case_report',title='Asthma case synthesis',source_documents=['d1'],ucks_repo=repo)
    assert first['body']==second['body']
    assert first['id'] != second['id']
    with e.connect() as c:
        row=c.execute('SELECT hit_count FROM generation_cache').fetchone()
    assert row['hit_count']==1

def test_generation_uses_retrieved_source_verbatim_and_labels_extractive_mode(tmp_path):
    e,repo=engine(tmp_path)
    a=e.generate(workspace='clinic',kind='case_report',title='Structured assessment',source_documents=['d1'],ucks_repo=repo)
    assert a['body']['generation_mode']=='retrieval_cache_extractive'
    for section in a['body']['sections']:
        claim=section['claims'][0]
        assert claim['text']==claim['citations'][0]['quote']
