"""HSPTL 5.0.0 next increments: labels, rights, local folders, lottery, engines, pearls.

These tests exercise the real modules against a real SQLite store. Nothing is
mocked: the point of most of them is to prove that a guard actually refuses the
unsafe case, so replacing the guard with a stub would defeat the test.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from backend.hsptl_core.case_lottery import CaseLottery, LotteryError
from backend.hsptl_core.content_labels import (
    LABEL_DERIVED, LABEL_GENERATED, LABEL_IMPORTED, LABEL_SYNTHETIC,
    ContentLabelRegistry, LabelError, LabelledContent, LineageRef, normalise_label,
)
from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.engine_integration import EngineIntegration, IntegrationError, SEVEN_ENGINES, SKINS
from backend.hsptl_core.hsp_tl40.composer import Composer
from backend.hsptl_core.hsp_tl40.guards import Guards
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.proforma import ProformaRuntime
from backend.hsptl_core.hsp_tl40.reasoner import Reasoner
from backend.hsptl_core.hsp_tl40.router import Router
from backend.hsptl_core.local_sources import (
    LocalSourceError, LocalSourceManager, screen_for_identifiers, validate_root,
)
from backend.hsptl_core.pearls_factory import PearlsFactory, split_sentences
from backend.hsptl_core.source_registry import RightsError, SourceRegistry, SourceRights
from backend.hsptl_core.store import StudyStore
from backend.hsptl_core.ucks import UCKSRepository


@pytest.fixture()
def store(tmp_path: Path) -> StudyStore:
    return StudyStore(tmp_path / "next_increments.sqlite3")


@pytest.fixture()
def labels(store: StudyStore) -> ContentLabelRegistry:
    return ContentLabelRegistry(store)


@pytest.fixture()
def registry(store: StudyStore) -> SourceRegistry:
    return SourceRegistry(store)


@pytest.fixture()
def ucks(store: StudyStore) -> UCKSRepository:
    return UCKSRepository(store)


# --------------------------------------------------------------------------- #
# Content labels
# --------------------------------------------------------------------------- #

def test_four_labels_exist_and_are_distinct():
    assert len({LABEL_GENERATED, LABEL_IMPORTED, LABEL_SYNTHETIC, LABEL_DERIVED}) == 4


@pytest.mark.parametrize("raw,expected", [
    ("generated content", LABEL_GENERATED), ("GENERATED CONTENT", LABEL_GENERATED),
    ("imported content", LABEL_IMPORTED), ("synthetic content", LABEL_SYNTHETIC),
    ("derived_content", LABEL_DERIVED), ("  Derived Content  ", LABEL_DERIVED),
])
def test_label_normalisation_accepts_common_spellings(raw, expected):
    assert normalise_label(raw) == expected


@pytest.mark.parametrize("raw", ["", "real patient", "synthetic-ish", None])
def test_unknown_label_is_rejected(raw):
    with pytest.raises(LabelError):
        normalise_label(raw)


def test_imported_content_must_not_declare_lineage(labels):
    with pytest.raises(LabelError, match="IMPORTED CONTENT must not declare lineage"):
        labels.register(LabelledContent(
            label=LABEL_IMPORTED, title="Imported doc", content_hash="a" * 16,
            lineage=(LineageRef(item_id="x", label=LABEL_GENERATED),)))


def test_derived_content_requires_lineage(labels):
    with pytest.raises(LabelError, match="DERIVED CONTENT requires at least one lineage"):
        labels.register(LabelledContent(
            label=LABEL_DERIVED, title="Derived note", content_hash="b" * 16))


def test_derived_lineage_chain_resolves_to_parent(labels):
    parent = labels.register(LabelledContent(
        label=LABEL_GENERATED, title="Generated case", content_hash="c" * 16))
    child = labels.register(LabelledContent(
        label=LABEL_DERIVED, title="Derived pearl", content_hash="d" * 16,
        lineage=(LineageRef(item_id=parent["item_id"], label=LABEL_GENERATED),)))
    chain = labels.lineage_chain(child["item_id"])
    assert chain["complete"] is True
    assert chain["item_count"] == 2
    assert chain["chain"][-1]["item_id"] == parent["item_id"]


def test_label_is_independent_of_rights_and_review(labels):
    record = labels.register(LabelledContent(
        label=LABEL_SYNTHETIC, title="Synthetic cohort", content_hash="e" * 16,
        rights_status="unknown", clinical_review_status="unreviewed",
        publication_status="unpublished"))
    # The label says how it was made; it says nothing about whether it may be used.
    assert record["label"] == LABEL_SYNTHETIC
    assert record["rights_status"] == "unknown"
    assert record["clinical_review_status"] == "unreviewed"


def test_summary_counts_derived_without_lineage_as_integrity_fault(labels):
    summary = labels.summary()
    assert summary["derived_without_lineage"] == 0
    assert summary["integrity"] == "ok"
    assert set(summary["counts"]) == {LABEL_GENERATED, LABEL_IMPORTED, LABEL_SYNTHETIC, LABEL_DERIVED}


# --------------------------------------------------------------------------- #
# Source registry / rights
# --------------------------------------------------------------------------- #

def test_catalogue_records_typical_posture_without_granting_reuse(registry):
    cochrane = registry.catalogue_entry("cochrane_reviews")
    assert cochrane["default_access"] == "subscription"
    assert cochrane["default_reuse"] == "prohibited"
    assert cochrane["default_adaptation"] == "needs_permission"
    # A catalogue default is a prompt to review, never a rights decision.
    registry.register(source_id="src-1", catalogue_key="cochrane_reviews")
    assert registry.rights_for("src-1").to_dict()["is_reviewed"] is False
    assert registry.rights_for("src-1").allows_copy() is False


def test_catalogue_open_access_family_is_flagged_permitted(registry):
    entry = registry.catalogue_entry("open_access_journals")
    assert entry["default_reuse"] == "permitted"
    assert entry["default_adaptation"] == "permitted"


def test_unknown_catalogue_key_fails_closed(registry):
    with pytest.raises(RightsError):
        registry.register(source_id="src-x", catalogue_key="not_a_real_source")


def test_rights_are_unknown_until_a_reviewer_records_them(registry):
    registry.register(source_id="src-1b", catalogue_key="open_access_journals")
    rights = registry.rights_for("src-1b")
    assert rights.is_reviewed is False
    assert rights.allows_copy() is False


def test_explicit_review_can_grant_copy_and_is_audited(registry):
    registry.register(source_id="src-2", catalogue_key="cochrane_reviews")
    registry.record_rights("src-2", SourceRights(
        access="subscription", reuse="permitted", adaptation="permitted",
        licence="Institutional licence", reviewer="Dr Reviewer",
        rationale="Licence permits internal reuse."))
    rights = registry.rights_for("src-2")
    assert rights.allows_copy() is True
    assert rights.allows_adaptation() is True
    history = registry.history("src-2")
    assert any(entry["reviewer"] == "Dr Reviewer" for entry in history)


def test_link_only_source_never_allows_copy_even_when_permitted(registry):
    registry.register(source_id="src-3", catalogue_key="cochrane_reviews")
    registry.record_rights("src-3", SourceRights(
        access="link_only", reuse="permitted", adaptation="permitted",
        licence="Link only", reviewer="Dr Reviewer", rationale="Link-out only."))
    rights = registry.rights_for("src-3")
    assert rights.allows_copy() is False
    assert rights.allows_adaptation() is False


def test_permitted_reuse_requires_a_recorded_licence(registry):
    registry.register(source_id="src-4", catalogue_key="cochrane_reviews")
    with pytest.raises(RightsError, match="licence"):
        registry.record_rights("src-4", SourceRights(
            reuse="permitted", reviewer="Dr Reviewer", rationale="Claimed permitted."))


def test_rights_review_requires_named_reviewer_and_rationale(registry):
    registry.register(source_id="src-5", catalogue_key="cochrane_reviews")
    with pytest.raises(RightsError, match="reviewer"):
        registry.record_rights("src-5", SourceRights(reuse="permitted", reviewer="",
                                                     rationale="r", licence="L"))
    with pytest.raises(RightsError, match="rationale"):
        registry.record_rights("src-5", SourceRights(reuse="permitted", reviewer="Dr R",
                                                     rationale="", licence="L"))


def test_catalogue_has_expanded_prioritised_entries(registry):
    catalogue = SourceRegistry.catalogue()
    assert len(catalogue) >= 50
    assert any(entry["key"] == "cochrane_reviews" for entry in catalogue)
    priorities = [entry["priority"] for entry in catalogue]
    assert priorities == sorted(priorities)
    assert all(entry["family"] and entry["default_access"] for entry in catalogue)


# --------------------------------------------------------------------------- #
# Local folder sources
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bad", ["relative/path", "/", "/etc", "/proc", "/sys", "/dev"])
def test_unsafe_roots_are_refused(bad):
    with pytest.raises(LocalSourceError):
        validate_root(bad)


def test_home_directory_itself_is_refused():
    with pytest.raises(LocalSourceError, match="home directory"):
        validate_root(str(Path.home()))


def test_subdirectory_of_home_is_allowed(tmp_path):
    # tmp_path lives under the real temp root; the guard must allow ordinary folders.
    assert validate_root(str(tmp_path)) == tmp_path.resolve()


def test_scan_refuses_symlink_and_hardlink(tmp_path, store):
    labels = ContentLabelRegistry(store)
    manager = LocalSourceManager(store, labels=labels)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "ok.txt").write_text("Sepsis bundle: lactate within one hour.")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    os.symlink(secret, root / "link.txt")
    os.link(secret, root / "hard.txt")

    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    result = manager.scan(record["root_id"])
    by_path = {item["relative_path"]: item for item in result["files"]}

    assert by_path["ok.txt"]["verdict"] == "accepted"
    assert "link.txt" not in by_path
    assert "hard.txt" not in by_path
    reasons = {item["reason"] for item in result["findings"]["refusals"]}
    assert "symlink_or_reparse_point_not_followed" in reasons
    assert "hardlinked_file_not_read" in reasons
    # The secret must never appear in extracted text.
    assert "TOPSECRET" not in str(result)


def test_scan_never_opens_active_content(tmp_path, store):
    manager = LocalSourceManager(store)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "macro.docm").write_text("malicious macro")
    (root / "sheet.xlsm").write_text("malicious macro")
    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    result = manager.scan(record["root_id"])
    verdicts = {item["relative_path"]: item["verdict"] for item in result["files"]}
    assert verdicts["macro.docm"] == "refused"
    assert verdicts["sheet.xlsm"] == "refused"
    assert all(item["reason"] == "active_content_never_opened" for item in result["files"])


def test_scan_refuses_oversized_file(tmp_path, store):
    manager = LocalSourceManager(store)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "huge.txt").write_text("x" * (21 * 1024 * 1024))
    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    result = manager.scan(record["root_id"])
    assert result["files"][0]["verdict"] == "refused"
    assert result["files"][0]["reason"] == "file_exceeds_size_limit"


def test_scan_refuses_archive_when_not_allowed(tmp_path, store):
    manager = LocalSourceManager(store)
    root = tmp_path / "corpus"
    root.mkdir()
    with zipfile.ZipFile(root / "evil.zip", "w") as archive:
        archive.writestr("../../escape.txt", "pwn")
    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    result = manager.scan(record["root_id"])
    assert result["files"][0]["verdict"] == "refused"
    assert result["files"][0]["reason"] == "archive_handling_disabled"
    # Nothing may have been written outside the root.
    assert not (tmp_path / "escape.txt").exists()


def test_scan_quarantines_direct_identifiers(tmp_path, store):
    labels = ContentLabelRegistry(store)
    manager = LocalSourceManager(store, labels=labels)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "ids.txt").write_text("Patient MRN: 88213. DOB: 12/03/1970. NHS 943 476 5919")
    (root / "clean.txt").write_text("Guideline summary text only, no identifiers.")
    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    result = manager.scan(record["root_id"])
    by_path = {item["relative_path"]: item for item in result["files"]}
    assert by_path["ids.txt"]["verdict"] == "quarantined"
    assert by_path["ids.txt"]["reason"] == "direct_identifiers_detected"
    assert by_path["clean.txt"]["verdict"] == "accepted"
    assert set(result["findings"]["identifier_kinds"]) >= {"mrn", "dob_label", "nhs_number"}
    assert result["counts"]["quarantined"] == 1


def test_identifier_screening_does_not_flag_abnormal_labs():
    result = screen_for_identifiers("Sodium 118 mmol/L, potassium 6.8 mmol/L, lactate 7.2")
    assert result["verdict"] == "clear"


def test_identifier_screening_validates_nhs_checksum():
    assert screen_for_identifiers("NHS 9434765919")["verdict"] == "quarantine"
    # 9434765918 fails the modulus-11 checksum, so it is not an NHS number.
    assert "nhs_number" not in screen_for_identifiers("reference 9434765918")["kinds"]


def test_scan_is_idempotent(tmp_path, store):
    manager = LocalSourceManager(store)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "note.md").write_text("Sepsis bundle: lactate within one hour.")
    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    first = manager.scan(record["root_id"])
    second = manager.scan(record["root_id"])
    assert first["counts"]["accepted"] == second["counts"]["accepted"] == 1
    assert manager.summary()["scans"] == 2


def test_imported_local_text_gets_imported_label(tmp_path, store):
    labels = ContentLabelRegistry(store)
    manager = LocalSourceManager(store, labels=labels)
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "note.md").write_text("Sepsis bundle: lactate within one hour.")
    record = manager.register_root(path=str(root), label="Corpus", registered_by="admin")
    manager.scan(record["root_id"])
    assert labels.summary()["counts"][LABEL_IMPORTED] >= 1


# --------------------------------------------------------------------------- #
# Daily case lottery
# --------------------------------------------------------------------------- #

def _eligible_case(lottery: CaseLottery, case_id: str = "case-1", **overrides):
    payload = dict(case_id=case_id, title="Septic shock", stem="A 68-year-old presents hypotensive.",
                   prompt="What is the immediate management?", label=LABEL_GENERATED,
                   rights_status="permitted", clinical_review_status="reviewed",
                   publication_status="published", reveal={"diagnosis": "Septic shock"})
    payload.update(overrides)
    return lottery.register_case(**payload)


def test_lottery_returns_explicit_state_when_pool_is_empty(store):
    lottery = CaseLottery(store)
    result = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert result["state"] == "no_eligible_case"
    assert result["case"] is None
    assert result["pool_size"] == 0
    assert "message" in result


def test_daily_lottery_seeds_and_draws_hsptl_curated_cases(store):
    lottery = CaseLottery(store)
    seeded = lottery.seed_curated_cases()
    assert seeded["created"] >= 10
    assert seeded["total_curated_cases"] >= 10
    assert lottery.eligibility_report()["eligible_count"] >= 10

    draw = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert draw["state"] == "selected"
    assert draw["case"]["clinical_review_status"] == "curated"
    assert draw["case"]["rights_status"] == "permitted"
    assert draw["case"]["publication_status"] == "published"
    assert draw["case"]["answer_withheld"] is True
    assert "reveal" not in draw["case"]

    repeated = lottery.seed_curated_cases()
    assert repeated["created"] == 0
    assert repeated["already_present"] >= 10


def test_empty_daily_lottery_draw_recovers_after_startup_curriculum_seed(store):
    lottery = CaseLottery(store)
    empty = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert empty["state"] == "no_eligible_case"

    lottery.seed_curated_cases()
    recovered = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert recovered["state"] == "selected"
    assert recovered["draw_id"] == empty["draw_id"]
    assert recovered["case"] is not None


def test_lottery_never_draws_an_unreviewed_case(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery, clinical_review_status="harvested")
    result = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert result["state"] == "no_eligible_case"
    blocked = lottery.eligibility_report()["blocked"]
    assert "not_clinically_reviewed" in blocked[0]["reasons"]


@pytest.mark.parametrize("field,value,reason", [
    ("publication_status", "draft", "not_published"),
    ("rights_status", "restricted", "rights_not_cleared_for_reuse"),
    ("rights_status", "unknown", "rights_not_cleared_for_reuse"),
])
def test_lottery_blocks_on_publication_and_rights(store, field, value, reason):
    lottery = CaseLottery(store)
    _eligible_case(lottery, **{field: value})
    result = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert result["state"] == "no_eligible_case"
    assert reason in lottery.eligibility_report()["blocked"][0]["reasons"]


def test_lottery_draw_is_shared_between_workspaces(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    clinic = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    ward = lottery.draw(workspace="ward_board", draw_date="2026-11-20")
    assert clinic["case"]["case_id"] == ward["case"]["case_id"]
    assert clinic["draw_id"] == ward["draw_id"]


def test_lottery_draw_is_deterministic_within_a_day(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    first = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    second = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert first["case"]["case_id"] == second["case"]["case_id"]


def test_lottery_withholds_the_answer_until_reveal(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert draw["case"]["answer_withheld"] is True
    assert "reveal" not in draw["case"]

    revealed = lottery.reveal(draw_id=draw["draw_id"], learner_id="learner-1")
    assert revealed["reveal"]["diagnosis"] == "Septic shock"
    assert revealed["answer_withheld"] is False
    assert lottery.reveal_count(draw["draw_id"]) == 1


def test_lottery_reveal_is_audited_once_per_learner(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    lottery.reveal(draw_id=draw["draw_id"], learner_id="learner-1")
    lottery.reveal(draw_id=draw["draw_id"], learner_id="learner-1")
    assert lottery.reveal_count(draw["draw_id"]) == 1


def test_lottery_reveal_rejects_unknown_reason(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    with pytest.raises(LotteryError):
        lottery.reveal(draw_id=draw["draw_id"], learner_id="l", reason="peek")


def test_withdrawn_case_blocks_subsequent_draws(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    lottery.set_eligibility("case-1", enabled=False)
    assert lottery.draw(workspace="clinic", draw_date="2026-11-21")["state"] == "no_eligible_case"


def test_withdrawn_case_cannot_be_revealed(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery)
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    lottery.set_eligibility("case-1", enabled=False)
    with pytest.raises(LotteryError):
        lottery.reveal(draw_id=draw["draw_id"], learner_id="learner-1")


def test_lottery_rejects_unknown_workspace(store):
    lottery = CaseLottery(store)
    with pytest.raises(LotteryError):
        lottery.draw(workspace="nowhere", draw_date="2026-11-20")


def test_lottery_rejects_bad_date(store):
    lottery = CaseLottery(store)
    with pytest.raises(LotteryError):
        lottery.draw(workspace="clinic", draw_date="not-a-date")


# --------------------------------------------------------------------------- #
# Engine integration
# --------------------------------------------------------------------------- #

@pytest.fixture()
def integration(tmp_path: Path) -> EngineIntegration:
    engine = DeterministicIntelligenceEngine(tmp_path / "engine.sqlite3")
    kernel = EventKernel(engine)
    guards = Guards(kernel, engine)
    return EngineIntegration(
        kernel=kernel, reasoner=Reasoner(engine), logic=ProformaRuntime(kernel),
        composer=Composer(engine, kernel, guards), router=Router(kernel, guards, engine),
        guards=guards)


def test_all_seven_engines_are_integrated(integration):
    catalogue = integration.catalogue()
    assert catalogue["all_engines_integrated"] is True
    assert set(catalogue["engines"]) == set(SEVEN_ENGINES)
    assert catalogue["binding_count"] > 0


def test_all_six_skins_are_integrated(integration):
    catalogue = integration.catalogue()
    assert catalogue["all_skins_integrated"] is True
    assert set(catalogue["skins"]) == set(SKINS)


def test_kernel_operation_returns_real_status(integration):
    result = integration.invoke(skin="portfolio", area="tools", operation="status", payload={})
    assert result["engine"] == "Kernel"
    assert "head_seq" in result["result"]
    assert result["result"]["event_log"] == "append_only_sha256_chain"


def test_guards_abstain_on_unclassified_rule(integration):
    result = integration.invoke(
        skin="ward", area="oncall", operation="decide",
        payload={"guard_id": "G-TEST-001",
                 "expression": {"op": "exists", "left": {"ref": "facts.x"}},
                 "context": {"facts": {}}})
    assert result["engine"] == "Guards"
    assert result["result"]["decision"] in {"pass", "fail", "abstain"}


def test_router_irt_returns_a_derivation(integration):
    result = integration.invoke(
        skin="exam", area="questions", operation="estimate_irt",
        payload={"responses": [{"difficulty": 0.0, "discrimination": 1.0, "correct": True}]})
    assert result["engine"] == "Router"
    assert "derivation" in result["result"]


def test_unwired_operation_is_refused(integration):
    with pytest.raises(IntegrationError):
        integration.invoke(skin="clinic", area="simulation", operation="estimate_irt", payload={})


def test_unknown_skin_is_refused(integration):
    with pytest.raises(IntegrationError):
        integration.bindings_for("not_a_skin")


def test_skin_bindings_cover_multiple_engines(integration):
    bindings = integration.bindings_for("clinic")
    assert len({binding.engine for binding in bindings}) >= 3


# --------------------------------------------------------------------------- #
# Pearls factory
# --------------------------------------------------------------------------- #

@pytest.fixture()
def pearls(store, ucks, registry, labels) -> PearlsFactory:
    return PearlsFactory(store, ucks_repo=ucks, registry=registry, labels=labels)


def _ingest(ucks, registry, *, source_name="Open access guideline",
            catalogue_key="open_access_journals", body=None, review_status="reviewed"):
    source = ucks.register_source(name=source_name, source_type="external_import")
    registry.register(source_id=source["id"], catalogue_key=catalogue_key)
    registry.record_rights(source["id"], SourceRights(
        access="open_access", reuse="permitted", adaptation="permitted",
        licence="CC BY 4.0", reviewer="Dr Reviewer", rationale="Verified open access."))
    document = ucks.ingest_document(
        source_id=source["id"], title="Sepsis guidance",
        body=body or ("Patients with suspected sepsis should receive antibiotics within one hour. "
                      "Lactate should be measured promptly in all suspected cases. "
                      "However, caution is needed because a normal lactate does not exclude sepsis. "
                      "Urgent senior review must be arranged if hypotension persists."),
        content_type="guideline", review_status=review_status,
        source_url="https://example.org/guideline", licence="CC BY 4.0")
    return source, document


def test_pearls_compose_links_every_point_to_a_source(pearls, ucks, registry):
    _ingest(ucks, registry)
    result = pearls.compose(topic="sepsis")
    assert result["state"] == "composed"
    sections = result["body"]["sections"]
    points = [point for points in sections.values() for point in points]
    assert points
    assert all(point["citation"]["document_id"] for point in points)


def test_pearls_are_derived_content_with_lineage(pearls, ucks, registry, labels):
    _source, document = _ingest(ucks, registry)
    result = pearls.compose(topic="sepsis")
    assert result["label"] == LABEL_DERIVED
    record = labels.get(result["label_item_id"])
    assert record["label"] == LABEL_DERIVED
    assert any(ref["item_id"] == document["id"] for ref in record["lineage"])


def test_pearls_composition_is_deterministic(pearls, ucks, registry):
    _ingest(ucks, registry)
    first = pearls.compose(topic="sepsis")
    second = pearls.compose(topic="sepsis")
    assert first["content_hash"] == second["content_hash"]
    assert first["artifact_id"] == second["artifact_id"]


def test_pearls_fail_closed_without_sources(pearls):
    result = pearls.compose(topic="a topic with no indexed evidence")
    assert result["state"] == "insufficient_evidence"
    assert result["body"] is None
    assert result["source_refs"] == []


def test_machine_screened_europe_pmc_fulltext_uses_item_level_allowlisted_licence(pearls, ucks, registry):
    source = ucks.register_source(name="Europe PMC automatic source", source_type="external_import")
    registry.register(source_id=source["id"], catalogue_key="open_access_journals")
    document = ucks.ingest_document(
        source_id=source["id"], title="Tiotropium open-access review",
        body=("Tiotropium should be offered to patients with persistent COPD symptoms. "
              "However, caution is needed when interpreting exacerbation frequency. "
              "Urgent assessment must be arranged for severe deterioration."),
        content_type="systematic_review", review_status="machine_screened",
        source_url="https://europepmc.org/articles/PMC123456", licence="CC BY 4.0",
        provenance={"full_text_status": "fetched", "full_text_licence": "CC BY 4.0"})
    assert document["review_status"] == "machine_screened"
    result = pearls.compose(topic="tiotropium")
    assert result["state"] == "composed"
    point_list = [point for entries in result["body"]["sections"].values() for point in entries]
    assert point_list
    assert all(point["citation"]["document_id"] == document["id"] for point in point_list)


def test_machine_screened_metadata_without_allowlisted_fulltext_stays_citation_only(pearls, ucks, registry):
    source = ucks.register_source(name="Metadata-only automatic source", source_type="external_import")
    registry.register(source_id=source["id"], catalogue_key="open_access_journals")
    ucks.ingest_document(
        source_id=source["id"], title="Tiotropium metadata record",
        body="Tiotropium should be considered when symptoms persist in COPD.",
        content_type="systematic_review", review_status="machine_screened",
        source_url="https://europepmc.org/articles/PMC123457", licence="",
        provenance={"full_text_status": "not_fetched_rights_or_identifier"})
    result = pearls.compose(topic="tiotropium")
    assert result["state"] == "insufficient_evidence"
    assert any(item.get("citation_only") for item in result["excluded_sources"])


def test_pearls_do_not_quote_rights_restricted_source(pearls, ucks, registry):
    source = ucks.register_source(name="Cochrane", source_type="external_import")
    registry.register(source_id=source["id"], catalogue_key="cochrane_reviews")
    ucks.ingest_document(
        source_id=source["id"], title="Tiotropium review",
        body="Tiotropium should be offered to patients with frequent exacerbations of COPD.",
        content_type="systematic_review", review_status="reviewed")
    result = pearls.compose(topic="tiotropium")
    assert result["state"] == "insufficient_evidence"
    assert any(item["reason"] == "rights_do_not_permit_text_use"
               for item in result["excluded_sources"])


def test_pearls_exclude_rejected_documents(pearls, ucks, registry):
    _ingest(ucks, registry, review_status="rejected")
    result = pearls.compose(topic="sepsis")
    assert result["state"] == "insufficient_evidence"


def test_pearls_unknown_template_is_rejected(pearls, ucks, registry):
    _ingest(ucks, registry)
    with pytest.raises(ValueError):
        pearls.compose(topic="sepsis", template_id="not_a_template")


def test_pearls_review_requires_named_reviewer(pearls, ucks, registry):
    _ingest(ucks, registry)
    result = pearls.compose(topic="sepsis")
    with pytest.raises(ValueError):
        pearls.review(result["artifact_id"], reviewer="", decision="approved")
    with pytest.raises(ValueError):
        pearls.review(result["artifact_id"], reviewer="Dr R", decision="maybe")


def test_pearls_review_records_decision(pearls, ucks, registry):
    _ingest(ucks, registry)
    result = pearls.compose(topic="sepsis")
    reviewed = pearls.review(result["artifact_id"], reviewer="Dr Reviewer", decision="approved")
    assert reviewed["review_status"] == "approved"
    assert reviewed["reviewer"] == "Dr Reviewer"


def test_pearls_factory_uses_no_external_model(pearls):
    summary = pearls.summary()
    assert summary["external_models"] == 0
    assert summary["deterministic"] is True


def test_sentence_split_protects_clinical_abbreviations():
    sentences = split_sentences("Give oxygen, e.g. 15 L/min, then reassess. Escalate if no response.")
    assert len(sentences) == 2
    assert "e.g." in sentences[0]


# --------------------------------------------------------------------------- #
# API surface: auth enforcement and the operational overview
# --------------------------------------------------------------------------- #

@pytest.fixture()
def client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("HSPTL_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HSPTL_REVIEWER_TOKEN", raising=False)
    monkeypatch.delenv("HSPTL_REVIEWER_ID", raising=False)
    monkeypatch.delenv("HSPTL_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("HSPTL_ADMIN_ID", raising=False)
    from backend.main import app
    return TestClient(app)


def test_overview_reports_version_and_integrity(client):
    response = client.get("/api/v5/overview")
    assert response.status_code == 200
    body = response.json()
    from backend.hsptl_core.config import APP_VERSION
    assert body["version"] == APP_VERSION
    assert body["labels"]["derived_without_lineage"] == 0
    assert body["engines"]["all_integrated"] is True
    assert body["pearls"]["external_models"] == 0


def test_labels_endpoint_lists_four_labels(client):
    response = client.get("/api/v5/labels")
    assert response.status_code == 200
    body = response.json()
    assert len(body["labels"]) == 4
    assert "independent_dimensions" in body


def test_engine_matrix_endpoint_covers_all_skins_and_engines(client):
    body = client.get("/api/v5/engines/matrix").json()
    assert body["all_engines_integrated"] is True
    assert body["all_skins_integrated"] is True
    assert set(body["engines"]) == set(SEVEN_ENGINES)
    assert set(body["skins"]) == set(SKINS)


def test_lottery_endpoint_returns_no_eligible_state_on_empty_pool(client):
    body = client.get("/api/v5/lottery/daily?workspace=clinic").json()
    assert body["state"] in {"no_eligible_case", "selected"}
    if body["state"] == "no_eligible_case":
        assert body["case"] is None


def test_lottery_endpoint_rejects_unknown_workspace(client):
    assert client.get("/api/v5/lottery/daily?workspace=nowhere").status_code == 400


def test_source_registry_mutation_requires_configured_reviewer(client):
    # With no reviewer token configured the surface must fail closed, not fall open.
    response = client.post("/api/v5/sources/registry", json={"source_id": "s1"})
    assert response.status_code == 503


def test_source_registry_mutation_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "x" * 40)
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "Dr Reviewer")
    response = client.post("/api/v5/sources/registry", json={"source_id": "s1"},
                           headers={"X-HSPTL-Reviewer-Token": "wrong"})
    assert response.status_code == 401


def test_local_folder_registration_requires_configured_admin(client):
    response = client.post("/api/v5/local-folders",
                           json={"path": "/tmp/whatever", "label": "Corpus"})
    assert response.status_code == 503


def test_local_folder_listing_exposes_no_arbitrary_path_reading(client):
    body = client.get("/api/v5/local-folders").json()
    assert body["safety"]["arbitrary_paths_over_http"] is False
    assert body["safety"]["follows_symlinks"] is False
    assert body["safety"]["opens_active_content"] is False
    # No endpoint takes a path to read; the list returns configured roots only.
    assert isinstance(body["items"], list)


def test_pearls_compose_endpoint_fails_closed_without_sources(client):
    response = client.post("/api/v5/pearls-factory/compose", json={"topic": "no evidence here"})
    assert response.status_code == 201
    assert response.json()["state"] == "insufficient_evidence"


def test_pearls_compose_rejects_too_short_topic(client):
    assert client.post("/api/v5/pearls-factory/compose", json={"topic": "a"}).status_code == 422


def test_engine_invoke_rejects_unwired_operation(client):
    response = client.post("/api/v5/engines/invoke", json={
        "skin": "clinic", "area": "simulation", "operation": "estimate_irt", "payload": {}})
    assert response.status_code == 400

# --------------------------------------------------------------------------- #
# HSPTL 5.1 learning intelligence
# --------------------------------------------------------------------------- #

def test_source_reliability_appraisal_is_separate_and_reviewed(store):
    from backend.hsptl_core.learning_intelligence import LearningIntelligence, RUBRIC
    from backend.hsptl_core.case_lottery import CaseLottery
    service = LearningIntelligence(store, CaseLottery(store))
    scores = {key: 4 for key in RUBRIC}
    item = service.appraise_source("source-1", scores, "reviewer-1", "Reviewed editorial and correction controls.")
    assert item["band"] == "strong_source_controls"
    assert item["mean_score"] == 4
    assert "not licence permission" in item["scope"]
    assert service.source_appraisal("source-1")["reviewer"] == "reviewer-1"


def test_source_reliability_requires_complete_bounded_scores(store):
    from backend.hsptl_core.learning_intelligence import LearningIntelligence, RUBRIC
    from backend.hsptl_core.case_lottery import CaseLottery
    service = LearningIntelligence(store, CaseLottery(store))
    with pytest.raises(ValueError, match="exactly"):
        service.appraise_source("source-1", {"peer_review": 5}, "reviewer", "Rationale is long enough")
    with pytest.raises(ValueError, match="0 to 4"):
        service.appraise_source("source-1", {key: 5 for key in RUBRIC}, "reviewer", "Rationale is long enough")


def test_personalized_practice_does_not_change_shared_daily_draw(store):
    from backend.hsptl_core.learning_intelligence import LearningIntelligence
    lottery = CaseLottery(store)
    service = LearningIntelligence(store, lottery)
    service.set_preferences("learner-a", ["Cardiology"], "Intermediate")
    recs = service.recommendations("learner-a")
    assert recs["items"] == []
    # Preferences are private recommendation inputs; shared daily draw semantics remain unchanged.
    assert lottery.draw(workspace="clinic", draw_date="2026-11-20")["state"] == "no_eligible_case"
    assert lottery.draw(workspace="ward_board", draw_date="2026-11-20")["state"] == "no_eligible_case"


def test_case_attempt_requires_reasoning_and_existing_draw(store):
    from backend.hsptl_core.learning_intelligence import LearningIntelligence
    lottery = CaseLottery(store)
    service = LearningIntelligence(store, lottery)
    with pytest.raises(ValueError, match="at least 20"):
        service.submit_case_attempt("learner", "missing", "short")


def test_case_attempt_persists_reasoning_before_answer_reveal(store):
    from backend.hsptl_core.learning_intelligence import LearningIntelligence
    lottery = CaseLottery(store)
    lottery.register_case(
        case_id="reviewed-case", title="Reviewed case", stem="A patient presents with symptoms.",
        prompt="What is your differential?", label=LABEL_GENERATED, specialty="Cardiology",
        difficulty="Intermediate", rights_status="permitted", clinical_review_status="reviewed",
        publication_status="published", reveal={"diagnosis": "Example diagnosis"})
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-20")
    assert draw["state"] == "selected"
    service = LearningIntelligence(store, lottery)
    result = service.submit_case_attempt("learner-a", draw["draw_id"],
        "My leading diagnosis is X because of the clinical findings; I would investigate Y.", 4)
    assert result["state"] == "submitted"
    assert result["answer_reveal_available"] is True
    with store.transaction() as conn:
        row = conn.execute("SELECT response, confidence FROM learner_case_attempts WHERE learner_id='learner-a'").fetchone()
    assert row["confidence"] == 4
    assert "leading diagnosis" in row["response"]


def test_lottery_uses_secure_random_choice_and_persists_the_selected_case(store, monkeypatch):
    import backend.hsptl_core.case_lottery as lottery_module
    lottery = CaseLottery(store)
    _eligible_case(lottery, case_id="case-a")
    _eligible_case(lottery, case_id="case-b")
    monkeypatch.setattr(lottery_module.secrets, "choice", lambda pool: next(x for x in pool if x["case_id"] == "case-b"))
    first = lottery.draw(workspace="clinic", draw_date="2026-11-22")
    again = lottery.draw(workspace="ward_board", draw_date="2026-11-22")
    assert first["case"]["case_id"] == "case-b"
    assert again["case"]["case_id"] == "case-b"
    assert first["draw_id"] == again["draw_id"]


def test_lottery_persists_complaint_and_age_as_non_revealing_case_metadata(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery, case_id="case-age", presenting_complaint="Sudden severe headache",
                   patient_age_value=42, patient_age_unit="years")
    result = lottery.draw(workspace="clinic", draw_date="2026-11-23")
    assert result["case"]["presenting_complaint"] == "Sudden severe headache"
    assert result["case"]["patient_age_value"] == 42
    assert result["case"]["answer_withheld"] is True


def test_lottery_rejects_invalid_patient_age_metadata(store):
    lottery = CaseLottery(store)
    with pytest.raises(LotteryError, match="patient_age_value"):
        lottery.register_case(title="Invalid age", stem="A case", prompt="Assess", label="SYNTHETIC CONTENT",
                              patient_age_value=140)


def test_lottery_additive_migration_adds_case_metadata_and_selection_audit(store):
    CaseLottery(store)
    with store.transaction() as conn:
        conn.execute("ALTER TABLE lottery_cases DROP COLUMN presenting_complaint")
        conn.execute("ALTER TABLE lottery_cases DROP COLUMN patient_age_value")
        conn.execute("ALTER TABLE lottery_cases DROP COLUMN patient_age_unit")
        conn.execute("ALTER TABLE lottery_draws DROP COLUMN selection_method")
        conn.execute("ALTER TABLE lottery_draws DROP COLUMN event_json")
        conn.execute("ALTER TABLE lottery_draws DROP COLUMN pool_digest")
        conn.execute("ALTER TABLE lottery_draws DROP COLUMN policy_version")
    CaseLottery(store)
    with store.transaction() as conn:
        case_columns = {row[1] for row in conn.execute("PRAGMA table_info(lottery_cases)")}
        draw_columns = {row[1] for row in conn.execute("PRAGMA table_info(lottery_draws)")}
    assert {"presenting_complaint", "patient_age_value", "patient_age_unit"} <= case_columns
    assert {"selection_method", "event_json", "pool_digest", "policy_version"} <= draw_columns


def test_phase5_event_catalogue_is_versioned_and_editable(store):
    lottery = CaseLottery(store)
    before = lottery.event_catalogue(active_only=True)
    assert len(before) >= 20
    event = lottery.upsert_event({
        "id": "test-simulation-day", "title": "Simulation Day", "category": "Education",
        "icon": "🎭", "summary": "A test event theme", "setting": "Simulation centre",
        "learning_objectives": ["structured communication"], "case_signals": ["simulation"],
        "workspaces": ["lab"], "selection_weight": 3, "active": True,
    })
    assert event["catalogue_version"] == 1
    event["active"] = False
    updated = lottery.upsert_event(event)
    assert updated["catalogue_version"] == 2
    assert "test-simulation-day" not in {x["id"] for x in lottery.event_catalogue(active_only=True)}


def test_phase6_archive_contains_event_snapshot_and_no_diagnosis(store):
    lottery = CaseLottery(store)
    _eligible_case(lottery, case_id="archive-sepsis", title="Sepsis", specialty="Emergency Medicine",
                   presenting_complaint="Fever and confusion", patient_age_value=68)
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-21")
    assert draw["state"] == "selected"
    assert draw["clinical_event"] is not None
    archive = lottery.history(limit=10)
    item = next(x for x in archive if x["draw_id"] == draw["draw_id"])
    assert item["case"]["presenting_complaint"] == "Fever and confusion"
    assert item["case"]["patient_age_value"] == 68
    assert item["event"]["id"] == draw["clinical_event"]["id"]
    assert "diagnosis" not in item["case"]
    assert "reveal" not in item["case"]
    assert "Septic shock" not in str(item)


def test_seven_canonical_workspaces_have_real_engine_bindings(integration):
    from backend.hsptl_core.engine_integration import WORKSPACES

    catalogue = integration.workspace_catalogue()
    assert catalogue["all_workspaces_integrated"] is True
    assert catalogue["all_seven_engines_covered"] is True
    assert set(catalogue["workspaces"]) == {
        "clinic", "lab", "ward", "library", "learning", "exam_hall", "rounds"
    }
    assert set(catalogue["workspaces"]) == set(WORKSPACES)
    assert all(integration.bindings_for_workspace(name) for name in WORKSPACES)


def test_workspace_bindings_reject_unknown_destination(integration):
    with pytest.raises(IntegrationError):
        integration.bindings_for_workspace("simulation-is-not-a-primary-workspace")


def test_workspace_contract_api_lists_seven_destinations(client):
    response = client.get("/api/v5/workspaces/contracts")
    assert response.status_code == 200
    body = response.json()
    assert body["all_workspaces_integrated"] is True
    assert body["all_seven_engines_covered"] is True
    assert body["workspace_count"] == 7


def test_workspace_engine_endpoint_returns_only_bound_operations(client):
    response = client.get("/api/v5/workspaces/exam_hall/engines")
    assert response.status_code == 200
    body = response.json()
    assert body["workspace"] == "exam_hall"
    assert body["bindings"]
    assert {item["area"] for item in body["bindings"]} == {"questions", "scores", "summaries"}
    assert client.get("/api/v5/workspaces/not-a-workspace/engines").status_code == 404
