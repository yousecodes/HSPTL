/** Six workspace skins share runtime primitives and differ only in presentation/configuration. */
export type WorkspaceSkinId = 'clinic' | 'rounds' | 'lab' | 'ward' | 'exam' | 'portfolio';
export type WorkspaceModule = {
  id: string;
  contributes: string[];
  configurable: string[];
};
export type WorkspaceSkin = {
  id: WorkspaceSkinId;
  label: string;
  presentation: { density: string; canvas: string; accent: string };
  routingProfile: string;
  modules: string[];
  routeMap: Record<string, string>;
};

const modules: Record<string, WorkspaceModule> = {
  'case-reasoning': { id: 'case-reasoning', contributes: ['case-enactment', 'debrief', 'clinical-simulation'], configurable: ['focus', 'section_labels'] },
  'evidence-teaching': { id: 'evidence-teaching', contributes: ['viva', 'reports', 'procedure-prep'], configurable: ['focus', 'section_labels'] },
  'pulse-renderers': { id: 'pulse-renderers', contributes: ['vitals', 'spotters', 'osce'], configurable: ['display_units', 'visible_observations'] },
  'proforma-workflows': { id: 'proforma-workflows', contributes: ['on-call', 'handover', 'consult', 'progression'], configurable: ['focus', 'section_labels'] },
  'assessment-engine': { id: 'assessment-engine', contributes: ['question-delivery', 'irt', 'review-scheduling'], configurable: ['exam_presentation', 'section_labels'] },
  'portfolio-tools': { id: 'portfolio-tools', contributes: ['profile', 'progress', 'data-tools', 'governance'], configurable: ['focus', 'section_labels'] },
  'shared-event-api': { id: 'shared-event-api', contributes: ['event-projection', 'plugin-config', 'explainability'], configurable: [] },
};

const skins: Record<WorkspaceSkinId, WorkspaceSkin> = {
  clinic: { id: 'clinic', label: 'Clinic', presentation: { density: 'clinical', canvas: 'case', accent: 'blue' }, routingProfile: 'clinic-case-route', modules: ['case-reasoning', 'shared-event-api'], routeMap: { reports: 'case-reasoning', simulation: 'clinical-simulation', debriefs: 'case-debrief', conference: 'case-conference', archives: 'case-archive' } },
  rounds: { id: 'rounds', label: 'Rounds', presentation: { density: 'editorial', canvas: 'reading', accent: 'slate' }, routingProfile: 'rounds-teaching-route', modules: ['evidence-teaching', 'shared-event-api'], routeMap: { viva: 'viva-enactment', reports: 'tagged-report-library', procedure: 'procedure-theatre' } },
  lab: { id: 'lab', label: 'Lab', presentation: { density: 'focused', canvas: 'diagnostic', accent: 'teal' }, routingProfile: 'lab-practical-route', modules: ['pulse-renderers', 'shared-event-api'], routeMap: { spotters: 'visual-spotter', osce: 'osce-enactment' } },
  ward: { id: 'ward', label: 'Ward', presentation: { density: 'operational', canvas: 'workflow', accent: 'amber' }, routingProfile: 'ward-proforma-route', modules: ['proforma-workflows', 'shared-event-api'], routeMap: { oncall: 'on-call-plan', handover: 'handover-plan', consult: 'consult-plan', progression: 'progression-plan' } },
  exam: { id: 'exam', label: 'Exam Hall', presentation: { density: 'minimal', canvas: 'assessment', accent: 'indigo' }, routingProfile: 'exam-irt-route', modules: ['assessment-engine', 'shared-event-api'], routeMap: { pearls: 'pearls', summaries: 'summaries', lectures: 'attending-lectures', questions: 'question-delivery', scores: 'score-report' } },
  portfolio: { id: 'portfolio', label: 'Portfolio', presentation: { density: 'dashboard', canvas: 'portfolio', accent: 'neutral' }, routingProfile: 'portfolio-governance-route', modules: ['portfolio-tools', 'shared-event-api'], routeMap: { profile: 'profile', progress: 'progress-board', tools: 'data-tools', studio: 'content-studio', admin: 'question-review' } },
};

export function getWorkspaceSkin(id: WorkspaceSkinId): WorkspaceSkin {
  return skins[id];
}

export function getWorkspaceModules(id: WorkspaceSkinId): WorkspaceModule[] {
  return skins[id].modules.map(moduleId => modules[moduleId]);
}

/** Presentation-only allow-lists; clinical facts and executable predicates never belong to a skin. */
const configKeys: Record<WorkspaceSkinId, Record<string, { type: string; values?: string[]; maxItems?: number }>> = {
  clinic: { focus: { type: 'string' }, section_labels: { type: 'object' } },
  rounds: { focus: { type: 'string' }, section_labels: { type: 'object' } },
  lab: { display_units: { type: 'string', values: ['SI', 'US'] }, visible_observations: { type: 'array', maxItems: 64 } },
  ward: { focus: { type: 'string' }, section_labels: { type: 'object' } },
  exam: { exam_presentation: { type: 'string', values: ['focused', 'accessible', 'compact'] }, section_labels: { type: 'object' } },
  portfolio: { focus: { type: 'string' }, section_labels: { type: 'object' } },
};

export function validateSkinConfig(config: Record<string, unknown>, skinId?: WorkspaceSkinId): boolean {
  const forbidden = ['clinical_facts', 'diagnoses', 'evidence', 'appraisal_rules', 'routing_predicates', 'preconditions', 'clinical_thresholds', 'medical_rules'];
  if (forbidden.some(key => Object.prototype.hasOwnProperty.call(config, key))) return false;
  const allowed = skinId ? configKeys[skinId] : Object.assign({}, ...Object.values(configKeys));
  return Object.entries(config).every(([key, value]) => {
    const schema = allowed[key];
    if (!schema) return false;
    const validType = schema.type === 'array' ? Array.isArray(value)
      : schema.type === 'object' ? typeof value === 'object' && value !== null && !Array.isArray(value)
      : schema.type === 'string' ? typeof value === 'string' : false;
    if (!validType) return false;
    if (schema.values && !schema.values.includes(String(value))) return false;
    if (schema.maxItems !== undefined && Array.isArray(value) && value.length > schema.maxItems) return false;
    return true;
  });
}

export const workspaceSkinIds = Object.keys(skins) as WorkspaceSkinId[];
