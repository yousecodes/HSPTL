import json

from backend.hsptl_core.local_reasoning import OllamaLocalGenerator


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"response": json.dumps({"sections": [], "assessment_items": [], "limitations": ["test"]})}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


def test_ollama_adapter_uses_local_endpoint_and_no_api_key():
    session = FakeSession()
    client = OllamaLocalGenerator(session=session)
    result = client.generate(title="Test", kind="case_report",
        required_sections=["problem_representation"], spans=[{
            "chunk_id": "c1", "document_id": "d1", "text": "Source text", "source_url": "https://example.org"
        }])
    assert result["limitations"] == ["test"]
    url, request = session.calls[0]
    assert url.startswith("http://127.0.0.1:11434/")
    assert "Authorization" not in request.get("headers", {})
    assert request["json"]["stream"] is False


def test_ollama_adapter_rejects_non_loopback_endpoints():
    import pytest
    with pytest.raises(ValueError, match="loopback"):
        OllamaLocalGenerator(endpoint="https://example.com/api")
