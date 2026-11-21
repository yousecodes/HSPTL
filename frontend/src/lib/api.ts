
export type SharedClinicalTag = { tag_id: string; facet: string; label: string; aliases: string[] };
export type TaggedContentItem = {
  item_id: string; content_type: string; content_id: string; title: string; workspace: string;
  summary: string; source_status: string; content_url: string; updated_at: string;
  tags: Array<{ tag_id: string; facet: string; label: string }>;
};
export type TagCatalogue = { count: number; facets: Record<string, SharedClinicalTag[]>; tags: SharedClinicalTag[] };

export type Bootstrap = {
  name: string;
  version: string;
  data_ready: boolean;
  cohorts: string[];
  patient_count: number;
  stats: Record<string, number>;
  note_types: string[];
  levels: string[];
  jurisdictions: string[];
  default_dataset_path: string;
};



export type ProgressSummary = {
  lifetime: { cards: number; due: number; attempts: number; scripts: number; quizzes: number; debriefs: number };
  quiz_average_percent: number | null;
  quiz_groups: number;
  scope: string;
  practice?: { cases_completed: number; reasoning_attempts: number; quiz_attempts: number; exam_attempts: number; review_sessions: number };
  reasoning_process?: { attempts_with_externalised_reasoning: number; attempts_total: number; percent: number | null; attempts_citing_source_facts: number; scope: string };
  retention?: { cards_due: number; again_rate_percent: number | null; forecast: Array<{ days: number; due: number }>; scope: string };
  transfer?: { learning_actions_revisited: number; scope: string };
  exam?: { exam_attempts: number; mean_percentage: number | null; by_specialty: Array<{ specialty: string; correct: number; total: number; percentage: number }>; osce_attempts: number; osce_by_kind: Array<{ kind: string; correct: number; total: number; percentage: number }>; scope: string };
  recommendations?: Array<{ id: string; department: string; action: string; reason: string }>;
};

export type ClinicalPatient = {
  patient_key: string;
  source_key: string;
  source_patient_id: string;
  gender: string;
  birth_date: string;
  deceased: string;
  name: string;
  updated_at: string;
  encounter_count: number;
  fact_count: number;
};

export type ClinicalEncounter = {
  encounter_key: string;
  patient_key: string;
  source_encounter_id: string;
  start_at: string;
  end_at: string;
  status: string;
  encounter_type: string;
  source_file: string;
};

export type ClinicalFactRecord = {
  fact_key: string;
  patient_key: string;
  encounter_key: string | null;
  resource_type: string;
  source_resource_id: string;
  effective_at: string;
  code_text: string;
  value_text: string;
  unit: string;
  status: string;
  conclusion: string;
  provenance: string;
  source_file: string;
};

export type ClinicalNarrative = {
  case_code: string;
  source_type: string;
  patient_context: { age: number | null; age_provenance: string; gender: string | null; gender_provenance: string; birth_date: string | null; provenance: string };
  encounter: { start_at?: string; end_at?: string; status?: string; encounter_type?: string };
  sections: Array<{ title: string; items: Array<{ label: string; value: string | null; date: string | null; status: string | null; conclusion: string | null; provenance: string; source_file: string | null }>; availability: string; note: string }>;
  clinical_prompt: string;
  limitations: string[];
  diagnostic_puzzle_eligible: false;
};


export type ReasoningFeedback = {
  type: 'completeness_only'; label: string; completed: number; total: number; coverage_percent: number;
  dimensions: Array<{ id: string; label: string; documented: boolean; suggestion: string | null }>;
  confidence_reflection: { self_rated: number; prompt: string };
  limitations: string[];
};

export type ClinicalCaseEvent = { id: string; title: string; message: string };

export type ClinicalDebriefSection = { key: string; title: string; prompt: string; hint: string };
export type ClinicalDebrief = { responses: Record<string, string>; completed: number; total: number; sections?: ClinicalDebriefSection[] };
export type ClinicalLearningAttemptSummary = {
  attempt_id: string; case_code: string; problem_representation: string; working_diagnosis: string;
  specialty_pathway: string; confidence: number; stage_completed: number; created_at: string; updated_at: string;
  debrief_completed: number; debrief_total: number;
};
export type ClinicalLearningAttemptDetail = ClinicalLearningAttemptSummary & {
  differentials: string[]; evidence_for: string; evidence_against: string; investigation_plan: string;
  management_plan: string; safety_net: string; communication_plan: string;
  history_plan: string[]; examination_plan: string[]; investigation_selection: string[];
  cited_fact_keys: string[]; prioritisation_rationale: string;
};

export type ClinicalAttemptPayload = {
  patient_key: string; encounter_key: string; case_code: string;
  problem_representation: string; differentials: string[];
  evidence_for: string; evidence_against: string; investigation_plan: string;
  working_diagnosis: string; management_plan: string; safety_net: string;
  communication_plan: string; stage_completed: number; confidence: number;
  history_plan: string[]; examination_plan: string[]; investigation_selection: string[];
  specialty_pathway: string;
};

export type ClinicalCase = {
  patient: { patient_key: string; source: string; source_patient_id: string; gender: string; birth_date: string; deceased: string; name: string; provenance: string };
  selected_encounter: ClinicalEncounter | null;
  encounters: ClinicalEncounter[];
  facts: ClinicalFactRecord[];
  unlinked_facts: number;
  quality: {
    record_status: string;
    ready_for_human_review: boolean;
    diagnostic_puzzle_eligible: boolean;
    diagnostic_puzzle_reason: string;
    counts: { encounters: number; facts: number; encounter_linked_facts: number; undated_facts: number; unlinked_facts: number; resource_types: string[] };
    flags: Array<{ code: string; severity: string; message: string }>;
    assessment_scope: string;
  };
  scope: string;
  limitations: string[];
};

export type Puzzle = {
  run_id: string;
  id: string;
  title: string;
  specialty: string;
  difficulty: string;
  question: string;
  case_type: string;
  case_meta: { age: string | null; gender: string | null; chief_complaint: string };
  clues: string[];
  all_clues?: string[];
  clue_count: number;
  revealed: number;
  guesses: string[];
  guess_count: number;
  max_guesses: number;
  finished: boolean;
  solved: boolean;
  answer?: string;
  explanation?: string;
  takeaways?: string[];
  source_title: string;
  source_url: string;
};

export type SpecialtyTopic = {
  id: string;
  title: string;
  tagline?: string;
  summary?: string;
  source_title?: string;
  source_url?: string;
  keywords?: string[];
  questions?: Array<{
    question: string;
    options: string[];
    answer: number;
    explanation: string;
    takeaway?: string;
  }>;
};

export type Specialty = {
  slug: string;
  name: string;
  description: string;
  topic_count: number;
  focus_areas?: string[];
  common_presentations?: string[];
  learning_themes?: string[];
  curated_pack_count?: number;
  discovery_theme_count?: number;
  topics: Array<{
    id: string;
    title: string;
    tagline?: string;
    source_title?: string;
    source_url?: string;
    question_count: number;
  }>;
};

export type SpecialtyDetail = {
  slug: string;
  name: string;
  description: string;
  topic_count: number;
  focus_areas?: string[];
  common_presentations?: string[];
  learning_themes?: string[];
  topics: Array<SpecialtyTopic & {
    title: string;
    tagline?: string;
    summary?: string;
    source_title?: string;
    source_url?: string;
    questions?: Array<{ question: string; options: string[]; answer: number; explanation: string; takeaway?: string }>;
  }>;
};

export type NoteSection = {
  title: string;
  objective: string;
  evidence: Array<{
    text: string;
    citation: string;
    kind: string;
    url?: string;
    license?: string;
    license_url?: string;
    section?: string;
  }>;
  status: string;
};

export type StudyNote = {
  title: string;
  topic: string;
  note_type: string;
  level: string;
  jurisdiction: string;
  description: string;
  level_lens: string;
  jurisdiction_lens: string;
  sections: NoteSection[];
  curated_pack?: {
    title: string;
    summary: string;
    questions: Array<{ question: string; options: string[]; answer: number; explanation: string; takeaway?: string }>;
    source_title: string;
    source_url: string;
    curated_takeaways: string[];
  } | null;
  references: Array<{ citation: string; url: string; kind: string; license?: string; license_url?: string }>;
  recall_prompts: Array<{ question: string; answer: string; source: string; url?: string }>;
  evidence_count: number;
  supported_sections: number;
  total_sections: number;
  generated_mode: string;
};

export type SavedPearl = {
  id: string;
  title: string;
  topic: string;
  note_type: string;
  saved_at: string;
  supported_sections: number;
  total_sections: number;
};

export type ExamItem = {
  id: string;
  title: string;
  specialty: string;
  question_count: number;
  duration_minutes: number;
  difficulty: string;
};
export type QuestionItem = {
  id: string;
  version_id?: string;
  version?: number;
  kind: string;
  specialty: string;
  difficulty: string;
  question: string;
  options: string[];
  answer?: string;
  explanation?: string;
  source_title: string;
  source_url?: string;
  licence?: string;
  media_url?: string;
  reviewed: boolean;
  tags?: string[];
  candidate_instructions?: string;
  checklist?: string[];
  critical_errors?: string[];
  timer_seconds?: number;
};
export type ExamQuestionBank = {
  count: number;
  reviewed_count: number;
  questions: QuestionItem[];
};
export type ExamDetail = {
  exam: ExamItem;
  questions: QuestionItem[];
  blueprint?: Record<string, unknown>;
};
export type ExamReport = {
  attempt_id?: string;
  score: number;
  total: number;
  percentage: number;
  results: Array<{
    question_id: string;
    question_version_id?: string;
    response: string;
    correct: boolean;
    answer: string;
    explanation: string;
    specialty: string;
  }>;
  duration_seconds?: number;
  timing_clamped?: boolean;
  timing_source?: string;
  limitations?: string[];
};


export type HSPTLJob = {
  id: string; kind: string; status: string; payload: Record<string, unknown>;
  checkpoint: Record<string, unknown>; result: Record<string, unknown>;
  error_code?: string; progress_done?: number; progress_total?: number;
};
export type HarvestedCase = {
  specialty: string; title: string; year: string; journal: string; pmcid: string; pmid: string; doi: string;
  url: string; source: string; content_type: string; knowledge_profile: string; full_text_available: boolean;
  license_status: string; license_uri: string; review_status: string;
};


// --- HSPTL 5.1.0 learning intelligence ------------------------------------------ //
export type ContentLabel = 'GENERATED CONTENT' | 'IMPORTED CONTENT' | 'SYNTHETIC CONTENT' | 'DERIVED CONTENT';
export type LotteryCase = {
  case_id: string; title: string; specialty: string; difficulty: string; stem: string; prompt: string; presenting_complaint?: string; patient_age_value?: number | null; patient_age_unit?: string;
  label: ContentLabel; rights_status: string; clinical_review_status: string; publication_status: string;
  source_refs: Array<Record<string, unknown>>; answer_withheld: boolean;
  reveal?: Record<string, unknown>;
};
export type LotteryDaily = {
  state: 'selected' | 'no_eligible_case'; draw_id: string; draw_date: string; workspace: string;
  pool_size: number; case: LotteryCase | null; message?: string;
  shared_across_workspaces?: string[]; ineligibility_reasons?: string[];
  clinical_event?: { id: string; title: string; category: string; icon: string; summary: string; setting: string; learning_objectives: string[] } | null;
  selection_method?: string;
  eligibility?: { eligible_count: number; blocked_count: number };
};
export type LotteryArchiveItem = {
  draw_id: string; draw_date: string; state: string; pool_size: number; reveal_count: number;
  event: { id: string; title: string; icon: string; category: string } | null;
  case: { case_id: string; presenting_complaint: string; patient_age_value: number | null; patient_age_unit: string; specialty: string; difficulty: string; label: string } | null;
};
export type ExternalAutomationStatus = {
  status?: string;
  trigger_source?: string;
  last_started?: string;
  last_completed?: string;
  last_error?: string;
  api_key_required?: boolean;
  automatic_review_status?: string;
  automatic_import_enabled?: boolean;
  human_approval_required_for_import?: boolean;
  clinical_validity_assessed_automatically?: boolean;
  reuse_rights_granted_automatically?: boolean;
  auto_approve?: boolean;
  auto_publish?: boolean;
  profiles?: Array<{
    source_id: string;
    name: string;
    connector: string;
    enabled: boolean;
    schedule: { enabled: number; interval_minutes: number; next_run: string; last_success?: string; last_error?: string } | null;
  }>;
};

export type SourceCatalogueEntry = {
  key: string; name: string; family: string; priority: number; default_access: string;
  default_reuse: string; default_adaptation: string; note: string;
  url?: string; content_value?: string; coverage?: string[]; integration?: string;
};
export type LocalFolderSummary = {
  roots: number; scheduled_roots: number; scans: number; quarantined: number;
  files_by_verdict: Record<string, number>;
  safety: { read_only: boolean; arbitrary_paths_over_http: boolean; follows_symlinks: boolean; opens_active_content: boolean };
};
export type NextIncrementsOverview = {
  version: string;
  labels: { counts: Record<string, number>; derived_total: number; derived_without_lineage: number; integrity: string };
  source_registry: { registered: number; reviewed: number; unreviewed: number; catalogue_size: number };
  local_sources: LocalFolderSummary;
  lottery: { eligible_cases: number; blocked_cases: number; draws_recorded: number; reveals_recorded: number };
  engines: { bindings: number; all_integrated: boolean };
  pearls: { artifacts: number; external_models: number; deterministic: boolean };
  integrity_notes: string[];
};
export type EngineMatrix = {
  engines: string[]; skins: string[];
  matrix: Record<string, Record<string, Array<{ engine: string; operation: string; description: string }>>>;
  engine_coverage: Record<string, string[]>;
  binding_count: number; all_engines_integrated: boolean; all_skins_integrated: boolean; note: string;
};
export type WorkspaceEngineContracts = {
  workspaces: string[];
  matrix: Record<string, Array<{ skin: string; area: string; engine: string; operation: string; description: string }>>;
  workspace_count: number; binding_count: number;
  engine_coverage: Record<string, boolean>;
  all_workspaces_integrated: boolean; all_seven_engines_covered: boolean; note: string;
};

export type ClinicalEventCatalogueItem = {
  id: string; title: string; category: string; icon: string; summary: string; setting: string;
  learning_objectives: string[]; case_signals: string[]; workspaces: string[]; active: boolean;
  selection_weight: number; cooldown_days?: number; review_note: string;
};
export type ArtifactValidationSummary = {
  validation_percent: number; quality_score: number; contributor_count: number; target_contributors: number;
  evidence_coverage_percent: number; expert_signoff_coverage_percent: number;
  role_diversity_coverage_percent: number; affirmed_domains: number; dimension_coverage: number;
  dimension_scores: Record<string, number | null>; training_level_counts: Record<string, number>;
  approvals: Record<string, { decision: string; reviewer_id: string; reviewer_level?: string; reviewer_role?: string; note: string }>;
  all_domains_signed_off: boolean; open_critical_issues: number; state: string; content_hash: string;
  method: string; weights: Record<string, number>; rating_scale: string;
};
export type PublishedLearningArtifact = {
  id: string; title: string; workspace: string; kind: string; status: string; body: Record<string, unknown>;
  source_refs: Array<{ document_id?: string; title?: string; url?: string; source_id?: string; [key: string]: unknown }>;
  published_routes: Array<{ route_id: string; workspace: string; section: string; route_status: string; distributed_at: string }>;
  validation: ArtifactValidationSummary;
};
export type LearnerFeedbackItem = {
  feedback_id: string; artifact_id: string; artifact_title: string; workspace: string; kind: string;
  learner_id: string; rating: number | null; educational_rating?: number | null; clinical_rating?: number | null;
  source_rating?: number | null; assessment_rating?: number | null; learner_level?: string; account_role?: string;
  identity_verified?: number; severity?: string; categories: string[]; source_document_ids: string[];
  comment: string; status: string; created_at: string; resolution?: string;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export type GovernanceCredential = { token?: string; sessionId?: string };

/** Session logins take precedence so a browser session is never silently downgraded. */
function governanceHeaders(credential: GovernanceCredential): Record<string, string> {
  if (credential.sessionId) return { 'X-HSPTL-Session': credential.sessionId };
  if (credential.token) return { 'X-HSPTL-Admin-Token': credential.token };
  return {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...init, headers });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === 'object' && payload && 'detail' in payload
      ? String((payload as { detail: unknown }).detail)
      : `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

export type ContentFactoryUnitSummary = {
  unit_id: string; title: string; specialty: string; level: string; minutes: number;
  tags: string[]; objectives: string[]; case_preview: string; quiz_count: number;
  source_count: number; content_status: string; available_outputs: string[];
};
export type ContentFactoryCatalog = {
  pack_id: string; title: string; version: string; description: string; content_status: string;
  pack_count?: number; packs?: Array<{ pack_id: string; title: string; version: string; unit_count: number; content_status: string }>;
  unit_count: number; question_count: number; outputs_per_unit: number;
  generation_policy: { engine: string; model_required: boolean; seeded_variation: string; human_review_required_before_distribution: boolean };
  units: ContentFactoryUnitSummary[];
};
export type ContentFactoryQuestion = {
  stem: string; options: string[]; correct_index: number; rationale: string;
};
export type LearningUnitProgress = {
  units: Array<{ unit_id: string; title: string; opened_count: number; attempt_count: number;
    latest_score: number | null; latest_maximum: number | null; latest_percent: number | null;
    objective_results: Array<{ objective: string; correct: number; total: number; percent: number }>;
    last_attempt_at: string | null }>;
  total_attempts: number; completed_units: number; latest_average_percent: number | null;
  latest_average_units: number; projection: string;
};
export type CurriculumProjection = {
  active: null | { curriculum_id: string; version: number; title: string; unit_ids: string[]; stages: Array<Record<string, any>>; content_digest: string; status: string };
  drafts: Array<{ curriculum_id: string; version: number; title: string; unit_ids: string[]; stages: Array<Record<string, any>>; content_digest: string; status: string }>;
  projection: string; eligibility?: Array<{ unit_id: string; decision: string; proof_trace?: Array<Record<string, any>> }>;
  eligible_unit_ids?: string[]; completed_unit_ids?: string[];
};
export type QuizSubmission = { attempt: { attempt_id: string; score: number; maximum: number; percentage: number;
  responses: Array<{ index: number; selected_index: number; correct_index: number; correct: boolean; rationale: string; objective: string }>;
  objective_results: Array<{ objective: string; correct: number; total: number; percent: number }>; submitted_at: string };
  event_id: string; reused: boolean; message: string };

export type ContentFactoryUnit = ContentFactoryUnitSummary & {
  case: { patient: string; setting: string; presentation: string; history: string; observations: string; revealed_findings: string[]; task: string };
  teaching_points: string[]; pitfalls: string[]; quiz: ContentFactoryQuestion[];
  viva: Array<{ prompt: string; key_points: string[] }>;
  osce: { title: string; candidate_instructions: string; checklist: string[]; critical_errors: string[]; time_seconds: number };
  debrief: string[]; source_refs: Array<{ source_id: string; title: string; publisher: string; version: string; url: string; access_note: string }>;
  content_status: string; pack: { pack_id: string; version: string; title: string };
};

export const api = {
  bootstrap: () => request<Bootstrap>('/api/bootstrap'),
  contentFactoryCatalog: () => request<ContentFactoryCatalog>('/api/content-factory/catalog'),
  contentFactoryUnit: (unitId: string, curriculumId = '', curriculumVersion = 0) => request<ContentFactoryUnit>(`/api/content-factory/units/${encodeURIComponent(unitId)}?curriculum_id=${encodeURIComponent(curriculumId)}&curriculum_version=${curriculumVersion}`),
  contentFactoryStatus: () => request<Record<string, unknown>>('/api/content-factory/status'),
  refreshContent: () => request<{ status: string; pack_count: number; unit_count: number; requested_outputs: number; created_count: number; reused_count: number; draft_count: number; workspace_counts: Record<string, number>; review_required: boolean; auto_approved: boolean; auto_published: boolean; message: string }>('/api/content-factory/refresh', { method: 'POST' }),
  refreshExternalSources: () => request<{ status: string; queued: boolean; message: string }>('/api/ucks/automation/refresh', { method: 'POST' }),
  externalAutomationStatus: () => request<ExternalAutomationStatus>('/api/ucks/automation/status'),
  openLearningUnit: (unitId: string, curriculumId = '', curriculumVersion = 0) => request<Record<string, unknown>>(`/api/content-factory/units/${encodeURIComponent(unitId)}/opened?curriculum_id=${encodeURIComponent(curriculumId)}&curriculum_version=${curriculumVersion}`, { method: 'POST' }),
  submitLearningQuiz: (unitId: string, payload: { answers: Record<string, number>; idempotency_key: string; curriculum_id?: string; curriculum_version?: number }) => request<QuizSubmission>(`/api/content-factory/units/${encodeURIComponent(unitId)}/attempts`, { method: 'POST', body: JSON.stringify(payload) }),
  learningUnitProgress: () => request<LearningUnitProgress>('/api/content-factory/progress'),
  curricula: () => request<CurriculumProjection>('/api/content-factory/curricula'),
  composeCurriculum: (payload: { title: string; description?: string; unit_ids: string[]; prerequisites?: Record<string, string[]> }) => request<{ curriculum: CurriculumProjection['drafts'][number]; event_id: string; status: string; message: string }>('/api/content-factory/curricula/compose', { method: 'POST', body: JSON.stringify(payload) }),
  activateCurriculum: (curriculumId: string, reviewerToken: string) => request<Record<string, unknown>>(`/api/content-factory/curricula/${encodeURIComponent(curriculumId)}/activate`, { method: 'POST', headers: { 'X-HSPTL-Reviewer-Token': reviewerToken } }),
  scenarioAuthoringTemplate: () => request<{ scenario: Record<string, any>; note: string }>('/api/v4/simulation/scenario-authoring/template'),
  scenarioDrafts: () => request<{ items: Array<{ scenario_id: string; version: string; title: string; clinical_review_status: string; published?: boolean; updated_at: string }>; count: number }>('/api/v4/simulation/scenario-authoring/drafts'),
  scenarioDraftDetail: (scenarioId: string) => request<{ scenario: Record<string, any> }>(`/api/v4/simulation/scenario-authoring/drafts/${encodeURIComponent(scenarioId)}`),
  validateScenarioDraft: (scenario: Record<string, any>) => request<{ valid: boolean; errors: string[]; warnings: string[]; checks: string[]; dynamic_path_coverage: string; clinical_validity: string }>('/api/v4/simulation/scenario-authoring/validate', { method: 'POST', body: JSON.stringify({ scenario }) }),
  scenarioTraceMatrix: (scenario: Record<string, any>) => request<{ valid: boolean; trace_matrix: Array<Record<string, any>>; fault_injection: Array<Record<string, any>>; clinical_review_required: boolean }>('/api/v4/simulation/scenario-authoring/trace-matrix', { method: 'POST', body: JSON.stringify({ scenario }) }),
  saveScenarioDraft: (scenario: Record<string, any>) => request<Record<string, any>>('/api/v4/simulation/scenario-authoring/drafts', { method: 'POST', body: JSON.stringify({ scenario }) }),
  publishScenarioDraft: (scenarioId: string, token: string) => request<Record<string, any>>(`/api/v4/simulation/scenario-authoring/drafts/${encodeURIComponent(scenarioId)}/publish`, { method: 'POST', headers: { 'X-HSPTL-Clinical-Reviewer-Token': token } }),
  institutionalAuthenticate: (token: string, role: string, subjectId = '') => request<Record<string, any>>('/api/v4/institution/authenticate', { method: 'POST', headers: { 'X-HSPTL-Admin-Token': token }, body: JSON.stringify({ role, subject_id: subjectId }) }),
  createInstitutionalAccount: (credential: GovernanceCredential, payload: Record<string, any>) => request<Record<string, any>>('/api/v4/institution/accounts', { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  institutionalLogin: (subjectId: string, password: string) => request<Record<string, any>>('/api/v4/institution/login', { method: 'POST', body: JSON.stringify({ subject_id: subjectId, password }) }),
  institutionalSession: (credential: GovernanceCredential) => request<{ state: string; subject_id: string; institution_id: string; role: string }>('/api/v4/institution/session', { headers: governanceHeaders(credential) }),
  cohorts: (credential: GovernanceCredential) => request<{ items: Array<Record<string, any>>; count: number }>('/api/v4/institution/cohorts', { headers: governanceHeaders(credential) }),
  createCohort: (credential: GovernanceCredential, payload: Record<string, any>) => request<Record<string, any>>('/api/v4/institution/cohorts', { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  cohortMembers: (credential: GovernanceCredential, cohortId: string) => request<{ items: Array<Record<string, any>> }>(`/api/v4/institution/cohorts/${encodeURIComponent(cohortId)}/members`, { headers: governanceHeaders(credential) }),
  addCohortMember: (credential: GovernanceCredential, cohortId: string, payload: Record<string, any>) => request<Record<string, any>>(`/api/v4/institution/cohorts/${encodeURIComponent(cohortId)}/members`, { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  createFacilitationSession: (credential: GovernanceCredential, payload: Record<string, any>) => request<Record<string, any>>('/api/v4/institution/sessions', { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  facilitationSessions: (credential: GovernanceCredential, cohortId = '') => request<{ items: Array<Record<string, any>> }>(`/api/v4/institution/sessions?cohort_id=${encodeURIComponent(cohortId)}`, { headers: governanceHeaders(credential) }),
  recordFacilitationEvent: (credential: GovernanceCredential, sessionId: string, payload: Record<string, any>) => request<Record<string, any>>(`/api/v4/institution/sessions/${encodeURIComponent(sessionId)}/events`, { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  governanceReadiness: () => request<Record<string, any>>('/api/v4/institution/governance/readiness'),
  calibrationExport: (credential: GovernanceCredential) => request<Record<string, any>>('/api/v4/institution/calibration/export', { headers: governanceHeaders(credential) }),
  standardsManifest: () => request<Record<string, any>>('/api/v4/standards/manifest'),
  privacyPolicies: (credential: GovernanceCredential) => request<{ items: Array<Record<string, any>> }>('/api/v4/institution/privacy/policies', { headers: governanceHeaders(credential) }),
  createPrivacyPolicy: (credential: GovernanceCredential, payload: Record<string, any>) => request<Record<string, any>>('/api/v4/institution/privacy/policy', { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  purgeRetention: (credential: GovernanceCredential) => request<Record<string, any>>('/api/v4/institution/privacy/purge-retention', { method: 'POST', headers: governanceHeaders(credential) }),
  purgeAudit: (credential: GovernanceCredential) => request<{ items: Array<Record<string, any>> }>('/api/v4/institution/privacy/purge-audit', { headers: governanceHeaders(credential) }),
  createBackup: (credential: GovernanceCredential) => request<Record<string, any>>('/api/v4/institution/recovery/backup', { method: 'POST', headers: governanceHeaders(credential) }),
  recoveryBackups: (credential: GovernanceCredential) => request<{ items: Array<Record<string, any>>; count: number }>('/api/v4/institution/recovery/backups', { headers: governanceHeaders(credential) }),
  createSafetyCase: (credential: GovernanceCredential, payload: Record<string, any>) => request<Record<string, any>>('/api/v4/institution/safety-cases', { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  safetyCases: (credential: GovernanceCredential, scenarioId = '') => request<{ items: Array<Record<string, any>> }>(`/api/v4/institution/safety-cases?scenario_id=${encodeURIComponent(scenarioId)}`, { headers: governanceHeaders(credential) }),
  reviewSafetyCase: (credential: GovernanceCredential, caseId: string, payload: Record<string, any>) => request<Record<string, any>>(`/api/v4/institution/safety-cases/${encodeURIComponent(caseId)}/review`, { method: 'POST', headers: governanceHeaders(credential), body: JSON.stringify(payload) }),
  safetyCaseReviews: (credential: GovernanceCredential, caseId = '') => request<{ items: Array<Record<string, any>> }>(`/api/v4/institution/safety-cases/reviews?case_id=${encodeURIComponent(caseId)}`, { headers: governanceHeaders(credential) }),
  generateContentDraft: (payload: { unit_id: string; kind: string; seed?: number }) => request<Record<string, any>>('/api/content-factory/generate', { method: 'POST', body: JSON.stringify(payload) }),
  generateContentBatch: (payload: { unit_ids: string[]; kinds: string[]; seed?: number }) => request<{ requested: number; draft_count: number; items: Array<Record<string, any>>; auto_approved: boolean; message: string }>('/api/content-factory/batch', { method: 'POST', body: JSON.stringify(payload) }),
  tagCatalogue: (facet?: string) => request<TagCatalogue>(`/api/tagging/catalogue${facet ? `?facet=${encodeURIComponent(facet)}` : ''}`),
  taggedContent: (payload: { tag_ids?: string[]; workspace?: string; q?: string; limit?: number } = {}) => {
    const params = new URLSearchParams();
    (payload.tag_ids || []).forEach((tagId) => params.append('tag_id', tagId));
    if (payload.workspace) params.set('workspace', payload.workspace);
    if (payload.q) params.set('q', payload.q);
    if (payload.limit) params.set('limit', String(payload.limit));
    return request<{ count: number; items: TaggedContentItem[] }>(`/api/tagging/content?${params.toString()}`);
  },
  registerTaggedContent: (payload: { content_type: string; content_id: string; title: string; workspace: string; summary?: string; source_status?: string; content_url?: string; tags: string[]; assigned_by?: string }) => request<TaggedContentItem>('/api/tagging/content', { method: 'POST', body: JSON.stringify(payload) }),
  recordTagEvent: (itemId: string, payload: { action: 'opened' | 'attempted' | 'completed' | 'reviewed' | 'revisited'; score?: number; max_score?: number; confidence?: 'low' | 'medium' | 'high' | '' }) => request<{ event_id: string; item_id: string; action: string; occurred_at: string }>(`/api/tagging/content/${encodeURIComponent(itemId)}/events`, { method: 'POST', body: JSON.stringify(payload) }),
  tagAnalytics: () => request<{ items: Array<Record<string, unknown>>; note: string }>('/api/tagging/analytics'),
  dataToolsStatus: () => request<{ mednotegen: Record<string, unknown>; specialty_harvest: Record<string, unknown>; tool_architecture?: Record<string, unknown>; ucks?: Record<string, number | string | unknown>; output_root: string; jobs: HSPTLJob[] }>('/api/tools/status'),
  dataToolsMonitoring: () => request<{ jobs: HSPTLJob[]; job_counts: Record<string, number>; ucks: Record<string, number | string | unknown>; sources: Array<Record<string, unknown>>; ingestion_channels: string[] }>('/api/tools/monitoring'),
  dataToolsProviderHealth: (probe = false) => request<any>(`/api/tools/providers/health?probe=${probe}`),
  dataToolsProviderHealthHistory: (provider_id = "", limit = 50) => request<any>(`/api/tools/providers/health/history?provider_id=${encodeURIComponent(provider_id)}&limit=${limit}`),
  dataToolsGovernance: () => request<any>('/api/tools/ucks/governance'),
  workspaceManifest: () => request<{ items: Record<string, { label: string; purpose: string; sequence: string[]; outputs: string[]; content_types: string[] }>; customizations: Record<string, { config: Record<string, unknown> }> }>('/api/workspaces/manifest'),
  saveWorkspaceCustomization: (workspace: string, config: Record<string, unknown>) => request<{ workspace: string; config: Record<string, unknown> }>(`/api/workspaces/${encodeURIComponent(workspace)}/customization`, { method: 'PUT', body: JSON.stringify({ config }) }),
  ucksSearch: (q: string, limit = 20) => request<{ items: Array<{ document_id: string; title: string; content_type: string; specialty: string; review_status: string; source_url: string }> }>(`/api/ucks/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  generationArtifacts: (workspace?: string) => request<{ items: Array<Record<string, unknown>> }>(`/api/generation/artifacts${workspace ? `?workspace=${encodeURIComponent(workspace)}` : ''}`),
  generationProviderStatus: () => request<{ configured: boolean; mode: string; provider: string; requires_api_key: boolean }>('/api/generation/provider'),
  generateArtifact: (payload: { workspace: string; kind: string; title: string; source_documents: string[] }) => request<Record<string, unknown>>('/api/generation/artifacts', { method: 'POST', body: JSON.stringify(payload) }),
  reviewGeneratedArtifact: (id: string, token: string, decision: string) => request<Record<string, unknown>>(`/api/generation/artifacts/${encodeURIComponent(id)}/review`, { method: 'POST', headers: { 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify({ decision }) }),
  distributionRoutes: (workspace?: string) => request<{ items: Array<Record<string, unknown>> }>(`/api/distribution/routes${workspace ? `?workspace=${encodeURIComponent(workspace)}` : ''}`),
  distributeArtifact: (artifactId: string, workspace: string, section: string) => request<Record<string, unknown>>(`/api/distribution/routes?artifact_id=${encodeURIComponent(artifactId)}`, { method: 'POST', body: JSON.stringify({ workspace, section }) }),
  ucksReviewerStatus: () => request<{ configured: boolean; reviewer_id: string; authentication: string }>('/api/ucks/reviewer/status'),
  ucksRightsReviews: (documentId: string) => request<{ items: any[] }>(`/api/ucks/documents/${encodeURIComponent(documentId)}/rights-reviews`),
  ucksCreateRightsReview: (documentId: string, token: string, payload: { decision: string; licence?: string; licence_uri?: string; attribution?: string; scope: string; evidence_reference?: string; rationale?: string }) => request<any>(`/api/ucks/documents/${encodeURIComponent(documentId)}/rights-reviews`, { method: 'POST', headers: { 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify(payload) }),
  ucksEvidenceAppraisal: (documentId: string) => request<any>(`/api/ucks/documents/${encodeURIComponent(documentId)}/evidence-appraisal`),
  ucksSaveEvidenceAppraisal: (documentId: string, token: string, payload: Record<string, unknown>) => request<any>(`/api/ucks/documents/${encodeURIComponent(documentId)}/evidence-appraisal`, { method: 'PUT', headers: { 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify(payload) }),
  ucksAppraisalHistory: (documentId: string) => request<{ items: any[] }>(`/api/ucks/documents/${encodeURIComponent(documentId)}/evidence-appraisal/history`),
  cancelToolJob: (id: string) => request<{ cancel_requested: boolean }>(`/api/tools/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  queueMedNoteGen: (fhir_dir: string, output_dir?: string) => request<{ id: string; status: string }>('/api/tools/mednotegen/generate', { method: 'POST', body: JSON.stringify({ fhir_dir, output_dir }) }),
  queueSpecialtyHarvest: (payload: { specialties: string[]; max_cases_per_specialty: number; year_from?: number; year_to?: number; knowledge_profile?: string }) => request<{ id: string; status: string }>('/api/tools/specialty-harvest/run', { method: 'POST', body: JSON.stringify(payload) }),
  runToolJob: (id: string) => request<{ ran: boolean; job: HSPTLJob }>(`/api/tools/jobs/${encodeURIComponent(id)}/run`, { method: 'POST' }),
  harvestedCases: (specialty?: string) => request<{ count: number; items: HarvestedCase[] }>(`/api/tools/harvested-cases${specialty ? `?specialty=${encodeURIComponent(specialty)}` : ''}`),
  syntheticStatus: () => request<SyntheticStatus>('/api/synthetic/status'),
  syntheticSettings: () => request<SyntheticSettings>('/api/synthetic/settings'),
  saveSyntheticSettings: (payload: Record<string, unknown>) => request<SyntheticSettings>('/api/synthetic/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  syntheticRecipes: () => request<{ items: SyntheticRecipe[]; lifecycle: string[] }>('/api/synthetic/recipes'),
  syntheticRecipe: (id: string, version?: string) => request<SyntheticRecipe>(`/api/synthetic/recipes/${encodeURIComponent(id)}${version ? `?version=${encodeURIComponent(version)}` : ''}`),
  transitionSyntheticRecipe: (id: string, token: string, status: string, rationale = '') => request<SyntheticRecipe>(`/api/synthetic/recipes/${encodeURIComponent(id)}/transition`, { method: 'POST', headers: { 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify({ status, rationale }) }),
  syntheticPreflight: (payload: { recipe_id: string; population: number; fhir: boolean; csv: boolean; version?: string }) => request<SyntheticPreflight>('/api/synthetic/preflight', { method: 'POST', body: JSON.stringify(payload) }),
  queueSyntheticJob: (payload: { recipe_id: string; population: number; accepted_target?: number; seed?: number | null; fhir: boolean; csv: boolean; version?: string }) => request<{ run: SyntheticRun; job_id?: string; idempotent_reuse: boolean }>('/api/synthetic/jobs', { method: 'POST', body: JSON.stringify(payload) }),
  syntheticJobs: (limit = 50) => request<{ items: SyntheticRun[]; counts: Record<string, number> }>(`/api/synthetic/jobs?limit=${limit}`),
  syntheticJob: (id: string) => request<{ run: SyntheticRun; job: Record<string, unknown> | null; stages: string[] }>(`/api/synthetic/jobs/${encodeURIComponent(id)}`),
  runSyntheticJob: (id: string) => request<{ ran: boolean; job: unknown }>(`/api/synthetic/jobs/${encodeURIComponent(id)}/run`, { method: 'POST' }),
  cancelSyntheticJob: (id: string) => request<{ cancelled: boolean }>(`/api/synthetic/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  syntheticDatasets: (limit = 50) => request<{ items: SyntheticDataset[]; counts: Record<string, number> }>(`/api/synthetic/datasets?limit=${limit}`),
  syntheticDataset: (id: string) => request<SyntheticDataset>(`/api/synthetic/datasets/${encodeURIComponent(id)}`),
  syntheticQuality: (id: string) => request<SyntheticQuality>(`/api/synthetic/datasets/${encodeURIComponent(id)}/quality`),
  syntheticManifest: (id: string) => request<{ verified: boolean; verification: string; manifest: Record<string, unknown> }>(`/api/synthetic/datasets/${encodeURIComponent(id)}/manifest`),
  syntheticQuarantine: (params?: { dataset_id?: string; status?: string; severity?: string }) => { const q = new URLSearchParams(); if (params?.dataset_id) q.set('dataset_id', params.dataset_id); if (params?.status) q.set('status', params.status); if (params?.severity) q.set('severity', params.severity); return request<{ items: SyntheticQuarantineItem[]; count: number }>(`/api/synthetic/quarantine?${q.toString()}`); },
  reviewSyntheticQuarantine: (id: string, token: string, decision: string, rationale = '') => request<SyntheticQuarantineItem>(`/api/synthetic/quarantine/${encodeURIComponent(id)}/review`, { method: 'POST', headers: { 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify({ decision, rationale }) }),
  syntheticSchedules: () => request<{ items: SyntheticSchedule[] }>('/api/synthetic/schedules'),
  createSyntheticSchedule: (payload: { name: string; recipe_id: string; population: number; accepted_target?: number; frequency: string; enabled: boolean }) => request<SyntheticSchedule>('/api/synthetic/schedules', { method: 'POST', body: JSON.stringify(payload) }),
  updateSyntheticSchedule: (id: string, payload: Record<string, unknown>) => request<SyntheticSchedule>(`/api/synthetic/schedules/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  runDueSyntheticSchedules: () => request<{ queued: Array<Record<string, unknown>> }>('/api/synthetic/schedules/run-due', { method: 'POST' }),
  progress: () => request<ProgressSummary>('/api/progress'),
  connectDataset: (path: string) => request<{ connected: boolean; patients: number; cohorts: string[] }>('/api/data/connect', {
    method: 'POST', body: JSON.stringify({ path }),
  }),
  importFHIR: (path: string) => request<{ status: string; patients: number; encounters: number; facts: number; unlinked: number; files: number; skipped_unchanged: number; errors: number }>('/api/clinical/fhir/import', {
    method: 'POST', body: JSON.stringify({ path, batch_size: 250 }),
  }),
  clinicalPatients: (limit = 50, offset = 0) => request<{ total: number; limit: number; offset: number; items: ClinicalPatient[] }>(`/api/clinical/patients?limit=${limit}&offset=${offset}`),
  clinicalCase: (patientKey: string, encounterKey?: string) => request<ClinicalCase>(`/api/clinical/patients/${encodeURIComponent(patientKey)}${encounterKey ? `?encounter_key=${encodeURIComponent(encounterKey)}` : ''}`),
  clinicalNarrative: (patientKey: string, encounterKey: string) => request<ClinicalNarrative>(`/api/clinical/patients/${encodeURIComponent(patientKey)}/encounters/${encodeURIComponent(encounterKey)}/narrative`),
  saveClinicalAttempt: (payload: ClinicalAttemptPayload) => request<{ attempt_id: string; saved: boolean; created_at: string; feedback: ReasoningFeedback; case_events: ClinicalCaseEvent[] }>('/api/clinical/learning-attempts', { method: 'POST', body: JSON.stringify(payload) }),
  clinicalLearningAttempts: (limit = 100) => request<{ count: number; items: ClinicalLearningAttemptSummary[] }>(`/api/clinical/learning-attempts?limit=${limit}`),
  clinicalLearningAttempt: (attemptId: string) => request<ClinicalLearningAttemptDetail>(`/api/clinical/learning-attempts/${encodeURIComponent(attemptId)}`),
  createLearningPearl: (attemptId: string, focus: string, reflection: string) => request<{ saved: boolean; id: string; title: string; version: number; created: boolean }>(`/api/clinical/learning-attempts/${encodeURIComponent(attemptId)}/pearl`, { method: 'POST', body: JSON.stringify({ focus, reflection }) }),
  clinicalDebrief: (attemptId: string) => request<ClinicalDebrief>(`/api/clinical/learning-attempts/${encodeURIComponent(attemptId)}/debrief`),
  saveClinicalDebrief: (attemptId: string, responses: Record<string, string>) => request<{ saved: boolean; responses: Record<string, string>; completed: number; total: number }>(`/api/clinical/learning-attempts/${encodeURIComponent(attemptId)}/debrief`, { method: 'PUT', body: JSON.stringify({ responses }) }),
  dailyPuzzle: () => request<Puzzle>('/api/clinic/daily'),
  newPuzzle: (puzzleId?: string) => request<Puzzle>('/api/clinic/start', {
    method: 'POST', body: JSON.stringify({ puzzle_id: puzzleId ?? null }),
  }),
  guess: (runId: string, guess: string) => request<{ result: string } & Puzzle>('/api/clinic/guess', {
    method: 'POST', body: JSON.stringify({ run_id: runId, guess }),
  }),
  reveal: (runId: string) => request<Puzzle>(`/api/clinic/reveal/${encodeURIComponent(runId)}`, { method: 'POST' }),
  puzzles: (specialty?: string) => request<Array<{ id: string; title: string; specialty: string; difficulty: string; clue_count: number; source_title: string }>>(
    `/api/clinic/puzzles${specialty ? `?specialty=${encodeURIComponent(specialty)}` : ''}`,
  ),
  specialties: () => request<Specialty[]>('/api/specialties'),
  clinicalEventCatalogue: () => request<{ items: ClinicalEventCatalogueItem[]; count: number; note: string }>('/api/clinical-catalogue/events'),
  saveClinicalEvent: (event: ClinicalEventCatalogueItem, token: string) => request<ClinicalEventCatalogueItem>(`/api/v5/clinical-events/${encodeURIComponent(event.id)}`, { method: 'PUT', headers: { 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify(event) }),
  publishedLearningArtifacts: (workspace = '') => request<{ items: PublishedLearningArtifact[]; count: number; publication_rule: string }>(`/api/published-learning/artifacts${workspace ? `?workspace=${encodeURIComponent(workspace)}` : ''}`),
  recordPublishedArtifactUse: (artifactId: string, learnerId = 'local-default', sessionId = '') => request<{ usage_id: string; artifact_id: string; recorded: boolean; identity_verified: boolean; learner_level: string; validation_contribution: boolean }>(`/api/published-learning/artifacts/${encodeURIComponent(artifactId)}/use`, { method: 'POST', body: JSON.stringify({ learner_id: learnerId, session_id: sessionId }) }),
  completePublishedArtifactUse: (artifactId: string, usageId: string, learnerId = 'local-default', sessionId = '') => request<{ usage_id: string; artifact_id: string; completed: boolean; completed_at: string; identity_verified: boolean }>(`/api/published-learning/artifacts/${encodeURIComponent(artifactId)}/use/${encodeURIComponent(usageId)}/complete`, { method: 'POST', body: JSON.stringify({ learner_id: learnerId, session_id: sessionId }) }),
  submitPublishedArtifactFeedback: (artifactId: string, payload: { usage_id: string; learner_id?: string; session_id?: string; rating?: number | null; educational_rating?: number; clinical_rating?: number; source_rating?: number; assessment_rating?: number; severity?: 'routine'|'major'|'critical'; categories: string[]; source_document_ids?: string[]; comment?: string }) => request<{ feedback_id: string; status: string; received: boolean; identity_verified: boolean; validation_contribution: boolean; validation: ArtifactValidationSummary; message: string }>(`/api/published-learning/artifacts/${encodeURIComponent(artifactId)}/feedback`, { method: 'POST', body: JSON.stringify(payload) }),
  signoffPublishedArtifactValidation: (artifactId: string, sessionId: string, payload: { domain: 'educational'|'clinical'|'sources'|'assessment'; decision: 'affirmed'|'revision_required'|'rejected'; note: string }) => request<{ artifact_id: string; domain: string; decision: string; reviewer_id: string; validation: ArtifactValidationSummary; artifact_status_changed: boolean }>(`/api/published-learning/artifacts/${encodeURIComponent(artifactId)}/validation/signoffs`, { method: 'POST', headers: { 'X-HSPTL-Session': sessionId }, body: JSON.stringify(payload) }),
  learnerFeedbackQueue: (token: string, status = 'pending') => request<{ items: LearnerFeedbackItem[]; count: number }>('/api/published-learning/feedback/queue?status=' + encodeURIComponent(status), { headers: { 'X-HSPTL-Reviewer-Token': token } }),
  resolveLearnerFeedback: (feedbackId: string, token: string, status: 'acknowledged'|'source_review_required'|'artifact_revision_required'|'closed', resolution: string) => request<Record<string, unknown>>(`/api/published-learning/feedback/${encodeURIComponent(feedbackId)}/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-HSPTL-Reviewer-Token': token }, body: JSON.stringify({ status, resolution }) }),
  specialty: (slug: string) => request<SpecialtyDetail>(`/api/specialties/${encodeURIComponent(slug)}`),
  specialtyArticles: (slug: string, topic: string) => request<Array<{ title: string; authors: string; journal: string; year: string; pmcid: string; open_access: boolean; url: string; abstract: string }>>(
    `/api/specialties/${encodeURIComponent(slug)}/articles?q=${encodeURIComponent(topic)}`,
  ),
  specialtyImages: (slug: string, topic: string) => request<Array<Record<string, string>>>(
    `/api/specialties/${encodeURIComponent(slug)}/images?q=${encodeURIComponent(topic)}`,
  ),
  pearlsOptions: () => request<{ note_types: string[]; levels: string[]; jurisdictions: string[]; packs: Array<{ id: string; title: string; tagline: string; source_title: string; source_url: string }> }>('/api/pearls/options'),
  references: () => request<Array<{ name: string; modified: string; size_bytes: number }>>('/api/pearls/references'),
  uploadReference: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<{ saved: boolean; name: string; size_bytes: number }>('/api/pearls/references', { method: 'POST', body: form });
  },
  generateNote: (payload: { topic: string; note_type: string; level: string; jurisdiction: string; use_local_pdfs: boolean; use_open_access: boolean; pmcid?: string }) => request<{ note: StudyNote; markdown: string; tutor_prompt: string; local_reference_count: number; matched_curated_pack: boolean }>('/api/pearls/generate', {
    method: 'POST', body: JSON.stringify(payload),
  }),
  saveNote: (note: StudyNote) => request<{ saved: boolean; id?: string; title?: string }>('/api/pearls/save', {
    method: 'POST', body: JSON.stringify({ note }),
  }),
  savedPearls: () => request<SavedPearl[]>('/api/pearls/saved'),
  savedPearl: (id: string) => request<{ note: StudyNote; markdown: string }>(`/api/pearls/saved/${encodeURIComponent(id)}`),
  createCards: (note: StudyNote) => request<{ created: number }>('/api/pearls/cards', {
    method: 'POST', body: JSON.stringify({ note }),
  }),
  revision: () => request<{ stats: Record<string, number>; due_cards: Array<Record<string, unknown>> }>('/api/revision'),
  gradeCard: (id: string, grade: 'Again' | 'Hard' | 'Good' | 'Easy') => request<{ saved: boolean }>(`/api/revision/cards/${encodeURIComponent(id)}/grade`, {
    method: 'POST', body: JSON.stringify({ grade }),
  }),
  settings: () => request<{ theme: 'light' | 'dark'; dataset_dirs: string[]; reference_dirs: string[]; user_data_dir: string }>('/api/settings'),
  theme: (theme: 'light' | 'dark') => request<{ theme: string }>('/api/settings/theme', {
    method: 'PUT', body: JSON.stringify({ theme }),
  }),
examDatasets: () => request<Array<{ id: string; name: string; description: string; url: string; licence: string; format: string; priority: string }>>('/api/exams/datasets'),
exams: () => request<ExamItem[]>('/api/exams'),
examQuestions: () => request<ExamQuestionBank>('/api/exams/questions'),
reviewQuestion: (id: string, reviewed: boolean) => request<{ saved: boolean; reviewed: boolean }>(`/api/questions/${encodeURIComponent(id)}/review`, { method: 'POST', body: JSON.stringify({ reviewed }) }),
importExamQuestions: (file: File) => { const form = new FormData(); form.append('file', file); return request<{ created: number; skipped: number; truncated: number }>('/api/exams/import', { method: 'POST', body: form }); },
buildExam: (payload: { title: string; specialty: string; question_count: number; duration_minutes: number; difficulty: string }) => request<ExamItem>('/api/exams/build', { method: 'POST', body: JSON.stringify(payload) }),
addExamQuestion: (payload: Record<string, unknown>) => request<QuestionItem>('/api/exams/questions', { method: 'POST', body: JSON.stringify(payload) }),
exam: (id: string) => request<ExamDetail>(`/api/exams/${encodeURIComponent(id)}`),
submitExam: (id: string, responses: Record<string, string>, duration_seconds: number) => request<ExamReport>(`/api/exams/${encodeURIComponent(id)}/submit`, { method: 'POST', body: JSON.stringify({ responses, duration_seconds }) }),
examAttemptReport: (attemptId: string) => request<ExamReport>(`/api/exam-attempts/${encodeURIComponent(attemptId)}`),
osceChallenges: () => request<QuestionItem[]>('/api/osce/challenges'),
importOsce: (file: File) => { const form = new FormData(); form.append('file', file); return request<{ created: number; skipped: number; truncated: number }>('/api/osce/import', { method: 'POST', body: form }); },
osceAttempt: (id: string, response: string, durationSeconds = 0) => request<{ question_id: string; response: string; correct: boolean; answer: string; explanation: string; source_title: string; source_url: string; points: number }>('/api/osce/attempt', { method: 'POST', body: JSON.stringify({ question_id: id, response, duration_seconds: durationSeconds }) }),
episodes: (status?: string, limit = 30, offset = 0) => request<{ total: number; limit: number; offset: number; items: Array<Record<string, unknown>> }>(`/api/episodes?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ''}`),
episode: (id: string) => request<Record<string, unknown>>(`/api/episodes/${encodeURIComponent(id)}`),
episodeLineage: (id: string) => request<Record<string, unknown>>(`/api/episodes/${encodeURIComponent(id)}/lineage`),
saveEpisodeDraft: (id: string, draft: Record<string, string>, expected_revision?: number, stage?: number) => request<{ saved: boolean; draft_revision: number }>(`/api/episodes/${encodeURIComponent(id)}/draft`, { method:'PATCH', body:JSON.stringify({ draft, expected_revision, stage }) }),
addEpisodeArtifact: (id: string, payload: { kind: string; body: Record<string, unknown>; authored_by?: string; verification_status?: string; source_refs?: Array<Record<string, unknown>> }) => request<Record<string, unknown>>(`/api/episodes/${encodeURIComponent(id)}/artifacts`, { method:'POST', body:JSON.stringify(payload) }),
completeEpisode: (id: string) => request<Record<string, unknown>>(`/api/episodes/${encodeURIComponent(id)}/complete`, { method:'POST' }),
contentReviewQueue: (status = 'open') => request<Array<{ item_id:string; owner_kind:string; owner_id:string; reason:string; severity:string; status:string; due_date:string; created_at:string }>>(`/api/content/review?status=${encodeURIComponent(status)}`),
resolveContentReview: (id:string, status:'verified'|'retired'|'in_review'|'open', reviewer='local reviewer') => request<{item_id:string;status:string}>(`/api/content/review/${encodeURIComponent(id)}/resolve`, { method:'POST', body:JSON.stringify({status,reviewer}) }),
startEpisode: (payload: Record<string, unknown>) => request<Record<string, unknown>>('/api/episodes', { method: 'POST', body: JSON.stringify(payload) }),
nextAction: () => request<Record<string, unknown>>('/api/episodes/next'),
revisionAnalytics: () => request<Record<string, unknown>>('/api/revision/analytics'),
facetedSearch: (payload: { q: string; facets?: Record<string, unknown>; limit?: number; offset?: number }) => request<Record<string, unknown>>('/api/search/faceted', { method: 'POST', body: JSON.stringify(payload) }),
features: () => request<Array<Record<string, unknown>>>('/api/features'),
exportPortfolio: () => request<Record<string, unknown>>('/api/portability/export'),
  // --- HSPTL 5.1.0 learning intelligence ---------------------------------------- //
  labels: () => request<{ labels: Array<{ id: ContentLabel; description: string }>; independent_dimensions: string[]; note: string; registry: Record<string, unknown> }>('/api/v5/labels'),
  lineageSummary: () => request<Record<string, unknown>>('/api/v5/lineage/summary'),
  labelItem: (itemId: string) => request<Record<string, unknown>>(`/api/v5/labels/items/${encodeURIComponent(itemId)}`),
  labelLineage: (itemId: string) => request<{ chain: Array<Record<string, unknown>>; complete: boolean; item_count: number; children: Array<Record<string, unknown>> }>(`/api/v5/labels/items/${encodeURIComponent(itemId)}/lineage`),
  sourceCatalogue: () => request<{ items: SourceCatalogueEntry[]; count: number; note: string }>('/api/v5/sources/catalogue'),
  sourceRegistry: (family = '', reviewedOnly = false) => request<{ items: Array<Record<string, unknown>>; count: number; summary: Record<string, unknown> }>(`/api/v5/sources/registry?family=${encodeURIComponent(family)}&reviewed_only=${reviewedOnly}`),
  localFolders: () => request<{ items: Array<Record<string, unknown>>; summary: LocalFolderSummary; safety: Record<string, unknown> }>('/api/v5/local-folders'),
  localFolderFiles: (rootId = '', verdict = '') => request<{ items: Array<Record<string, unknown>>; count: number }>(`/api/v5/local-folders/files?root_id=${encodeURIComponent(rootId)}&verdict=${encodeURIComponent(verdict)}`),
  lotteryDaily: (workspace: 'ward_board' | 'clinic' = 'clinic') => request<LotteryDaily>(`/api/v5/lottery/daily?workspace=${workspace}`),
  lotteryReveal: (drawId: string, learnerId: string) => request<Record<string, unknown>>(`/api/v5/lottery/draws/${encodeURIComponent(drawId)}/reveal`, { method: 'POST', body: JSON.stringify({ learner_id: learnerId, reason: 'explicit_reveal' }) }),
  lotteryAttempt: (drawId: string, learnerId: string, response: string, confidence: number | null) => request<Record<string, unknown>>(`/api/v5/lottery/draws/${encodeURIComponent(drawId)}/attempt`, { method: 'POST', body: JSON.stringify({ learner_id: learnerId, response, confidence }) }),
  learningPreferences: (learnerId: string, specialties: string[], difficulty: string) => request<Record<string, unknown>>('/api/v5/learning/preferences', { method: 'PUT', body: JSON.stringify({ learner_id: learnerId, specialties, difficulty }) }),
  learningRecommendations: (learnerId: string) => request<Record<string, unknown>>(`/api/v5/learning/recommendations/${encodeURIComponent(learnerId)}`),
  lotteryHistory: (limit = 365) => request<{ items: LotteryArchiveItem[]; workspaces: string[]; count: number; privacy: string }>(`/api/v5/lottery/history?limit=${limit}`),
  lotterySummary: () => request<Record<string, unknown>>('/api/v5/lottery/summary'),
  engineMatrix: () => request<EngineMatrix>('/api/v5/engines/matrix'),
  workspaceEngineContracts: () => request<WorkspaceEngineContracts>('/api/v5/workspaces/contracts'),
  engineInvoke: (payload: { skin: string; area: string; operation: string; payload: Record<string, unknown> }) => request<{ skin: string; area: string; engine: string; operation: string; result: Record<string, unknown> }>('/api/v5/engines/invoke', { method: 'POST', body: JSON.stringify(payload) }),
  pearlsFactoryTemplates: () => request<{ templates: Array<Record<string, unknown>>; summary: Record<string, unknown> }>('/api/v5/pearls-factory/templates'),
  pearlsFactoryCompose: (payload: { topic: string; template_id?: string; seed?: number }) => request<Record<string, unknown>>('/api/v5/pearls-factory/compose', { method: 'POST', body: JSON.stringify(payload) }),
  pearlsFactoryArtifacts: (topic = '') => request<{ items: Array<Record<string, unknown>>; count: number }>(`/api/v5/pearls-factory/artifacts?topic=${encodeURIComponent(topic)}`),
  nextIncrementsOverview: () => request<NextIncrementsOverview>('/api/v5/overview'),
};

export type SyntheticStatus = {
  generator: { configured: boolean; version: string; path_set: boolean; checksum_pinned: boolean };
  java: { available: boolean; detail: string };
  validator: { configured: boolean; version: string; strict_available: boolean };
  worker: { enabled: boolean; note: string };
  storage: { root: string; free_mb: number; min_free_mb: number };
  limits: { max_heap_mb: number; concurrency: number };
  datasets: Record<string, number>;
  runs: Record<string, number>;
  pipeline: { stage_version: string; stages: string[] };
  rule_pack: { rule_pack_id: string; rule_pack_version: string };
};
export type SyntheticSettings = {
  synthea_jar: string; synthea_version: string; synthea_sha256: string; java_path: string;
  module_dir: string; config_file: string; validator_jar: string; validator_sha256: string;
  validator_version: string; max_heap_mb: number; min_free_disk_mb: number; strict_fhir_required: boolean;
};
export type SyntheticRecipe = {
  recipe_id: string; version: string; title: string; description: string; status: string;
  owner: string; builtin: number; content_digest: string; reviewer: string; reviewed_at: string;
  updated_at?: string; body?: Record<string, any>;
};
export type SyntheticRun = {
  run_id: string; job_id: string; recipe_id: string; recipe_version: string; status: string;
  stage: string; stage_index: number; dataset_id: string; error_code: string; diagnostic: string;
  counts: Record<string, any>; created_at: string; updated_at: string;
};
export type SyntheticDataset = {
  dataset_id: string; run_id: string; job_id: string; recipe_id: string; recipe_version: string;
  name: string; status: string; cohort_status: string; seed: string; synthea_version: string;
  fhir_version: string; manifest_digest: string; content_digest: string;
  generated_patients: number; matched_patients: number; accepted_patients: number;
  quarantined_patients: number; imported_patients: number; validation_status: string;
  strict_conformance: number; terminology_status: string; storage_bytes: number; created_at: string;
  artifacts?: Array<{ relative_path: string; kind: string; byte_size: number; sha256: string }>;
  quarantine?: SyntheticQuarantineItem[]; finding_counts?: Record<string, number>;
};
export type SyntheticQuality = {
  dataset: SyntheticDataset;
  findings: Array<{ dimension: string; rule_id: string; severity: string; message: string; patient_key: string; resource_type: string }>;
  severity_counts: Record<string, number>; dimension_counts: Record<string, number>; limitations: string[];
};
export type SyntheticQuarantineItem = {
  item_id: string; dataset_id: string; job_id: string; patient_key: string; bundle_path: string;
  reason: string; rule_ids: string[]; severity: string; status: string; reviewer: string;
  rationale: string; reviewed_at: string; created_at: string;
  reviews?: Array<{ reviewer: string; decision: string; rationale: string; created_at: string }>;
};
export type SyntheticSchedule = {
  schedule_id: string; name: string; recipe_id: string; recipe_version: string; population: number;
  accepted_target: number; frequency: string; enabled: number; last_run_at: string;
  next_run_at: string; last_status: string; created_at: string;
};
export type SyntheticPreflight = {
  ok: boolean;
  checks: Array<{ check_id: string; ok: boolean; blocking: boolean; detail: string }>;
  blockers: Array<{ check_id: string; ok: boolean; blocking: boolean; detail: string }>;
  recipe?: { recipe_id: string; version: string; status: string };
  generator?: { version: string; checksum_pinned: boolean };


};
