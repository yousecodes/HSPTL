import { HsptlMark, HsptlLockup } from '../components/HsptlMark';

type Props = {
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
  onBack: () => void;
};

/**
 * Logo specimen page. Reachable at `#logo-specimen`; it is a development
 * surface, not a learner destination, so it is deliberately not in the
 * navigation registry.
 *
 * It renders the mark at true pixel sizes (16px and 32px) on light and dark
 * backgrounds in both monochrome treatments, plus enlarged samples. The
 * honest 16px limitation is stated rather than glossed over.
 */

const SIZES = [16, 32] as const;

function Swatch({
  title,
  background,
  children,
  note,
}: {
  title: string;
  background: string;
  children: React.ReactNode;
  note?: string;
}) {
  return (
    <div className="spec-swatch">
      <h3>{title}</h3>
      <div className="spec-surface" style={{ background }}>
        {children}
      </div>
      {note && <p className="spec-note">{note}</p>}
    </div>
  );
}

function Row({ tone, label }: { tone: 'brand' | 'mono-dark' | 'mono-light'; label: string }) {
  return (
    <div className="spec-row">
      <span className="spec-row-label">{label}</span>
      <div className="spec-sizes">
        {SIZES.map((size) => (
          <div className="spec-cell" key={size}>
            <HsptlMark size={size} tone={tone} variant="primary" />
            <span>{size}px</span>
          </div>
        ))}
        <div className="spec-cell">
          <HsptlMark size={16} tone={tone} variant="compact" />
          <span>16px compact</span>
        </div>
        <div className="spec-cell">
          <HsptlMark size={32} tone={tone} variant="compact" />
          <span>32px compact</span>
        </div>
      </div>
    </div>
  );
}

export default function LogoSpecimenPage({ theme, onThemeToggle, onBack }: Props) {
  return (
    <div className="spec-page">
      <header className="spec-head">
        <div>
          <div className="s-eyebrow">Brand verification</div>
          <h1>Five-letter HSPTL monogram</h1>
          <p>
            True pixel sizes, not scaled previews. The 16px optical trade-off is stated below.
          </p>
        </div>
        <div className="s-toolbar">
          <button type="button" className="s-btn s-btn-secondary" onClick={onThemeToggle}>
            Theme: {theme}
          </button>
          <button type="button" className="s-btn s-btn-primary" onClick={onBack}>
            Back to app
          </button>
        </div>
      </header>

      <section className="spec-section">
        <h2>Light background</h2>
        <Swatch title="Primary mark" background="#FFFFFF">
          <Row tone="brand" label="Brand plate" />
        </Swatch>
        <Swatch title="Monochrome dark" background="#FFFFFF">
          <Row tone="mono-dark" label="One-colour black" />
        </Swatch>
      </section>

      <section className="spec-section">
        <h2>Dark background</h2>
        <Swatch title="Primary mark" background="#172B40">
          <Row tone="brand" label="Brand plate" />
        </Swatch>
        <Swatch title="Monochrome light" background="#172B40">
          <Row tone="mono-light" label="One-colour white" />
        </Swatch>
      </section>

      <section className="spec-section">
        <h2>Enlarged samples</h2>
        <div className="spec-enlarged">
          {([64, 128, 192] as const).map((size) => (
            <div className="spec-cell" key={size}>
              <HsptlMark size={size} />
              <span>{size}px</span>
            </div>
          ))}
          <div className="spec-cell">
            <HsptlMark size={128} tone="mono-dark" />
            <span>128px mono</span>
          </div>
        </div>
      </section>

      <section className="spec-section">
        <h2>Horizontal lockup</h2>
        <div className="spec-lockups">
          <HsptlLockup size={40} />
          <span className="spec-lockup-dark">
            <HsptlLockup size={40} tone="mono-light" />
          </span>
        </div>
      </section>

      <section className="spec-section spec-limits">
        <h2>16px optical trade-off</h2>
        <p>
          At <b>32px and above</b> all five letters — H, S, P, T and L — are arranged in a clear two-column grid.
        </p>
        <p>
          At <b>16px</b> the five-module cross silhouette survives, but the individual letters
          do not. The compact variant shown at 16px above keeps T, H, P and L and drops the S,
          whose three bars close up below roughly 24px. This is a deliberate optical reduction:
          at 16px the mark is a recognisable five-module cross, not five readable letters.
        </p>
        <p className="spec-note">
          Verify with a rasteriser at exact pixel sizes before shipping. Do not rely on a
          browser-scaled preview, which anti-aliases differently.
        </p>
      </section>
    </div>
  );
}
