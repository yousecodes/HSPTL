import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { GovernanceCredential, QuestionItem } from '../lib/api';

type ReviewItem = {
  item_id: string;
  owner_kind: string;
  owner_id: string;
  reason: string;
  severity: string;
  status: string;
  due_date: string;
  created_at: string;
};

export default function AdminReviewPage() {
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [tab, setTab] = useState<'content' | 'questions' | 'governance'>('content');
  const [reviewStatus, setReviewStatus] = useState<'open' | 'in_review'>('open');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [governance, setGovernance] = useState<Record<string, any> | null>(null);
  const [standards, setStandards] = useState<Record<string, any> | null>(null);
  const [adminToken, setAdminToken] = useState('');
  const [cohortTitle, setCohortTitle] = useState('');
  const [cohorts, setCohorts] = useState<Array<Record<string, any>>>([]);
  const [privacyPolicies, setPrivacyPolicies] = useState<Array<Record<string, any>>>([]);
  const [retentionDays, setRetentionDays] = useState('365');
  const [backups, setBackups] = useState<Array<Record<string, any>>>([]);
  const [accountId, setAccountId] = useState('');
  const [accountName, setAccountName] = useState('');
  const [accountPassword, setAccountPassword] = useState('');
  const [accountRole, setAccountRole] = useState('learner');
  const [accountTrainingLevel, setAccountTrainingLevel] = useState('student');
  const [sessionId, setSessionId] = useState('');
  const [sessionRole, setSessionRole] = useState('');
  const [loginSubject, setLoginSubject] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [safetyCases, setSafetyCases] = useState<Array<Record<string, any>>>([]);
  const [caseId, setCaseId] = useState('');
  const [caseHazard, setCaseHazard] = useState('');
  const [caseRequirement, setCaseRequirement] = useState('');
  const [caseControl, setCaseControl] = useState('');
  const [caseResidual, setCaseResidual] = useState('');
  const [caseOwner, setCaseOwner] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [riskAcceptance, setRiskAcceptance] = useState('');

  const credential: GovernanceCredential = sessionId ? { sessionId } : { token: adminToken };
  const hasCredential = Boolean(sessionId || adminToken);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [q, b] = await Promise.all([api.contentReviewQueue(reviewStatus), api.examQuestions()]);
      setQueue(q);
      setQuestions(b.questions);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load review queues.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [reviewStatus]);

  useEffect(() => {
    if (tab !== 'governance') return;
    void Promise.all([
      api.governanceReadiness(),
      api.standardsManifest(),
      hasCredential ? api.cohorts(credential) : Promise.resolve({ items: [], count: 0 }),
      hasCredential ? api.privacyPolicies(credential) : Promise.resolve({ items: [] }),
      hasCredential ? api.recoveryBackups(credential) : Promise.resolve({ items: [], count: 0 }),
      hasCredential ? api.safetyCases(credential) : Promise.resolve({ items: [] }),
    ])
      .then(([g, s, c, p, b, cases]) => {
        setGovernance(g);
        setStandards(s);
        setCohorts(c.items);
        setPrivacyPolicies(p.items);
        setBackups(b.items);
        setSafetyCases(cases.items);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not load governance.'));
  }, [tab, adminToken, sessionId]);

  async function resolve(id: string, status: 'verified' | 'retired' | 'in_review') {
    try {
      await api.resolveContentReview(id, status);
      setMessage(`Review item marked ${status}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update review item.');
    }
  }

  async function reviewQuestion(q: QuestionItem, reviewed: boolean) {
    try {
      await api.reviewQuestion(q.id, reviewed);
      setMessage(`Question ${reviewed ? 'approved for use' : 'returned to unreviewed status'}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update question review.');
    }
  }

  async function createCohort() {
    if (!hasCredential || !cohortTitle.trim()) return;
    try {
      const cohort = await api.createCohort(credential, {
        title: cohortTitle,
        retention_days: 365,
        privacy_notice: 'Local educational use; no patient identifiers.',
      });
      setCohorts(previous => [cohort, ...previous]);
      setCohortTitle('');
      setMessage(`Created local cohort ${String(cohort.cohort_id)}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create cohort.');
    }
  }

  async function createAccount() {
    if (!hasCredential || !accountId.trim() || !accountName.trim() || accountPassword.length < 12) return;
    try {
      await api.createInstitutionalAccount(credential, {
        subject_id: accountId,
        display_name: accountName,
        password: accountPassword,
        role: accountRole,
        training_level: accountTrainingLevel,
      });
      setAccountId('');
      setAccountName('');
      setAccountPassword('');
      setMessage('Institutional learner or facilitator account created.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create account.');
    }
  }

  async function savePrivacyPolicy() {
    if (!hasCredential) return;
    try {
      const policy = await api.createPrivacyPolicy(credential, {
        data_scope: 'local_hsptl_learning_records',
        retention_days: Number(retentionDays),
        consent_status: 'acknowledged',
        encryption_at_rest: 'deployment_managed',
      });
      setPrivacyPolicies(previous => [policy, ...previous.filter(item => item.policy_id !== policy.policy_id)]);
      setMessage('Privacy and retention policy saved.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save privacy policy.');
    }
  }

  async function createBackup() {
    if (!hasCredential) return;
    try {
      const backup = await api.createBackup(credential);
      setBackups(previous => [backup, ...previous]);
      setMessage('Verified SQLite backup created.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create backup.');
    }
  }

  async function signIn() {
    if (!loginSubject.trim() || loginPassword.length < 12) return;
    try {
      const session = await api.institutionalLogin(loginSubject, loginPassword);
      setSessionId(String(session.session_id));
      setSessionRole(String(session.role));
      setAdminToken('');
      setLoginPassword('');
      setMessage(`Signed in as ${String(session.display_name)} (${String(session.role)}).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not sign in.');
    }
  }

  async function signOut() {
    setSessionId('');
    setSessionRole('');
    setCohorts([]);
    setPrivacyPolicies([]);
    setBackups([]);
    setSafetyCases([]);
    setMessage('Signed out of the local institutional session.');
  }

  async function purgeRetention() {
    if (!hasCredential) return;
    try {
      const result = await api.purgeRetention(credential);
      setMessage(`Retention purge removed ${String(result.removed_records)} record(s).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not run the retention purge.');
    }
  }

  async function createSafetyCase() {
    if (!hasCredential || !caseId.trim() || !caseHazard.trim() || !caseRequirement.trim()
        || !caseControl.trim() || !caseResidual.trim() || !caseOwner.trim()) return;
    try {
      const created = await api.createSafetyCase(credential, {
        scenario_id: caseId, scenario_version: '1.0.0', hazard: caseHazard,
        safety_requirement: caseRequirement, control: caseControl,
        residual_risk: caseResidual, clinical_owner: caseOwner,
      });
      setSafetyCases(previous => [created, ...previous]);
      setCaseHazard(''); setCaseRequirement(''); setCaseControl('');
      setCaseResidual(''); setCaseOwner('');
      setMessage(`Recorded safety case ${String(created.case_id)} (pending external clinical review).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not record the safety case.');
    }
  }

  async function decideSafetyCase(target: string, decision: string) {
    if (!hasCredential || !reviewerId.trim()) return;
    try {
      const review = await api.reviewSafetyCase(credential, target, {
        reviewer_id: reviewerId, decision,
        residual_risk_acceptance: decision === 'approved_with_residual_risk' ? riskAcceptance : '',
      });
      setSafetyCases(previous => previous.map(item => item.case_id === target
        ? { ...item, approval_status: review.decision } : item));
      setMessage(`Safety case decision recorded: ${String(review.decision)}. External clinical approval is still required.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not record the safety-case decision.');
    }
  }

  return <div className="space-y-5">
    <header>
      <div className="eyebrow">PORTFOLIO · CONTENT GOVERNANCE</div>
      <h2 className="page-title mt-2">Admin, Governance and Review</h2>
      <p className="muted mt-2 max-w-3xl text-sm">Review source and quality flags separately from question approval. Institutional controls are local governance primitives: role-based sessions and institution-scoped records inside one local database. They are not SSO/MFA, enterprise encryption or a production multi-tenant service.</p>
    </header>
    {error && <div role="alert" className="status-error">{error}</div>}
    {message && <div role="status" className="status-success">{message}</div>}
    <div className="flex flex-wrap gap-2">
      <button className={tab === 'content' ? 'primary-button' : 'secondary-button'} onClick={() => setTab('content')}>Content review ({queue.length})</button>
      <button className={tab === 'questions' ? 'primary-button' : 'secondary-button'} onClick={() => setTab('questions')}>Question bank ({questions.length})</button>
      <button className={tab === 'governance' ? 'primary-button' : 'secondary-button'} onClick={() => setTab('governance')}>Institutional governance</button>
      <button className="secondary-button ml-auto" onClick={() => void load()}>Refresh</button>
    </div>

    {tab === 'governance' ? <section className="grid gap-4 lg:grid-cols-2">
      <div className="hsptl-card p-5">
        <h3 className="font-bold">Production readiness</h3>
        {governance ? <dl className="mt-3 space-y-2 text-sm">
          {Object.entries(governance).filter(([key]) => key !== 'limitations').map(([key, value]) => <div key={key} className="flex justify-between gap-3 border-b border-[var(--line)] py-2"><dt className="muted">{key.replaceAll('_', ' ')}</dt><dd className="text-right font-semibold">{typeof value === 'boolean' ? (value ? 'Configured' : 'Not configured') : String(value)}</dd></div>)}
        </dl> : <p className="muted mt-2 text-sm">Loading governance status…</p>}
        {Array.isArray(governance?.limitations) && <ul className="muted mt-3 list-disc space-y-1 pl-5 text-xs">{governance.limitations.map((item: string) => <li key={item}>{item}</li>)}</ul>}
      </div>
      <div className="hsptl-card p-5">
        <h3 className="font-bold">Standards adapters</h3>
        {standards ? <dl className="mt-3 space-y-2 text-sm">{Object.entries(standards).map(([key, value]) => <div key={key} className="border-b border-[var(--line)] py-2"><dt className="muted">{key}</dt><dd className="mt-1 break-words font-semibold">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl> : <p className="muted mt-2 text-sm">Loading standards manifest…</p>}
      </div>
      <div className="hsptl-card p-5 lg:col-span-2">
        <h3 className="font-bold">Institutional access</h3>
        <p className="muted mt-1 text-xs">Sign in with a password-backed account, or supply the local deployment admin token. Sessions are preferred and expire after eight hours.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-semibold">Subject ID<input className="form-field mt-1 w-full" value={loginSubject} onChange={(e) => setLoginSubject(e.target.value)} autoComplete="username" /></label>
          <label className="text-xs font-semibold">Password<input type="password" className="form-field mt-1 w-full" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} autoComplete="current-password" /></label>
          <label className="text-xs font-semibold">Or deployment admin token<input type="password" className="form-field mt-1 w-full" value={adminToken} onChange={(e) => { setAdminToken(e.target.value); setSessionId(''); }} placeholder="HSPTL_ADMIN_TOKEN" /></label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button className="primary-button" disabled={!loginSubject.trim() || loginPassword.length < 12} onClick={() => void signIn()}>Sign in</button>
          {sessionId && <button className="secondary-button" onClick={() => void signOut()}>Sign out</button>}
          <span className="muted text-xs">{sessionId ? `Active session · role ${sessionRole || 'unknown'}` : adminToken ? 'Deployment token credential' : 'No credential supplied'}</span>
        </div>
      </div>
      <div className="hsptl-card p-5 lg:col-span-2">
        <h3 className="font-bold">Local cohort governance</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-semibold">Cohort title<input className="form-field mt-1 w-full" value={cohortTitle} onChange={(e) => setCohortTitle(e.target.value)} placeholder="Acute care teaching cohort" /></label>
          <label className="text-xs font-semibold">Retention (days)<input type="number" min="1" max="3650" className="form-field mt-1 w-full" value={retentionDays} onChange={(e) => setRetentionDays(e.target.value)} /></label>
        </div>
        <button className="primary-button mt-3" disabled={!hasCredential || !cohortTitle.trim()} onClick={() => void createCohort()}>Create cohort</button>
        <div className="mt-4 space-y-2">{cohorts.map(cohort => <div key={String(cohort.cohort_id)} className="rounded-lg border border-[var(--line)] p-3"><b className="text-sm">{String(cohort.title)}</b><p className="muted mt-1 text-xs">{String(cohort.cohort_id)} · {String(cohort.specialty)} · retention {String(cohort.retention_days)} days</p></div>)}</div>
      </div>
      <div className="hsptl-card p-5">
        <h3 className="font-bold">Password-backed institutional accounts</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-semibold">Subject ID<input className="form-field mt-1 w-full" value={accountId} onChange={(e) => setAccountId(e.target.value)} /></label>
          <label className="text-xs font-semibold">Display name<input className="form-field mt-1 w-full" value={accountName} onChange={(e) => setAccountName(e.target.value)} /></label>
          <label className="text-xs font-semibold">Initial password<input type="password" autoComplete="new-password" className="form-field mt-1 w-full" value={accountPassword} onChange={(e) => setAccountPassword(e.target.value)} /></label>
          <label className="text-xs font-semibold">Role<select className="form-field mt-1 w-full" value={accountRole} onChange={(e) => setAccountRole(e.target.value)}><option value="learner">Learner</option><option value="facilitator">Facilitator</option><option value="reviewer">Reviewer</option></select></label>
          <label className="text-xs font-semibold">Institution-assigned training level<select className="form-field mt-1 w-full" value={accountTrainingLevel} onChange={(e) => setAccountTrainingLevel(e.target.value)}>{[['student','Medical student'],['intern','Intern'],['resident','Resident'],['registrar','Registrar'],['fellow','Fellow'],['specialist','Specialist'],['consultant','Consultant'],['faculty','Faculty / educator'],['unspecified','Unspecified']].map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>
        <button className="primary-button mt-3" disabled={!hasCredential || !accountId || !accountName || accountPassword.length < 12} onClick={() => void createAccount()}>Create account</button>
        <p className="muted mt-3 text-xs">Passwords use PBKDF2-SHA256 and are never stored in plaintext. This is a local account boundary, not SSO or MFA.</p>
      </div>
      <div className="hsptl-card p-5">
        <h3 className="font-bold">Privacy, retention and recovery</h3>
        <label className="mt-3 block text-xs font-semibold">Retention period (days)<input type="number" min="1" max="3650" className="form-field mt-1 w-full" value={retentionDays} onChange={(e) => setRetentionDays(e.target.value)} /></label>
        <div className="mt-3 flex flex-wrap gap-2"><button className="secondary-button" disabled={!hasCredential} onClick={() => void savePrivacyPolicy()}>Save privacy policy</button><button className="secondary-button" disabled={!hasCredential} onClick={() => void purgeRetention()}>Run retention purge</button><button className="primary-button" disabled={!hasCredential} onClick={() => void createBackup()}>Create verified backup</button></div>
        <div className="mt-4 space-y-2">{privacyPolicies.map(policy => <div key={String(policy.policy_id)} className="rounded-lg border border-[var(--line)] p-3 text-xs"><b>{String(policy.data_scope)}</b><p className="muted mt-1">Retention: {String(policy.retention_days)} days · Consent: {String(policy.consent_status)}</p></div>)}</div>
        <div className="mt-4 space-y-2">{backups.map((backup, index) => <div key={String(backup.sha256 || backup.backup || index)} className="rounded-lg bg-[var(--workspace-tint)] p-3 text-xs"><b>SQLite backup</b><p className="muted mt-1 break-all">{String(backup.backup)}</p>{backup.sha256 && <p className="muted mt-1 break-all">SHA-256: {String(backup.sha256)}</p>}</div>)}</div>
      </div>
      <div className="hsptl-card p-5 lg:col-span-2">
        <h3 className="font-bold">Clinical safety cases</h3>
        <p className="muted mt-1 text-xs">Record a hazard, its safety requirement and control, then capture a named reviewer decision. A local decision never substitutes for institutional clinical approval.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-semibold">Scenario ID<input className="form-field mt-1 w-full" value={caseId} onChange={(e) => setCaseId(e.target.value)} placeholder="asthma_moderate_adult_v1" /></label>
          <label className="text-xs font-semibold">Clinical owner<input className="form-field mt-1 w-full" value={caseOwner} onChange={(e) => setCaseOwner(e.target.value)} /></label>
          <label className="text-xs font-semibold">Hazard<input className="form-field mt-1 w-full" value={caseHazard} onChange={(e) => setCaseHazard(e.target.value)} /></label>
          <label className="text-xs font-semibold">Safety requirement<input className="form-field mt-1 w-full" value={caseRequirement} onChange={(e) => setCaseRequirement(e.target.value)} /></label>
          <label className="text-xs font-semibold">Control<input className="form-field mt-1 w-full" value={caseControl} onChange={(e) => setCaseControl(e.target.value)} /></label>
          <label className="text-xs font-semibold">Residual risk<input className="form-field mt-1 w-full" value={caseResidual} onChange={(e) => setCaseResidual(e.target.value)} /></label>
          <label className="text-xs font-semibold">Reviewer ID<input className="form-field mt-1 w-full" value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} /></label>
          <label className="text-xs font-semibold">Residual-risk acceptance<input className="form-field mt-1 w-full" value={riskAcceptance} onChange={(e) => setRiskAcceptance(e.target.value)} placeholder="Required to approve" /></label>
        </div>
        <button className="primary-button mt-3" disabled={!hasCredential || !caseId.trim() || !caseHazard.trim() || !caseRequirement.trim() || !caseControl.trim() || !caseResidual.trim() || !caseOwner.trim()} onClick={() => void createSafetyCase()}>Record safety case</button>
        <div className="mt-4 space-y-2">{safetyCases.map(item => <div key={String(item.case_id)} className="rounded-lg border border-[var(--line)] p-3 text-xs">
          <b>{String(item.scenario_id)} · {String(item.scenario_version)}</b>
          <p className="muted mt-1">{String(item.hazard)}</p>
          <p className="muted mt-1">Approval status: {String(item.approval_status)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="secondary-button" disabled={!hasCredential || !reviewerId.trim()} onClick={() => void decideSafetyCase(String(item.case_id), 'changes_requested')}>Request changes</button>
            <button className="secondary-button" disabled={!hasCredential || !reviewerId.trim()} onClick={() => void decideSafetyCase(String(item.case_id), 'rejected')}>Reject</button>
            <button className="primary-button" disabled={!hasCredential || !reviewerId.trim() || !riskAcceptance.trim()} onClick={() => void decideSafetyCase(String(item.case_id), 'approved_with_residual_risk')}>Approve with residual risk</button>
          </div>
        </div>)}</div>
      </div>
    </section> : loading ? <div className="hsptl-card p-8 text-center muted">Loading review queues…</div> : tab === 'content' ? <section className="space-y-3">
      <div className="flex gap-2">
        <button className={reviewStatus === 'open' ? 'primary-button' : 'secondary-button'} onClick={() => setReviewStatus('open')}>Open</button>
        <button className={reviewStatus === 'in_review' ? 'primary-button' : 'secondary-button'} onClick={() => setReviewStatus('in_review')}>In review</button>
      </div>
      {queue.length ? queue.map(item => <article key={item.item_id} className="hsptl-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-900">{item.severity}</span><h3 className="mt-2 font-bold">{item.reason.replaceAll('_', ' ')}</h3><p className="muted mt-1 break-all text-xs">{item.owner_kind} · {item.owner_id}</p></div>
          <div className="flex flex-wrap gap-2"><button className="secondary-button" onClick={() => void resolve(item.item_id, 'in_review')}>In review</button><button className="primary-button" onClick={() => void resolve(item.item_id, 'verified')}>Verify</button><button className="secondary-button" onClick={() => void resolve(item.item_id, 'retired')}>Retire</button></div>
        </div>
      </article>) : <div className="hsptl-card p-8 text-center"><h3 className="font-bold">No open content review items</h3><p className="muted mt-1 text-sm">The current review queue is empty.</p></div>}
    </section> : <section className="space-y-3">
      {questions.length ? questions.map(q => <article key={q.id} className="hsptl-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1"><div className="muted text-xs">{q.kind} · {q.specialty} · {q.difficulty} · {q.source_title || 'Source unspecified'}</div><h3 className="mt-2 font-semibold text-sm leading-relaxed">{q.question}</h3><div className="mt-2 rounded-lg bg-[var(--workspace-tint)] p-3 text-xs"><b>Key:</b> {q.answer || 'Not supplied'}<p className="mt-1"><b>Explanation:</b> {q.explanation || 'Not supplied'}</p></div></div>
          <button className={q.reviewed ? 'secondary-button' : 'primary-button'} onClick={() => void reviewQuestion(q, !q.reviewed)}>{q.reviewed ? 'Return to review' : 'Approve question'}</button>
        </div>
        <p className="muted mt-3 text-xs">Question approval is not proof of clinical correctness.</p>
      </article>) : <div className="hsptl-card p-8 text-center muted">No questions are currently in the bank.</div>}
    </section>}
  </div>;
}
