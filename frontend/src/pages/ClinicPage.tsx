import { Icon } from '../components/Icon';
import ClinicalEventCataloguePanel from '../components/ClinicalEventCataloguePanel';
import PatientRecordExplorer from '../components/PatientRecordExplorer';
import DailyCaseLottery from '../components/DailyCaseLottery';

/**
 * Clinic uses the shared Daily Case Lottery as its only daily-case source.
 * Ward Board and Clinic therefore resolve the same persisted draw for the day.
 */
export default function ClinicPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[.16em] text-hsptl-teal">
            <span className="h-2 w-2 rounded-full bg-hsptl-teal" /> Shared daily case
          </div>
          <h1 className="page-title">Clinic</h1>
          <p className="muted mt-1 text-sm">
            Today's case comes directly from the shared Daily Case Lottery. Clinic and Ward
            use the same persisted draw; the clinical event catalogue provides themes, not cases.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-hsptl-border px-3 py-2 text-xs dark:border-hsptl-dark-border">
          <Icon name="shuffle" size={15} /> Daily lottery
        </div>
      </header>

      <DailyCaseLottery workspace="clinic" />

      <ClinicalEventCataloguePanel />

      <div className="flex items-center gap-4 pt-2">
        <div className="h-px flex-1 bg-hsptl-border dark:bg-hsptl-dark-border" />
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">Patient Record Explorer</span>
        <div className="h-px flex-1 bg-hsptl-border dark:bg-hsptl-dark-border" />
      </div>
      <PatientRecordExplorer />
    </div>
  );
}
