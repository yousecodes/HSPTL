import hashlib
import pytest
from backend.hsptl_core.deterministic_intelligence import DeterministicIntelligenceEngine, Abstention
from backend.hsptl_core.deterministic_intelligence.constraints import evaluate


def engine(tmp_path): return DeterministicIntelligenceEngine(tmp_path/'di.db')


def test_event_log_append_only_and_replay(tmp_path):
    e=engine(tmp_path)
    e.register_entity('ev1','Guideline','Guideline 1',{})
    replay=e.replay()
    assert replay['verified'] and replay['events_replayed']>=2
    assert replay['projection']['entities']['ev1']['entity_class']=='Guideline'
    with e.connect() as c:
        with pytest.raises(Exception): c.execute("UPDATE di_events SET payload_json='{}' WHERE seq=1")
        with pytest.raises(Exception): c.execute('DELETE FROM di_events WHERE seq=1')


def test_ontology_type_and_unknown_class_fail_closed(tmp_path):
    e=engine(tmp_path)
    with pytest.raises(Abstention): e.register_entity('x','UnknownClinicalThing','X')
    with pytest.raises(Abstention): e.assert_relationship('a','unknown_predicate','b','ev')


def test_evidence_requires_explicit_rights_and_typed_entity(tmp_path):
    e=engine(tmp_path);e.register_entity('ev1','Guideline','Guideline')
    with pytest.raises(Abstention): e.register_evidence('e1','ev1','src','hash','unknown','full_text','1')
    assert e.register_evidence('e1','ev1','src','hash','permitted','full_text','1')['evidence_id']=='e1'


def test_appraisal_and_source_span_are_canonical(tmp_path):
    e=engine(tmp_path);e.register_entity('ev1','Guideline','Guideline')
    e.register_evidence('e1','ev1','src','abc123','permitted','full_text','1')
    with pytest.raises(Abstention): e.record_appraisal('a1','e1','pass',derivation=None)
    e.record_appraisal('a1','e1','pass',derivation={'criteria':['methodological validity'],'reviewer':'reviewer-1'})
    assert e.register_source_span('s1','e1','abc123','Evidence statement.',0,19)['span_id']=='s1'
    with pytest.raises(Abstention): e.register_source_span('s2','e1','wrong','Evidence statement.',0,19)


def test_composition_abstains_when_solver_unavailable_or_evidence_fails(tmp_path):
    e=engine(tmp_path);e.register_entity('ev1','Guideline','Guideline')
    e.register_evidence('e1','ev1','src','abc123','permitted','full_text','1')
    e.record_appraisal('a1','e1','pass',derivation={'review':'complete'})
    e.register_source_span('s1','e1','abc123','Evidence statement.',0,19)
    try:
        import z3  # noqa
    except ImportError:
        with pytest.raises(Abstention,match='SMT solver'): e.compose_learning_object('lo1','clinic','clinical-evidence-object','1.0.0',{'clinical_assertion':'x','evidence_context':'e1','limitations':'s1'},[{'evidence_id':'e1','source_span_id':'s1','text':'Evidence statement.'}])


def test_curriculum_is_dag_and_topologically_sorted(tmp_path):
    e=engine(tmp_path)
    e.register_competency('c1','Foundations')
    e.register_competency('c2','Applied',prerequisites=['c1'])
    assert e.curriculum_order(['c2','c1'])==['c1','c2']
    assert e.prerequisites_satisfied('c2',[])['eligible'] is False
    with pytest.raises(Abstention): e.register_competency('c1','Foundations',prerequisites=['c2'])


def test_routing_requires_explicit_satisfied_predicates(tmp_path):
    e=engine(tmp_path)
    with pytest.raises(Abstention): e.route('missing','clinic',{'stage':'intern'},{'stage':'intern'})
    with pytest.raises(Abstention): e.route('missing','clinic',{'stage':'intern'},{'jurisdiction':'Egypt'})


def test_projection_staleness_fails_closed(tmp_path):
    e=engine(tmp_path);e.register_entity('ev1','Guideline','Guideline');e.replay()
    assert e.projection_status()['fresh'] is True
    e.register_entity('ev2','Trial','Trial')
    with pytest.raises(Abstention,match='stale'): e.projection_status()


def test_replay_detects_tampering(tmp_path):
    e=engine(tmp_path);e.register_entity('ev1','Guideline','Guideline')
    with e.connect() as c:
        c.execute('DROP TRIGGER di_events_no_update')
        c.execute("UPDATE di_events SET event_hash='bad' WHERE seq=1")
    with pytest.raises(Abstention,match='Hash-chain'):e.replay()


def test_predicate_dsl_returns_unknown_for_missing_or_unsupported():
    assert evaluate({'op':'eq','attribute':'stage','value':'intern'},{'stage':'intern'}) is True
    assert evaluate({'op':'eq','attribute':'stage','value':'intern'},{}) is None
    assert evaluate({'op':'model_magic','attribute':'stage','value':'intern'},{'stage':'intern'}) is None


def test_rule_tables_are_versioned_data(tmp_path):
    e=engine(tmp_path)
    tables=e.rule_tables()
    assert any(x['rule_id']=='APP-001' and x['version']=='1.0.0' for x in tables)


def test_gap_analysis_is_set_difference_not_score(tmp_path):
    e=engine(tmp_path)
    result=e.analyse_gap('gap1',['population','intervention','outcome'],['population','outcome'],'PICO-Q1')
    assert result['missing']==['intervention'] and result['complete'] is False


def test_conflict_analysis_abstains_without_smt(tmp_path):
    e=engine(tmp_path)
    e.register_entity('ev1','Guideline','Guideline 1');e.register_evidence('e1','ev1','src','h1','permitted','metadata','1')
    e.register_entity('ev2','Trial','Trial 2');e.register_evidence('e2','ev2','src2','h2','permitted','metadata','1')
    try: import z3  # noqa
    except ImportError:
        with pytest.raises(Abstention,match='SMT solver unavailable'):
            e.detect_conflict('cf1','benefit','adult-population','e1','e2','positive','negative')
    else:
        result=e.detect_conflict('cf1','benefit','adult-population','e1','e2','positive','negative')
        assert result['conflict'] is True and result['proof']['result']=='unsat'
