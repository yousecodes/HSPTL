import { useEffect, useState } from 'react';
import { api, type ContentFactoryCatalog, type ProgressSummary, type LearningUnitProgress } from '../lib/api';
import { Icon } from '../components/Icon';

type Props = { onNavigate: (view: string, unitId?: string) => void };

export default function HomeDashboardPage({ onNavigate }: Props) {
  const [catalog, setCatalog] = useState<ContentFactoryCatalog | null>(null);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [unitProgress, setUnitProgress] = useState<LearningUnitProgress | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([api.contentFactoryCatalog(), api.progress(), api.learningUnitProgress()])
      .then(([library, summary, learning]) => {
        if (!active) return;
        setCatalog(library); setProgress(summary); setUnitProgress(learning);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Dashboard data is unavailable.'));
    return () => { active = false; };
  }, []);

  const starterUnit = catalog?.units[0];
  const attempted = unitProgress?.units.filter((unit) => unit.attempt_count > 0).length ?? 0;
  const topics = catalog?.units ?? [];

  return <div className="hx-home hx-home-compact">
    <section className="hx-welcome hx-welcome-slim">
      <div className="hx-welcome-copy">
        <div className="hx-eyebrow hx-eyebrow-light">LOCAL CLINICAL LEARNING</div>
        <h2 className="hx-welcome-heading">Learn. Practise. Improve.</h2>
        <p>{catalog ? `${catalog.unit_count} starter topics · ${catalog.question_count} questions · no API key required` : 'Your clinical practice workspace.'}</p>
        <div className="hx-welcome-actions">
          <button className="hx-button-light" onClick={() => onNavigate('library', starterUnit?.unit_id)}>Start learning <Icon name="arrow" size={15}/></button>
          <button className="hx-button-ghost" onClick={() => onNavigate('simulation')}>Run a simulation</button>
        </div>
      </div>
      <div className="hx-welcome-mark" aria-hidden="true"><img src="/hsptl-mark.svg" alt=""/></div>
    </section>

    {error && <div role="alert" className="status-error">{error}</div>}

    <section className="hx-home-metrics" aria-label="Learning overview">
      <div><span>Topics</span><b>{catalog?.unit_count ?? '—'}</b></div>
      <div><span>Questions</span><b>{catalog?.question_count ?? '—'}</b></div>
      <div><span>Topics practised</span><b>{unitProgress ? `${attempted}/${unitProgress.units.length}` : '—'}</b></div>
      <div><span>Saved attempts</span><b>{unitProgress?.total_attempts ?? progress?.lifetime?.attempts ?? 0}</b></div>
    </section>

    <section className="hx-home-section">
      <div className="hx-section-heading"><div><span className="hx-eyebrow">START PRACTISING</span><h2>Choose an activity</h2></div></div>
      <div className="hx-activity-grid hx-activity-grid-compact">
        <button className="hx-activity-card" onClick={() => onNavigate('library', starterUnit?.unit_id)}>
          <div className="hx-activity-visual hx-visual-blue"><Icon name="book" size={27}/></div>
          <div className="hx-activity-content"><span>STARTER CURRICULUM</span><h3>{starterUnit?.title || 'Learning library'}</h3><p>Cases, MCQs, viva and OSCE practice.</p><b>Open library <Icon name="arrow" size={14}/></b></div>
        </button>
        <button className="hx-activity-card" onClick={() => onNavigate('practice')}>
          <div className="hx-activity-visual hx-visual-amber"><Icon name="clinic" size={27}/></div>
          <div className="hx-activity-content"><span>CASE REASONING</span><h3>Daily clinical case</h3><p>Build a differential and explain your plan.</p><b>Open Clinic <Icon name="arrow" size={14}/></b></div>
        </button>
        <button className="hx-activity-card" onClick={() => onNavigate('simulation')}>
          <div className="hx-activity-visual hx-visual-teal"><Icon name="activity" size={27}/></div>
          <div className="hx-activity-content"><span>SIMULATION</span><h3>Acute breathlessness</h3><p>Make decisions and review the debrief.</p><b>Start simulation <Icon name="arrow" size={14}/></b></div>
        </button>
        <button className="hx-activity-card" onClick={() => onNavigate('skills')}>
          <div className="hx-activity-visual hx-visual-purple"><Icon name="osce" size={27}/></div>
          <div className="hx-activity-content"><span>SKILLS</span><h3>OSCE and viva</h3><p>Rehearse practical stations.</p><b>Practise skills <Icon name="arrow" size={14}/></b></div>
        </button>
      </div>
    </section>

    <section className="hx-getting-started">
      <div className="hx-section-heading"><div><span className="hx-eyebrow">QUICK GUIDE</span><h2>How to use HSPTL</h2></div><button className="hx-text-action" onClick={() => onNavigate('studio')}>Open content factory <Icon name="arrow" size={14}/></button></div>
      <div className="hx-guide-steps">
        <article><span>01</span><div><h3>Practise existing content</h3><p>Open Library → choose a topic → read the case → answer the quiz. Your score is saved locally.</p><button onClick={() => onNavigate('library', starterUnit?.unit_id)}>Open starter topics</button></div></article>
        <article><span>02</span><div><h3>Content prepares automatically</h3><p>HSPTL prepares local learning drafts when it starts. Use <b>Update content</b> in any workspace to check installed packs for updates.</p><button onClick={() => onNavigate('studio')}>Advanced content tools</button></div></article>
        <article><span>03</span><div><h3>Review before publishing</h3><p>New generated material stays in drafts until a qualified reviewer approves it. Existing approved content is never overwritten.</p><button onClick={() => onNavigate('review')}>Open review queue</button></div></article>
      </div>
    </section>

    <section className="hx-home-topics">
      <div className="hx-section-heading"><div><span className="hx-eyebrow">STARTER PACK</span><h2>Available topics</h2></div><button className="hx-text-action" onClick={() => onNavigate('library')}>All topics <Icon name="arrow" size={14}/></button></div>
      {topics.length ? <div className="hx-topic-chips">{topics.slice(0, 8).map((topic) => <button key={topic.unit_id} onClick={() => onNavigate('library', topic.unit_id)}>{topic.title}<Icon name="arrow" size={13}/></button>)}</div> : <div className="s-empty"><strong>Starter content is unavailable</strong><span>Check that the bundled content pack is installed and the backend is running.</span></div>}
    </section>
    <details className="hx-pack-help">
      <summary>How do I add my own learning topics?</summary>
      <div><p>Copy the bundled pack in <code>backend/content_packs</code> to a new versioned file such as <code>cardiology_v1.json</code>. Give it a unique <code>pack_id</code> and unique <code>unit_id</code> values.</p>
      <p>Use <code>content_pack.schema.json</code> as the structure guide. Each topic needs a synthetic case, objectives, teaching points, pitfalls, at least 3 MCQs with rationales, 2 viva prompts, an OSCE checklist, debrief prompts and source references.</p>
      <p>From the project root run <code>python scripts/validate_content_packs.py</code>. Restart HSPTL; the versioned pack is loaded into Library and Create automatically. Use material you authored or have permission to adapt, and keep the source references accurate.</p></div>
    </details>
  </div>;
}
