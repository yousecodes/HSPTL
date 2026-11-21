from __future__ import annotations

import pytest
import sqlite3
from fastapi import HTTPException

from backend.hsptl_core.clinical_catalogues import clinical_event_catalogue, specialty_catalogue
from backend.hsptl_core.generation_distribution import GenerationDistribution
from backend.hsptl_core.source_registry import PRIORITY_SOURCE_CATALOGUE
import backend.routers.published_learning as published_learning


def test_specialty_catalogue_is_broad_and_enriched():
    items = specialty_catalogue()
    assert len(items) >= 40
    assert len({item["slug"] for item in items}) == len(items)
    for item in items:
        assert item["description"]
        assert len(item["focus_areas"]) >= 3
        assert len(item["common_presentations"]) >= 3
        assert len(item["learning_themes"]) >= 2
        assert item["topics"]


def test_clinical_event_catalogue_has_learning_metadata_and_safety_note():
    items = clinical_event_catalogue()
    assert len(items) >= 25
    assert len({item["id"] for item in items}) == len(items)
    for item in items:
        assert item["summary"] and item["setting"]
        assert item["learning_objectives"]
        assert item["case_signals"]
        assert item["workspaces"]
        assert "Scenario theme only" in item["review_note"]


def test_source_directory_is_extensive_and_rights_conservative():
    assert len(PRIORITY_SOURCE_CATALOGUE) >= 50
    assert len({item["key"] for item in PRIORITY_SOURCE_CATALOGUE}) == len(PRIORITY_SOURCE_CATALOGUE)
    for item in PRIORITY_SOURCE_CATALOGUE:
        assert item["name"] and item["family"]
        assert item["content_value"] and item["coverage"] and item["integration"]
        assert item["default_access"] in {"open_access", "subscription", "link_only", "institutional_licence", "unknown"}
        assert item["default_reuse"] in {"permitted", "prohibited", "needs_permission", "unknown"}
        assert item["default_adaptation"] in {"permitted", "prohibited", "needs_permission", "unknown"}
    egypt = next(item for item in PRIORITY_SOURCE_CATALOGUE if item["key"] == "egypt_mohp")
    assert egypt["default_reuse"] == "unknown"
    assert egypt["default_adaptation"] == "unknown"


def test_learner_usage_completion_migration_is_additive(tmp_path, monkeypatch):
    db_path = tmp_path / "old_learner_usage.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE learner_artifact_uses (usage_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, learner_id TEXT NOT NULL, opened_at TEXT NOT NULL)")
    monkeypatch.setattr(published_learning, "DB_PATH", db_path)
    published_learning._init()
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(learner_artifact_uses)")}
    assert "completed_at" in columns


def _configure_feedback_db(tmp_path, monkeypatch):
    db_path = tmp_path / "published_feedback.sqlite3"
    monkeypatch.setattr(published_learning, "DB_PATH", db_path)
    monkeypatch.setattr(published_learning, "ENGINE", GenerationDistribution(db_path))
    published_learning._init()
    artifact = published_learning.ENGINE.create_structured_draft(
        workspace="clinic", kind="case_report", title="Learning artefact for feedback test",
        body={"sections": [{"title": "Reasoning", "content": "Teaching content"}]},
        source_refs=[{"document_id": "doc-linked", "title": "Linked evidence", "url": "https://example.org/evidence"}],
    )
    published_learning.ENGINE.review(artifact["id"], "approved", "educator")
    published_learning.ENGINE.route(artifact["id"], "clinic", "learning_library")
    return artifact


def test_publication_gate_allows_provisional_after_delivery_but_not_before(tmp_path, monkeypatch):
    db_path = tmp_path / "publication_gate.sqlite3"
    monkeypatch.setattr(published_learning, "DB_PATH", db_path)
    monkeypatch.setattr(published_learning, "ENGINE", GenerationDistribution(db_path))
    published_learning._init()
    artifact = published_learning.ENGINE.create_structured_draft(
        workspace="clinic", kind="case_report", title="Not yet published",
        body={"sections": [{"title": "Reasoning", "content": "Draft text"}]},
    )
    assert published_learning._published_artifact(artifact["id"]) is None
    published_learning.ENGINE.route(artifact["id"], "clinic", "learning_library")
    available = published_learning._published_artifact(artifact["id"])
    assert available is not None
    assert available["status"] == "provisional"
    assert available["publication_state"] == "provisionally_available"
    assert available["clinical_approval"] == "not_granted"


def test_learner_feedback_requires_actual_use_and_only_linked_sources(tmp_path, monkeypatch):
    artifact = _configure_feedback_db(tmp_path, monkeypatch)
    assert published_learning._published_artifact(artifact["id"]) is not None
    with pytest.raises(HTTPException) as exc:
        published_learning.submit_artifact_feedback(
            artifact["id"], published_learning.FeedbackRequest(
                usage_id="use_not_real", learner_id="learner-1", rating=4,
                categories=["unclear_explanation"], comment="Could use more context",
            ),
        )
    assert exc.value.status_code == 409

    use = published_learning.record_artifact_use(
        artifact["id"], published_learning.UseRequest(learner_id="learner-1"),
    )
    with pytest.raises(HTTPException) as exc:
        published_learning.submit_artifact_feedback(
            artifact["id"], published_learning.FeedbackRequest(
                usage_id=use["usage_id"], learner_id="learner-1", rating=4,
                categories=["unclear_explanation"], comment="Before completion",
            ),
        )
    assert exc.value.status_code == 409
    published_learning.complete_artifact_use(
        artifact["id"], use["usage_id"], published_learning.CompleteUseRequest(learner_id="learner-1"),
    )
    with pytest.raises(HTTPException) as exc:
        published_learning.submit_artifact_feedback(
            artifact["id"], published_learning.FeedbackRequest(
                usage_id=use["usage_id"], learner_id="learner-1", rating=2,
                categories=["citation_or_source_problem"], source_document_ids=["unlinked-doc"],
                comment="This is not linked to the artefact",
            ),
        )
    assert exc.value.status_code == 400

    result = published_learning.submit_artifact_feedback(
        artifact["id"], published_learning.FeedbackRequest(
            usage_id=use["usage_id"], learner_id="learner-1", rating=3,
            categories=["unclear_explanation"], source_document_ids=["doc-linked"],
            comment="Clarify the limitations section",
        ),
    )
    assert result["status"] == "pending"
    assert published_learning.ENGINE.get_artifact(artifact["id"])["status"] == "approved"
    with pytest.raises(HTTPException) as exc:
        published_learning.submit_artifact_feedback(
            artifact["id"], published_learning.FeedbackRequest(
                usage_id=use["usage_id"], learner_id="learner-1", rating=3,
                categories=["other"], comment="Duplicate report",
            ),
        )
    assert exc.value.status_code == 409


def test_feedback_triage_is_authenticated_and_does_not_change_content_status(tmp_path, monkeypatch):
    artifact = _configure_feedback_db(tmp_path, monkeypatch)
    use = published_learning.record_artifact_use(artifact["id"], published_learning.UseRequest(learner_id="learner-2"))
    published_learning.complete_artifact_use(
        artifact["id"], use["usage_id"], published_learning.CompleteUseRequest(learner_id="learner-2"),
    )
    feedback = published_learning.submit_artifact_feedback(
        artifact["id"], published_learning.FeedbackRequest(
            usage_id=use["usage_id"], learner_id="learner-2", rating=1,
            categories=["factual_accuracy"], comment="Please verify this point",
        ),
    )
    monkeypatch.delenv("HSPTL_REVIEWER_TOKEN", raising=False)
    monkeypatch.delenv("HSPTL_REVIEWER_ID", raising=False)
    with pytest.raises(HTTPException) as unconfigured:
        published_learning.learner_feedback_queue(x_hsptl_reviewer_token="r" * 40)
    assert unconfigured.value.status_code == 503
    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "r" * 40)
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "educator-reviewer")
    queue = published_learning.learner_feedback_queue(x_hsptl_reviewer_token="r" * 40)
    assert queue["count"] == 1
    resolved = published_learning.resolve_learner_feedback(
        feedback["feedback_id"], published_learning.ResolveRequest(
            status="artifact_revision_required", resolution="Educator to review claim and update source citation.",
        ), x_hsptl_reviewer_token="r" * 40,
    )
    assert resolved["source_or_artifact_status_changed"] is False
    assert published_learning.ENGINE.get_artifact(artifact["id"])["status"] == "approved"
    with pytest.raises(HTTPException) as exc:
        published_learning.learner_feedback_queue(x_hsptl_reviewer_token="wrong")
    assert exc.value.status_code == 401

class _ValidationAuth:
    def __init__(self, people):
        self.people = people

    def validate_session(self, session_id, required_roles):
        from backend.hsptl_core.institutional import InstitutionalError
        person = self.people.get(session_id)
        if not person:
            raise InstitutionalError("Invalid session")
        if person["role"] not in required_roles:
            raise PermissionError("Role not allowed")
        return {"state": "authenticated", **person}


def _submit_validated_vote(artifact_id, session_id, level, monkeypatch):
    use = published_learning.record_artifact_use(
        artifact_id, published_learning.UseRequest(session_id=session_id),
    )
    published_learning.complete_artifact_use(
        artifact_id, use["usage_id"], published_learning.CompleteUseRequest(session_id=session_id),
    )
    return published_learning.submit_artifact_feedback(
        artifact_id, published_learning.FeedbackRequest(
            usage_id=use["usage_id"], session_id=session_id,
            educational_rating=5, clinical_rating=5, source_rating=5, assessment_rating=5,
            categories=["no_issue"], comment=f"Post-use validation by institution assigned {level}.",
        ),
    )


def test_validation_score_uses_verified_role_weighted_votes_and_evidence_coverage(tmp_path, monkeypatch):
    artifact = _configure_feedback_db(tmp_path, monkeypatch)
    people = {
        "student-session": {"subject_id": "student-1", "role": "learner", "training_level": "student", "institution_id": "hospital-a"},
        "intern-session": {"subject_id": "intern-1", "role": "learner", "training_level": "intern", "institution_id": "hospital-a"},
        "resident-session": {"subject_id": "resident-1", "role": "learner", "training_level": "resident", "institution_id": "hospital-a"},
        "registrar-session": {"subject_id": "registrar-1", "role": "learner", "training_level": "registrar", "institution_id": "hospital-a"},
        "fellow-session": {"subject_id": "fellow-1", "role": "learner", "training_level": "fellow", "institution_id": "hospital-a"},
        "specialist-session": {"subject_id": "specialist-1", "role": "learner", "training_level": "specialist", "institution_id": "hospital-a"},
        "consultant-session": {"subject_id": "consultant-1", "role": "learner", "training_level": "consultant", "institution_id": "hospital-a"},
        "student-session-2": {"subject_id": "student-2", "role": "learner", "training_level": "student", "institution_id": "hospital-a"},
        "intern-session-2": {"subject_id": "intern-2", "role": "learner", "training_level": "intern", "institution_id": "hospital-a"},
        "resident-session-2": {"subject_id": "resident-2", "role": "learner", "training_level": "resident", "institution_id": "hospital-a"},
    }
    monkeypatch.setattr(published_learning, "INSTITUTIONAL_AUTH", _ValidationAuth(people))

    first = _submit_validated_vote(artifact["id"], "student-session", "student", monkeypatch)
    assert first["validation_contribution"] is True
    assert first["validation"]["validation_percent"] == 7
    assert first["validation"]["state"] == "collecting_learner_evidence"

    for session_id, person in list(people.items())[1:]:
        _submit_validated_vote(artifact["id"], session_id, person["training_level"], monkeypatch)

    summary = published_learning._validation_summary(artifact["id"], artifact["content_hash"])
    assert summary["validation_percent"] == 70
    assert summary["quality_score"] == 100
    assert summary["contributor_count"] == 10
    assert summary["state"] == "expert_signoff_pending"
    assert summary["training_level_counts"]["student"] == 2


def test_validation_requires_domain_signoffs_and_critical_issues_block_completion(tmp_path, monkeypatch):
    artifact = _configure_feedback_db(tmp_path, monkeypatch)
    people = {}
    for i in range(10):
        sid = f"learner-{i}-session"
        people[sid] = {"subject_id": f"learner-{i}", "role": "learner",
                       "training_level": ["student", "intern", "resident", "registrar", "fellow"][i % 5],
                       "institution_id": "hospital-a"}
    people.update({
        "clinical-reviewer": {"subject_id": "clinical-reviewer", "role": "reviewer", "training_level": "consultant", "institution_id": "hospital-a"},
        "source-reviewer": {"subject_id": "source-reviewer", "role": "reviewer", "training_level": "specialist", "institution_id": "hospital-a"},
        "faculty-reviewer": {"subject_id": "faculty-reviewer", "role": "reviewer", "training_level": "faculty", "institution_id": "hospital-a"},
        "student-critical": {"subject_id": "student-critical", "role": "learner", "training_level": "student", "institution_id": "hospital-a"},
    })
    monkeypatch.setattr(published_learning, "INSTITUTIONAL_AUTH", _ValidationAuth(people))
    for i in range(10):
        _submit_validated_vote(artifact["id"], f"learner-{i}-session", people[f"learner-{i}-session"]["training_level"], monkeypatch)

    def signoff(session_id, domain, decision="affirmed"):
        return published_learning.signoff_artifact_validation(
            artifact["id"], published_learning.SignoffRequest(domain=domain, decision=decision,
                note=f"Reviewed current version and evidence for {domain} domain."),
            x_hsptl_session=session_id,
        )

    assert signoff("clinical-reviewer", "clinical")["validation"]["state"] == "expert_signoff_pending"
    signoff("source-reviewer", "sources")
    signoff("faculty-reviewer", "educational")
    last = signoff("faculty-reviewer", "assessment")
    assert last["validation"]["state"] == "validated"
    assert last["artifact_status_changed"] is False

    # A post-use critical flag is visible immediately and blocks the validated state.
    _submit_validated_vote(artifact["id"], "student-critical", "student", monkeypatch)
    # The helper submits routine/no-issue; insert an auditable critical issue against that completed session.
    with published_learning._connect() as conn:
        row = conn.execute("SELECT usage_id FROM learner_artifact_uses WHERE learner_id='student-critical'").fetchone()
        conn.execute("UPDATE learner_artifact_feedback SET severity='critical',status='pending' WHERE usage_id=?", (row["usage_id"],))
    blocked = published_learning._validation_summary(artifact["id"], artifact["content_hash"])
    assert blocked["open_critical_issues"] == 1
    assert blocked["state"] == "critical_review_pending"


def test_validation_votes_are_bound_to_content_version_and_unique_per_learner(tmp_path, monkeypatch):
    artifact = _configure_feedback_db(tmp_path, monkeypatch)
    people = {"resident-session": {"subject_id": "resident-1", "role": "learner",
                                  "training_level": "resident", "institution_id": "hospital-a"}}
    monkeypatch.setattr(published_learning, "INSTITUTIONAL_AUTH", _ValidationAuth(people))
    _submit_validated_vote(artifact["id"], "resident-session", "resident", monkeypatch)
    second_use = published_learning.record_artifact_use(artifact["id"], published_learning.UseRequest(session_id="resident-session"))
    published_learning.complete_artifact_use(artifact["id"], second_use["usage_id"], published_learning.CompleteUseRequest(session_id="resident-session"))
    with pytest.raises(HTTPException) as duplicate:
        published_learning.submit_artifact_feedback(artifact["id"], published_learning.FeedbackRequest(
            usage_id=second_use["usage_id"], session_id="resident-session",
            educational_rating=5, clinical_rating=5, source_rating=5, assessment_rating=5,
            categories=["no_issue"],
        ))
    assert duplicate.value.status_code == 409

    with published_learning._connect() as conn:
        conn.execute("UPDATE generated_artifacts SET content_hash='revised-version-hash' WHERE id=?", (artifact["id"],))
    revised = published_learning._validation_summary(artifact["id"], "revised-version-hash")
    assert revised["validation_percent"] == 0
    assert revised["contributor_count"] == 0


def test_clinical_signoff_rejects_unqualified_role_or_training_level(tmp_path, monkeypatch):
    artifact = _configure_feedback_db(tmp_path, monkeypatch)
    people = {
        "learner": {"subject_id": "student-1", "role": "learner", "training_level": "student", "institution_id": "local"},
        "junior-reviewer": {"subject_id": "reviewer-1", "role": "reviewer", "training_level": "resident", "institution_id": "local"},
    }
    monkeypatch.setattr(published_learning, "INSTITUTIONAL_AUTH", _ValidationAuth(people))
    payload = published_learning.SignoffRequest(domain="clinical", decision="affirmed", note="Clinical review notes and evidence.")
    with pytest.raises(HTTPException) as exc:
        published_learning.signoff_artifact_validation(artifact["id"], payload, x_hsptl_session="learner")
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        published_learning.signoff_artifact_validation(artifact["id"], payload, x_hsptl_session="junior-reviewer")
    assert exc.value.status_code == 403
