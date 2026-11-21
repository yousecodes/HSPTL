import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './Icon';
import type { IconName } from './Icon';
import { HsptlMark } from './HsptlMark';

export type DirectoryDestination = {
  id: string;
  label: string;
  description: string;
  icon: IconName;
  group: string;
};

type Props = {
  open: boolean;
  destinations: DirectoryDestination[];
  currentView: string;
  onSelect: (id: string) => void;
  onClose: () => void;
};

/**
 * Visual Hospital Directory.
 *
 * Opened from the shared All modules control. It lists the application's real
 * destination registry - no invented departments, floors or specialties.
 *
 * Floor/area grouping is intentionally absent: the repository has no reliable
 * floor or specialty metadata for destinations, so inventing one would be
 * fabricating hospital structure. Grouping therefore uses the navigation
 * registry's own `group` field. If a real floor/specialty registry is added
 * later, add it as a new `DirectoryView` and filter on that metadata; do not
 * derive floors from group names.
 *
 * Accessibility: modal dialog semantics, Escape to close, focus trap, focus
 * return to the trigger (handled by the caller), and arrow/Home/End keyboard
 * navigation within the destination list.
 */

const VIEWS = [
  { id: 'essentials', label: 'Essentials' },
  { id: 'all', label: 'All modules' },
] as const;

const ESSENTIAL_IDS = new Set(['home', 'library', 'practice', 'simulation', 'skills', 'exams', 'progress']);

type DirectoryView = (typeof VIEWS)[number]['id'];

export function HospitalDirectory({ open, destinations, currentView, onSelect, onClose }: Props) {
  const [query, setQuery] = useState('');
  const [view, setView] = useState<DirectoryView>('essentials');
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const list = Array.from(focusables).filter((node) => !node.hasAttribute('disabled'));
      const first = list[0];
      const last = list[list.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return destinations;
    return destinations.filter(
      (item) =>
        item.label.toLowerCase().includes(needle) ||
        item.description.toLowerCase().includes(needle) ||
        item.group.toLowerCase().includes(needle),
    );
  }, [destinations, query]);

  const visibleDestinations = useMemo(
    () => view === 'essentials' ? filtered.filter((item) => ESSENTIAL_IDS.has(item.id)) : filtered,
    [filtered, view],
  );

  const grouped = useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, DirectoryDestination[]>();
    for (const item of visibleDestinations) {
      if (!map.has(item.group)) {
        map.set(item.group, []);
        order.push(item.group);
      }
      map.get(item.group)!.push(item);
    }
    return order.map((group) => ({ group, items: map.get(group)! }));
  }, [visibleDestinations]);

  function onListKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    const nodes = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>('[data-destination]') ?? [],
    );
    if (nodes.length === 0) return;
    const active = document.activeElement as HTMLElement | null;
    const index = nodes.findIndex((node) => node === active);
    event.preventDefault();
    if (event.key === 'Home') nodes[0].focus();
    else if (event.key === 'End') nodes[nodes.length - 1].focus();
    else if (event.key === 'ArrowDown') nodes[index < 0 ? 0 : (index + 1) % nodes.length].focus();
    else nodes[index <= 0 ? nodes.length - 1 : index - 1].focus();
  }

  if (!open) return null;

  const renderCard = (item: DirectoryDestination) => (
    <button
      key={item.id}
      type="button"
      data-destination
      className={`dir-card ${item.id === currentView ? 'is-current' : ''}`}
      onClick={() => onSelect(item.id)}
      aria-current={item.id === currentView ? 'page' : undefined}
    >
      <span className="dir-card-icon" aria-hidden="true">
        <Icon name={item.icon} size={20} />
      </span>
      <span className="dir-card-text">
        <b>{item.label}</b>
        <small>{item.description}</small>
      </span>
      {item.id === currentView ? (
        <span className="dir-card-flag">Current</span>
      ) : (
        <Icon name="arrow" size={16} className="dir-card-go" />
      )}
    </button>
  );

  return (
    <div className="dir-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div
        className="dir-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dir-title"
        ref={dialogRef}
      >
        <header className="dir-head">
          <div className="dir-head-brand">
            <HsptlMark size={36} title={null} />
            <div>
              <h2 id="dir-title">All modules</h2>
              <p>Search and open a workspace.</p>
            </div>
          </div>
          <button type="button" className="dir-close" onClick={onClose} aria-label="Close hospital directory">
            <Icon name="close" size={18} />
          </button>
        </header>

        <div className="dir-controls">
          <label className="dir-search">
            <Icon name="search" size={17} />
            <input
              ref={searchRef}
              autoFocus
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search modules"
              aria-label="Search HSPTL modules"
            />
          </label>
          <div className="dir-views" role="group" aria-label="Directory view">
            {VIEWS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={view === option.id ? 'is-active' : ''}
                aria-pressed={view === option.id}
                onClick={() => setView(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="dir-body" ref={listRef} onKeyDown={onListKeyDown}>
          {visibleDestinations.length === 0 && (
            <div className="s-empty" role="status">
              <strong>No modules match “{query}”</strong>
              <span>Try Library, Clinic, Simulation or Skills.</span>
            </div>
          )}

          {view === 'essentials'
            ? <div className="dir-grid dir-grid-all">{visibleDestinations.map(renderCard)}</div>
            : grouped.map((section) => (
                <section key={section.group} className="dir-section">
                  <h3>{section.group}</h3>
                  <div className="dir-grid">{section.items.map(renderCard)}</div>
                </section>
              ))}
        </div>

        <footer className="dir-foot">
          <span>{view === 'essentials' ? `${visibleDestinations.length} essential destinations` : `${filtered.length} of ${destinations.length} modules`}</span>
          <span>
            <kbd>Esc</kbd> to close · <kbd>↑</kbd><kbd>↓</kbd> to move
          </span>
        </footer>
      </div>
    </div>
  );
}
