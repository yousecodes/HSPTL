from fastapi.testclient import TestClient

from backend.main import app


def test_shared_tag_catalogue_has_clinical_facets():
    with TestClient(app) as client:
        response = client.get('/api/tagging/catalogue')
    assert response.status_code == 200
    payload = response.json()
    assert payload['count'] >= 70
    assert {'specialty', 'presentation', 'task', 'modality', 'setting', 'difficulty'} <= set(payload['facets'])
    assert any(item['tag_id'] == 'specialty.cardiology' for item in payload['tags'])
    assert any(item['tag_id'] == 'modality.ecg' for item in payload['tags'])


def test_tagged_content_can_be_found_across_workspaces_and_recorded():
    with TestClient(app) as client:
        item = client.post('/api/tagging/content', json={
            'content_type': 'case',
            'content_id': 'test-acute-chest-pain-case',
            'title': 'Acute chest pain case',
            'workspace': 'clinic',
            'summary': 'Progressive chest pain case for education.',
            'source_status': 'approved',
            'tags': ['specialty.cardiology', 'presentation.chest-pain', 'task.diagnosis'],
        })
        assert item.status_code == 200
        item_id = item.json()['item_id']
        assert len(item.json()['tags']) == 3

        search = client.get('/api/tagging/content', params=[
            ('tag_id', 'specialty.cardiology'), ('tag_id', 'presentation.chest-pain')
        ])
        assert search.status_code == 200
        assert search.json()['count'] >= 1
        assert any(row['item_id'] == item_id for row in search.json()['items'])

        event = client.post(f'/api/tagging/content/{item_id}/events', json={
            'action': 'completed', 'score': 4, 'max_score': 5, 'confidence': 'medium'
        })
        assert event.status_code == 200
        analytics = client.get('/api/tagging/analytics')
        assert analytics.status_code == 200
        cardiology = next(row for row in analytics.json()['items'] if row['tag_id'] == 'specialty.cardiology')
        assert cardiology['event_count'] >= 1
        assert cardiology['mean_score'] == 80.0


def test_tagging_rejects_unknown_tag_ids():
    with TestClient(app) as client:
        response = client.post('/api/tagging/content', json={
            'content_type': 'viva', 'content_id': 'unknown-tag-test', 'title': 'Viva prompt',
            'workspace': 'rounds', 'tags': ['specialty.not-a-real-tag'],
        })
    assert response.status_code == 422
