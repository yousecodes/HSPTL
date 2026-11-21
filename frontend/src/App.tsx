import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
const ClinicPage = lazy(() => import('./pages/ClinicPage'));
const PearlsPage = lazy(() => import('./pages/PearlsPage'));
const ExamCentrePage = lazy(() => import('./pages/ExamCentrePage'));
const OSCEPage = lazy(() => import('./pages/OSCEPage'));
const ProgressPage = lazy(() => import('./pages/ProgressPage'));
const DataToolsPage = lazy(() => import('./pages/DataToolsPage'));
const AttendingRoomPage = lazy(() => import('./pages/AttendingRoomPage'));
const CaseDebriefsPage = lazy(() => import('./pages/CaseDebriefsPage'));
const WorkflowPage = lazy(() => import('./pages/WorkflowPage'));
const AdminReviewPage = lazy(() => import('./pages/AdminReviewPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const ClinicalSimulationPage = lazy(() => import('./pages/ClinicalSimulationPage'));
const LearningLibraryPage = lazy(() => import('./pages/LearningLibraryPage'));
const HomeDashboardPage = lazy(() => import('./pages/HomeDashboardPage'));
const ContentFactoryPage = lazy(() => import('./pages/ContentFactoryPage'));
const SpecialtiesPage = lazy(() => import('./pages/SpecialtiesPage'));
const DailyCaseArchivePage = lazy(() => import('./pages/DailyCaseArchivePage'));
const LogoSpecimenPage = lazy(() => import('./pages/LogoSpecimenPage'));
const SyntheticDataPage = lazy(() => import('./pages/SyntheticDataPage'));
const ContentOperationsPage = lazy(() => import('./pages/ContentOperationsPage'));
import { api } from './lib/api';
import type { Bootstrap } from './lib/api';
import { Icon } from './components/Icon';
import type { IconName } from './components/Icon';
import { HospitalDirectory } from './components/HospitalDirectory';
import { getWorkspaceSkin } from './hsptl40/skinRegistry';

type View = 'home' | 'library' | 'practice' | 'simulation' | 'skills' | 'exams' | 'debriefs' | 'progress' | 'studio' | 'review' | 'tools' | 'viva' | 'viva-station' | 'pearls' | 'lectures' | 'archives' | 'conference' | 'procedures' | 'progression' | 'summaries' | 'oncall' | 'handover' | 'consult' | 'profile' | 'synthetic' | 'operations';
type ThemePreference = 'system' | 'light' | 'dark';
type NavEntry = { id: View; label: string; description: string; icon: IconName; group: string };

function RouteLoading() {
  return <div className="hx-route-loading" role="status" aria-live="polite">
    <span className="hx-route-loading-dot"/>
    Loading workspace…
  </div>;
}

const navigation: NavEntry[] = [
  { id: 'home', label: 'Home', description: 'Daily clinical case', icon: 'clinic', group: 'HOME' },
  { id: 'practice', label: 'Clinic', description: 'Daily case and clinical reports', icon: 'stethoscope', group: 'HOSPITAL' },
  { id: 'skills', label: 'Lab', description: 'OSCE, examination and practical skills', icon: 'microscope', group: 'HOSPITAL' },
  { id: 'oncall', label: 'Ward', description: 'Acute care, handover and ward workflows', icon: 'bed-double', group: 'HOSPITAL' },
  { id: 'library', label: 'Library', description: 'Clinical references and learning resources', icon: 'book', group: 'HOSPITAL' },
  { id: 'lectures', label: 'Learning', description: 'Lectures, guided teaching and topic learning', icon: 'graduation-cap', group: 'HOSPITAL' },
  { id: 'exams', label: 'Exam Hall', description: 'Question bank and mock examinations', icon: 'clipboard-list', group: 'HOSPITAL' },
  { id: 'viva', label: 'Rounds', description: 'Specialty rounds, viva and tagged reports', icon: 'layers', group: 'HOSPITAL' },
  { id: 'simulation', label: 'Simulation', description: 'Observe, act and debrief', icon: 'heart', group: 'MORE' },
  { id: 'viva-station', label: 'Viva Practice', description: 'Oral examination and structured viva stations', icon: 'osce', group: 'MORE' },
  { id: 'debriefs', label: 'Case Debriefs', description: 'Review clinical reasoning and feedback', icon: 'clipboard', group: 'MORE' },
  { id: 'pearls', label: 'Clinical Pearls', description: 'High-yield clinical recall', icon: 'pearls', group: 'MORE' },
  { id: 'archives', label: 'Case Archive', description: 'Browse previous daily cases', icon: 'fileSearch', group: 'MORE' },
  { id: 'studio', label: 'Content factory', description: 'Generate curriculum content', icon: 'sparkles', group: 'CREATE & REVIEW' },
  { id: 'synthetic', label: 'Synthetic data factory', description: 'Generate and validate synthetic clinical datasets', icon: 'flask', group: 'CREATE & REVIEW' },
  { id: 'operations', label: 'Content operations', description: 'Lineage, sources, engines and pearls', icon: 'database', group: 'CREATE & REVIEW' },
  { id: 'review', label: 'Admin · Question Review', description: 'Review and approve learning materials', icon: 'shield', group: 'CREATE & REVIEW' },
  { id: 'conference', label: 'Case conference', description: 'Complex case discussion', icon: 'clinic', group: 'MORE' },
  { id: 'procedures', label: 'Procedure Theatre', description: 'Prepare and rehearse procedures', icon: 'activity', group: 'MORE' },
  { id: 'handover', label: 'Handover Desk', description: 'Practise safe clinical handover', icon: 'clipboard', group: 'MORE' },
  { id: 'consult', label: 'Consult Room', description: 'Practise clinical consultations', icon: 'stethoscope', group: 'MORE' },
  { id: 'progression', label: 'Clinical progression', description: 'Development pathway', icon: 'target', group: 'MORE' },
  { id: 'summaries', label: 'Topic summaries', description: 'Structured clinical summaries', icon: 'book', group: 'MORE' },
  { id: 'tools', label: 'Data Tools', description: 'Data and utilities', icon: 'database', group: 'TOOLS & SETTINGS' },
  { id: 'profile', label: 'My Profile', description: 'Profile, progress and preferences', icon: 'stethoscope', group: 'TOOLS & SETTINGS' },
];

const primaryNavigation = navigation.filter((item) => ['practice', 'skills', 'oncall', 'library', 'lectures', 'exams', 'viva'].includes(item.id));

const viewDetails: Record<View, { title: string; subtitle: string; skin: 'clinic' | 'rounds' | 'lab' | 'ward' | 'exam' | 'portfolio' }> = {
  home: { title: 'Your learning space', subtitle: 'A clear path from study to clinical practice.', skin: 'portfolio' },
  library: { title: 'Learning library', subtitle: 'Structured clinical topics, questions and practical stations.', skin: 'exam' },
  practice: { title: 'Case practice', subtitle: 'Build a differential, interpret clues and explain your decisions.', skin: 'clinic' },
  simulation: { title: 'Simulation lab', subtitle: 'Practise decisions in a deterministic synthetic patient scenario.', skin: 'clinic' },
  skills: { title: 'Skills & OSCE', subtitle: 'Practise examination, communication and clinical reasoning skills.', skin: 'lab' },
  exams: { title: 'Exams', subtitle: 'Test recall and apply knowledge under assessment conditions.', skin: 'exam' },
  debriefs: { title: 'Debriefs', subtitle: 'Reconstruct decisions, review feedback and identify next steps.', skin: 'clinic' },
  progress: { title: 'My progress', subtitle: 'Understand your attempts, performance and areas to revisit.', skin: 'portfolio' },
  operations: { title: 'Content operations', subtitle: 'Lineage, source rights, engine coverage and the pearls factory.', skin: 'portfolio' },
  synthetic: { title: 'Synthetic data factory', subtitle: 'Local, model-free generation with layered validation and provenance.', skin: 'lab' },
  studio: { title: 'Content factory', subtitle: 'Compose reusable learning resources from versioned content packs.', skin: 'portfolio' },
  review: { title: 'Review queue', subtitle: 'Quality review and controlled distribution of learning content.', skin: 'portfolio' },
  tools: { title: 'Clinical tools', subtitle: 'Local data utilities and evidence workflows.', skin: 'portfolio' },
  viva: { title: 'Specialty Rounds', subtitle: 'Explore clinical learning by specialty service and topic.', skin: 'rounds' },
  'viva-station': { title: 'Viva Practice', subtitle: 'Practise oral examination with structured feedback.', skin: 'lab' },
  pearls: { title: 'Clinical pearls', subtitle: 'Short, high-yield learning points.', skin: 'exam' },
  lectures: { title: 'Teaching room', subtitle: 'Guided clinical explanations and teaching sessions.', skin: 'rounds' },
  archives: { title: 'Daily Case Archive', subtitle: 'Revisit previous daily clinical assignments by date.', skin: 'clinic' },
  conference: { title: 'Case conference', subtitle: 'Explore complex cases and alternative reasoning.', skin: 'rounds' },
  procedures: { title: 'Procedure practice', subtitle: 'Prepare for practical clinical workflows.', skin: 'lab' },
  progression: { title: 'Clinical progression', subtitle: 'Review development milestones and learning pathways.', skin: 'ward' },
  summaries: { title: 'Topic summaries', subtitle: 'Review concise structured clinical topics.', skin: 'exam' },
  oncall: { title: 'On-call room', subtitle: 'Prioritise and manage an acute clinical episode.', skin: 'ward' },
  handover: { title: 'Handover desk', subtitle: 'Practise safe transitions of clinical responsibility.', skin: 'ward' },
  consult: { title: 'Consult room', subtitle: 'Request and respond to consultations.', skin: 'ward' },
  profile: { title: 'Profile & settings', subtitle: 'Manage your learning identity and preferences.', skin: 'portfolio' },
};

export default function App() {
  const [view, setView] = useState<View>('home');
  const [selectedUnitId, setSelectedUnitId] = useState<string | undefined>();
  const [theme, setTheme] = useState<ThemePreference>('system');
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [contentRefreshing, setContentRefreshing] = useState(false);
  const [contentNotice, setContentNotice] = useState('');
  const [contentNoticeError, setContentNoticeError] = useState(false);
  const [logoSpecimen, setLogoSpecimen] = useState(() => window.location.hash === '#logo-specimen');
  const detail = viewDetails[view];
  const skin = useMemo(() => getWorkspaceSkin(detail.skin), [detail.skin]);

  useEffect(() => {
    const onHashChange = () => setLogoSpecimen(window.location.hash === '#logo-specimen');
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const saved = window.localStorage.getItem('hsptl-theme');
    const initial: ThemePreference = saved === 'dark' || saved === 'light' || saved === 'system' ? saved : 'system';
    const apply = (preference: ThemePreference) => {
      const next = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
      setResolvedTheme(next);
      document.documentElement.classList.toggle('dark', next === 'dark');
      document.documentElement.style.colorScheme = next;
    };
    setTheme(initial);
    apply(initial);
    void api.bootstrap().then(setBootstrap).catch(() => setBootstrap(null));
    const onChange = () => { if ((window.localStorage.getItem('hsptl-theme') || 'system') === 'system') apply('system'); };
    media.addEventListener?.('change', onChange);
    return () => media.removeEventListener?.('change', onChange);
  }, []);

  function navigate(next: string, unitId?: string) {
    const valid = navigation.some((item) => item.id === next);
    if (!valid) return;
    setView(next as View);
    setSelectedUnitId(unitId);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function updateContent() {
    setContentRefreshing(true);
    setContentNotice('');
    setContentNoticeError(false);
    try {
      const result = await api.refreshContent();
      let externalNotice = 'External source refresh could not be queued.';
      try {
        const external = await api.refreshExternalSources();
        externalNotice = external.queued
          ? ' External sources were queued in the background; imported records remain in the review queue.'
          : ` External source status: ${external.status}.`;
      } catch {
        // Preserve the local pack refresh result when an external provider queue
        // is temporarily unavailable or the network is offline.
      }
      const total = Object.values(result.workspace_counts || {}).reduce((sum, count) => sum + count, 0);
      const workspaceLabels: Record<string, string> = {
        clinic: 'Clinic', exam_hall: 'Exams', rounds: 'Rounds', lab: 'Skills', ward: 'Ward', simulation: 'Simulation',
      };
      const workspaceNames = Object.keys(result.workspace_counts || {}).map((key) => workspaceLabels[key] || key).join(', ');
      setContentNotice(result.created_count > 0
        ? `${result.created_count} new drafts prepared for ${workspaceNames}. Open All modules → Review Queue to inspect them; drafts are never auto-published.${externalNotice}`
        : `${total} learning drafts across ${workspaceNames} are already current. Open Review Queue to inspect or approve pending drafts.${externalNotice}`);
    } catch (err) {
      setContentNotice(err instanceof Error ? err.message : 'Could not update learning content.');
      setContentNoticeError(true);
    } finally {
      setContentRefreshing(false);
    }
  }

  async function toggleTheme() {
    // Flip the appearance the user is actually looking at. Cycling through
    // 'system' first made the first click appear to do nothing.
    const next: ThemePreference = resolvedTheme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    window.localStorage.setItem('hsptl-theme', next);
    setResolvedTheme(next);
    document.documentElement.classList.toggle('dark', next === 'dark');
    document.documentElement.style.colorScheme = next;
    try { await api.theme(next); } catch { /* Local preference remains authoritative. */ }
  }

  function renderWardWorkflow(currentSection: 'oncall' | 'handover' | 'consult') { return <WorkflowPage workflow={currentSection} />; }

  function renderPage() {
    switch (view) {
      case 'home': return <ClinicPage/>;
      case 'library': return <LearningLibraryPage key={selectedUnitId || 'library'} initialUnitId={selectedUnitId}/>;
      case 'practice': return <ClinicPage/>;
      case 'simulation': return <ClinicalSimulationPage/>;
      case 'skills': return <OSCEPage initialKind="Clinical examination" workspaceMode="osce"/>;
      case 'exams': return <ExamCentrePage/>;
      case 'debriefs': return <CaseDebriefsPage/>;
      case 'progress': return <ProgressPage mode="portfolio"/>;
      case 'studio': return <ContentFactoryPage/>;
      case 'synthetic': return <SyntheticDataPage/>;
      case 'operations': return <ContentOperationsPage/>;
      case 'review': return <AdminReviewPage/>;
      case 'tools': return <DataToolsPage/>;
      case 'viva': return <SpecialtiesPage mode="rounds"/>;
      case 'viva-station': return <OSCEPage initialKind="Viva" workspaceMode="viva"/>;
      case 'pearls': return <PearlsPage mode="pearls"/>;
      case 'lectures': return <AttendingRoomPage/>;
      case 'archives': return <DailyCaseArchivePage/>;
      case 'conference': return <WorkflowPage workflow="conference"/>;
      case 'procedures': return <WorkflowPage workflow="procedure"/>;
      case 'progression': return <WorkflowPage workflow="progression"/>;
      case 'summaries': return <WorkflowPage workflow="summaries"/>;
      case 'oncall': return renderWardWorkflow('oncall');
      case 'handover': return renderWardWorkflow('handover');
      case 'consult': return renderWardWorkflow('consult');
      case 'profile': return <ProfilePage/>;
      default: return <HomeDashboardPage onNavigate={navigate}/>;
    }
  }

  if (logoSpecimen) {
    return <div className={`hx-app hx-theme-${resolvedTheme}`} style={{ gridTemplateColumns: '1fr' }}>
      <Suspense fallback={<RouteLoading/>}>
        <LogoSpecimenPage theme={resolvedTheme} onThemeToggle={() => void toggleTheme()} onBack={() => { window.location.hash = ''; setLogoSpecimen(false); }} />
      </Suspense>
    </div>;
  }

  return <div className={`hx-app hx-theme-${resolvedTheme}`} data-workspace-skin={skin.id} data-skin-canvas={skin.presentation.canvas} data-skin-density={skin.presentation.density}>
    <header className="hx-appbar">
      <button className="hx-brand" onClick={() => navigate('home')} aria-label="HSPTL home" title="HSPTL home">
        <img src="/hsptl-mark.svg" alt=""/><span><b>HSPTL</b><small>CLINICAL LEARNING</small></span>
      </button>
      <nav className="hx-primary-nav" aria-label="Main navigation">
        {primaryNavigation.map((item) => <button key={item.id} className={`hx-nav-link ${view === item.id ? 'is-active' : ''}`} onClick={() => navigate(item.id)} aria-current={view === item.id ? 'page' : undefined} title={item.description}>
          <Icon name={item.icon} size={16}/><span>{item.label}</span>
        </button>)}
      </nav>
      <button className="hx-all-modules" onClick={() => setDirectoryOpen(true)} aria-haspopup="dialog" aria-expanded={directoryOpen}>
        <Icon name="layers" size={16}/><span>All modules</span>
      </button>
    </header>
    <div className="hx-main">
      <header className="hx-topbar">
        <div className="hx-topbar-left"><h1>{detail.title}</h1></div>
        <div className="hx-topbar-right">
          <button className="hx-content-refresh" type="button" onClick={() => void updateContent()} disabled={contentRefreshing} title="Refresh local learning drafts across all workspaces">
            <Icon name="refresh" size={15}/><span>{contentRefreshing ? 'Updating…' : 'Update content'}</span>
          </button>
          <span className="hx-environment"><i className={bootstrap?.data_ready ? 'is-ready' : ''}/>{bootstrap?.data_ready ? 'Dataset connected' : 'Practice mode'}</span>
          <button className="hx-icon-button" onClick={() => void toggleTheme()} aria-label={`Theme: ${theme}. Change theme.`} title={`Theme: ${theme}`}><Icon name={resolvedTheme === 'dark' ? 'sun' : 'moon'} size={18}/></button>
          <button className="hx-archive-button" onClick={() => navigate('archives')} title="Open daily case archive"><Icon name="fileSearch" size={16}/><span>Archive</span></button>
          <button className="hx-profile-button" onClick={() => navigate('profile')} aria-label="Open My Profile and Progress"><Icon name="stethoscope" size={16}/><b>My Profile</b></button>
        </div>
      </header>
      {contentNotice && <div className={`hx-content-notice ${contentNoticeError ? 'is-error' : ''}`} role={contentNoticeError ? 'alert' : 'status'}>{contentNotice}<button type="button" onClick={() => setContentNotice('')} aria-label="Dismiss update message">×</button></div>}
      <main className={`hx-main-content hx-view-${view}`} key={view}>
        <Suspense fallback={<RouteLoading/>}>{renderPage()}</Suspense>
      </main>
      <footer className="hx-footer"><span>HSPTL 6.0.0</span><span>Deterministic · Governed · Human-reviewed</span></footer>
    </div>
    <HospitalDirectory
      open={directoryOpen}
      destinations={navigation}
      currentView={view}
      onSelect={(id) => { setDirectoryOpen(false); navigate(id); }}
      onClose={() => {
        setDirectoryOpen(false);
        document.querySelector<HTMLButtonElement>('.hx-all-modules')?.focus();
      }}
    />
  </div>;
}
