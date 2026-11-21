from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_brand_and_minimal_workspace_theme_tokens_exist():
    css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for token in ("#174438", "#1F5B49", "#2F7764", "#F4F7F2", "#FCFDF9", "#DCE5DB", "#10241D", "#1A342B", "#365244", "#3C936C", "#C28D40", "#B95D50"):
        assert token in css
    assert "HSPTL" in html
    assert "Plus+Jakarta+Sans" in html
    assert "JetBrains+Mono" in html
    assert "--mark-accent" in css


def test_hospital_workspaces_and_nested_service_navigation_exist():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "label: 'Clinic'" in app
    assert "label: 'Rounds'" in app
    assert "label: 'Lab'" in app
    assert "label: 'Ward'" in app
    assert "label: 'My Profile'" in app
    assert "label: 'Home'" in app and "primaryNavigation = navigation.filter" in app
    assert "label: 'Learning'" in app and "label: 'Exam Hall'" in app
    assert "label: 'Case Archive'" in app
    assert "label: 'Procedure Theatre'" in app
    assert "label: 'Handover Desk'" in app
    assert "label: 'Consult Room'" in app
    assert "label: 'Admin · Question Review'" in app
    assert "label: 'Exam Hall'" in app
    assert "Data Tools" in app
    assert "Case Archive" in app and "Case Debriefs" in app
    assert "<CaseDebriefsPage/>" in app
    debriefs = (ROOT / "frontend" / "src" / "pages" / "CaseDebriefsPage.tsx").read_text(encoding="utf-8")
    assert "clinicalLearningAttempts" in debriefs and "problem_representation" in debriefs
    assert "evidence_against" in debriefs and "POST-CASE REFLECTION" in debriefs
    assert "Clinical Pearls" in app and "Learning" in app and "Rounds" in app
    assert "OSCE" in app and "TagIndexPage" not in app  # Unused lazy import must stay out of the application bundle.
    assert "Curriculum" not in app
    assert "<AttendingRoomPage/>" in app
    assert (ROOT / "frontend" / "src" / "pages" / "TagIndexPage.tsx").is_file()  # Module remains available without an unused App import.
    assert "<OSCEPage initialKind=\"Viva\" workspaceMode=\"viva\"/>" in app


def test_shared_daily_lottery_precedes_patient_record_explorer():
    clinic = (ROOT / "frontend" / "src" / "pages" / "ClinicPage.tsx").read_text(encoding="utf-8")
    assert clinic.index("Shared daily case") < clinic.index("<PatientRecordExplorer />")
    assert clinic.index('<DailyCaseLottery workspace="clinic" />') < clinic.index("<PatientRecordExplorer />")


def test_requested_investigation_evidence_is_visible_during_reasoning():
    component = (ROOT / "frontend" / "src" / "components" / "PatientRecordExplorer.tsx").read_text(encoding="utf-8")
    assert "Evidence requested during Investigation" in component
    assert "const requestedEvidence = narrative?.sections.filter" in component


def test_clinic_uses_progressive_encounter_evidence_disclosure():
    component = (ROOT / "frontend" / "src" / "components" / "PatientRecordExplorer.tsx").read_text(encoding="utf-8")
    assert "Request encounter evidence" in component
    assert "setRevealedSections" in component
    assert "Review all available groups" in component
    assert "selected.facts.map" not in component



def test_clinic_has_structured_assessment_and_investigation_planning():
    component = (ROOT / "frontend" / "src" / "components" / "PatientRecordExplorer.tsx").read_text(encoding="utf-8")
    assert "What would you clarify?" in component
    assert "History" in component and "Examination" in component
    assert "Investigation categories to consider" in component
    assert "not source findings" in component
    assert "not recommendations or results" in component
    assert "Learner-selected history domains to clarify" in component
    assert "Learner-selected examination domains to perform" in component
    assert "Investigation categories selected for consideration" in component
    assert "setHistoryFocus([])" in component
    assert "setExaminationFocus([])" in component
    assert "setInvestigationFocus([])" in component


def test_progress_page_uses_real_lifetime_api_and_avoids_mastery_claims():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "src" / "pages" / "ProgressPage.tsx").read_text(encoding="utf-8")
    assert "ProgressPage mode=\"portfolio\"" in (ROOT / "frontend" / "src" / "pages" / "ProfilePage.tsx").read_text(encoding="utf-8")
    assert 'F-to-S grade scale' in page
    assert "scoreGrade(data.quiz_average_percent)" in page
    assert "mode=\"portfolio\"" in app
    assert "request<ProgressSummary>('/api/progress')" in api
    assert "api.progress()" in page
    assert "not clinical competence or mastery" in page
    assert "diagnostic-accuracy score" in page


def test_case_events_are_rendered_as_nonclinical_reflection_prompts():
    component = (ROOT / "frontend" / "src" / "components" / "PatientRecordExplorer.tsx").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    assert "setCaseEvents(result.case_events)" in component
    assert "Case reflection prompts" in component
    assert "not clinical triage or care advice" in component
    assert "case_events: ClinicalCaseEvent[]" in api


def test_clinic_accessibility_status_focus_and_target_sizes():
    patient_records = (ROOT / "frontend" / "src" / "components" / "PatientRecordExplorer.tsx").read_text(encoding="utf-8")
    clinic = (ROOT / "frontend" / "src" / "pages" / "ClinicPage.tsx").read_text(encoding="utf-8")
    lottery = (ROOT / "frontend" / "src" / "components" / "DailyCaseLottery.tsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    assert 'role="group" aria-label="Clinical encounter stages"' in patient_records
    assert "aria-current={current ? 'step' : undefined}" in patient_records
    assert "h-6 w-6 shrink-0 accent-hsptl-indigo" in patient_records
    assert "min-h-6 w-full accent-hsptl-indigo" in patient_records
    assert "inline-flex min-h-6 items-center px-2" in patient_records
    assert 'role="status" aria-live="polite" className="status-success' in patient_records
    assert 'role="alert" aria-live="assertive" className="status-error' in patient_records
    assert 'role="status" aria-live="polite"' in lottery
    assert 'role="alert" aria-live="assertive"' in lottery
    assert "Today’s clinical case" in lottery
    assert "aria-pressed={selectedKey === patient.patient_key}" in patient_records
    assert "summary:focus-visible" in css
    assert ".form-field:focus-visible" in css
    assert "outline: 3px solid #7FA58F" in css
    assert "provenance-badge" not in patient_records + clinic + lottery


def test_hsptl_brand_and_workspace_specific_minimalist_tokens_exist():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    assert "<b>HSPTL</b>" in app
    assert "/hsptl-mark.svg" in app
    for token in ("--workspace-accent: #16805D", "--workspace-accent: #5267A8", "--workspace-accent: #0D8B91", "--workspace-accent: #B77924", "--hsptl-canvas"):
        assert token in css
    assert "HSPTL — Clinical Practice & Learning" in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_unfinished_workspaces_are_real_episode_backed_workflows():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "src" / "pages" / "WorkflowPage.tsx").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    for route in ("conference", "procedure", "progression", "summaries"):
        assert f'workflow="{route}"' in app
    for route in ("oncall", "handover", "consult"):
        assert "<WorkflowPage workflow={currentSection} />" in app
        assert f"  {route}: {{ id:'{route}'" in workflow
    for method in ("startEpisode", "saveEpisodeDraft", "addEpisodeArtifact", "completeEpisode", "episodeLineage"):
        assert f"{method}:" in api
    for heading in ("ABCDE assessment", "Receiver confirmation", "Supervisor review", "Consent and preparation", "Decision points"):
        assert heading in workflow
    assert "does not verify clinical accuracy" in workflow


def test_portfolio_profile_and_admin_use_persistent_or_review_apis():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    admin = (ROOT / "frontend" / "src" / "pages" / "AdminReviewPage.tsx").read_text(encoding="utf-8")
    profile = (ROOT / "frontend" / "src" / "pages" / "ProfilePage.tsx").read_text(encoding="utf-8")
    assert "<AdminReviewPage/>" in app
    assert "contentReviewQueue" in admin and "reviewQuestion" in admin and "resolveContentReview" in admin
    assert "hsptl-profile" in profile and "localStorage" in profile
    assert "not proof of clinical correctness" in admin


def test_hsptl_60_primary_navigation_is_seven_clinical_workspaces_and_home_is_logo_only():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    icons = (ROOT / "frontend" / "src" / "components" / "Icon.tsx").read_text(encoding="utf-8")
    assert "['practice', 'skills', 'oncall', 'library', 'lectures', 'exams', 'viva']" in app
    assert "onClick={() => navigate('home')}" in app
    assert "hx-archive-button" in app and "hx-profile-button" in app
    for icon in ("graduation-cap", "clipboard-list", "stethoscope", "microscope"):
        assert f"'{icon}'" in icons

def test_daily_lottery_exposes_complaint_and_patient_age_without_revealing_answer():
    lottery = (ROOT / "backend" / "hsptl_core" / "case_lottery.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "next_increments.py").read_text(encoding="utf-8")
    ui = (ROOT / "frontend" / "src" / "components" / "DailyCaseLottery.tsx").read_text(encoding="utf-8")
    assert "presenting_complaint TEXT NOT NULL" in lottery
    assert "patient_age_value INTEGER" in lottery
    assert "secrets.choice(pool)" in lottery
    assert "patient_age_value: int | None" in router
    assert "item.presenting_complaint" in ui and "item.patient_age_value" in ui


def test_phases5_to_8_archive_rounds_journey_and_export_are_wired():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "DailyCaseArchivePage" in app
    assert "case 'archives': return <DailyCaseArchivePage/>" in app
    assert "case 'viva': return <SpecialtiesPage mode=\"rounds\"/>" in app
    assert "case 'viva-station': return <OSCEPage initialKind=\"Viva\" workspaceMode=\"viva\"/>" in app
    archive = (ROOT / "frontend" / "src" / "pages" / "DailyCaseArchivePage.tsx").read_text(encoding="utf-8")
    assert "presenting_complaint" in archive and "patient_age_value" in archive
    assert "diagnosis" not in archive.lower()
    assert "lotteryHistory(365)" in archive
    profile = (ROOT / "frontend" / "src" / "pages" / "ProfilePage.tsx").read_text(encoding="utf-8")
    assert "Clinical learning goals" in profile
    assert "institution-assigned level" in profile
    progress = (ROOT / "frontend" / "src" / "pages" / "ProgressPage.tsx").read_text(encoding="utf-8")
    assert "Your learning journey" in progress
    assert "exportJourney" in progress and "Export journey" in progress


def test_clinic_daily_case_comes_only_from_shared_lottery():
    clinic = (ROOT / "frontend" / "src" / "pages" / "ClinicPage.tsx").read_text(encoding="utf-8")
    lottery = (ROOT / "frontend" / "src" / "components" / "DailyCaseLottery.tsx").read_text(encoding="utf-8")
    assert clinic.count('<DailyCaseLottery workspace="clinic" />') == 1
    assert "api.dailyPuzzle" not in clinic
    assert "api.newPuzzle" not in clinic
    assert "puzzle.source_title" not in clinic
    assert "ADDITIONAL LEARNING CONTENT" not in clinic
    assert "only daily-case source" in clinic
    assert "HSPTL-authored fictional teaching vignette" in lottery
    assert "No eligible case in today’s lottery" in lottery
    assert "No separate puzzle or synthetic-case fallback" in lottery


def test_daily_case_lottery_seeds_existing_curriculum_at_startup():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    lottery = (ROOT / "backend" / "hsptl_core" / "case_lottery.py").read_text(encoding="utf-8")
    events = (ROOT / "frontend" / "src" / "components" / "ClinicalEventCataloguePanel.tsx").read_text(encoding="utf-8")
    assert "_CASE_LOTTERY.seed_curated_cases()" in main
    assert "from .puzzles import PUZZLES" in lottery
    assert "clinical_review_status=\"curated\"" in lottery
    assert "clinical_review_status IN ('curated','reviewed','validated')" in lottery
    assert "not patient-case content" in events


def test_daily_case_pool_combines_curated_and_approved_adaptations():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    puzzle_engine = (ROOT / "backend" / "hsptl_core" / "puzzle_engine.py").read_text(encoding="utf-8")
    events = (ROOT / "frontend" / "src" / "components" / "ClinicalEventCataloguePanel.tsx").read_text(encoding="utf-8")
    assert "combined = [*PUZZLES, *load_approved_puzzles(STORE)]" in main
    assert 'store.notes("ApprovedPuzzle")' in puzzle_engine
    assert "not patient-case content" in events

def test_failed_frontend_build_cannot_leave_a_stale_production_bundle():
    package = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    clean_script = (ROOT / "frontend" / "scripts" / "clean-dist.mjs").read_text(encoding="utf-8")
    installer = (ROOT / "install_hsptl.bat").read_text(encoding="utf-8")
    assert "clean-dist.mjs" in package
    assert "recursive: true, force: true" in clean_script
    assert 'if exist "dist" rmdir /s /q "dist"' in installer



def test_frontend_icon_references_are_declared():
    import re

    component = (ROOT / "frontend" / "src" / "components" / "Icon.tsx").read_text(encoding="utf-8")
    union = re.search(r"export type IconName = (.*?);", component, re.S)
    assert union is not None
    declared = set(re.findall(r"'([^']+)'", union.group(1)))

    used = set()
    for source in (ROOT / "frontend" / "src").rglob("*.tsx"):
        text = source.read_text(encoding="utf-8")
        used.update(re.findall(r'<Icon\s+name=["\']([^"\']+)["\']', text))

    assert used <= declared, f"Undeclared icon names: {sorted(used - declared)}"
