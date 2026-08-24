"""Contract tests for Cypher queries used across the application."""

import pytest

from pipelines.ingestion.graph_loader import KuzuGraphLoader
from tools.adapters.kuzu_store import make_graph_store
from tools.elicitation.db_schema import ElicitationSchemaInitializer


from tools.adapters.ladybug_store import LadybugGraphStore


@pytest.fixture(autouse=True)
def _clear_db_cache():
    yield
    LadybugGraphStore.clear_cache()
    import gc
    gc.collect()


@pytest.mark.deterministic
def test_char_save_subject_check(tmp_path):
    """1. save_subject_check"""
    db_path = str(tmp_path / "db1")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', engagement: 'eng1', level: 'L1'})")
    
    query = "MATCH (s:Subject) WHERE s.name = 'subj1' AND (s.engagement = 'eng1' OR s.engagement = 'default') RETURN s.name as name, s.level as level;"
    res = client.execute_cypher(query)
    assert sorted([r['name'] for r in res]) == ['subj1']
    assert sorted([r['level'] for r in res]) == ['L1']
    client.close()

@pytest.mark.deterministic
def test_char_save_subject_update(tmp_path):
    """2. save_subject_update"""
    db_path = str(tmp_path / "db2")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', engagement: 'eng1', definition: 'old'})")
    
    query = "MATCH (s:Subject) WHERE s.name = 'subj1' AND (s.engagement = 'eng1' OR s.engagement = 'default') SET s.definition = 'new';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (s:Subject) RETURN s.definition as definition;")
    assert res[0]['definition'] == 'new'
    client.close()

@pytest.mark.deterministic
def test_char_save_subject_create(tmp_path):
    """3. save_subject_create"""
    db_path = str(tmp_path / "db3")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (s:Subject {id: '1'}) SET s.name = 'subj1', s.engagement = 'eng1', s.definition = 'def1', s.level = 'L0_named', s.origin = 'orig', s.updated_at = 'now';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (s:Subject) RETURN s.id as id, s.name as name, s.level as level;")
    assert res[0]['id'] == '1'
    assert res[0]['name'] == 'subj1'
    assert res[0]['level'] == 'L0_named'
    client.close()

@pytest.mark.deterministic
def test_char_subject_levels(tmp_path):
    """4. subject_levels"""
    db_path = str(tmp_path / "db4")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', level: 'L2'})")
    
    query = "MATCH (s:Subject) RETURN s.name as name, s.level as level;"
    res = client.execute_cypher(query)
    assert res[0]['name'] == 'subj1'
    assert res[0]['level'] == 'L2'
    client.close()

@pytest.mark.deterministic
def test_char_sections_with_statements(tmp_path):
    """5. sections_with_statements"""
    db_path = str(tmp_path / "db5")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Statement {id: '1', engagement: 'eng1', status: 'active', section: 'sec1'})")
    
    query = "MATCH (s:Statement {engagement: 'eng1', status: 'active'}) RETURN s.section as section;"
    res = client.execute_cypher(query)
    assert res[0]['section'] == 'sec1'
    client.close()

@pytest.mark.deterministic
def test_char_save_question(tmp_path):
    """6. save_question"""
    db_path = str(tmp_path / "db6")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (q:Question {id: 'q1'}) SET q.engagement = 'eng1', q.gap_type = 'gap1';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (q:Question) RETURN q.id as id, q.engagement as engagement, q.gap_type as gap_type;")
    assert res[0]['id'] == 'q1'
    assert res[0]['engagement'] == 'eng1'
    assert res[0]['gap_type'] == 'gap1'
    client.close()

@pytest.mark.deterministic
def test_char_save_question_targets(tmp_path):
    """7. save_question_targets"""
    db_path = str(tmp_path / "db7")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (q:Question {id: 'q1'}) MERGE (s:Subject {id: 's1'}) MERGE (q)-[:TARGETS]->(s);"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (q:Question)-[:TARGETS]->(s:Subject) RETURN q.id as q_id, s.id as s_id;")
    assert res[0]['q_id'] == 'q1'
    assert res[0]['s_id'] == 's1'
    client.close()

@pytest.mark.deterministic
def test_char_update_question_status(tmp_path):
    """8. update_question_status"""
    db_path = str(tmp_path / "db8")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (q:Question {id: 'q1', status: 'open'})")
    
    query = "MATCH (q:Question {id: 'q1'}) SET q.status = 'closed';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (q:Question) RETURN q.status as status;")
    assert res[0]['status'] == 'closed'
    client.close()

@pytest.mark.deterministic
def test_char_save_statement_merge(tmp_path):
    """9. save_statement_merge"""
    db_path = str(tmp_path / "db9")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (st:Statement {id: 'st1'}) SET st.engagement = 'eng1', st.section = 'sec1';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (st:Statement) RETURN st.id as id, st.engagement as engagement;")
    assert res[0]['id'] == 'st1'
    assert res[0]['engagement'] == 'eng1'
    client.close()

@pytest.mark.deterministic
def test_char_save_statement_about(tmp_path):
    """10. save_statement_about"""
    db_path = str(tmp_path / "db10")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (st:Statement {id: 'st1'}) MERGE (sub:Subject {id: 'sub1'}) MERGE (st)-[:ABOUT]->(sub);"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (st:Statement)-[:ABOUT]->(sub:Subject) RETURN st.id as st_id, sub.id as sub_id;")
    assert res[0]['st_id'] == 'st1'
    assert res[0]['sub_id'] == 'sub1'
    client.close()

@pytest.mark.deterministic
def test_char_save_conflict_create(tmp_path):
    """11. save_conflict_create"""
    db_path = str(tmp_path / "db11")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "CREATE (c:Conflict {id: 'c1', kind: 'k1', detail: 'd1', status: 's1', origin: 'o1', resolution: '', arbitrated_by: ''});"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (c:Conflict) RETURN c.id as id, c.kind as kind;")
    assert res[0]['id'] == 'c1'
    assert res[0]['kind'] == 'k1'
    client.close()

@pytest.mark.deterministic
def test_char_save_conflict_involves(tmp_path):
    """12. save_conflict_involves"""
    db_path = str(tmp_path / "db12")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (c:Conflict {id: 'c1'}) MERGE (st:Statement {id: 'st1'}) MERGE (c)-[:INVOLVES]->(st);"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (c:Conflict)-[:INVOLVES]->(st:Statement) RETURN c.id as c_id, st.id as st_id;")
    assert res[0]['c_id'] == 'c1'
    assert res[0]['st_id'] == 'st1'
    client.close()

@pytest.mark.deterministic
def test_char_arbitrate_conflict_set(tmp_path):
    """13. arbitrate_conflict_set"""
    db_path = str(tmp_path / "db13")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (c:Conflict {id: 'c1'})")
    
    query = "MATCH (c:Conflict {id: 'c1'}) SET c.status = 'arbitrated', c.resolution = 'res1', c.arbitrated_by = 'user1';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (c:Conflict) RETURN c.status as status, c.resolution as resolution;")
    assert res[0]['status'] == 'arbitrated'
    assert res[0]['resolution'] == 'res1'
    client.close()

@pytest.mark.deterministic
def test_char_arbitrate_conflict_involved(tmp_path):
    """14. arbitrate_conflict_involved"""
    db_path = str(tmp_path / "db14")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (c:Conflict {id: 'c1'})-[:INVOLVES]->(st:Statement {id: 'st1'})")
    
    query = "MATCH (c:Conflict {id: 'c1'})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'st1'
    client.close()

@pytest.mark.deterministic
def test_char_arbitrate_conflict_superseded(tmp_path):
    """15. arbitrate_conflict_superseded"""
    db_path = str(tmp_path / "db15")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (st:Statement {id: 'st1'})")
    
    query = "MATCH (st:Statement {id: 'st1'}) SET st.status = 'superseded';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (st:Statement) RETURN st.status as status;")
    assert res[0]['status'] == 'superseded'
    client.close()

@pytest.mark.deterministic
def test_char_save_uncertainty_count(tmp_path):
    """16. save_uncertainty_count"""
    db_path = str(tmp_path / "db16")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (u:Uncertainty {id: 'u1'})")
    client.execute_cypher("CREATE (u:Uncertainty {id: 'u2'})")
    
    query = "MATCH (u:Uncertainty) RETURN count(u.id) as c;"
    res = client.execute_cypher(query)
    assert res[0]['c'] == 2
    client.close()

@pytest.mark.deterministic
def test_char_save_uncertainty_create(tmp_path):
    """17. save_uncertainty_create"""
    db_path = str(tmp_path / "db17")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "CREATE (u:Uncertainty {id: 'u1', engagement: 'eng1', text: 'txt1', subject: 'sub1'});"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (u:Uncertainty) RETURN u.id as id, u.text as text;")
    assert res[0]['id'] == 'u1'
    assert res[0]['text'] == 'txt1'
    client.close()

@pytest.mark.deterministic
def test_char_get_statement(tmp_path):
    """18. get_statement"""
    db_path = str(tmp_path / "db18")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Statement {id: 'st1', section: 'sec1'})-[:ABOUT]->(sub:Subject {id: 'sub1', name: 'subj1'})")
    
    query = "MATCH (s:Statement {id: 'st1'}) OPTIONAL MATCH (s)-[:ABOUT]->(sub:Subject) RETURN s.id as id, s.section as section, sub.name as subject;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'st1'
    assert res[0]['section'] == 'sec1'
    assert res[0]['subject'] == 'subj1'
    client.close()

@pytest.mark.deterministic
def test_char_get_uncertainties(tmp_path):
    """19. get_uncertainties"""
    db_path = str(tmp_path / "db19")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (u:Uncertainty {id: 'u1', text: 't1', subject: 's1', engagement: 'eng1'})")
    
    query = "MATCH (u:Uncertainty {engagement: 'eng1'}) RETURN u.id as id, u.text as text, u.subject as subject;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'u1'
    assert res[0]['text'] == 't1'
    assert res[0]['subject'] == 's1'
    client.close()

@pytest.mark.deterministic
def test_char_get_conflict_detail(tmp_path):
    """20. get_conflict_detail"""
    db_path = str(tmp_path / "db20")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (c:Conflict {id: 'c1', kind: 'k1', detail: 'd1', status: 's1'})")
    
    query = "MATCH (c:Conflict {id: 'c1'}) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'c1'
    assert res[0]['kind'] == 'k1'
    assert res[0]['detail'] == 'd1'
    assert res[0]['status'] == 's1'
    client.close()

@pytest.mark.deterministic
def test_char_get_conflict_involved(tmp_path):
    """21. get_conflict_involved (Same as #14)"""
    db_path = str(tmp_path / "db21")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (c:Conflict {id: 'c1'})-[:INVOLVES]->(st:Statement {id: 'st1'})")
    
    query = "MATCH (c:Conflict {id: 'c1'})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'st1'
    client.close()

@pytest.mark.deterministic
def test_char_run_checks_contradiction(tmp_path):
    """22. run_checks_contradiction"""
    db_path = str(tmp_path / "db22")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s1:Statement {id: '1', engagement: 'eng1', status: 'active', subject: 'subj1', predicate: 'p1', value: 'v1'})")
    client.execute_cypher("CREATE (s2:Statement {id: '2', engagement: 'eng1', status: 'active', subject: 'subj1', predicate: 'p1', value: 'v2'})")
    
    query = "MATCH (s1:Statement {engagement: 'eng1', status: 'active'}), (s2:Statement {engagement: 'eng1', status: 'active'}) WHERE s1.id < s2.id AND s1.subject = s2.subject AND ((s1.predicate = s2.predicate AND s1.value <> s2.value) OR (s1.author <> s2.author AND s1.predicate = s2.predicate)) RETURN s1.id as s1_id, s2.id as s2_id, s1.subject as subject, s1.predicate as pred, s1.value as v1, s2.value as v2;"
    res = client.execute_cypher(query)
    assert res[0]['s1_id'] == '1'
    assert res[0]['s2_id'] == '2'
    assert res[0]['v1'] == 'v1'
    assert res[0]['v2'] == 'v2'
    client.close()

@pytest.mark.deterministic
def test_char_get_question(tmp_path):
    """23. get_question"""
    db_path = str(tmp_path / "db23")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (q:Question {id: 'q1', engagement: 'eng1'})")
    
    query = "MATCH (q:Question {id: 'q1'}) RETURN q.id as id, q.engagement as engagement;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'q1'
    assert res[0]['engagement'] == 'eng1'
    client.close()

@pytest.mark.deterministic
def test_char_get_active_statements(tmp_path):
    """24. get_active_statements"""
    db_path = str(tmp_path / "db24")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Statement {id: 'st1', engagement: 'eng1'})-[:ABOUT]->(sub:Subject {id: 'sub1', name: 'subj1'})")
    
    query = "MATCH (s:Statement {engagement: 'eng1'}) OPTIONAL MATCH (s)-[:ABOUT]->(sub:Subject) RETURN s.id as id, sub.name as subject;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'st1'
    assert res[0]['subject'] == 'subj1'
    client.close()

@pytest.mark.deterministic
def test_char_get_conflicts(tmp_path):
    """25. get_conflicts"""
    db_path = str(tmp_path / "db25")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (c:Conflict {id: 'c1', status: 'open', kind: 'k1'})")
    
    query = "MATCH (c:Conflict {status: 'open'}) RETURN c.id as id, c.kind as kind;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'c1'
    assert res[0]['kind'] == 'k1'
    client.close()

@pytest.mark.deterministic
def test_char_advance_subject_level(tmp_path):
    """26. advance_subject_level"""
    db_path = str(tmp_path / "db26")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', level: 'L1'})")
    
    query = "MATCH (s:Subject {name: 'subj1'}) SET s.level = 'L2', s.updated_at = 'now';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (s:Subject) RETURN s.level as level, s.updated_at as updated_at;")
    assert res[0]['level'] == 'L2'
    assert res[0]['updated_at'] == 'now'
    client.close()

@pytest.mark.deterministic
def test_char_get_subject_maturity(tmp_path):
    """27. get_subject_maturity"""
    db_path = str(tmp_path / "db27")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', engagement: 'eng1', level: 'L1', origin: 'o1', updated_at: 'now'})")
    
    query = "MATCH (s:Subject) WHERE s.name = 'subj1' AND (s.engagement = 'eng1' OR s.engagement = 'default' OR s.engagement IS NULL) RETURN s.name as name, s.level as level, s.origin as origin, s.updated_at as updated_at;"
    res = client.execute_cypher(query)
    assert res[0]['name'] == 'subj1'
    assert res[0]['level'] == 'L1'
    client.close()

@pytest.mark.deterministic
def test_char_get_subjects_maturity_board(tmp_path):
    """28. get_subjects_maturity_board"""
    db_path = str(tmp_path / "db28")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', level: 'L1', origin: 'o1', updated_at: 'now'})")
    
    query = "MATCH (s:Subject) RETURN s.name as name, s.level as level, s.origin as origin, s.updated_at as updated_at;"
    res = client.execute_cypher(query)
    assert res[0]['name'] == 'subj1'
    assert res[0]['level'] == 'L1'
    client.close()

@pytest.mark.deterministic
def test_char_maturity_board_open_questions(tmp_path):
    """29. maturity_board_open_questions"""
    db_path = str(tmp_path / "db29")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (q:Question {id: 'q1', status: 'open', routed_to: 'r1'})-[:TARGETS]->(s:Subject {id: 's1', name: 'subj1'})")
    
    query = "MATCH (q:Question {status: 'open'})-[:TARGETS]->(s:Subject {name: 'subj1'}) RETURN q.id as id, q.routed_to as routed_to;"
    res = client.execute_cypher(query)
    assert res[0]['id'] == 'q1'
    assert res[0]['routed_to'] == 'r1'
    client.close()

@pytest.mark.deterministic
def test_char_demote_subject_level(tmp_path):
    """30. demote_subject_level"""
    db_path = str(tmp_path / "db30")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (s:Subject {id: '1', name: 'subj1', level: 'L2'})")
    
    query = "MATCH (s:Subject {name: 'subj1'}) SET s.level = 'L1', s.updated_at = 'now';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (s:Subject) RETURN s.level as level, s.updated_at as updated_at;")
    assert res[0]['level'] == 'L1'
    assert res[0]['updated_at'] == 'now'
    client.close()

@pytest.mark.deterministic
def test_char_demote_statements(tmp_path):
    """31. demote_statements"""
    db_path = str(tmp_path / "db31")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (st:Statement {id: '1', engagement: 'eng1', subject: 'sub1', status: 'active'})")
    
    query = "MATCH (st:Statement {engagement: 'eng1', subject: 'sub1'}) WHERE st.status = 'active' SET st.status = 'under_review';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (st:Statement) RETURN st.status as status;")
    assert res[0]['status'] == 'under_review'
    client.close()

@pytest.mark.deterministic
def test_char_demote_reopen_questions(tmp_path):
    """32. demote_reopen_questions"""
    db_path = str(tmp_path / "db32")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (q:Question {id: 'q1', engagement: 'eng1', status: 'confirmed'})-[:TARGETS]->(s:Subject {id: 's1', name: 'subj1'})")
    
    query = "MATCH (q:Question {engagement: 'eng1'})-[:TARGETS]->(s:Subject {name: 'subj1'}) WHERE q.status IN ['confirmed', 'sent'] SET q.status = 'open';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (q:Question) RETURN q.status as status;")
    assert res[0]['status'] == 'open'
    client.close()

@pytest.mark.deterministic
def test_char_merge_glossary_term(tmp_path):
    """33. merge_glossary_term"""
    db_path = str(tmp_path / "db33")
    KuzuGraphLoader(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (g:GlossaryTerm {term: 't1'}) SET g.definition = 'def1';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (g:GlossaryTerm) RETURN g.term as term, g.definition as definition;")
    assert res[0]['term'] == 't1'
    assert res[0]['definition'] == 'def1'
    client.close()

@pytest.mark.deterministic
def test_char_merge_asset(tmp_path):
    """34. merge_asset"""
    db_path = str(tmp_path / "db34")
    KuzuGraphLoader(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "MERGE (a:Asset {id: 'a1'}) SET a.title = 't1', a.type = 'type1';"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (a:Asset) RETURN a.id as id, a.title as title, a.type as type;")
    assert res[0]['id'] == 'a1'
    assert res[0]['title'] == 't1'
    assert res[0]['type'] == 'type1'
    client.close()

@pytest.mark.deterministic
def test_char_merge_supersedes_rel(tmp_path):
    """35. merge_supersedes_rel"""
    db_path = str(tmp_path / "db35")
    KuzuGraphLoader(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (a1:Asset {id: 'a1'})")
    client.execute_cypher("CREATE (a2:Asset {id: 'a2'})")
    
    query = "MATCH (a1:Asset {id: 'a1'}), (a2:Asset {id: 'a2'}) MERGE (a1)-[:SUPERSEDES]->(a2);"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (a1:Asset)-[:SUPERSEDES]->(a2:Asset) RETURN a1.id as a1_id, a2.id as a2_id;")
    assert res[0]['a1_id'] == 'a1'
    assert res[0]['a2_id'] == 'a2'
    client.close()

@pytest.mark.deterministic
def test_char_merge_requires_rel(tmp_path):
    """36. merge_requires_rel"""
    db_path = str(tmp_path / "db36")
    KuzuGraphLoader(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (a1:Asset {id: 'a1'})")
    client.execute_cypher("CREATE (a2:Asset {id: 'a2'})")
    
    query = "MATCH (a1:Asset {id: 'a1'}), (a2:Asset {id: 'a2'}) MERGE (a1)-[:REQUIRES]->(a2);"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (a1:Asset)-[:REQUIRES]->(a2:Asset) RETURN a1.id as a1_id, a2.id as a2_id;")
    assert res[0]['a1_id'] == 'a1'
    assert res[0]['a2_id'] == 'a2'
    client.close()

@pytest.mark.deterministic
def test_char_merge_defines_rel(tmp_path):
    """37. merge_defines_rel"""
    db_path = str(tmp_path / "db37")
    KuzuGraphLoader(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    client.execute_cypher("CREATE (a:Asset {id: 'a1'})")
    client.execute_cypher("CREATE (g:GlossaryTerm {term: 't1'})")
    
    query = "MATCH (a:Asset {id: 'a1'}), (g:GlossaryTerm {term: 't1'}) MERGE (a)-[:DEFINES]->(g);"
    client.execute_cypher(query)
    
    res = client.execute_cypher("MATCH (a:Asset)-[:DEFINES]->(g:GlossaryTerm) RETURN a.id as a_id, g.term as g_term;")
    assert res[0]['a_id'] == 'a1'
    assert res[0]['g_term'] == 't1'
    client.close()

@pytest.mark.deterministic
def test_char_health_check(tmp_path):
    """38. health_check"""
    db_path = str(tmp_path / "db38")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "RETURN 1;"
    res = client.execute_cypher(query)
    assert res[0]['1'] == 1
    client.close()

@pytest.mark.deterministic
def test_char_show_tables(tmp_path):
    """39. show_tables"""
    db_path = str(tmp_path / "db39")
    ElicitationSchemaInitializer(db_path=db_path)
    client = make_graph_store(db_path, read_only=False)
    
    query = "CALL show_tables() RETURN name;"
    res = client.execute_cypher(query)
    tables = sorted([r['name'] for r in res])
    assert 'Subject' in tables
    assert 'Statement' in tables
    client.close()
