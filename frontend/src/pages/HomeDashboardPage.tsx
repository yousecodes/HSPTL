import { useEffect, useState } from 'react';
import { api, type LotteryDaily, type ProgressSummary } from '../lib/api';
import { Icon } from '../components/Icon';

type Props = { onNavigate: (view: string, unitId?: string) => void };

/**
 * Focus home: one shared daily challenge first, then a small set of clear
 * routes into the rest of HSPTL. The answer is never requested here; it stays
 * behind the existing server-side attempt/reveal flow in Clinic.
 */
export default function HomeDashboardPage({ onNavigate }: Props) {
  const [daily, setDaily] = useState<LotteryDaily | null>(null);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [dailyError, setDailyError] = useState('');

  useEffect(() => {
    let active = true;
    api.lotteryDaily('clinic')
      .then((result) => { if (active) setDaily(result); })
      .catch((err: unknown) => {
        if (active) setDailyError(err instanceof Error ? err.message : 'Today’s challenge is unavailable.');
      });
    api.progress()
      .then((result) => { if (active) setProgress(result); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const challenge = daily?.case;
  const totalAttempts = progress?.lifetime?.attempts ?? 0;

  return <div className="hx-focus-home">
    <section className="hx-focus-intro">
      <div className="hx-focus-intro-copy">
        <span className="hx-focus-eyebrow">HSPTL · Dx, Ix, Tx</span>
        <h2>One case. A new perspective.</h2>
        <p>Start with today’s shared challenge. Explore the rest when you’re ready.</p>
      </div>
      <img className="hx-focus-brand-mark" src="/brand/hsptl-case-mosaic-mark.svg" alt="" aria-hidden="true" />
    </section>

    <section className="hx-focus-daily" aria-labelledby="hx-focus-daily-title">
      <div className="hx-focus-daily-topline">
        <span className="hx-focus-eyebrow">TODAY’S DAILY CASE</span>
        {daily?.draw_date && <span className="hx-focus-date">{daily.draw_date}</span>}
      </div>
      {dailyError ? <div className="hx-focus-empty" role="alert">
        <h3 id="hx-focus-daily-title">Today’s case is unavailable</h3>
        <p>{dailyError}</p>
        <button type="button" className="hx-focus-secondary" onClick={() => onNavigate('practice')}>Open Clinic <Icon name="arrow" size={17}/></button>
      </div> : !daily ? <div className="hx-focus-empty" role="status" aria-live="polite">
        <h3 id="hx-focus-daily-title">Your case is being drawn</h3>
        <p>The shared daily challenge is loading.</p>
      </div> : challenge ? <div className="hx-focus-daily-content">
        <div className="hx-focus-case-copy">
          {daily.clinical_event && <span className="hx-focus-event">{daily.clinical_event.icon} {daily.clinical_event.title}</span>}
          <h3 id="hx-focus-daily-title">{challenge.presenting_complaint || challenge.title}</h3>
          <p className="hx-focus-case-subtitle">{challenge.specialty || 'Clinical reasoning'} <span>·</span> {challenge.difficulty || 'Mixed difficulty'}</p>
          <p className="hx-focus-case-prompt">A new clinical challenge is ready. Work through the case before revealing the explanation.</p>
          <button type="button" className="hx-focus-primary" onClick={() => onNavigate('practice')}>Solve today’s case <Icon name="arrow" size={18}/></button>
        </div>
        <div className="hx-focus-daily-art" aria-hidden="true">
          <img src="/brand/hsptl-case-mosaic-mark.svg" alt="" />
          <span>DAILY<br/>LOTTERY</span>
        </div>
      </div> : <div className="hx-focus-empty" role="status">
        <h3 id="hx-focus-daily-title">No eligible case is available yet</h3>
        <p>{daily.message || 'Explore another workspace while HSPTL prepares more challenges.'}</p>
        <button type="button" className="hx-focus-secondary" onClick={() => onNavigate('practice')}>Explore Clinic <Icon name="arrow" size={17}/></button>
      </div>}
      <div className="hx-focus-trust-note">Educational challenge · Source and validation status are shown with the case.</div>
    </section>

    <section className="hx-focus-explore" aria-labelledby="hx-focus-explore-title">
      <div className="hx-focus-section-heading">
        <div>
          <span className="hx-focus-eyebrow">EXPLORE</span>
          <h2 id="hx-focus-explore-title">Choose another space</h2>
        </div>
        <button type="button" className="hx-focus-link" onClick={() => onNavigate('profile')}>My profile <Icon name="arrow" size={15}/></button>
      </div>
      <div className="hx-focus-shortcuts">
        <button type="button" onClick={() => onNavigate('practice')}>
          <span className="hx-focus-shortcut-icon"><Icon name="clinic" size={25}/></span>
          <span><b>Clinic</b><small>Reason through cases</small></span>
          <Icon name="arrow" size={17}/>
        </button>
        <button type="button" onClick={() => onNavigate('skills')}>
          <span className="hx-focus-shortcut-icon"><Icon name="microscope" size={25}/></span>
          <span><b>Lab</b><small>Interpret findings</small></span>
          <Icon name="arrow" size={17}/>
        </button>
        <button type="button" onClick={() => onNavigate('oncall')}>
          <span className="hx-focus-shortcut-icon"><Icon name="stethoscope" size={25}/></span>
          <span><b>Ward</b><small>Manage patient journeys</small></span>
          <Icon name="arrow" size={17}/>
        </button>
        <button type="button" onClick={() => onNavigate('library')}>
          <span className="hx-focus-shortcut-icon"><Icon name="book" size={25}/></span>
          <span><b>Library</b><small>Explore knowledge</small></span>
          <Icon name="arrow" size={17}/>
        </button>
        <button type="button" onClick={() => onNavigate('exams')}>
          <span className="hx-focus-shortcut-icon"><Icon name="clipboard-list" size={25}/></span>
          <span><b>Exam Hall</b><small>Test your reasoning</small></span>
          <Icon name="arrow" size={17}/>
        </button>
        <button type="button" onClick={() => onNavigate('lectures')}>
          <span className="hx-focus-shortcut-icon"><Icon name="graduation-cap" size={25}/></span>
          <span><b>Learning</b><small>Build understanding</small></span>
          <Icon name="arrow" size={17}/>
        </button>
        <button type="button" onClick={() => onNavigate('viva')}>
          <span className="hx-focus-shortcut-icon"><Icon name="layers" size={25}/></span>
          <span><b>Rounds</b><small>Discuss and reflect</small></span>
          <Icon name="arrow" size={17}/>
        </button>
      </div>
    </section>

    <footer className="hx-focus-footer">
      <span><Icon name="target" size={16}/> {totalAttempts.toLocaleString()} learning attempts recorded</span>
      <button type="button" onClick={() => onNavigate('archives')}>Past daily cases <Icon name="arrow" size={14}/></button>
    </footer>
  </div>;
}
